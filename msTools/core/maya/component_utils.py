"""
Operate on components in Maya.

----------------------------------------------------------------

Retrival
--------

    The `OpenMaya`_ API represents components as an encapsulation of indices and a component type.
    Depending on the component type, the encapsulation will either be a single indexed list (eg. vertices) or a double index list (eg. surface CVs).

    - See :data:`msTools.core.maya.constants.COMPONENT_CONSTANT_CLASS_MAPPING` for a mapping of component types to function set types capable of producing the encapsulation.
    - For example :class:`OpenMaya.MFnSingleIndexedComponent` is capable of producing an object that encapsulates the vertices of a shape node.

    To retrieve component indices from a shape there are a range of component iterators available in the `OpenMaya`_ API.

    - See :data:`msTools.core.maya.constants.COMPONENT_CONSTANT_ITERATOR_CLASS_MAPPING` for a mapping of component types to component iterators.
    - The only component type which does not have a respective iterator is :attr:`OpenMaya.MFn.kCurveCVComponent`.
    - Curve CVs do not require an iterator due to the simplicity of their arrangement.

----------------------------------------------------------------

Selection
---------

    To select components through the `OpenMaya`_ API an :class:`OpenMaya.MSelectionList` can be used.
    Selections are made via a two-element tuple of (:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`).

    - The :class:`OpenMaya.MDagPath` specifies a path to a specific instance of a shape node.
    - The :class:`OpenMaya.MObject` represents an encapsulation of the components to be selected for the shape instance.

----------------------------------------------------------------
"""
from maya.api import OpenMaya as om2

from msTools.core.maya import constants as CONST
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import om_utils as OM


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def areEqual(componentA, componentB):
    """Check if two component objects are equivalent in terms of indices and component type.

    Args:
        componentA (:class:`OpenMaya.MObject`): Wrapper of a component object.
        componentB (:class:`OpenMaya.MObject`): Wrapper of a component object.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` or ``componentB`` do not reference components.

    Returns:
        :class:`bool`: :data:`True` if ``componentA`` is equivalent to ``componentB`` in terms of indices and component type, otherwise :data:`False`.
    """
    OM.validateComponentType(componentA)
    OM.validateComponentType(componentB)

    return om2.MFnComponent(componentA).isEqual(componentB)


# --------------------------------------------------------------
# --- Retrieval ---
# --------------------------------------------------------------

def getComponentsFromShape(shape, componentType=om2.MFn.kMeshVertComponent):
    """Return the components of a shape for a specific component type.

    The result can be used to select the components of ``shape`` via an :class:`OpenMaya.MSelectionList`.

    Args:
        shape (:class:`OpenMaya.MObject`): Wrapper of a shape node of type mesh, surface or curve.
        componentType (:class:`int`, optional): Component type constant from :class:`OpenMaya.MFn`, compatible with ``shape``.
            See :data:`msTools.core.maya.constants.SHAPE_CONSTANT_COMPONENT_CONSTANTS_MAPPING` for a mapping of valid shape types to valid component type constants.
            Defaults to :attr:`OpenMaya.MFn.kMeshVertComponent`.

    Raises:
        :exc:`~exceptions.ValueError`: If the ``componentType`` is not compatible with ``shape``.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shape`` is neither a mesh, surface nor curve.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the component indices and ``componentType``.
    """
    shapePath = om2.MDagPath.getAPathTo(shape)

    # Validate the component type is compatible with the shape type
    for shapeTypeConst, componentTypeConsts in CONST.SHAPE_CONSTANT_COMPONENT_CONSTANTS_MAPPING.iteritems():
        if shape.hasFn(shapeTypeConst):
            if componentType not in componentTypeConsts:
                raise ValueError("Component type constant `OpenMaya.MFn.{}` is not supported by `OpenMaya.MFn.{}` type nodes".format(CONST.CONSTANT_NAME_MAPPING[componentType], CONST.CONSTANT_NAME_MAPPING[shapeTypeConst]))
            break
    else:
        raise EXC.MayaTypeError("Expected node of type `OpenMaya.MFn.kMesh`, `OpenMaya.MFn.kSurface` or `OpenMaya.MFn.kCurve`, received `OpenMaya.MFn.{}` type object instead".format(shape.apiTypeStr))

    try:
        componentIterClass = CONST.COMPONENT_CONSTANT_ITERATOR_CLASS_MAPPING[componentType]
    except KeyError:
        # Nurbs curve does not have an iterator
        nurbsCurveFn = om2.MFnNurbsCurve(shapePath)
        if nurbsCurveFn.form == om2.MFnNurbsCurve.kPeriodic:
            # The last N (degree) CVs are overlapping and do not need to be included
            # These last N CVs are permanently bound to the first N CVs and cannot be repositioned by selecting them (only by the first N CVs)
            numCVs = nurbsCurveFn.numCVs - nurbsCurveFn.degree
        else:
            numCVs = nurbsCurveFn.numCVs
        componentWrapper = nurbsCurveFn.cvs(0, numCVs - 1)
    else:
        componentFn = CONST.COMPONENT_CONSTANT_CLASS_MAPPING[componentType]()

        if componentType == om2.MFn.kSurfaceCVComponent:
            componentIter = componentIterClass(shapePath)
            uIndices = om2.MIntArray()
            vIndices = om2.MIntArray()
            while not componentIter.isDone():
                while not componentIter.isRowDone():
                    u, v = componentIter.uvIndices()
                    uIndices.append(u)
                    vIndices.append(v)
                    componentIter.next()
                componentIter.nextRow()
            indices = zip(uIndices, vIndices)
            componentWrapper = componentFn.create(componentType)
            componentFn.addElements(indices)
        elif componentType in [om2.MFn.kMeshVertComponent, om2.MFn.kMeshEdgeComponent, om2.MFn.kMeshPolygonComponent]:
            componentIter = componentIterClass(shapePath)
            indices = om2.MIntArray()
            while not componentIter.isDone():
                index = componentIter.index()
                indices.append(index)
                if componentType == om2.MFn.kMeshPolygonComponent:
                    componentIter.next(0)  # Random arg is needed??
                else:
                    componentIter.next()
            componentWrapper = componentFn.create(componentType)
            componentFn.addElements(indices)
        elif componentType == om2.MFn.kMeshVtxFaceComponent:
            # This creates a component where vertices are relative to a face (instead of global vertex indices)
            componentIter = componentIterClass(shapePath)
            faceIndices = om2.MIntArray()
            vertexIndices = om2.MIntArray()
            while not componentIter.isDone():
                faceId = componentIter.faceId()
                # The iterator has two options for returning vertex IDs (relative indices or global indices)
                # Maya uses the global indices when selecting a Vertex Face so that is what is used here
                vertexId = componentIter.vertexId()
                faceIndices.append(faceId)
                vertexIndices.append(vertexId)
                componentIter.next()
            indices = zip(vertexIndices, faceIndices)
            componentWrapper = componentFn.create(componentType)
            componentFn.addElements(indices)

    return componentWrapper


def getUnion(componentA, componentB):
    """Return the union of ``componentA`` with ``componentB``.
    The union contains all elements of ``componentA`` and ``componentB``.

    Args:
        componentA (:class:`OpenMaya.MObject`): Wrapper of a component object.
        componentB (:class:`OpenMaya.MObject`): Wrapper of a component object.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` or ``componentB`` do not reference components.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` and ``componentB`` do not have the same component types.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of a component object representing the union of ``componentA`` with ``componentB``.
    """
    OM.validateComponentType(componentA)
    OM.validateComponentType(componentB)

    if componentA.apiType() != componentB.apiType():
        raise EXC.MayaTypeError("Component objects must be of the same component type")

    # Use a path to a default node to make the selection
    worldPath = om2.MDagPath.getAPathTo(om2.MItDag().root())
    selection = om2.MSelectionList()
    selection.add((worldPath, componentA))
    selection.merge(worldPath, componentB)
    return selection.getComponent(0)[1]


def getIntersection(componentA, componentB):
    """Return the intersection of ``componentA`` and ``componentB``.
    The intersection contains all elements which are common to both ``componentA`` and ``componentB``.

    Args:
        componentA (:class:`OpenMaya.MObject`): Wrapper of a component object.
        componentB (:class:`OpenMaya.MObject`): Wrapper of a component object.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` or ``componentB`` do not reference components.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` and ``componentB`` do not have the same component types.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of a component object representing the intersection of ``componentA`` and ``componentB``.
    """
    OM.validateComponentType(componentA)
    OM.validateComponentType(componentB)

    if componentA.apiType() != componentB.apiType():
        raise EXC.MayaTypeError("Component objects must be of the same component type")

    # Use a path to a default node to make the selection
    worldPath = om2.MDagPath.getAPathTo(om2.MItDag().root())
    selectionA = om2.MSelectionList()
    selectionA.add((worldPath, componentA))
    selectionB = om2.MSelectionList()
    selectionB.add((worldPath, componentB))
    selectionA.intersect(selectionB)
    return selectionA.getComponent(0)[1]


def getDifference(componentA, componentB):
    """Return the difference of ``componentB`` subtracted from ``componentA``.
    The difference contains all elements of ``componentA`` which are not in ``componentB``.

    Args:
        componentA (:class:`OpenMaya.MObject`): Wrapper of a component object.
        componentB (:class:`OpenMaya.MObject`): Wrapper of a component object.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` or ``componentB`` do not reference components.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``componentA`` and ``componentB`` do not have the same component types.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of a component object representing the difference of ``componentB`` subtracted from ``componentA``.
    """
    OM.validateComponentType(componentA)
    OM.validateComponentType(componentB)

    if componentA.apiType() != componentB.apiType():
        raise EXC.MayaTypeError("Component objects must be of the same component type")

    # Use a path to a default node to make the selection
    worldPath = om2.MDagPath.getAPathTo(om2.MItDag().root())
    selection = om2.MSelectionList()
    selection.add((worldPath, componentA))
    selection.merge(worldPath, componentB, strategy=om2.MSelectionList.kRemoveFromList)
    return selection.getComponent(0)[1]
