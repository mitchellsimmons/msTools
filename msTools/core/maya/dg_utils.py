"""
Maya dependency graph operations including dependency node modifications and iteration of the graph.
For operations specific to plugs and attributes see :mod:`msTools.core.maya.plug_utils` or :mod:`msTools.core.maya.attribute_utils`.

----------------------------------------------------------------

Dependencies
------------

    A dependency is formed when data flows between two connected plugs via a directed edge in the graph.
    Dependency paths define the flow of data in the dependency graph.
    They are a product of the internal ``attributeAffects`` relationships of nodes and the edges which connect plugs in the graph.

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2

from msTools.core.maya import attribute_utils as ATTR
from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import decorator_utils as DECORATOR
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM
from msTools.core.maya import plug_utils as PLUG
from msTools.core.py import context_utils as PY_CONTEXT


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def iterNodes(filterTypes=None):
    """Yield dependency nodes in the scene.

    Args:
        filterTypes (iterable [:class:`int`], optional): Filter nodes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of dependency nodes in the scene.
    """
    acceptedTypes, excludedTypes = OM.inspectTypes(types=filterTypes)
    nodeIter = om2.MItDependencyNodes()

    if acceptedTypes:
        iterType = OM.createIteratorTypeFilter(objectType=om2.MIteratorType.kMObject, filterTypes=acceptedTypes)
        nodeIter.reset(iterType)
    else:
        nodeIter.reset(om2.MFn.kInvalid)

    while not nodeIter.isDone():
        node = nodeIter.thisNode()

        if not excludedTypes or not OM.hasCompatibleType(node, types=excludedTypes):
            yield node

        nodeIter.next()


def iterSelectedNodes(filterTypes=None):
    """Yield dependency nodes in the active selection.

    Args:
        filterTypes (iterable [:class:`int`], optional): Filter selected nodes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of dependency nodes in the active selection.
    """
    # Use a set since it is possible for multiple instances of the same node to be selected
    selectedNodeSet = OM.MObjectSet()

    selection = om2.MGlobal.getActiveSelectionList()
    for i in xrange(selection.length()):
        selectedNode = selection.getDependNode(i)
        if selectedNodeSet.add(selectedNode):
            if OM.hasCompatibleType(selectedNode, types=filterTypes):
                yield selectedNode


def iterDependenciesByNode(root, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None):
    """Yield the node dependencies of a plug or node.

    If ``root`` is a node, each connected plug on ``root`` will be traversed. A node is yielded if it has not been visited.

    Note:
        Cyclic dependency paths may terminate back on ``root``.

    Args:
        root (:class:`OpenMaya.MPlug` | :class:`OpenMaya.MObject`): Plug object or wrapper of a dependency node from which to traverse dependencies.
        directionType (:class:`int`, optional): The direction of traversal for dependencies of ``root``.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
            Values correspond to either downstream or upstream dependency traversal of ``root``. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
        traversalType (:class:`int`, optional): The type of dependency traversal.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
            If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
            If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
            Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
        walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
            If ``root`` is a node, each connected plug on ``root`` acts as the root of a path. Defaults to :data:`True`.
        pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
        filterTypes (iterable [:class:`int`], optional): Filter node dependencies based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` is an :class:`OpenMaya.MObject` but does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers for the node dependencies of ``root``.
    """
    isRootNode = isinstance(root, om2.MObject)
    if isRootNode:
        rootNode = root
        OM.validateNodeType(rootNode)
    else:
        rootNode = root.node()

    acceptedTypes, excludedTypes = OM.inspectTypes(types=filterTypes)
    dgIter = om2.MItDependencyGraph(root)

    def traverse(direction):
        # Because we are using kPlugLevel traversal, we must track which nodes have been visited (ie. there may be multiple paths to a node)
        seenNodeSet = OM.MObjectSet()

        # The iterator will automatically advance to the next node after the root node that matches one of the filterTypes
        # If kInvalid is used because filterTypes is None, the iterator will be set to an invalid root, we must proceed to the first connected plug dependency
        if acceptedTypes:
            objectType = om2.MIteratorType.kMObject if isRootNode else om2.MIteratorType.kMPlugObject
            iterType = OM.createIteratorTypeFilter(objectType=objectType, filterTypes=acceptedTypes)
            # Documentation is incorrect, if the filter is a MIteratorType it must also be the second argument
            dgIter.resetTo(root, iterType, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
        else:
            dgIter.resetTo(root, om2.MFn.kInvalid, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
            dgIter.next()

        while not dgIter.isDone():
            # If `root` is a node, the iterator will essentially reset itself every time it visits a plug on `root` (ie. there is no previous plug)
            # If the iterator is currently pointing to a plug on the `root` node, we want to proceed to a plug on the next connected node
            try:
                dgIter.previousPlug()
            except RuntimeError:
                dgIter.next()

                # The iterator may realise it has already visited the next plug and is actually finished
                # This issue occurs specifically when traversing upstream of a `root` node which has multiple plugs directly connected to the same source plug
                if dgIter.isDone():
                    return

            previousPlug = dgIter.previousPlug()
            currentPlug = dgIter.currentPlug()
            currentNode = dgIter.currentNode()

            if pruneMessage:
                if ((direction == om2.MItDependencyGraph.kDownstream and previousPlug.attribute().apiType() == om2.MFn.kMessageAttribute)
                        or (direction == om2.MItDependencyGraph.kUpstream and currentPlug.attribute().apiType() == om2.MFn.kMessageAttribute)):
                    dgIter.prune()
                    dgIter.next()
                    continue

            if not walk:
                if previousPlug.node() != rootNode:
                    dgIter.prune()
                    dgIter.next()
                    continue

            if seenNodeSet.add(currentNode):
                if not excludedTypes or not OM.hasCompatibleType(currentNode, types=excludedTypes):
                    yield currentNode

            dgIter.next()

    for node in traverse(directionType):
        yield node


def iterDependenciesByPlug(root, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None):
    """Yield the plug dependencies of a plug or node.

    If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kDownstream`, dependencies will correspond to destination plug connections.
    If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kUpstream`, dependencies will correspond to source plug connections.

    If ``root`` is a node, each connected plug on ``root`` will be traversed. A plug is yielded if it has not been visited.

    Note:
        Cyclic dependency paths may terminate back on ``root``.

    Args:
        root (:class:`OpenMaya.MPlug` | :class:`OpenMaya.MObject`): Plug object or wrapper of a dependency node from which to traverse dependencies.
        directionType (:class:`int`, optional): The direction of traversal for dependencies of ``root``.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
            Values correspond to either downstream or upstream dependency traversal of ``root``. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
        traversalType (:class:`int`, optional): The type of dependency traversal.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
            If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
            If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
            Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
        walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
            If ``root`` is a node, each connected plug on ``root`` acts as the root of a path. Defaults to :data:`True`.
        pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
        filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` is an :class:`OpenMaya.MObject` but does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MPlug`: Plugs for each plug dependency of ``root``.
    """
    isRootNode = isinstance(root, om2.MObject)
    if isRootNode:
        rootNode = root
        OM.validateNodeType(rootNode)
    else:
        rootNode = root.node()

    acceptedTypes, excludedTypes = OM.inspectTypes(types=filterTypes)
    dgIter = om2.MItDependencyGraph(root)

    def traverse(direction):
        # If `root` is a node it may have two destination plugs whose dependency paths merge (ie. they share upstream dependencies)
        # Upstream traversal of `root` will visit the shared dependency for each path (ie. the iterator will traverse all unique edges)
        seenPlugSet = OM.MPlugSet()

        # The iterator will automatically advance to the next node after the root node that matches one of the filterTypes
        # If kInvalid is used because filterTypes is None, the iterator will be set to an invalid root, we must proceed to the first connected plug dependency
        if acceptedTypes:
            objectType = om2.MIteratorType.kMObject if isRootNode else om2.MIteratorType.kMPlugObject
            iterType = OM.createIteratorTypeFilter(objectType=objectType, filterTypes=acceptedTypes)
            # Documentation is incorrect, if the filter is a MIteratorType it must also be the second argument
            dgIter.resetTo(root, iterType, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
        else:
            dgIter.resetTo(root, om2.MFn.kInvalid, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
            dgIter.next()

        while not dgIter.isDone():
            # If `root` is a node, the iterator will essentially reset itself every time it visits a plug on `root` (ie. there is no previous plug)
            # If the iterator is currently pointing to a plug on the `root` node, we want to proceed to a plug on the next connected node
            try:
                dgIter.previousPlug()
            except RuntimeError:
                dgIter.next()

                # The iterator may realise it has already visited the next plug and is actually finished
                # This issue occurs specifically when traversing upstream of a `root` node which has multiple plugs directly connected to the same source plug
                if dgIter.isDone():
                    return

            previousPlug = dgIter.previousPlug()
            currentPlug = dgIter.currentPlug()
            currentNode = dgIter.currentNode()

            if pruneMessage:
                if ((direction == om2.MItDependencyGraph.kDownstream and previousPlug.attribute().apiType() == om2.MFn.kMessageAttribute)
                        or (direction == om2.MItDependencyGraph.kUpstream and currentPlug.attribute().apiType() == om2.MFn.kMessageAttribute)):
                    dgIter.prune()
                    dgIter.next()
                    continue

            if not walk:
                if previousPlug.node() != rootNode:
                    dgIter.prune()
                    dgIter.next()
                    continue

            if not seenPlugSet.add(currentPlug):
                dgIter.prune()
                dgIter.next()
                continue

            if not excludedTypes or not OM.hasCompatibleType(currentNode, types=excludedTypes):
                yield currentPlug

            dgIter.next()

    for plug in traverse(directionType):
        yield plug


def iterDependenciesByEdge(root, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None):
    """Yield dependencies of a plug or node as edges represented by a pair of connected source and destination plugs.

    Each pair will correspond to a connection from a source plug to a destination plug regardless of the ``directionType``.

    If ``root`` is a node, each connected plug on ``root`` will be traversed.

    Note:
        Cyclic dependency paths may terminate back on ``root``.

    Args:
        root (:class:`OpenMaya.MPlug` | :class:`OpenMaya.MObject`): Plug object or wrapper of a dependency node from which to traverse dependencies.
        directionType (:class:`int`, optional): The direction of traversal for dependencies of ``root``.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
            Values correspond to either downstream or upstream dependency traversal of ``root``. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
        traversalType (:class:`int`, optional): The type of dependency traversal.
            Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
            If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
            If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
            Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
        walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
            If ``root`` is a node, each connected plug on ``root`` acts as the root of a path. Defaults to :data:`True`.
        pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
        filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` is an :class:`OpenMaya.MObject` but does not reference a dependency node.

    Yields:
        (:class:`OpenMaya.MPlug`, :class:`OpenMaya.MPlug`): A two-element :class:`tuple` of connected plugs.

        #. A source plug connection for a dependency of ``root``.
        #. A corresponding destination plug connection for a dependency of ``root``.

        Together each pair represents a connected edge in the graph.
    """
    isRootNode = isinstance(root, om2.MObject)
    if isRootNode:
        rootNode = root
        OM.validateNodeType(rootNode)
    else:
        rootNode = root.node()

    acceptedTypes, excludedTypes = OM.inspectTypes(types=filterTypes)
    dgIter = om2.MItDependencyGraph(root)

    def traverse(direction):
        # The iterator will automatically advance to the next node after the root node that matches one of the filterTypes
        # If kInvalid is used because filterTypes is None, the iterator will be set to an invalid root, we must proceed to the first connected plug dependency
        if acceptedTypes:
            objectType = om2.MIteratorType.kMObject if isRootNode else om2.MIteratorType.kMPlugObject
            iterType = OM.createIteratorTypeFilter(objectType=objectType, filterTypes=acceptedTypes)
            # Documentation is incorrect, if the filter is a MIteratorType it must also be the second argument
            dgIter.resetTo(root, iterType, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
        else:
            dgIter.resetTo(root, om2.MFn.kInvalid, direction=direction, traversal=traversalType, level=om2.MItDependencyGraph.kPlugLevel)
            dgIter.next()

        while not dgIter.isDone():
            # If `root` is a node, the iterator will essentially reset itself every time it visits a plug on `root` (ie. there is no previous plug)
            # If the iterator is currently pointing to a plug on the `root` node, we want to proceed to a plug on the next connected node
            try:
                dgIter.previousPlug()
            except RuntimeError:
                dgIter.next()

                # The iterator may realise it has already visited the next plug and is actually finished
                # This issue occurs specifically when traversing upstream of a `root` node which has multiple plugs directly connected to the same source plug
                if dgIter.isDone():
                    return

            previousPlug = dgIter.previousPlug()
            currentPlug = dgIter.currentPlug()
            currentNode = dgIter.currentNode()

            if pruneMessage:
                if ((direction == om2.MItDependencyGraph.kDownstream and previousPlug.attribute().apiType() == om2.MFn.kMessageAttribute)
                        or (direction == om2.MItDependencyGraph.kUpstream and currentPlug.attribute().apiType() == om2.MFn.kMessageAttribute)):
                    dgIter.prune()
                    dgIter.next()
                    continue

            if not walk:
                if previousPlug.node() != rootNode:
                    dgIter.prune()
                    dgIter.next()
                    continue

            if not excludedTypes or not OM.hasCompatibleType(currentNode, types=excludedTypes):
                if direction == om2.MItDependencyGraph.kDownstream:
                    yield (previousPlug, currentPlug)
                else:
                    yield (currentPlug, previousPlug)

            dgIter.next()

    for edge in traverse(directionType):
        yield edge


def getCachedComponent(plug, instanceNumber=0):
    """Retrieve cached component data from a dependency node plug. Designed for use with :func:`cacheComponent`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug which holds :attr:`OpenMaya.MFnData.kComponentList` type data.
            The plug should be connected to an input shape node which has components corresponding to the data.
        instanceNumber (:class:`int`, optional): Instance number to be used by the path encapsulation of the cached node. Defaults to ``0``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not reference a typed attribute which holds :attr:`OpenMaya.MFnData.kComponentList` type data.
        :exc:`~exceptions.RuntimeError`: If ``plug`` is not connected to an input shape node.
        :exc:`~exceptions.ValueError`: If there is no instance of the cached shape node with corresponding ``instanceNumber``.
    ..

    Returns:
        (:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`): A two-element :class:`tuple` containing the cached component data.

        #. Path encapsulation of the cached shape node with ``instanceNumber``.
        #. Wrapper of the cached :attr:`OpenMaya.MFn.kComponent` type data.
    """
    # Retrieve a wrapper of the cached component data
    component = PLUG.getValue(plug)

    if not isinstance(component, om2.MObject) or not component.hasFn(om2.MFn.kComponent):
        raise EXC.MayaTypeError("{}: Plug does not reference component type data".format(NAME.getPlugFullName(plug)))

    if not plug.isDestination:
        raise RuntimeError("{}: Plug has no input connection from a shape node".format(NAME.getPlugFullName(plug)))

    sourcePlug = plug.sourceWithConversion()
    sourceNode = sourcePlug.node()

    if not sourceNode.hasFn(om2.MFn.kShape):
        raise RuntimeError("{}: Plug has no input connection from a shape node".format(NAME.getPlugFullName(plug)))

    if instanceNumber == 0:
        shapePath = om2.MDagPath.getAPathTo(sourceNode)
    else:
        # Must return a copy, MDagPathArray does not reference count
        shapePaths = om2.MDagPath.getAllPathsTo(sourceNode)
        try:
            shapePath = om2.MDagPath(shapePaths[instanceNumber])
        except IndexError:
            raise ValueError("Connected shape does not have an instance for instance number: {}".format(instanceNumber))

    return (shapePath, component)


def getCachedNode(plug):
    """Retrieve a cached dependency node from a dependency node plug. Designed for use with :func:`cacheNode`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug which references a message type attribute and is a destination.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not reference a message type attribute.
        :exc:`~exceptions.RuntimeError`: If ``plug`` does not have an input connection.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the dependency node connected as the input of ``plug``.
    """
    if plug.attribute().apiType() != om2.MFn.kMessageAttribute:
        raise EXC.MayaTypeError("{}: Plug does not reference a message type attribute")

    if not plug.isDestination:
        raise RuntimeError("{}: Plug has no input connection".format(NAME.getPlugFullName(plug)))

    sourcePlug = plug.sourceWithConversion()
    return sourcePlug.node()


def getCachedPlug(plug):
    """Retrieve a cached dependency node plug from a dependency node plug. Designed for use with :func:`cachePlug`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug which references a message type attribute and is a destination.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not reference a message type attribute.
        :exc:`~exceptions.RuntimeError`: If ``plug`` does not have an input connection.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation of a dependency node plug connected as the input of ``plug``.
    """
    if plug.attribute().apiType() != om2.MFn.kMessageAttribute:
        raise EXC.MayaTypeError("{}: Plug does not reference a message type attribute")

    if not plug.isDestination:
        raise RuntimeError("{}: Plug has no input connection".format(NAME.getPlugFullName(plug)))

    return plug.sourceWithConversion()


# --------------------------------------------------------------
# --- Modify ---
# --------------------------------------------------------------

def createNode(nodeType):
    """Create a node.

    Note:
        Use :func:`msTools.core.maya.dag_utils.createNode` to create a DAG node.

    Args:
        nodeType (:class:`basestring`): Name of the node type identifier used to create a node.

    Raises:
        :exc:`~exceptions.ValueError`: If ``nodeType`` is an invalid node type identifier.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper for the new dependency node.
    """
    dgMod = OM.MDGModifier()

    try:
        node = dgMod.createNode(nodeType)
    except TypeError:
        raise ValueError("{}: Invalid node type".format(nodeType))

    dgMod.doIt()

    return node


def deleteNode(node):
    """Delete a node.

    Note:
        Use :func:`msTools.core.maya.dag_utils.deleteNode` to delete a DAG node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
    """
    OM.validateNodeType(node)

    dgMod = OM.MDGModifier()
    dgMod.deleteNode(node)
    dgMod.doIt()


def renameNode(node, name):
    """Rename a node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        name (:class:`basestring`): New name for ``node``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
    """
    OM.validateNodeType(node)

    dgMod = OM.MDGModifier()
    dgMod.renameNode(node, name)
    dgMod.doIt()


def lockNode(node):
    """Lock a node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`bool`: :data:`True` if the lock state of ``node`` has changed, otherwise :data:`False`.
    """
    OM.validateNodeType(node)

    hasChanged = not om2.MFnDependencyNode(node).isLocked

    dgMod = OM.MDGModifier()
    dgMod.setNodeLockState(node, True)
    dgMod.doIt()

    return hasChanged


def unlockNode(node):
    """Unlock a node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`bool`: :data:`True` if the lock state of ``node`` has changed, otherwise :data:`False`.
    """
    OM.validateNodeType(node)

    hasChanged = om2.MFnDependencyNode(node).isLocked

    dgMod = OM.MDGModifier()
    dgMod.setNodeLockState(node, False)
    dgMod.doIt()

    return hasChanged


@DECORATOR.undoOnError(StandardError)
def disconnectDependencies(root, upstream=False, downstream=False, walk=False, filterTypes=None, forceLocked=False):
    """Disconnect pairs of source and destination plugs for the dependencies of a plug or node.

    Args:
        root (:class:`OpenMaya.MPlug` | :class:`OpenMaya.MObject`): Plug object or wrapper of a dependency node from which to traverse dependencies.
        upstream (:class:`bool`, optional): Whether to disconnect upstream dependencies of ``root``. Defaults to :data:`False`.
        downstream (:class:`bool`, optional): Whether to disconnect downstream dependencies of ``root``. Defaults to :data:`False`.
        walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
            If ``root`` is a node, each connected plug on ``root`` acts as the root of a path. Defaults to :data:`True`.
        filterTypes (iterable [:class:`int`], optional): Filter dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.
        forceLocked (:class:`bool`, optional): Whether to force disconnect a dependency that is connected via a locked destination plug. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``root`` is an :class:`OpenMaya.MObject` but does not reference a dependency node.
        :exc:`~exceptions.RuntimeError`: If any of the dependencies are connected via a locked destination plug and ``forceLocked`` is :data:`False`.

    Example:
        .. code-block:: python

            # Remove direct connections to any constraints downstream of `root`
            disconnectDependencies(root, downstream=True, filterTypes=(OpenMaya.MFn.kConstraint,))
    """
    if upstream:
        upstreamEdges = list(iterDependenciesByEdge(root, directionType=om2.MItDependencyGraph.kUpstream, walk=walk, filterTypes=filterTypes))
        for edge in upstreamEdges:
            PLUG.disconnect(edge[0], edge[1], forceLocked=forceLocked)

    if downstream:
        downstreamEdges = list(iterDependenciesByEdge(root, directionType=om2.MItDependencyGraph.kDownstream, walk=walk, filterTypes=filterTypes))
        for edge in downstreamEdges:
            PLUG.disconnect(edge[0], edge[1], forceLocked=forceLocked)


def cacheNode(sourceNode, destNode, shortName=None, longName=None):
    """Cache a dependency node on another dependency node via a message type attribute.

    A connection will be made from the static ``'message'`` attribute of the souce node to a message type attribute on the destination node.

    Args:
        sourceNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node to cache on ``destNode``.
        destNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node on which to cache the ``sourceNode``.
        shortName (:class:`basestring`, optional): Short name for the new message type attribute used to cache the ``sourceNode``.
            If :data:`None`, the ``longName`` will be used. If the ``longName`` is also :data:`None`, the ``sourceNode`` short name will be used.
            Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the new message type attribute used to cache the ``sourceNode``.
            If :data:`None`, the ``shortName`` will be used. If the ``shortName`` is also :data:`None`, the ``sourceNode`` short name will be used.
            Defaults to :data:`None`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``sourceNode`` or ``destNode`` does not reference a dependency node.
        :exc:`~exceptions.RuntimeError`: If ``destNode`` already has an attribute with the same ``shortName`` or ``longName``.
    """
    OM.validateNodeType(sourceNode)

    if not shortName and not longName:
        longName = NAME.getNodeShortName(sourceNode)

    # Add attribute
    msgAttr = ATTR.createMessageAttribute(shortName=shortName, longName=longName, readable=False)
    ATTR.addToNode(destNode, msgAttr)

    # Connect plugs
    sourcePlug = OM.getPlugFromNodeByName(sourceNode, "message")
    destPlug = om2.MPlug(destNode, msgAttr)
    PLUG.connect(sourcePlug, destPlug)


def cachePlug(sourcePlug, destNode, shortName=None, longName=None):
    """Cache a dependency node plug on a dependency node.

    A connection will be made from the source plug to a message type attribute on the destination node.

    Args:
        sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug to cache on ``destNode``.
        destNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node on which to cache the ``sourcePlug``.
        shortName (:class:`basestring`, optional): Short name for the new message type attribute used to cache the ``sourcePlug``. If :data:`None`, the ``longName`` will be used.
            If the ``longName`` is also :data:`None`, :meth:`msTools.core.maya.name_utils.getPlugStorableName` will be used to determine a name for the ``sourcePlug``.
            Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the new message type attribute used to cache the ``sourcePlug``. If :data:`None`, the ``shortName`` will be used.
            If the ``shortName`` is also :data:`None`, :meth:`msTools.core.maya.name_utils.getPlugStorableName` will be used to determine a name for the ``sourcePlug``.
            Defaults to :data:`None`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``destNode`` does not reference a dependency node.
        :exc:`~exceptions.RuntimeError`: If ``destNode`` already has an attribute with the same ``shortName`` or ``longName``.
    """
    if not shortName and not longName:
        longName = NAME.getPlugStorableName(sourcePlug)

    # Add attribute
    msgAttr = ATTR.createMessageAttribute(shortName=shortName, longName=longName, readable=False)
    ATTR.addToNode(destNode, msgAttr)

    # Connect plugs
    destPlug = om2.MPlug(destNode, msgAttr)
    PLUG.connect(sourcePlug, destPlug)


def cacheComponent(sourceComponent, destNode, shortName=None, longName=None):
    """Cache shape node components on a destination node.

    A connection will be made from the static ``'message'`` attribute of the souce node to a typed attribute on the destination node.
    The typed attribute will hold the component data from the source node.

    Args:
        sourceComponent ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` representing component data to cache on ``destNode``.

            #. Path encapsulation of a shape node.
            #. Wrapper holding :attr:`OpenMaya.MFn.kComponent` type date corresponding to components on the shape node.

        destNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node on which to cache the ``sourceComponent`` data.
        shortName (:class:`basestring`, optional): Short name for the new typed attribute used to cache the component data. If :data:`None`, the ``longName`` will be used.
            If the ``longName`` is also :data:`None`, the short name of the ``sourceNode`` will be suffixed by ``'__components'``.
            Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the new typed attribute used to cache the component data. If :data:`None`, the ``shortName`` will be used.
            If the ``shortName`` is also :data:`None`, the short name of the ``sourceNode`` will be suffixed by ``'__components'``.
            Defaults to :data:`None`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the first element of ``sourceComponent`` does not reference a shape node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the second element of ``sourceComponent`` does not reference component data.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``destNode`` does not reference a dependency node.
        :exc:`~exceptions.RuntimeError`: If ``destNode`` already has an attribute with the same ``shortName`` or ``longName``.
    """
    sourceNode = sourceComponent[0].node()
    OM.validateNode(sourceNode, om2.MFn.kShape)

    if not shortName and not longName:
        longName = "__".join([NAME.getNodeShortName(sourceNode), "components"])

    # Add attribute
    compListAttr = ATTR.createTypedAttribute(shortName=shortName, longName=longName, dataType=om2.MFnData.kComponentList, value=sourceComponent[1], readable=False)
    ATTR.addToNode(destNode, compListAttr)

    # Connect plugs
    sourcePlug = OM.getPlugFromNodeByName(sourceNode, "message")
    destPlug = om2.MPlug(destNode, compListAttr)
    PLUG.connect(sourcePlug, destPlug)


def setCachedComponent(sourceComponent, destPlug, forceLocked=False):
    """Update shape node components which are cached on a dependency node via a plug holding :attr:`OpenMaya.MFnData.kComponentList` data.

    A connection will be made from the static ``'message'`` attribute of the souce node to an existing typed attribute.
    The existing typed attribute will be updated to hold the component data from the source node.

    Args:
        sourceComponent ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` used to update the component data of ``destPlug``.

            #. Path encapsulation of a shape node.
            #. Wrapper holding :attr:`OpenMaya.MFn.kComponent` type date corresponding to components on the shape node.

        destPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug holding :attr:`OpenMaya.MFnData.kComponentList` data.
        forceLocked (:class:`bool`, optional): Whether to force the update if ``destPlug`` is locked. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the first element of ``sourceComponent`` does not reference a shape node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the second element of ``sourceComponent`` does not reference component data.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``destPlug`` does not hold :attr:`OpenMaya.MFnData.kComponentList` data.
        :exc:`~exceptions.RuntimeError`: If ``destPlug`` is locked and ``forceLocked`` is :data:`False`.
    """
    sourceNode = sourceComponent[0].node()
    OM.validateNode(sourceNode, om2.MFn.kShape)
    OM.validateComponentType(sourceComponent[1])

    attr = destPlug.attribute()
    if not attr.hasFn(om2.MFn.kTypedAttribute):
        raise EXC.MayaTypeError("{}: Plug does not hold data of type OpenMaya.MFnData.kComponentList".format(NAME.getPlugFullName(destPlug)))

    attrFn = om2.MFnTypedAttribute(attr)
    attrDataType = attrFn.attrType()
    if not attrDataType == om2.MFnData.kComponentList:
        raise EXC.MayaTypeError("{}: Plug does not hold data of type OpenMaya.MFnData.kComponentList".format(NAME.getPlugFullName(destPlug)))

    # Checks the ancestor hierarchy (the lock state of an unconnected descendant does not automatically update when an ancestor is locked)
    isLocked = PLUG.isLocked(destPlug)
    if isLocked and not forceLocked:
        raise RuntimeError("{}: Plug is locked. Use 'forceLocked=True' to temporarily unlocked".format(NAME.getPlugFullName(destPlug)))

    context = CONTEXT.UnlockPlug(destPlug) if isLocked else PY_CONTEXT.Null()
    with context:
        # Disconnect the current shape node
        if destPlug.isDestination:
            PLUG.disconnect(destPlug.sourceWithConversion(), destPlug)

        # Create a kComponentListData wrapper to set as the value
        dataFn = om2.MFnComponentListData()
        dataWrapper = dataFn.create()
        dataFn.add(sourceComponent[1])
        dgMod = OM.MDGModifier()
        dgMod.newPlugValue(destPlug, dataWrapper)
        dgMod.doIt()

        # Connect the new shape node
        shape = sourceNode
        shapeMessagePlug = OM.getPlugFromNodeByName(shape, "message")
        PLUG.connect(shapeMessagePlug, destPlug)
