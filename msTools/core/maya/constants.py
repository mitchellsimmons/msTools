"""
Contant data relating to the `OpenMaya`_ API.

----------------------------------------------------------------
"""
from maya.api import OpenMaya as om2


# ----------------------------------------------------------------------------
# --- Dynamic Constants ---
# ----------------------------------------------------------------------------

CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MFn.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MFn` type constants to their respective names."""

DATA_CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MFnData.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MFnData` data type constants to their respective names."""

NUMERIC_DATA_CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MFnNumericData.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MFnNumericData` numeric type constants to their respective names."""

ANGLE_UNIT_CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MAngle.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MAngle` unit type constants to their respective names."""

DISTANCE_UNIT_CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MDistance.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MDistance` unit type constants to their respective names."""

TIME_UNIT_CONSTANT_NAME_MAPPING = {v: k for k, v in om2.MTime.__dict__.items() if k.startswith('k')}
""":class:`dict` [:class:`int`, :class:`str`]: Constant mapping of :class:`OpenMaya.MTime` unit type constants to their respective names."""


# ----------------------------------------------------------------------------
# --- Static Constants ---
# ----------------------------------------------------------------------------

COMPONENT_CONSTANT_ITERATOR_CLASS_MAPPING = {
    om2.MFn.kMeshVertComponent: om2.MItMeshVertex, om2.MFn.kMeshEdgeComponent: om2.MItMeshEdge, om2.MFn.kMeshPolygonComponent: om2.MItMeshPolygon,
    om2.MFn.kMeshVtxFaceComponent: om2.MItMeshFaceVertex, om2.MFn.kSurfaceCVComponent: om2.MItSurfaceCV
}
""":class:`dict` [:class:`int`, :class:`type`]: Constant mapping of :class:`OpenMaya.MFn` component type constants to their respective iterator class.

Valid component type constants are :attr:`OpenMaya.MFn.kMeshVertComponent`, :attr:`OpenMaya.MFn.kMeshEdgeComponent`, :attr:`OpenMaya.MFn.kMeshPolygonComponent`,
:attr:`OpenMaya.MFn.kMeshVtxFaceComponent`, :attr:`OpenMaya.MFn.kSurfaceCVComponent`.

Note:
    :attr:`OpenMaya.MFn.kCurveCVComponent` does not have an iterator.
"""

# Used to return the correct function set (for creating a component MObject) for the given MFn component type
COMPONENT_CONSTANT_CLASS_MAPPING = {
    om2.MFn.kMeshVertComponent: om2.MFnSingleIndexedComponent,
    om2.MFn.kMeshEdgeComponent: om2.MFnSingleIndexedComponent,
    om2.MFn.kMeshPolygonComponent: om2.MFnSingleIndexedComponent,
    om2.MFn.kMeshVtxFaceComponent: om2.MFnDoubleIndexedComponent,
    om2.MFn.kSurfaceCVComponent: om2.MFnDoubleIndexedComponent,
    om2.MFn.kCurveCVComponent: om2.MFnSingleIndexedComponent
}
""":class:`dict` [:class:`int`, :class:`type`]: Constant mapping of :class:`OpenMaya.MFn` component type constants to their respective component function set class.
Each function set is a strict subclass of :class:`OpenMaya.MFnComponent`.

Valid component type constants are :attr:`OpenMaya.MFn.kMeshVertComponent`, :attr:`OpenMaya.MFn.kMeshEdgeComponent`, :attr:`OpenMaya.MFn.kMeshPolygonComponent`,
:attr:`OpenMaya.MFn.kMeshVtxFaceComponent`, :attr:`OpenMaya.MFn.kSurfaceCVComponent`, :attr:`OpenMaya.MFn.kCurveCVComponent`.

The function set classes can be used to create or inspect a component encapsulation of the respective component type.
"""

SHAPE_CONSTANT_COMPONENT_CONSTANTS_MAPPING = {
    om2.MFn.kMesh: (om2.MFn.kMeshVertComponent, om2.MFn.kMeshEdgeComponent, om2.MFn.kMeshPolygonComponent, om2.MFn.kMeshVtxFaceComponent),
    om2.MFn.kNurbsSurface: (om2.MFn.kSurfaceCVComponent,),
    om2.MFn.kNurbsCurve: (om2.MFn.kCurveCVComponent,)
}
""":class:`dict` [:class:`int`, (:class:`int`, ...)]: Constant mapping of :class:`OpenMaya.MFn` shape type constants to :class:`OpenMaya.MFn` component type constants.

Valid shape type constants are :attr:`OpenMaya.MFn.kMesh`, :attr:`OpenMaya.MFn.kNurbsSurface`, :attr:`OpenMaya.MFn.kNurbsCurve`.

Each shape type constant maps to one or more component type constants, representing the types of components which can be retrieved from a shape of the given type.
"""

# Used to return the correct function set for the given MFn shape type (not all shapes have a specific function set)
SHAPE_CONSTANT_CLASS_MAPPING = {
    om2.MFn.kCamera: om2.MFnCamera, om2.MFn.kMesh: om2.MFnMesh,
    om2.MFn.kNurbsCurve: om2.MFnNurbsCurve, om2.MFn.kNurbsSurface: om2.MFnNurbsSurface
}
""":class:`dict` [:class:`int`, :class:`type`]: Constant mapping of :class:`OpenMaya.MFn` shape type constants to their respective shape function set class.
Each function set is a strict subclass of :class:`OpenMaya.MFnDagNode`.

Valid shape type constants are :attr:`OpenMaya.MFn.kCamera`, :attr:`OpenMaya.MFn.kMesh`, :attr:`OpenMaya.MFn.kNurbsCurve`, :attr:`OpenMaya.MFn.kNurbsSurface`.

Note:
    Not all shape types have a respective function set.
"""

DATA_CONSTANT_CLASS_MAPPING = {
    om2.MFnData.kComponentList: om2.MFnComponentListData, om2.MFnData.kDoubleArray: om2.MFnDoubleArrayData, om2.MFnData.kIntArray: om2.MFnIntArrayData,
    om2.MFnData.kMatrix: om2.MFnMatrixData, om2.MFnData.kMesh: om2.MFnMeshData, om2.MFnData.kNumeric: om2.MFnNumericData, om2.MFnData.kNurbsCurve: om2.MFnNurbsCurveData,
    om2.MFnData.kNurbsSurface: om2.MFnNurbsSurfaceData, om2.MFnData.kPlugin: om2.MFnPluginData, om2.MFnData.kPluginGeometry: om2.MFnGeometryData,
    om2.MFnData.kPointArray: om2.MFnPointArrayData, om2.MFnData.kString: om2.MFnStringData, om2.MFnData.kStringArray: om2.MFnStringArrayData, om2.MFnData.kVectorArray: om2.MFnVectorArrayData
}
""":class:`dict` [:class:`int`, :class:`type`]: Constant mapping of :class:`OpenMaya.MFnData` data type constants to their respective function set class.
Each function set is a strict subclass of :class:`OpenMaya.MFnData`.

Valid data type constants are :attr:`OpenMaya.MFnData.kComponentList`, :attr:`OpenMaya.MFnData.kDoubleArray`, :attr:`OpenMaya.MFnData.kIntArray`,
:attr:`OpenMaya.MFnData.kMatrix`, :attr:`OpenMaya.MFnData.kMesh`, :attr:`OpenMaya.MFnData.kNumeric`, :attr:`OpenMaya.MFnData.kNurbsCurve`,
:attr:`OpenMaya.MFnData.kNurbsSurface`, :attr:`OpenMaya.MFnData.kPlugin`, :attr:`OpenMaya.MFnData.kPluginGeometry`, :attr:`OpenMaya.MFnData.kPointArray`,
:attr:`OpenMaya.MFnData.kString`, :attr:`OpenMaya.MFnData.kStringArray`, :attr:`OpenMaya.MFnData.kVectorArray`.

The function set classes can be used to extract data from :class:`OpenMaya.MObject` wrappers of the corresponding data types.
They can also be used to create :class:`OpenMaya.MObject` data wrappers which can be used as default values when creating typed attributes.

Note:
    Function sets corresponding to the following data types cannot be used for the creation of typed attributes.

    - :attr:`OpenMaya.MFnData.kNumeric`: Use function sets corresponding to :attr:`OpenMaya.MFnData.kDoubleArray` or :attr:`OpenMaya.MFnData.kIntArray` to encapsulate numeric data.
    - :attr:`OpenMaya.MFnData.kPluginGeometry`: Corresponds to the base function set type for :attr:`OpenMaya.MFnData.kMesh`, :attr:`OpenMaya.MFnData.kNurbsCurve` and :attr:`OpenMaya.MFnData.kNurbsSurface`.
"""

NUMERIC_DATA_CONSTANT_SIZE_MAPPING = {
    om2.MFnNumericData.kFloat: 1, om2.MFnNumericData.kAddr: 1, om2.MFnNumericData.kChar: 1, om2.MFnNumericData.kByte: 1, om2.MFnNumericData.kInt64: 1,
    om2.MFnNumericData.kShort: 1, om2.MFnNumericData.kInt: 1, om2.MFnNumericData.kDouble: 1, om2.MFnNumericData.kBoolean: 1,
    om2.MFnNumericData.k2Short: 2, om2.MFnNumericData.k2Int: 2, om2.MFnNumericData.k2Float: 2, om2.MFnNumericData.k2Double: 2,
    om2.MFnNumericData.k3Short: 3, om2.MFnNumericData.k3Int: 3, om2.MFnNumericData.k3Float: 3, om2.MFnNumericData.k3Double: 3,
    om2.MFnNumericData.k4Double: 4
}
""":class:`dict` [:class:`int`, :class:`int`]: Constant mapping of :class:`OpenMaya.MFnNumericData` numeric type constants to a value representing the size of the numeric type.

Example:
    .. code-block:: python

        NUMERIC_DATA_CONSTANT_SIZE_MAPPING[OpenMaya.MFnNumericData.kFloat] == 1
        NUMERIC_DATA_CONSTANT_SIZE_MAPPING[OpenMaya.MFnNumericData.k3Int] == 3
"""

NUMERIC_DATA_CONSTANT_TYPE_MAPPING = {
    om2.MFnNumericData.kFloat: float, om2.MFnNumericData.kAddr: int, om2.MFnNumericData.kChar: int, om2.MFnNumericData.kByte: int, om2.MFnNumericData.kInt64: int,
    om2.MFnNumericData.kShort: int, om2.MFnNumericData.kInt: int, om2.MFnNumericData.kDouble: float, om2.MFnNumericData.kBoolean: bool,
    om2.MFnNumericData.k2Short: int, om2.MFnNumericData.k2Int: int, om2.MFnNumericData.k2Float: float, om2.MFnNumericData.k2Double: float,
    om2.MFnNumericData.k3Short: int, om2.MFnNumericData.k3Int: int, om2.MFnNumericData.k3Float: float, om2.MFnNumericData.k3Double: float,
    om2.MFnNumericData.k4Double: float
}
""":class:`dict` [:class:`int`, :class:`type`]: Constant mapping of :class:`OpenMaya.MFnNumericData` numeric type constants to the class of the corresponding numeric data type.
Classes are either :class:`bool`, :class:`float` or :class:`int`.
"""
