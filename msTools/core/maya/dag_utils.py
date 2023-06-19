"""
Maya directed acyclic graph operations including modification and iteration of the graph.

----------------------------------------------------------------

Instanced Nodes
---------------

    An instanced node has multiple parents but will always reference the same internal :class:`OpenMaya.MObject`.

    - Children of instanced nodes are considered indirect instances.
    - A child can simultaneously exist as a direct and indirect instance.

    An :class:`OpenMaya.MDagPath` retrieved using an :class:`OpenMaya.MObject` will always reference the zeroth indexed instance.

    - Index numbers are determined by position in the internal DAG hierarchy (see outliner).
    - Changing the order of instances will affect their :meth:`OpenMaya.MDagPath.instanceNumber`.

----------------------------------------------------------------

Parenting
---------

    When a direct instance is reparented with absolute positioning, a new intermediary transform is created between the parent and the instance.

    - It stores the offset between the old parent and the new parent so that other instances are not affected.
    - This is similiar to what happens when a shape node is reparented with absolute positioning to preserve component positions.

    When an indirect instance is reparented, a new intermediary transform is created between the parent and each indirect instance.

    - Each indirect instance will now be directly instanced under its own intermediary transform.
    - Unless the new parent is the world, in which case a single intermediary transform will be created for the specific indirect instance.
      All other indirect instances are removed.

----------------------------------------------------------------

Intermediate Nodes
------------------

    An intermediate node usually acts as a component cache for the original state of a deformable shape node.

    - They do not render in the viewport and are not visible in the outliner.
    - Any DAG node can be set as an intermediate but they are usually reserved for shapes and are usally suffixed with ``'Orig'``.

----------------------------------------------------------------

Note:
    1. Functions for iterating ancestors by :class:`OpenMaya.MDagPath` are not provided since ancestral iteration is non-instance specific.
       If paths to ancestors are required, the user can simply call :meth:`OpenMaya.MDagPath.getAPathTo` or :meth:`OpenMaya.MDagPath.getAllPathsTo` for each ancestral :class:`OpenMaya.MObject` wrapper.

Note:
    2. Functions for retrieving parents by name are not provided since multiple parents of an instance can have the same shortName.

Note:
    3. Reindexing the name of a DAG node using ``'transform#'`` will crosscheck against all existing nodes whose unindexed shortName begins with ``'transform'``.
       Meaning any DAG node, regardless of hierarchy or namespace can cause the index to increment.

Note:
    4. Deleting instanced mesh nodes can sometimes cause shading issues due to the way Maya handles shader assignment.
       Maya controls the shading of instances by connecting instance specific plugs from a mesh to a shading group.
       When an instance is deleted these connections are not automatically updated.
       Rebuilding the scene should resolve these issues.

.. _warning_1:

Warning:
    1. Do not duplicate and reparent an indirect instance as a combined operation.
       Upon undoing this operation an uninteractable relic will be rendered in the viewport for any descendant shape node.

.. _warning_2:

Warning:
    2. Do not duplicate and reparent a shape node as a combined operation.
       The reparented shape will be unshaded as it will not be assigned to the source shading group.

----------------------------------------------------------------
"""
import collections
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.core.maya import callback_utils as CALLBACK
from msTools.core.maya import decorator_utils as DECORATOR
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isIndirectInstance(path):
    """
    Args:
        path (:class:`OpenMaya.MDagPath`): Path to a DAG node.

    Returns:
        :class:`bool`: :data:`True` if ``path`` references an indirectly instanced node, :data:`False` otherwise.
    """
    isIndirectInstance = False
    if path.isInstanced():
        if om2.MDagPath(path).pop().isInstanced():
            isIndirectInstance = True
    return isIndirectInstance


def hasShapes(transform):
    """
    Args:
        transform (:class:`OpenMaya.MObject`): Wrapper of a transform.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``transform`` does not reference a transform.

    Returns:
        :class:`bool`: :data:`True` if ``transform`` has child shapes, :data:`False` otherwise.
    """
    shapeGen = iterShapes(transform)

    try:
        shapeGen.next()
    except StopIteration:
        return False

    return True


def hasIntermediateShapes(transform):
    """
    Args:
        transform (:class:`OpenMaya.MObject`): Wrapper of a transform.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``transform`` does not reference a transform.

    Returns:
        :class:`bool`: :data:`True` if ``transform`` has intermediate child shapes, :data:`False` otherwise.
    """
    shapeGen = iterShapes(transform, nonIntermediates=False)

    try:
        shapeGen.next()
    except StopIteration:
        return False

    return True


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def inspectVisibility(path):
    """Inspect the visibility of a DAG node.

    The global visibility state of a node is given by :meth:`OpenMaya.MDagPath.isVisible`.
    If any of the return values are :data:`False`, ``path.isVisible()`` will also be :data:`False`.

    Args:
        path (:class:`OpenMaya.MDagPath`): Path to a DAG node.

    Returns:
        (:class:`bool`, :class:`bool`, :class:`bool`, :class:`bool`): A four-element :class:`tuple`.

        #. Value of the ``'visibility'`` attribute for the node referenced by ``path``.
        #. Value of the ``'lodVisibility'`` attribute for the node referenced by ``path``.
        #. Visibility state of draw-overrides for the node referenced by ``path``.
           If :data:`False`, the ``'overrideEnabled'`` attribute is on and the ``'overrideVisibility'`` attribute is off.
        #. Visibility state for ancestors of ``path``. If :data:`False`, ``path`` is hidden because of an ancestor.
    """
    node = path.node()

    visibility = OM.getPlugFromNodeByName(node, 'visibility').asBool()
    lodVisibility = OM.getPlugFromNodeByName(node, 'lodVisibility').asBool()
    drawOverrideVisibility = not (OM.getPlugFromNodeByName(node, 'overrideEnabled').asBool() and not
                                  OM.getPlugFromNodeByName(node, 'overrideVisibility').asBool())
    ancestorVisibility = path.length() == 1 or om2.MDagPath(path).pop().isVisible()

    return visibility, lodVisibility, drawOverrideVisibility, ancestorVisibility


def getChildByName(parent, childShortName):
    """Return a child of a transform.

    Args:
        parent (:class:`OpenMaya.MObject`): Wrapper of a transform.
        childShortName (:class:`basestring`): Short name of a child node parented under ``parent``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``parent`` does not have a child node with name ``childShortName``.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the child node.
    """
    OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
    parentPath = om2.MDagPath.getAPathTo(parent)

    for i in xrange(parentPath.childCount()):
        child = parentPath.child(i)
        if NAME.getNodeShortName(child) == childShortName:
            return child

    raise EXC.MayaLookupError("{}: Transform does not have a child with given short name: {}".format(NAME.getNodeFullName(parent), childShortName))


def getChildPathByName(parentPath, childShortName):
    """Return a path to a child of a transform.

    Args:
        parentPath (:class:`OpenMaya.MDagPath`): Path to a transform.
        childShortName (:class:`basestring`): Short name of a child node parented under ``parentPath``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``parentPath`` does not have a child node with name ``childShortName``.

    Returns:
        :class:`OpenMaya.MDagPath`: Path to the child node.
    """
    OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)
    parentPath = om2.MDagPath(parentPath)

    try:
        child = getChildByName(parentPath.node(), childShortName)
    except EXC.MayaLookupError:
        raise EXC.MayaLookupError("{}: Transform does not have a child with given short name: {}".format(parentPath.fullPathName(), childShortName))

    return parentPath.push(child)


def getParent(childPath):
    """Return the parent transform of a child node.

    Args:
        childPath (:class:`OpenMaya.MDagPath`): Path to a child node.

    Raises:
        :exc:`~exceptions.RuntimeError`: If ``childPath`` does not have a parent transform.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the parent transform.
    """
    return getParentPath(childPath).node()


def getParentPath(childPath):
    """Return a path to the parent transform of a child node.

    Args:
        childPath (:class:`OpenMaya.MDagPath`): Path to a child node.

    Raises:
        :exc:`~exceptions.RuntimeError`: If ``childPath`` does not have a parent transform.

    Returns:
        :class:`OpenMaya.MDagPath`: Path to the parent transform.

    Example:
        .. code-block:: python

            # Returns an OpenMaya.MDagPath
            getParentPath(childPath)
            # Similiar to returning a path via the following Maya command
            maya.cmds.listRelatives(childPartialName, parent=True, path=True)
    """
    if childPath.length() > 1:
        return om2.MDagPath(childPath).pop()

    raise RuntimeError("{} : Transform does not have a parent".format(childPath.fullPathName()))


def iterShapes(parent, nonIntermediates=True, intermediates=True, filterTypes=None):
    """Yield shapes parented under a transform.

    Note:
        At least one parameter must be :data:`True` from the pair of filter options: ``nonIntermediates``, ``intermediates``.

    Args:
        parent (:class:`OpenMaya.MObject`): Wrapper of a transform.
        nonIntermediates (:class:`bool`, optional): Whether to yield non-intermediate shapes. Defaults to :data:`True`.
        intermediates (:class:`bool`, optional): Whether to yield intermediate shapes. Defaults to :data:`True`.
        filterTypes (iterable [:class:`int`], optional): Filter child shapes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kCamera`, :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.
        :exc:`~exceptions.ValueError`: If neither ``nonIntermediates`` nor ``intermediates`` is :data:`True`.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of child shape nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers of mesh shapes directly under `parent`
            iterShapes(parent, filterTypes=(OpenMaya.MFn.kMesh,))
            # Yields OpenMaya.MObject wrappers of non-mesh shapes directly under `parent`
            iterShapes(parent, filterTypes=(-OpenMaya.MFn.kMesh,))
    """
    OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
    parentPath = om2.MDagPath.getAPathTo(parent)

    for shapePath in iterShapesByPath(parentPath, nonIntermediates=nonIntermediates, intermediates=intermediates, filterTypes=filterTypes):
        yield shapePath.node()


def iterShapesByPath(parentPath, nonIntermediates=True, intermediates=True, filterTypes=None):
    """Yield paths to shapes parented under a specific transform path.

    Note:
        At least one of ``nonIntermediates`` or ``intermediates`` must be :data:`True`.

    Args:
        parentPath (:class:`OpenMaya.MDagPath`): Path to a transform.
        nonIntermediates (:class:`bool`, optional): Whether to yield non-intermediate shapes. Defaults to :data:`True`.
        intermediates (:class:`bool`, optional): Whether to yield intermediate shapes. Defaults to :data:`True`.
        filterTypes (iterable [:class:`int`], optional): Filter child shapes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kCamera`, :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` does not reference a transform.
        :exc:`~exceptions.ValueError`: If neither ``nonIntermediates`` nor ``intermediates`` is :data:`True`.

    Yields:
        :class:`OpenMaya.MDagPath`: Paths to child shape nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MDagPaths to mesh shapes directly under `parentPath`
            iterShapesByPath(parentPath, filterTypes=(OpenMaya.MFn.kMesh,))
            # Yields OpenMaya.MDagPaths to non-mesh shapes directly under `parentPath`
            iterShapesByPath(parentPath, filterTypes=(-OpenMaya.MFn.kMesh,))
            # Called without filtering is similiar to returning paths via the following Maya command
            maya.cmds.listRelatives(parentPartialName, shapes=True, path=True)
    """
    OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)
    if not (nonIntermediates or intermediates):
        raise ValueError("At least one argument must be true from the following pair of filter options: (nonIntermediates, intermediates)")

    for i in xrange(parentPath.numberOfShapesDirectlyBelow()):
        shapePath = om2.MDagPath(parentPath).extendToShape(i)
        shape = shapePath.node()

        if not (nonIntermediates and intermediates):
            shapeDagFn = om2.MFnDagNode(shapePath)
            isIntermediate = shapeDagFn.isIntermediateObject
            if not (isIntermediate and intermediates) and not (not isIntermediate and nonIntermediates):
                continue

        if OM.hasCompatibleType(shape, types=filterTypes):
            yield shapePath


def iterChildren(parent, filterTypes=None):
    """Yield children parented under a transform.

    Args:
        parent (:class:`OpenMaya.MObject`): Wrapper of a transform.
        filterTypes (iterable [:class:`int`], optional): Filter children based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of child nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers of transforms directly under `parent`
            iterChildren(parent, filterTypes=(OpenMaya.MFn.kTransform,))
            # Yields OpenMaya.MObject wrappers of transforms directly under `parent`, excluding constraints
            iterChildren(parent, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
    """
    OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
    parentPath = om2.MDagPath.getAPathTo(parent)

    for childPath in iterChildrenByPath(parentPath, filterTypes=filterTypes):
        yield childPath.node()


def iterChildrenByPath(parentPath, filterTypes=None):
    """Yield paths to children parented under a specific transform path.

    Args:
        parentPath (:class:`OpenMaya.MDagPath`): Path to a transform.
        filterTypes (iterable [:class:`int`], optional): Filter children based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` does not reference a transform.

    Yields:
        :class:`OpenMaya.MDagPath`: Paths to child nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MDagPaths to transforms directly under `parentPath`
            iterChildrenByPath(parentPath, filterTypes=(OpenMaya.MFn.kTransform,))
            # Yields OpenMaya.MDagPaths to transforms directly under `parentPath`, excluding constraints
            iterChildrenByPath(parentPath, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
            # Called without filtering is similiar to returning paths via the following Maya command
            maya.cmds.listRelatives(parentPartialName, children=True, path=True)
    """
    OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)

    for i in xrange(parentPath.childCount()):
        child = parentPath.child(i)

        if OM.hasCompatibleType(child, types=filterTypes):
            yield om2.MDagPath(parentPath).push(child)


def iterDescendants(root=None, depthLimit=-1, breadth=False, filterTypes=None):
    """Yield descendants of a transform.

    Args:
        root (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as root.
        depthLimit (:class:`int`, optional): Limit the depth of iteration down descendant branches. Defaults to ``-1``.

            - ``<0`` : Full traversal of descendants.
            - ``=0`` : No traversal.
            - ``>0`` : Traverse until the given depth.

        breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
            If :data:`True`, exhaust an entire level of descendants before proceeding to the next level.
            If :data:`False`, exhaust an entire branch of descendants before proceeding to the next closest branch using depth first traversal.
        filterTypes (iterable [:class:`int`], optional): Filter descendants based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` is given but does not reference a transform.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of descendant nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers for descendant transforms of `root`
            iterDescendants(root, filterTypes=(OpenMaya.MFn.kTransform,))
            # Yields OpenMaya.MObject wrappers for descendant transforms of `root`, excluding constraints
            iterDescendants(root, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
    """
    if root:
        OM.validateNodeType(root, nodeType=om2.MFn.kTransform)
        rootPath = om2.MDagPath.getAPathTo(root)
    else:
        rootPath = None

    for descendantPath in iterDescendantsByPath(rootPath=rootPath, allPaths=False, depthLimit=depthLimit, breadth=breadth, filterTypes=filterTypes):
        yield descendantPath.node()


def iterDescendantsByPath(rootPath=None, allPaths=False, depthLimit=-1, breadth=False, filterTypes=None):
    """Yield paths to descendants of a specific transform instance.

    Args:
        rootPath (:class:`OpenMaya.MDagPath`, optional): Path to a root transform. Defaults to :data:`None` - world is used as root.
        allPaths (:class:`bool`): Whether to yield a path for every instance in the descendant hierarchy of ``rootPath``.
            If :data:`False`, only yield a single path to instanced nodes in the descendant hierarchy of ``rootPath``.
            Defaults to :data:`False`.
        depthLimit (:class:`int`, optional): Limit the depth of iteration down descendant branches. Defaults to ``-1``.

            - ``<0`` : Full traversal of descendants.
            - ``=0`` : No traversal.
            - ``>0`` : Traverse until the given depth.

        breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
            If :data:`True`, exhaust an entire level of descendants before proceeding to the next level.
            If :data:`False`, exhaust an entire branch of descendants before proceeding to the next closest branch using depth first traversal.
        filterTypes (iterable [:class:`int`], optional): Filter descendants based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``rootPath`` is given but does not reference a transform.

    Yields:
        :class:`OpenMaya.MDagPath`: Paths to descendant nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MDagPaths to descendant transforms of `rootPath`
            iterDescendantsByPath(rootPath, filterTypes=(OpenMaya.MFn.kTransform,))
            # Yields OpenMaya.MDagPaths to descendant transforms of `rootPath`, excluding constraints
            iterDescendantsByPath(rootPath, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
            # Called without filtering is similiar to returning paths via the following Maya command
            maya.cmds.listRelatives(rootPartialName, allDescendants=True, path=True)
    """
    if rootPath:
        rootPath = om2.MDagPath(rootPath)
        root = rootPath.node()
        OM.validateNodeType(root, nodeType=om2.MFn.kTransform)
    else:
        # Use 'world' MObject if root is None
        root = om2.MItDag().root()
        rootPath = om2.MDagPath.getAPathTo(root)

    acceptedTypes, excludedTypes = OM.inspectTypes(types=filterTypes)
    traversalType = om2.MItDag.kBreadthFirst if breadth else om2.MItDag.kDepthFirst
    depthLimited = depthLimit >= 0
    dagIter = om2.MItDag()

    if acceptedTypes:
        iterType = OM.createIteratorTypeFilter(objectType=om2.MIteratorType.kMDagPathObject, filterTypes=acceptedTypes)
        dagIter.reset(iterType, rootPath, traversalType)
    else:
        dagIter.reset(rootPath, traversalType, filterType=om2.MFn.kInvalid)

    # The iterator will be set to the root MDagPath if the filterType is kInvalid or the MIteratorType is compatible with the root MObject
    # In this case we must proceed to the next path but in any other case the iterator will already have proceeded upon calling reset()
    if not dagIter.isDone() and dagIter.currentItem() == root:
        dagIter.next()

    if allPaths:
        while not dagIter.isDone():
            if depthLimited and dagIter.depth() > depthLimit:
                dagIter.prune()
                dagIter.next()
                continue

            if not excludedTypes or not OM.hasCompatibleType(dagIter.currentItem(), types=excludedTypes):
                yield dagIter.getPath()

            dagIter.next()
    else:
        descendantSet = OM.MObjectSet()

        while not dagIter.isDone():
            if depthLimited and dagIter.depth() > depthLimit:
                dagIter.prune()
                dagIter.next()
                continue

            descendant = dagIter.currentItem()

            # If the node is instanced, prune the branch if it has already been traversed
            if dagIter.isInstanced(indirect=True):
                if not descendantSet.add(descendant):
                    dagIter.prune()
                    dagIter.next()
                    continue

            if not excludedTypes or not OM.hasCompatibleType(descendant, types=excludedTypes):
                yield dagIter.getPath()

            dagIter.next()


def iterParents(child, filterTypes=None):
    """Yield parents of a child node.

    Note:
        By default the world :class:`OpenMaya.MObject` will be yielded if ``child`` is parented to the world.
        The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this parent if necessary.

    Args:
        child (:class:`OpenMaya.MObject`): Wrapper of a child node.
        filterTypes (iterable [:class:`int`], optional): Filter parents based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kConstraint`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kConstraint`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``child`` does not reference a DAG node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the parent nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers for parents of `child`
            iterParents(child)
            # Yields OpenMaya.MObject wrappers for parents of `child`, excluding constraints
            iterParents(child, filterTypes=(-OpenMaya.MFn.kConstraint,))
            # Yields OpenMaya.MObject wrappers for parent transforms of `child`
            iterParents(child, filterTypes=(-OpenMaya.MFn.kWorld,))
    """
    OM.validateNodeType(child, nodeType=om2.MFn.kDagNode)
    childDagFn = om2.MFnDagNode(child)

    for i in xrange(childDagFn.parentCount()):
        parent = childDagFn.parent(i)

        if OM.hasCompatibleType(parent, types=filterTypes):
            yield parent


def _iterAncestorsBreadthFirst(root, depthLimit=-1):
    """Generator for yielding parents in a breadth first order. Utilises a queued approach to iterate up the parent hierarchy of a root node by level."""
    parentSet = OM.MObjectSet()
    depthLimited = depthLimit >= 0
    traversalQueue = collections.deque([(0, root)])

    while traversalQueue:
        currentDepth, currentNode = traversalQueue.popleft()
        if depthLimited and currentDepth > depthLimit:
            return

        parentDepth = currentDepth + 1
        for parent in iterParents(currentNode):
            if parentSet.add(parent):
                yield parent
                traversalQueue.append((parentDepth, parent))


def _iterAncestorsDepthFirst(root, depthLimit=-1):
    """Generator for yielding parents in a depth first order. Utilises a recursive approach to iterate up the parent hierarchy of a root node by branch."""
    parentSet = OM.MObjectSet()
    depthLimited = depthLimit >= 0

    def recurse(currentRoot, depth=0):
        # currentDepth is the current level of recursion for a specific branch in the parent hierarchy of an instance
        currentDepth = depth + 1
        if depthLimited and currentDepth > depthLimit:
            return

        for parent in iterParents(currentRoot):
            # If the parent hierarchy of two instances converged you would end up with the same parent twice
            # There is no need to recurse up the parent hierarchy again once the convergence is found
            if parentSet.add(parent):
                yield parent
            else:
                continue

            for parent in recurse(parent, currentDepth):
                yield parent

    for parent in recurse(root):
        yield parent


def iterAncestors(root, depthLimit=-1, breadth=False, filterTypes=None):
    """Yield ancestors of a root DAG node.

    Note:
        By default the world :class:`OpenMaya.MObject` will be yielded since it is the root ancestor of all children.
        The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this ancestor if necessary.

    Args:
        root (:class:`OpenMaya.MObject`): Wrapper of a DAG node.
        depthLimit (:class:`int`, optional): Limit the depth of iteration up ancestral branches. Defaults to ``-1``.

            - ``<0`` : Full traversal of ancestors.
            - ``=0`` : No traversal.
            - ``>0`` : Traverse until the given depth.

        breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
            If :data:`True`, exhaust an entire level of ancestors before proceeding to the next level.
            If :data:`False`, exhaust an entire branch of ancestors before proceeding to the next closest branch using depth first traversal.
        filterTypes (iterable [:class:`int`], optional): Filter ancestors based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kConstraint`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kConstraint`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` does not reference a DAG node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the ancestor nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers for ancestors of `root`
            iterAncestors(root)
            # Yields OpenMaya.MObject wrappers for ancestors of `root`, excluding constraints
            iterAncestors(root, filterTypes=(-OpenMaya.MFn.kConstraint,))
            # Yields OpenMaya.MObject wrappers for ancestor transforms of `root`
            iterAncestors(root, filterTypes=(-OpenMaya.MFn.kWorld,))
    """
    OM.validateNodeType(root, nodeType=om2.MFn.kDagNode)
    ancestorGen = _iterAncestorsBreadthFirst if breadth else _iterAncestorsDepthFirst

    for ancestor in ancestorGen(root, depthLimit=depthLimit):
        # We must filter in the outer scope to avoid pruning ancestral branches
        if OM.hasCompatibleType(ancestor, types=filterTypes):
            yield ancestor


def iterRelatives(root, shapes=False, children=False, descendants=False, parents=False, ancestors=False, filterTypes=None):
    """Yield relatives of a DAG node.

    Note:
        By default if ``parents`` is :data:`True`, the world :class:`OpenMaya.MObject` will be yielded if ``root`` is parented to the world.
        By default if ``ancestors`` is :data:`True`, the world :class:`OpenMaya.MObject` will be yielded since it is the root ancestor of all children.
        The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this ancestor if necessary.

    Args:
        root (:class:`OpenMaya.MObject`): Wrapper of a DAG node.
        shapes (:class:`bool`, optional): Whether to yield child shapes. Defaults to :data:`False`.
        children (:class:`bool`, optional): Whether to yield all children. Overrides the ``shapes`` argument. Defaults to :data:`False`.
        descendants (:class:`bool`, optional): Whether to yield all descendants. Traversal will be depth first.
            Overrides the ``shapes`` and ``children`` arguments. Defaults to :data:`False`.
        parents (:class:`bool`, optional): Whether to yield parent transforms. If ``root`` is instanced, the parent of each instance will be yielded.
            Defaults to :data:`False`.
        ancestors (:class:`bool`, optional): Whether to yield ancestor transforms. If ``root`` is instanced, the ancestors of each instance will be yielded.
            Traversal will be depth first. Overrides the ``parents`` argument. Defaults to :data:`False`.
        filterTypes (iterable [:class:`int`], optional): Filter relative nodes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh` or :attr:`~OpenMaya.MFn.kConstraint`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If either ``shapes``, ``children`` or ``descendants`` is :data:`True` and ``root`` does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If either ``parents`` or ``ancestors`` is :data:`True` and ``root`` does not reference a DAG node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the relative nodes.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers for transforms directly under `root`
            iterRelatives(root, children=True, filterTypes=(OpenMaya.MFn.kTransform,))
            # Yields OpenMaya.MObject wrappers for transforms directly under `root`, excluding constraints
            iterRelatives(root, children=True, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
            # Yields OpenMaya.MObject wrappers for ancestor transforms of `root`
            iterRelatives(root, ancestors=True, filterTypes=(-OpenMaya.MFn.kWorld,))
    """
    descendantGen = None
    ancestorGen = None

    if descendants:
        descendantGen = iterDescendants(root=root, filterTypes=filterTypes)
    elif children:
        descendantGen = iterChildren(root, filterTypes=filterTypes)
    elif shapes:
        descendantGen = iterShapes(root, filterTypes=filterTypes)

    if ancestors:
        ancestorGen = iterAncestors(root=root, filterTypes=filterTypes)
    elif parents:
        ancestorGen = iterParents(root, filterTypes=filterTypes)

    if descendantGen is not None:
        for descendant in descendantGen:
            yield descendant

    if ancestorGen is not None:
        for ancestor in ancestorGen:
            yield ancestor


def iterRootTransforms(filterTypes=None):
    """Yield transforms parented directly under the world.

    Args:
        filterTypes (iterable [:class:`int`], optional): Filter transforms based on :class:`OpenMaya.MDagPath` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude root transforms which have certain types of children.
            Applicable values include :attr:`~OpenMaya.MFn.kCamera`, :attr:`~OpenMaya.MFn.kLight`.
            Defaults to None - no type filtering will occur.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the root transforms.

    Example:
        .. code-block:: python

            # Yields OpenMaya.MObject wrappers of root transforms which have child camera nodes
            iterRootTransforms(filterTypes=(OpenMaya.MFn.kCamera,))
            # Yields OpenMaya.MObject wrappers of root transforms, excluding those which have child camera or light nodes
            iterRootTransforms(filterTypes=(-OpenMaya.MFn.kCamera, -OpenMaya.MFn.kLight))
    """
    rootPathGen = iterDescendantsByPath(depthLimit=1)

    for rootPath in rootPathGen:
        # Note MDagPaths will support a function set if a child does (it is less strict than MObject support)
        if OM.hasCompatibleType(rootPath, types=filterTypes):
            yield rootPath.node()


def iterSelectedNodesByPath(allPaths=False, filterTypes=None):
    """Yield paths to DAG nodes in the active selection. Non-DAG nodes will be ignored.

    Args:
        allPaths (:class:`bool`): Whether to yield a path for every selected instance of a node.
            If :data:`False`, only yield a single path to the first selected instance of a node in the active selection.
            Defaults to :data:`False`.
        filterTypes (iterable [:class:`int`], optional): Filter paths to selected node based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh` or :attr:`~OpenMaya.MFn.kConstraint`.
            Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
            :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
            Defaults to :data:`None` - no type filtering will occur.

    Yields:
        :class:`OpenMaya.MDagPath`: Paths to nodes in the active selection.
    """
    # Use a set since we want to check if multiple instances of the same node are selected when allPaths=True
    selectedNodeSet = OM.MObjectSet()

    sel = om2.MGlobal.getActiveSelectionList()
    for i in xrange(sel.length()):
        try:
            selectedNodePath = sel.getDagPath(i)
        except TypeError:
            continue

        selectedNode = selectedNodePath.node()

        if allPaths:
            if OM.hasCompatibleType(selectedNode, types=filterTypes):
                yield selectedNodePath
        else:
            if selectedNodeSet.add(selectedNode):
                if OM.hasCompatibleType(selectedNode, types=filterTypes):
                    yield selectedNodePath


# --------------------------------------------------------------
# --- Modify ---
# --------------------------------------------------------------

@DECORATOR.undoOnError(StandardError)
def renameShapes(parent):
    """Rename all child shape nodes under a parent transform.

    Names for non-instanced shapes will follow the format ``'<parentShortName>_shape<##>'``.

    Names for instanced shapes will follow the format ``'<parentShortName>_instance_shape<##>'``.

    - ``'<parentShortName>'`` will correspond to the parent of the zeroth indexed shape instance.
    - The addition of the ``'instance'`` token aims to prevent confusion for instances whose parent does not correspond to ``'<parentShortName>'``.

    A recursive call will be made for the parents of every instanced shape in order to avoid name clashes with their own child shapes.

    Args:
        parent (:class:`OpenMaya.MObject`): Wrapper of a parent transform.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.
    """
    OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)

    # Retrieve path to first instance
    parentPath = om2.MDagPath.getAPathTo(parent)
    shapes = list(iterShapes(parent))
    ancestorPathName, parentShortName = parentPath.fullPathName().rsplit('|', 1)

    # Rename all with TMP to avoid clashes with rename proper
    dagModRenameTemp = OM.MDagModifier()
    for shape in shapes:
        # NOTE : Re-indexing by hash will crosscheck against all shortNames of existing nodes (meaning any DAG node can cause the index to increment)
        # For the temp names this is fine as we are only concerned with order/uniqueness
        tempName = '_'.join([parentShortName, 'shapeTMP#'])
        dagModRenameTemp.renameNode(shape, tempName)
    dagModRenameTemp.doIt()

    dagModRenameProper = OM.MDagModifier()
    recursedParentPathSet = OM.MDagPathSet()
    for shape in shapes:
        shape0Path = om2.MDagPath.getAPathTo(shape)

        if shape0Path.isInstanced():
            shape0ParentPath = shape0Path.pop()
            # Only rename shapes if the current parent is the parent of the first shape instance otherwise call renameShapes for the parent of the first instance
            if shape0ParentPath == parentPath:
                # As mentioned, hash renaming is not adequate when we want to re-index nodes within a local hierarchy
                index = 1
                newName = '_'.join([parentShortName, 'instance', 'shape01'])
                while cmds.objExists('|'.join([ancestorPathName, newName])):
                    index += 1
                    newName = '_'.join([parentShortName, 'instance', 'shape{}'.format(str(index).zfill(2))])
            else:
                # If the current parent contains multiple shape instances from a seperate parent, we want to avoid renaming its shapes more than once
                if recursedParentPathSet.add(shape0ParentPath):
                    renameShapes(shape0ParentPath.node())
                continue
        else:
            index = 1
            newName = '_'.join([parentShortName, 'shape01'])
            while cmds.objExists('|'.join([ancestorPathName, newName])):
                index += 1
                newName = '_'.join([parentShortName, 'shape{}'.format(str(index).zfill(2))])

        dagModRenameProper.renameNode(shape, newName)
    dagModRenameProper.doIt()


def _parent(childPath, parentPath=None, relative=False, renameShapes=True):
    """Reparent a node using relative or absolute transforms.

    Used internally by :func:`relativeReparent` and :func:`absoluteReparent`.
    Hidden from the public interface due to a potentially confusing function signature:

    - When absolute parenting is used, it should be clear that an instance specific parent is required via an :class:`OpenMaya.MDagPath`.
    - When relative parenting is used, it should be clear that a non-instance specific parent is required via an :class:`OpenMaya.MObject`.
    """
    newParentPath = parentPath
    oldParentPath = om2.MDagPath(childPath).pop() if childPath.length() > 1 else None
    reparentedChildPaths = []
    # Ensure the shape is reparented if child is a shape
    isChildShape = childPath.node().hasFn(om2.MFn.kShape)

    if isChildShape and not parentPath:
        raise EXC.MayaTypeError('Cannot parent shapes to the world')

    if newParentPath:
        # Reparent (API does not have instance specific methods)
        reparentedChildNames = cmds.parent(childPath.partialPathName(), newParentPath.partialPathName(), relative=relative, shape=isChildShape)
    else:
        reparentedChildNames = cmds.parent(childPath.partialPathName(), relative=relative, shape=isChildShape, world=True)

    # We must retrieve each MDagPath before any renaming since children may be instanced and renaming one may invalidate the paths to others
    # If the child was instanced, each shape will remain instanced under a non-instanced intermediary transform (MObjects would not be unique)
    for reparentedChildName in reparentedChildNames:
        reparentedChildPath = OM.getPathByName(reparentedChildName)
        reparentedChildPaths.append(reparentedChildPath)

    if renameShapes:
        # A reparented shape node will either be under a new intermediary transform or the given parent
        if isChildShape:
            for reparentedChildPath in reparentedChildPaths:
                newParentPath = om2.MDagPath(reparentedChildPath).pop()
                globals()["renameShapes"](newParentPath.node())

        if oldParentPath and oldParentPath.numberOfShapesDirectlyBelow():
            globals()["renameShapes"](oldParentPath.node())

    return reparentedChildPaths


@DECORATOR.undoOnError(StandardError)
def absoluteReparent(childPath, parentPath=None, renameShapes=True):
    """Reparent a DAG node under a transform or the world whilst preserving its current world space transforms.

    Note:
        - If ``childPath`` is an uninstanced shape, it will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.
        - If ``childPath`` is an uninstanced transform, its local matrix will inherit the relative transform from the old parent to ``parentPath``.
        - If ``childPath`` is directly instanced, it will be reinstanced under a new intermediary transform, inserted between ``parentPath`` and the instance.
        - If ``childPath`` is indirectly instanced, other instances with the same parent will be parented under a new intermediary transform, inserted between ``parentPath`` and the instance.

    Args:
        childPath (:class:`OpenMaya.MDagPath`): Path to a DAG node to reparent.
        parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the new and old parents if ``childPath`` is a shape.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``childPath`` is a shape and ``parentPath`` is :data:`None`.
        :exc:`~exceptions.RuntimeError`: If ``childPath`` is already a child of ``parentPath``.

    Returns:
        :class:`list` [:class:`OpenMaya.MDagPath`]: A path to the reparented node for the first instance of each new parent. If ``childPath`` is an indirect instance there will be multiple paths.
    """
    if parentPath:
        OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)

    return _parent(childPath, parentPath=parentPath, relative=True, renameShapes=renameShapes)


@DECORATOR.undoOnError(StandardError)
def relativeReparent(childPath, parent=None, renameShapes=True):
    """Reparent a DAG node under a transform or the world whilst preserving its current local space transforms.

    Note:
        - If :attr:`childPath` is uninstanced, it will be reparented directly under ``parent``.
        - If :attr:`childPath` is instanced, it will be reinstanced directly under ``parent``.
        - If :attr:`childPath` is indirectly instanced, other instances with the same parent will be reinstanced under their own intermediary transform,
          inserted between ``parent`` and the instance.

    Args:
        childPath (:class:`OpenMaya.MDagPath`): Path to a DAG node to reparent.
        parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the new and old parents if ``childPath`` is a shape.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``childPath`` is a shape and ``parent`` is :data:`None`.
        :exc:`~exceptions.RuntimeError`: If ``childPath`` is already a child of ``parent``.

    Returns:
        :class:`list` [:class:`OpenMaya.MDagPath`]: A path to the reparented node for the first instance of each new parent. If ``childPath`` is an indirect instance there will be multiple paths.
    """
    if parent:
        OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
        parentPath = om2.MDagPath.getAPathTo(parent)
    else:
        parentPath = None

    return _parent(childPath, parentPath=parentPath, relative=True, renameShapes=renameShapes)


def duplicate(sourcePath, renameShapes=True, **kwargs):
    """Duplicate a DAG hierarchy.

    Args:
        sourcePath (:class:`OpenMaya.MDagPath`): Path to a DAG node. If the path references a shape, its parent transform will be duplicated.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers of the duplicate nodes, including any descendants.
        The first element is always the root transform of the duplicate hierarchy.
        If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
        If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned.
    """
    if kwargs.get('returnRootsOnly'):
        duplicateShortName = cmds.duplicate(sourcePath.partialPathName(), **kwargs)[0]
        isSourceShape = sourcePath.node().hasFn(om2.MFn.kShape)
        duplicateParentPath = om2.MDagPath(sourcePath).pop(2 if isSourceShape else 1)
        duplicatePartialName = "|".join([duplicateParentPath.partialPathName(), duplicateShortName])
        ret = [OM.getNodeByName(duplicatePartialName)]
    else:
        ret = CALLBACK.getNodesCreatedBy(cmds.duplicate, sourcePath.partialPathName(), **kwargs)[0]

    if renameShapes:
        duplicate_ = ret[0]
        globals()["renameShapes"](duplicate_)

    return ret


def _duplicateTo(sourcePath, parentPath=None, relative=False, renameShapes=True, **kwargs):
    """Duplicate and reparent a node using relative or absolute transforms.

    Mitigates the issues described by :ref:`warning-1 <warning_1>` and :ref:`warning-2 <warning_2>` so that even indirect instances and shapes can be used as ``sourcePath``.

    Used internally by :func:`relativeDuplicateTo` and :func:`absoluteDuplicateTo`.
    Hidden from the public interface due to a potentially confusing function signature:

    - When absolute parenting is used, it should be clear that an instance specific source and parent are required via :class:`OpenMaya.MDagPath`.
    - When relative parenting is used, it should be clear that a non-instance specific source and parent are required via :class:`OpenMaya.MObject`.
    """
    source = sourcePath.node()
    isSourceIndirectInstance = isIndirectInstance(sourcePath)
    isSourceShape = source.hasFn(om2.MFn.kShape)

    if isSourceShape and not parentPath:
        raise EXC.MayaTypeError('Cannot parent shapes to the world')

    # If the source node was an indirect instance, the duplicate will still be instanced (multiple paths, same MObject)
    # If the source node was a shape, its transform will have been duplicated (the shapes siblings are also duplicated)
    duplicates = duplicate(sourcePath, renameShapes=False, **kwargs)
    duplicate_ = duplicates[0]

    # The index of the shape is required to retrieve the duplicate shape
    if isSourceShape:
        sourceParent = om2.MDagPath(sourcePath).pop().node()
        for childIndex, child in enumerate(iterChildren(sourceParent)):
            if source == child:
                break

    # Find the path for the duplicate transform relative to the source parent. Note, the parent may be the world
    duplicateParentPath = om2.MDagPath(sourcePath).pop(2 if isSourceShape else 1)
    duplicatePath = om2.MDagPath(duplicateParentPath).push(duplicate_)

    # The following section is designed to safely reparent the duplicate so that we can avoid the issues described by warning-1 and warning-2
    # These issues can be mitigated by instancing the duplicate instead of directly reparenting it

    if isSourceShape:
        # This section provides mitigation for both warnings when source is a shape (ie. source can also be an indirectly instanced shape)
        duplicateShapePath = om2.MDagPath(duplicatePath).push(duplicatePath.child(childIndex))
        duplicateShape = duplicateShapePath.node()

        if relative:
            # Instance the duplicate shape to the parent before removing the duplicate transform
            cmds.parent(duplicateShapePath.partialPathName(), parentPath.partialPathName(), add=True, shape=True)

            # Replace or remove the duplicate transform from the return value
            if kwargs.get("returnRootsOnly"):
                duplicates[0] = duplicateShape
            else:
                del duplicates[0]
        else:
            # Emulate absolute parenting of a shape by manually creating the intermediary transform
            # Then instance the duplicate shape to the intermediary transform before removing the duplicate transform
            intermediary = createNode(nodeType='transform')
            intermediaryPath = om2.MDagPath.getAPathTo(intermediary)
            intermediaryTransFn = om2.MFnTransform(intermediaryPath)

            duplicateInclusiveTransMatrix = om2.MTransformationMatrix(duplicatePath.inclusiveMatrix())
            intermediaryTransFn.setTranslation(duplicateInclusiveTransMatrix.translation(om2.MSpace.kTransform), om2.MSpace.kTransform)
            intermediaryTransFn.setRotation(duplicateInclusiveTransMatrix.rotation(), om2.MSpace.kTransform)
            intermediaryTransFn.setScale(duplicateInclusiveTransMatrix.scale(om2.MSpace.kTransform))
            cmds.xform(intermediaryPath.partialPathName(), matrix=cmds.xform(intermediaryPath.partialPathName(), q=True, matrix=True))

            cmds.parent(duplicateShapePath.partialPathName(), intermediaryPath.partialPathName(), add=True, shape=True)
            _parent(intermediaryPath, parentPath=parentPath, relative=False)

            # Replace the duplicate transform from the return value
            duplicates[0] = intermediary

        dagMod = OM.MDagModifier()
        dagMod.deleteNode(duplicatePath.node())
        dagMod.doIt()
    elif isSourceIndirectInstance:
        # This section provides mitigation for warning-1 only (ie. when source is an indirectly instanced transform)
        # When an indirect instance is reparented to the world, it is parented under an intermediary transform and all other instances are removed
        # Emulating this behaviour by instancing the duplicate before directly reparenting will resolve the issue (ie. an intermediary step is required)
        temp = createNode(nodeType='transform')
        tempPath = om2.MDagPath.getAPathTo(temp)
        tempTransFn = om2.MFnTransform(tempPath)

        duplicateParentInclusiveTransMatrix = om2.MTransformationMatrix(duplicateParentPath.inclusiveMatrix())
        tempTransFn.setTranslation(duplicateParentInclusiveTransMatrix.translation(om2.MSpace.kTransform), om2.MSpace.kTransform)
        tempTransFn.setRotation(duplicateParentInclusiveTransMatrix.rotation(), om2.MSpace.kTransform)
        tempTransFn.setScale(duplicateParentInclusiveTransMatrix.scale(om2.MSpace.kTransform))
        cmds.xform(tempPath.partialPathName(), matrix=cmds.xform(tempPath.partialPathName(), q=True, matrix=True))

        cmds.parent(duplicatePath.partialPathName(), tempPath.partialPathName(), add=True)
        duplicatePath = om2.MDagPath(tempPath).push(tempTransFn.child(0))
        removeOtherInstances(duplicatePath)

        # The duplicate transform can inherit any offset, the temp transform can be deleted
        _parent(duplicatePath, parentPath=parentPath, relative=relative)

        dagMod = OM.MDagModifier()
        dagMod.deleteNode(temp)
        dagMod.doIt()
    else:
        # This section handles reparenting for any directly instanced or non-instanced transform
        if duplicatePath.length() > 1 or parentPath:
            _parent(duplicatePath, parentPath=parentPath, relative=relative)

    if renameShapes:
        if isSourceShape and relative:
            globals()["renameShapes"](parentPath.node())
        else:
            globals()["renameShapes"](duplicates[0])

    return duplicates


@DECORATOR.undoOnError(StandardError)
def absoluteDuplicateTo(sourcePath, parentPath=None, renameShapes=True, **kwargs):
    """Duplicate a DAG node and parent it under a transform or the world whilst preserving its current world space transforms.

    Mitigates the issues described by :ref:`warning-1 <warning_1>` and :ref:`warning-2 <warning_2>` so that even indirect instances and shapes can be used as ``sourcePath``.

    If ``sourcePath`` is an indirect instance, a single duplicate will be created for that specific indirect instance.

    Note:
        - If ``sourcePath`` is a transform, the duplicate's local matrix will inherit the relative transform from the old parent to ``parentPath``.
        - If ``sourcePath`` is a shape, the duplicate will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.

    Args:
        sourcePath (:class:`OpenMaya.MDagPath`): Path to a DAG node to duplicate and reparent.
        parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``sourcePath`` is a shape and ``parentPath`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers of the duplicate nodes, including any descendants.
        The first element is always the root transform of the duplicate hierarchy.
        If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
        If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned.
    """
    if parentPath:
        OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)

    return _duplicateTo(sourcePath, parentPath=parentPath, relative=False, renameShapes=renameShapes, **kwargs)


@DECORATOR.undoOnError(StandardError)
def relativeDuplicateTo(source, parent=None, renameShapes=True, **kwargs):
    """Duplicate a DAG node and parent it under a transform or the world whilst preserving its current local space transforms.

    Mitigates the issues described by :ref:`warning-1 <warning_1>` and :ref:`warning-2 <warning_2>` so that even indirect instances and shapes can be used as ``source``.

    Args:
        source (:class:`OpenMaya.MObject`): Wrapper of a DAG node to duplicate and reparent.
        parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
            If ``source`` is a shape, renaming will occur for all shapes under ``parent``.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``source`` does not reference a DAG node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``source`` is a shape and ``parent`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the duplicate nodes, including any descendants.
        The first element is always the root of the duplicate hierarchy.
        If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
        If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned.
    """
    OM.validateNodeType(source, nodeType=om2.MFn.kDagNode)
    if parent:
        OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)

    sourcePath = om2.MDagPath.getAPathTo(source)
    parentPath = om2.MDagPath.getAPathTo(parent) if parent else None
    return _duplicateTo(sourcePath, parentPath=parentPath, relative=True, renameShapes=renameShapes, **kwargs)


def instance(source, parent):
    """Instance a node under a transform.

    Note:
        The ``source`` instance will always be added relative to ``parent`` since all instances must share the same transforms.

    Args:
        source (:class:`OpenMaya.MObject`): Wrapper of a DAG node to instance.
        parent (:class:`OpenMaya.MObject`): Wrapper of a transform.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``source`` does not reference a DAG node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.
        :exc:`~exceptions.RuntimeError`: If ``source`` is already a child of ``parent``.

    Returns:
        :class:`OpenMaya.MDagPath`: A path to ``source`` for the first instance of ``parent``.
    """
    OM.validateNodeType(source, nodeType=om2.MFn.kDagNode)
    OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)

    sourcePath = om2.MDagPath.getAPathTo(source)
    parentDagFn = om2.MFnDagNode(parent)
    isSourceShape = source.hasFn(om2.MFn.kShape)

    if parentDagFn.hasChild(source):
        raise RuntimeError("{} : is already a child of: {}".format(sourcePath.fullPathName(), parentDagFn.fullPathName()))

    cmds.parent(sourcePath.partialPathName(), parentDagFn.partialPathName(), add=True, shape=isSourceShape)

    return om2.MDagPath.getAPathTo(parent).push(source)


def _uninstanceTo(instancePath, parentPath=None, relative=False, renameShapes=True, **kwargs):
    """Duplicate and reparent a DAG node instance using relative or absolute transforms then remove the original instance from its parent.

    Used internally by :func:`relativeUninstanceTo` and :func:`absoluteUninstanceTo`.
    Hidden from the public interface due to a potentially confusing function signature:

    - When absolute parenting is used, it should be clear that an instance specific parent is required via an :class:`OpenMaya.MDagPath`.
    - When relative parenting is used, it should be clear that a non-instance specific parent is required via an :class:`OpenMaya.MObject`.
    """

    if not instancePath.isInstanced():
        raise RuntimeError("{} : is not an instanced node".format(instancePath.fullPathName()))

    uninstancedRoots = []
    instance_ = instancePath.node()
    instanceParentPath = om2.MDagPath(instancePath).pop()
    instanceParent = instanceParentPath.node()

    if isIndirectInstance(instancePath):
        relatedInstancePathArray = om2.MDagPath.getAllPathsTo(instance_)

        # Find all related indirect instances (eg. if grandparent was instanced)
        relatedIndirectInstancePaths = []
        for relatedInstancePath in relatedInstancePathArray:
            if om2.MDagPath(relatedInstancePath).pop().node() == instanceParent:
                relatedIndirectInstancePaths.append(relatedInstancePath)

        # Duplicate each related indirect instance to the parent
        for relatedIndirectInstance in relatedIndirectInstancePaths:
            duplicates = _duplicateTo(relatedIndirectInstance, parentPath=parentPath, relative=relative, renameShapes=renameShapes, **kwargs)
            uninstancedRoots.append(duplicates[0])
    else:
        # If it is directly instanced, we can duplicate it and remove the old instance
        duplicates = _duplicateTo(instancePath, parentPath=parentPath, relative=relative, renameShapes=renameShapes, **kwargs)
        uninstancedRoots.append(duplicates[0])

    removeNode(instancePath)

    return uninstancedRoots


@DECORATOR.undoOnError(StandardError)
def absoluteUninstanceTo(instancePath, parentPath=None, renameShapes=True, **kwargs):
    """Duplicate and reparent a DAG node instance to a transform or the world whilst preserving its current world space transforms,
    then remove the original instance from its current parent.

    If ``instancePath`` references an indirect instance, all related indirect instances will be uninstanced.
    Meaning any instance which shares the same instanced parent as ``instancePath`` will be duplicated to ``parentPath``.

    Note:
        - If ``instancePath`` is a transform, the duplicate's local matrix will inherit the relative transform from the old parent to ``parentPath``.
        - If ``instancePath`` is a shape, the duplicate will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.

    Args:
        instancePath (:class:`OpenMaya.MDagPath`): Path to an instanced DAG node.
        parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`. Used to duplicate ``instancePath``.
            Note, this function only returns duplicate roots meaning the ``returnRootsOnly`` argument has no affect.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
        :exc:`~exceptions.RuntimeError`: If ``instancePath`` does not reference an instanced node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``instancePath`` is a shape and ``parentPath`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the root transforms of each uninstanced duplicate hierarchy.
        Usually contains a single transform unless ``instancePath`` is indirectly instanced.
    """
    if parentPath:
        OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)

    return _uninstanceTo(instancePath, parentPath=parentPath, relative=False, renameShapes=renameShapes, **kwargs)


@DECORATOR.undoOnError(StandardError)
def relativeUninstanceTo(instancePath, parent=None, renameShapes=True, **kwargs):
    """Duplicate and reparent a DAG node instance to a transform or the world whilst preserving its current local space transforms,
    then remove the original instance from its current parent.

    If ``instancePath`` references an indirect instance, all related indirect instances will be uninstanced.
    Meaning any instance which shares the same instanced parent as ``instancePath`` will be duplicated to ``parent``.

    Args:
        instancePath (:class:`OpenMaya.MDagPath`): Path to an instanced DAG node.
        parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
            If ``instancePath`` is a shape, renaming will occur for all shapes under ``parent``.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`. Used to duplicate ``instancePath``.
            Note, this function only returns duplicate roots meaning the ``returnRootsOnly`` argument has no affect.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
        :exc:`~exceptions.RuntimeError`: If ``instancePath`` does not reference an instanced node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``instancePath`` is a shape and ``parent`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the root nodes of each uninstanced duplicate hierarchy.
        Usually contains a single node unless ``instancePath`` is indirectly instances.
    """
    if parent:
        OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
        parentPath = om2.MDagPath.getAPathTo(parent)
    else:
        parentPath = None

    return _uninstanceTo(instancePath, parentPath=parentPath, relative=True, renameShapes=renameShapes, **kwargs)


@DECORATOR.undoOnError(StandardError)
def absoluteUninstanceAllTo(instanced, parentPath=None, renameShapes=True, **kwargs):
    """Duplicate and reparent each instance of a DAG node to a transform or the world whilst preserving the current world space transforms of the instance,
    then remove the original instance from its current parent.

    All direct and indirect instances of ``instanced`` will be uninstanced.

    Note:
        - If ``instanced`` is a transform, the local matrix of each duplicate will inherit the relative transform from the old parent to ``parentPath``.
        - If ``instanced`` is a shape, each duplicate will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.

    Args:
        instanced (:class:`OpenMaya.MObject`): Wrapper of an instanced DAG node.
        parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under each duplicate.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`. Used to duplicate each instance of the ``instanced`` node.
            Note, this function only returns duplicate roots meaning the ``returnRootsOnly`` argument has no affect.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
        :exc:`~exceptions.RuntimeError`: If ``instanced`` does not reference an instanced node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``instanced`` is a shape and ``parentPath`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the root transforms of each uninstanced duplicate hierarchy.
        One for each instance of the ``instanced`` node.
    """
    if parentPath:
        OM.validateNodeType(parentPath.node(), nodeType=om2.MFn.kTransform)

    instanceParents = OM.MObjectSet()
    uniqueInstancePaths = []
    uninstancedRoots = []
    instancePathArray = om2.MDagPath.getAllPathsTo(instanced)

    # Retrieve a single instance for each unique parent transform since uninstancing handles related indirect instances
    # Ensure retrieval occurs before uninstancing since removal of instances may invalidate paths to related indirect instances
    for instancePath in instancePathArray:
        instanceParent = om2.MDagPath(instancePath).pop().node()
        if instanceParents.add(instanceParent):
            uniqueInstancePaths.append(instancePath)

    for instancePath in uniqueInstancePaths:
        # If the last instance to be uninstanced is not an indirect instance, it will no longer be instanced since we have removed all the other instances
        if instancePath.isInstanced():
            uninstancedRoots += _uninstanceTo(instancePath, parentPath=parentPath, relative=False, renameShapes=renameShapes, **kwargs)
        else:
            reparentedPath = _parent(instancePath, parentPath=parentPath, relative=False, renameShapes=renameShapes)[0]
            reparented = reparentedPath.node()
            if reparented.hasFn(om2.MFn.kShape):
                reparentedIntermediary = getParent(reparentedPath)
                uninstancedRoots.append(reparentedIntermediary)
            else:
                uninstancedRoots.append(reparented)

    return uninstancedRoots


@DECORATOR.undoOnError(StandardError)
def relativeUninstanceAllTo(instanced, parent=None, renameShapes=True, **kwargs):
    """Duplicate and reparent each instance of a DAG node to a transform or the world whilst preserving the current local space transforms of the instance,
    then remove the original instance from its current parent.

    All direct and indirect instances of ``instanced`` will be uninstanced.

    Args:
        instanced (:class:`OpenMaya.MObject`): Wrapper of an instanced DAG node.
        parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
        renameShapes (:class:`bool`, optional): Whether to rename shape nodes under each duplicate.
            Renaming is completed via :func:`renameShapes`. Defaults to :data:`True`.
        **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`. Used to duplicate each instance of the ``instanced`` node.
            Note, this function only returns duplicate roots meaning the ``returnRootsOnly`` argument has no affect.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
        :exc:`~exceptions.RuntimeError`: If ``instanced`` does not reference an instanced node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``instanced`` is a shape and ``parent`` is :data:`None`.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the root nodes of each uninstanced duplicate hierarchy.
        One for each instance of the ``instanced`` node.
    """
    if parent:
        OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
        parentPath = om2.MDagPath.getAPathTo(parent)
    else:
        parentPath = None

    instanceParents = OM.MObjectSet()
    uniqueInstancePaths = []
    uninstancedRoots = []
    instancePathArray = om2.MDagPath.getAllPathsTo(instanced)

    # Retrieve a single instance for each unique parent transform since uninstancing handles related indirect instances
    # Ensure retrieval occurs before uninstancing since removal of instances may invalidate paths to related indirect instances
    for instancePath in instancePathArray:
        instanceParent = om2.MDagPath(instancePath).pop().node()
        if instanceParents.add(instanceParent):
            uniqueInstancePaths.append(instancePath)

    for instancePath in uniqueInstancePaths:
        # If the last instance to be uninstanced is not an indirect instance, it will no longer be instanced since we have removed all the other instances
        if instancePath.isInstanced():
            uninstancedRoots += _uninstanceTo(instancePath, parentPath=parentPath, relative=True, renameShapes=renameShapes, **kwargs)
        else:
            reparented = _parent(instancePath, parentPath=parentPath, relative=True, renameShapes=renameShapes)[0].node()
            uninstancedRoots.append(reparented)

    return uninstancedRoots


@DECORATOR.undoOnError(StandardError)
def removeOtherInstances(instancePath):
    """Removes all other instances of the node referenced by the given path.

    Note:
        If ``instancePath`` references an indirect instance, it will remain indirectly instanced under its current parent.

    Args:
        instancePath (:class:`OpenMaya.MDagPath`): Path to an instanced DAG node.

    Raises:
        :exc:`~exceptions.RuntimeError`: If ``instancePath`` does not reference an instanced node.
    """
    if not instancePath.isInstanced():
        raise RuntimeError("{} : is not an instanced node".format(instancePath.fullPathName()))

    instance_ = instancePath.node()
    instanceParent = om2.MDagPath(instancePath).pop().node()

    # Ensure parentCount does not change during iteration (ie. do not yield parents)
    # Note we must include the world if it exists as a parent
    for parent in list(iterParents(instance_)):
        if parent != instanceParent:
            parentPath = om2.MDagPath.getAPathTo(parent)
            otherInstancePath = om2.MDagPath(parentPath).push(instance_)
            removeNode(otherInstancePath)


def removeNode(path):
    """Remove a DAG node from one of its parents.

    Args:
        path (:class:`OpenMaya.MDagPath`): Path to a DAG node. The node will be removed from the parent given by ``node.pop()``.

    Example:
        .. code-block:: python

            # This function is equivalent to the following Maya command
            maya.cmds.parent(nodePartialName, removeObject=True)
    """
    isShape = path.node().hasFn(om2.MFn.kShape)
    cmds.parent(path.partialPathName(), shape=isShape, removeObject=True)


def deleteNode(node):
    """Delete a DAG node including all of its children.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a DAG node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a DAG node.

    Example:
        .. code-block:: python

            # This function is equivalent to the following Maya command
            maya.cmds.delete(nodePartialName)
    """
    OM.validateNodeType(node, nodeType=om2.MFn.kDagNode)

    # NOTE: Even though MDagModifier inherits from MDGModifier, the latter will cause issues for instanced DAG nodes
    # NOTE: Deleting a DAG node using MDagModifier.deleteNode() can result in ancestor nodes being deleted if the node is instanced
    path = om2.MDagPath.getAPathTo(node)
    cmds.delete(path.partialPathName())


def createNode(nodeType='transform', parent=None):
    """Create a DAG node under a parent.

    Args:
        nodeType (:class:`basestring`, optional): Name of the node type identifier used to create a DAG node. Defaults to ``'transform'``.
        parent (:class:`OpenMaya.MObject`, optional): Wrapper of a parent transform. Defaults to :data:`None` - world is used as the parent.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
        :exc:`~exceptions.ValueError`: If ``nodeType`` is an invalid node type identifier.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper for the root of the new node hierarchy.
        If ``nodeType`` is a shape and ``parent`` is :data:`None`, the new root node will be a transform.

    Example:
        .. code-block:: python

            # This function is equivalent to the following Maya command
            maya.cmds.createNode(nodeType, parent=parentPartialName)
    """
    if parent:
        OM.validateNodeType(parent, nodeType=om2.MFn.kTransform)
    else:
        parent = om2.MObject.kNullObj

    dagMod = OM.MDagModifier()

    try:
        node = dagMod.createNode(nodeType, parent=parent)
    except TypeError:
        raise ValueError("{}: Invalid node type".format(nodeType))

    dagMod.doIt()

    return node
