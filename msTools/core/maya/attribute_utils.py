"""
Create, modify and access attributes in Maya.

----------------------------------------------------------------

Creation
--------

    Attributes act like templates in defining certain default values for plugs including the data type, name and initial value.
    Attributes are generally declared as static :class:`OpenMaya.MObject` wrappers inside the class definition of a node but can also be created dynamically.

    - A static attribute can act as the template for a plug on multiple dependency nodes.
    - A dynamic attribute can act as the template for a plug on a single dependency node.

    .. _properties:

    By default, attributes are:

    - Readable.
    - Writable.
    - Connectable.
    - Storable.
    - Cached.
    - Not arrays.
    - Have indices that matter.
    - Do not use an array builder.
    - Not keyable.
    - Not hidden.
    - Not used as colors.
    - Not indeterminant.
    - Set to disconnect behavior kNothing.

----------------------------------------------------------------

Types
-----

    Each attribute type has a corresponding Function Set that subclasses :class:`OpenMaya.MFnAttribute`.
    Each attribute type is capable of accepting certain data types.
    Complex data types can be manipulated through a subclass of :class:`OpenMaya.MFnData`.

----------------------------------------------------------------

.. _modifying:

Modifying
---------

    The properties of an attribute can be modified via the :class:`OpenMaya.MFnAttribute` Function Set.
    If an attribute was statically defined, modifying its properties can affect a plug on multiple nodes.
    If an attribute was dynamically defined, modifying its properties can affect a plug on a single node.
    Plug specific modifications can be made through an :class:`OpenMaya.MPlug` encapsulation.

----------------------------------------------------------------

Note:
    1. Compound attributes do not create a unique namespace for child attributes. Any child attribute of a compound must have a unique name from all other attributes on a given node.

Note:
    2. Attributes which are descendant to a compound array will produce placeholder indices for ancestral elements when used to instantiate an :class:`OpenMaya.MPlug`.

.. _note_3:

Note:
    3. It is possible to set both :attr:`OpenMaya.MFnAttribute.keyable` and :attr:`OpenMaya.MFnAttribute.channelBox` properties :data:`True` for an attribute.
       However once instantiated as a plug this causes an invalid state in which :attr:`OpenMaya.MPlug.isKeyable` and :attr:`OpenMaya.MPlug.isChannelBox` are both :data:`True`.
       When setting these properties manually, Maya tries to prevent this from occuring as it produces a visual bug whereby any associated UI control appears non-keyable.

Note:
    4. An attribute can be renamed via :meth:`OpenMaya.MDGModifier.renameAttribute` even if the corresponding dependency node plug is locked.
       This behaviour is inconsistent with Maya commands.

.. _warning_1:

Warning:
    1. An error is not produced when trying to delete an attribute that corresponds to a locked array plug.
       Subsequently Maya will crash if that locked array plug is connected or has at least one connected element plug.

Warning:
    2. An attribute can be renamed via :meth:`OpenMaya.MDGModifier.renameAttribute` even if the new short or long name already exists on the node.
       This will result in undefined behaviour.

----------------------------------------------------------------
"""
import json
import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2

from msTools.core.maya import constants as CONST
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM


# --------------------------------------------------------------
# --- Classes ---
# --------------------------------------------------------------

class _PropertyModifier(OM.Modifier):
    """Modify properties of an attribute via :class:`OpenMaya.MFnAttribute`.
    Modifications will be placed on the Maya undo queue.
    """

    def __init__(self, attribute, **properties):
        OM.validateAttributeType(attribute)
        self._attrFn = om2.MFnAttribute(attribute)

        if properties.get("keyable") and properties.get("channelBox"):
            # If channelBox is enabled we need to disable it
            # Unlike MPlug, MFnAttribute does not do this automatically
            log.info("Do not attempt to set `keyable=True` and `channelBox=True`. Disabling `channelBox` in order to enable `keyable`, only one property should be enabled")
            properties["channelBox"] = False
        elif properties.get("keyable") and self._attrFn.channelBox:
            log.info("Disabling `channelBox` in order to enable `keyable`, only one property should be enabled")
            properties["channelBox"] = False
        elif properties.get("channelBox") and self._attrFn.keyable:
            log.info("Disabling `keyable` in order to enable `channelBox`, only one property should be enabled")
            properties["keyable"] = False

        self._doItValues = properties
        self._undoItValues = {}

        super(_PropertyModifier, self).__init__()

    def doIt(self):
        for prop, newValue in self._doItValues.iteritems():
            self._undoItValues[prop] = getattr(self._attrFn, prop)
            setattr(self._attrFn, prop, newValue)

    def undoIt(self):
        for prop, oldValue in self._undoItValues.iteritems():
            setattr(self._attrFn, prop, oldValue)


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def validateNames(shortName=None, longName=None):
    """Attempts to return valid attribute names from the data given.

    Args:
        shortName (:class:`basestring`, optional): Short name of an attribute. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name of an attribute. Defaults to :data:`None`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
    ..

    Returns:
        (:class:`str`, :class:`str`): A two-element :class:`tuple`.

        #. Short name of an attribute.
        #. Long name of an attribute.
    """
    if not any((shortName, longName)):
        raise ValueError('Attribute must be given at minimum a shortName or a longName')

    return shortName or longName, longName or shortName


# --------------------------------------------------------------
# --- Create ---
# --------------------------------------------------------------

def createCompoundAttribute(shortName=None, longName=None, **kwargs):
    """Create a dynamic compound attribute, useful for storing a related set of data.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)
    attrFn = om2.MFnCompoundAttribute()
    attr = attrFn.create(longName, shortName)

    setProperties(attr, **kwargs)

    return attr


def createNumericAttribute(shortName=None, longName=None, dataType=om2.MFnNumericData.kFloat, point=False, color=False, value=None, min_=None, max_=None, softMin=None, softMax=None, **kwargs):
    """Create a dynamic numeric attribute based on a data type constant from :class:`OpenMaya.MFnNumericData`.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnNumericData` representing the default data type.
            Valid values are :attr:`~OpenMaya.MFnNumericData.kFloat`, :attr:`~OpenMaya.MFnNumericData.kAddr`, :attr:`~OpenMaya.MFnNumericData.kChar`,
            :attr:`~OpenMaya.MFnNumericData.kByte`, :attr:`~OpenMaya.MFnNumericData.kShort`, :attr:`~OpenMaya.MFnNumericData.kInt`,
            :attr:`~OpenMaya.MFnNumericData.kInt64`, :attr:`~OpenMaya.MFnNumericData.kDouble`, :attr:`~OpenMaya.MFnNumericData.kBoolean`,
            :attr:`~OpenMaya.MFnNumericData.k2Short`, :attr:`~OpenMaya.MFnNumericData.k2Int`, :attr:`~OpenMaya.MFnNumericData.k2Float`,
            :attr:`~OpenMaya.MFnNumericData.k2Double`, :attr:`~OpenMaya.MFnNumericData.k3Short`, :attr:`~OpenMaya.MFnNumericData.k3Int`,
            :attr:`~OpenMaya.MFnNumericData.k3Float`, :attr:`~OpenMaya.MFnNumericData.k3Double`, :attr:`~OpenMaya.MFnNumericData.k4Double`.
            Multi data point types such as :attr:`~OpenMaya.MFnNumericData.k2Float` will create a compound attribute of type :attr:`OpenMaya.MFn.kAttribute2Float`.
            In this case, child attribute names would be suffixed with an index and would be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data.
            Defaults to :attr:`~OpenMaya.MFnNumericData.kFloat`.
        point (:class:`bool`, optional): If :data:`True`, the ``dataType`` will be ignored and an attribute of type :attr:`OpenMaya.MFn.kAttribute3Float` will be created, storing :attr:`~OpenMaya.MFnNumericData.k3Float` data.
            If ``value`` is given, it must be a three-element :class:`tuple`.
            Child attribute names will be suffixed with ``'X'``, ``'Y'``, ``'Z'`` respectively and will be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data. Defaults to :data:`False`.
        color (:class:`bool`, optional): If :data:`True` and ``point`` is :data:`False`, the ``dataType`` will be ignored and an attribute of type :attr:`OpenMaya.MFn.kAttribute3Float` will be created, storing :attr:`~OpenMaya.MFnNumericData.k3Float` data.
            If ``value`` is given, it must be a three-element :class:`tuple`.
            Child attribute names will be suffixed with ``'R'``, ``'G'``, ``'B'`` respectively and will be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data. Defaults to :data:`False`.
        value (numeric-type, optional): Default value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        min_ (:class:`float` | :class:`int`, optional): Min value for the attribute. Defaults to :data:`None`.
        max_ (:class:`float` | :class:`int`, optional): Max value for the attribute. Defaults to :data:`None`.
        softMin (:class:`float` | :class:`int`, optional): Soft min value for the attribute. Defaults to :data:`None`.
        softMax (:class:`float` | :class:`int`, optional): Soft max value for the attribute. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
        :exc:`~exceptions.ValueError`: If a compound attribute type is passed a ``value`` with an incompatible number of elements.
        :exc:`~exceptions.TypeError`: If the ``value`` type is incompatible with the ``dataType``.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)
    dataSize = CONST.NUMERIC_DATA_CONSTANT_SIZE_MAPPING[dataType]
    attrFn = om2.MFnNumericAttribute()

    if value is None:
        if point or color:
            value = (0, 0, 0)
        elif dataSize == 1:
            value = 0
        else:
            value = tuple([0 for x in range(dataSize)])
    else:
        if point or color:
            if len(value) != 3:
                raise ValueError("Point or color attribute only accepts sequence of length 3, not {}".format(len(value)))
            value = tuple(value)
        elif dataSize > 1:
            if len(value) != dataSize:
                raise ValueError("Sequence of length {}, not compatible with data type: OpenMaya.MFnNumericData.{}".format(len(value), CONST.MFN_NUMERIC_DATA_NAME_REGISTRY[dataType]))
            value = tuple(value)

    # The create methods do not accept a sequence for the defaultData, set it after instead
    if dataType == om2.MFnNumericData.kAddr:
        attr = attrFn.createAddr(longName, shortName, defaultValue=0)
    elif point:
        attr = attrFn.createPoint(longName, shortName)
    elif color:
        attr = attrFn.createColor(longName, shortName)
    else:
        attr = attrFn.create(longName, shortName, dataType, defaultValue=0)

    attrFn.default = value
    if min_:
        attrFn.setMin(min_)
    if max_:
        attrFn.setMax(max_)
    if softMin:
        attrFn.setSoftMin(softMin)
    if softMax:
        attrFn.setSoftMax(softMax)

    setProperties(attr, **kwargs)

    return attr


def createUnitAttribute(shortName=None, longName=None, dataType=om2.MFnUnitAttribute.kDistance, value=None, min_=None, max_=None, softMin=None, softMax=None, **kwargs):
    """Create a dynamic unit attribute based on a data type constant from :class:`OpenMaya.MFnUnitAttribute`.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnUnitAttribute` representing the default data type.
            Valid values are :attr:`~OpenMaya.MFnUnitAttribute.kAngle`, :attr:`~OpenMaya.MFnUnitAttribute.kDistance`, :attr:`~OpenMaya.MFnUnitAttribute.kTime`.
            Defaults to :attr:`~OpenMaya.MFnUnitAttribute.kDistance`.
        value (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
            Default value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        min_ (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
            Min value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        max_ (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
            Max value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        softMin (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
            Soft min value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        softMax (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
            Soft max value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
        :exc:`~exceptions.TypeError`: If the ``value``, ``min``, ``max``, ``softMin`` or ``softMax`` type is incompatible with the ``dataType``.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)
    attrFn = om2.MFnUnitAttribute()

    if isinstance(value, (om2.MAngle, om2.MDistance, om2.MTime)):
        attr = attrFn.create(longName, shortName, value)
    else:
        attr = attrFn.create(longName, shortName, type, defaultValue=value)

    if min_:
        attrFn.setMin(min_)
    if max_:
        attrFn.setMax(max_)
    if softMin:
        attrFn.setSoftMin(softMin)
    if softMax:
        attrFn.setSoftMax(softMax)

    setProperties(attr, **kwargs)

    return attr


def createEnumAttribute(fields, shortName=None, longName=None, default=None, **kwargs):
    """Create a dynamic enum attribute based on a mapping of field names to integer values.

    Args:
        fields (:class:`dict` [ :class:`basestring`, :class:`int` ]): Mapping of field names to unique values.
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        default (:class:`basestring`, optional): Default field, must correspond to a key in the ``fields`` mapping.
            If :data:`None`, the field with the smallest value will be used. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
        :exc:`~exceptions.ValueError`: If the ``fields`` mapping is empty or the set of values contained within the ``fields`` mapping is not unique.
        :exc:`~exceptions.KeyError`: If the ``default`` field does not exist within the ``fields`` mapping.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    if not fields:
        raise ValueError("Received null fields mapping")
    if len(fields) != len(set(fields.values())):
        raise ValueError("Fields mapping does not contain unique values")

    defaultValue = min(fields.values()) if default is None else fields[default]
    shortName, longName = validateNames(shortName, longName)
    attrFn = om2.MFnEnumAttribute()

    attr = attrFn.create(longName, shortName, defaultValue=defaultValue)
    for name, value in fields.items():
        attrFn.addField(name, value)

    setProperties(attr, **kwargs)

    return attr


def createMessageAttribute(shortName=None, longName=None, **kwargs):
    """Create a dynamic message attribute.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)
    attrFn = om2.MFnMessageAttribute()
    attr = attrFn.create(longName, shortName)

    setProperties(attr, **kwargs)

    return attr


def createTypedAttribute(shortName=None, longName=None, dataType=om2.MFnData.kString, value=None, **kwargs):
    """Create a dynamic typed attribute based on a data type constant from :class:`OpenMaya.MFnData`.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnData` representing the default data type.
            Supported constants are: :attr:`~OpenMaya.MFnData.kComponentList`, :attr:`~OpenMaya.MFnData.kDoubleArray`, :attr:`~OpenMaya.MFnData.kIntArray`,
            :attr:`~OpenMaya.MFnData.kMatrix`, :attr:`~OpenMaya.MFnData.kMesh`, :attr:`~OpenMaya.MFnData.kNurbsCurve`, :attr:`~OpenMaya.MFnData.kNurbsSurface`,
            :attr:`~OpenMaya.MFnData.kPlugin`, :attr:`~OpenMaya.MFnData.kPointArray`, :attr:`~OpenMaya.MFnData.kString`, :attr:`~OpenMaya.MFnData.kStringArray`,
            :attr:`~OpenMaya.MFnData.kVectorArray`. Defaults to :attr:`~OpenMaya.MFnData.kString`.
        value (any, optional): Default value for the attribute. The following values are compatible with each ``dataType`` constant:

            - :attr:`~OpenMaya.MFnData.kComponentList`: An :class:`OpenMaya.MObject` referencing derived :attr:`OpenMaya.MFn.kComponent` type data.
            - :attr:`~OpenMaya.MFnData.kMatrix`: An :class:`OpenMaya.MMatrix` or :class:`OpenMaya.MTransformationMatrix`.
            - :attr:`~OpenMaya.MFnData.kDoubleArray`, :attr:`~OpenMaya.MFnData.kIntArray`: An iterable of numeric data.
            - :attr:`~OpenMaya.MFnData.kVectorArray`: An iterable of :class:`OpenMaya.MVector` data.
            - :attr:`~OpenMaya.MFnData.kPointArray`: An iterable of :class:`OpenMaya.MPoint` data.
            - :attr:`~OpenMaya.MFnData.kStringArray`: An iterable of :class:`basestring` or :mod:`json` serializable data.
            - :attr:`~OpenMaya.MFnData.kString`: A :class:`basestring` or :mod:`json` serializable data.
            - :attr:`~OpenMaya.MFnData.kPlugin`: An :class:`OpenMaya.MTypeId` specifying a user defined data type.
            - :attr:`~OpenMaya.MFnData.kMesh`, :attr:`~OpenMaya.MFnData.kNurbsCurve`, :attr:`~OpenMaya.MFnData.kNurbsSurface`: :data:`None`.

            Defaults to :data:`None`.

        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
        :exc:`~exceptions.ValueError`: If the ``dataType`` is unsupported (eg. :attr:`~OpenMaya.MFnData.kNumeric`, :attr:`~OpenMaya.MFnData.kFloatArray`, etc).
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the ``dataType`` is :attr:`~OpenMaya.MFnData.kComponentList` and the :class:`OpenMaya.MObject` ``value`` does not reference component data.
        :exc:`~exceptions.TypeError`: If the ``value`` type is incompatible with the ``dataType``.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)

    # kNumeric and kPluginGeometry have function sets which cannot be used to created typed attributes
    if dataType == om2.MFnData.kNumeric:
        raise ValueError("`OpenMaya.MFnData.kNumeric` data type is not supported. If encapsulation of numeric data is required use `OpenMaya.MFnData.kIntArray` or `OpenMaya.MFnData.kDoubleArray`")
    elif dataType == om2.MFnData.kPluginGeometry:
        raise ValueError("`OpenMaya.MFnData.kPluginGeometry` data type is not supported. If support for shape data is required use `OpenMaya.MFnData.kMesh`, `OpenMaya.MFnData.kNurbsCurve` or `OpenMaya.MFnData.kNurbsSurface`")

    try:
        dataFn = CONST.DATA_CONSTANT_CLASS_MAPPING[dataType]()
    except KeyError:
        raise ValueError("`OpenMaya.MFnData.{}` data type is not supported".format(CONST.CONSTANT_NAME_MAPPING[dataType]))

    # If the attribute is intended to store kString data, check if the value needs to be serialized
    if dataType == om2.MFnData.kString:
        if not isinstance(value, basestring):
            value = json.dumps(value)
    elif dataType == om2.MFnData.kStringArray:
        value = value[:]
        for index, x in enumerate(value):
            if not isinstance(x, basestring):
                value[index] = json.dumps(x)

    # Wrap the data
    if value is not None:
        if dataType == om2.MFnData.kComponentList:
            if isinstance(value, om2.MObject):
                OM.validateComponentType(value)
                dataWrapper = dataFn.create()
                dataFn.add(value)
            else:
                raise TypeError("{} expected".format(om2.MObject))
        else:
            dataWrapper = dataFn.create(value)
    else:
        dataWrapper = dataFn.create()

    attrFn = om2.MFnTypedAttribute()
    attr = attrFn.create(longName, shortName, dataType, defaultValue=dataWrapper)

    setProperties(attr, **kwargs)

    return attr


def createMatrixAttribute(shortName=None, longName=None, dataType=om2.MFnMatrixAttribute.kDouble, matrix=None, **kwargs):
    """Create a dynamic matrix attribute based on a data type constant from :class:`OpenMaya.MFnMatrixAttribute`.

    Args:
        shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
        longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
        dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnMatrixAttribute` representing the default data type.
            Either single precision (:attr:`~OpenMaya.MFnMatrixAttribute.kFloat`) or double precision (:attr:`~OpenMaya.MFnMatrixAttribute.kDouble`).
            Defaults to :attr:`~OpenMaya.MFnMatrixAttribute.kDouble`.
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`, optional): Default value for the attribute.
            If :data:`None`, an identity matrix of the given ``dataType`` will be used. Defaults to :data:`None`.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the attribute object.
    """
    shortName, longName = validateNames(shortName, longName)
    attrFn = om2.MFnMatrixAttribute()

    attr = attrFn.create(longName, shortName, dataType)
    if matrix:
        attrFn.default = matrix

    setProperties(attr, **kwargs)

    return attr


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def iterChildren(attribute, recurse=False):
    """Yield the children of a compound attribute.

    Args:
        attribute (:class:`OpenMaya.MObject`): Wrapper of a compound attribute object.
        recurse (:class:`bool`, optional): Whether to search recursively for child attributes if child compound attributes exist. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference a compound attribute.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the child attributes.
    """
    OM.validateAttributeType(attribute, attributeType=om2.MFn.kCompoundAttribute)

    attrType = attribute.apiType()

    if attrType == om2.MFn.kCompoundAttribute:
        attrFn = om2.MFnCompoundAttribute(attribute)
        numChildren = attrFn.numChildren()
    else:
        attrFn = om2.MFnNumericAttribute(attribute)
        attrDataType = attrFn.numericType()
        numChildren = CONST.NUMERIC_DATA_CONSTANT_SIZE_MAPPING[attrDataType]

    for index in xrange(numChildren):
        childAttr = attrFn.child(index)
        yield childAttr

        if recurse:
            try:
                for grandchildAttr in iterChildren(childAttr):
                    yield grandchildAttr
            except EXC.MayaTypeError:
                pass


# --------------------------------------------------------------
# --- Set ---
# --------------------------------------------------------------

def setProperties(attribute, **kwargs):
    """Set properties corresponding to any writable property on :class:`OpenMaya.MFnAttribute` for any attribute. Changes are placed on the undo queue.

    Note:
        See :ref:`modifying <modifying>` attributes as well as :ref:`note-3 <note_3>`.

    Args:
        attribute (:class:`OpenMaya.MObject`): Wrapper of an attribute object.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            See default values :ref:`above <properties>`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference an attribute.

    Examples:
        .. code-block:: python

            # Set `attribute` keyable and unreadable
            setProperties(attribute, keyable=True, readable=False)
    """
    _PropertyModifier(attribute, **kwargs)


# --------------------------------------------------------------
# --- Rename ---
# --------------------------------------------------------------

def renameOnNode(node, attribute, newShortName=None, newLongName=None):
    """Rename a dynamic attribute on a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        attribute (:class:`OpenMaya.MObject`): Wrapper of a dynamic attribute that exists on ``node`` and corresponds to an unlocked plug.
        newShortName (:class:`basestring`): New short name for ``attribute``. Must not clash with an existing attribute on ``node``.
            ``newLongName`` used if :data:`None`. Defaults to :data:`None`.
        newLongName (:class:`basestring`): New long name for ``attribute``. Must not clash with an existing attribute on ``node``.
            ``newShortName`` used if :data:`None`. Defaults to :data:`None`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference an attribute.
        :exc:`~exceptions.ValueError`: If both ``newShortName`` and ``newLongName`` are :data:`None`.
        :exc:`~exceptions.ValueError`: If either of the ``newShortName`` or ``newLongName`` already exists on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attribute`` does not exist on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` references a static attribute.
        :exc:`~exceptions.RuntimeError`: If the plug corresponding to ``attribute`` is locked.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
    """
    OM.validateNodeType(node)
    OM.validateAttributeType(attribute)
    newShortName, newLongName = validateNames(shortName=newShortName, longName=newLongName)

    nodeFn = om2.MFnDependencyNode(node)
    attrFn = om2.MFnAttribute(attribute)

    # MDGModifier allows you to use a name that already exists, this behaviour is undefined
    if nodeFn.hasAttribute(newShortName):
        raise ValueError("{}.{}: Attribute already exists".format(NAME.getNodeFullName(node), newShortName))
    if nodeFn.hasAttribute(newLongName):
        raise ValueError("{}.{}: Attribute already exists".format(NAME.getNodeFullName(node), newLongName))

    if not nodeFn.hasAttribute(attrFn.name):
        raise EXC.MayaLookupError("{}.{}: Attribute does not exist".format(NAME.getNodeFullName(node), attrFn.name))
    if nodeFn.attribute(attrFn.name) != attribute:
        raise EXC.MayaLookupError("{}.{}: Attribute exists but wrapper references a different internal object".format(NAME.getNodeFullName(node), attrFn.name))

    if not attrFn.dynamic:
        raise EXC.MayaTypeError("Cannot rename static attribute: {}.{}".format(NAME.getNodeFullName(node), attrFn.name))

    # MDGModifier allows you to rename a locked plug, we check for consistency with other operations
    if om2.MPlug(node, attribute).isLocked:
        raise RuntimeError("Cannot rename attribute with locked plug: {}".format(NAME.getPlugFullName(om2.MPlug(node, attribute))))

    if nodeFn.isLocked:
        raise RuntimeError("Cannot rename attribute for locked dependency node: {}".format(NAME.getNodeFullName(node)))

    dgMod = OM.MDGModifier()
    dgMod.renameAttribute(node, attribute, newShortName, newLongName)
    dgMod.doIt()


def renameOnNodeByName(node, attributeName, newShortName=None, newLongName=None):
    """Rename a dynamic attribute on a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        attributeName (:class:`basestring`): Name of a dynamic attribute that exists on ``node`` and corresponds to an unlocked plug.
        newShortName (:class:`basestring`): New short name for the attribute corresponding to ``attributeName``. Must not clash with an existing attribute on ``node``.
            ``newLongName`` used if :data:`None`. Defaults to :data:`None`.
        newLongName (:class:`basestring`): New long name for the attribute corresponding to ``attributeName``. Must not clash with an existing attribute on ``node``.
            ``newShortName`` used if :data:`None`. Defaults to :data:`None`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`~exceptions.ValueError`: If both ``newShortName`` and ``newLongName`` are :data:`None`.
        :exc:`~exceptions.ValueError`: If either of the ``newShortName`` or ``newLongName`` already exists on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attributeName`` does not exist on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attributeName`` references a static attribute.
        :exc:`~exceptions.RuntimeError`: If the plug corresponding to ``attributeName`` is locked.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
    """
    OM.validateNodeType(node)
    newShortName, newLongName = validateNames(shortName=newShortName, longName=newLongName)

    # MDGModifier allows you to use a name that already exists, this behaviour is undefined
    nodeFn = om2.MFnDependencyNode(node)
    if nodeFn.hasAttribute(newShortName):
        raise ValueError("{}.{}: Attribute already exists".format(NAME.getNodeFullName(node), newShortName))
    if nodeFn.hasAttribute(newLongName):
        raise ValueError("{}.{}: Attribute already exists".format(NAME.getNodeFullName(node), newLongName))

    attr = om2.MFnDependencyNode(node).attribute(attributeName)
    if attr.isNull():
        raise EXC.MayaLookupError("{}.{}: Attribute does not exist".format(NAME.getNodeFullName(node), attributeName))

    attrFn = om2.MFnAttribute(attr)
    if not attrFn.dynamic:
        raise EXC.MayaTypeError("Cannot rename static attribute: {}.{}".format(NAME.getNodeFullName(node), attributeName))

    # MDGModifier allows you to rename a locked plug, we check for consistency with other operations
    if om2.MPlug(node, attr).isLocked:
        raise RuntimeError("Cannot rename attribute with locked plug: {}".format(NAME.getPlugFullName(om2.MPlug(node, attr))))

    if nodeFn.isLocked:
        raise RuntimeError("Cannot rename attribute for locked dependency node: {}".format(NAME.getNodeFullName(node)))

    dgMod = OM.MDGModifier()
    dgMod.renameAttribute(node, attr, newShortName, newLongName)
    dgMod.doIt()


# --------------------------------------------------------------
# --- Add ---
# --------------------------------------------------------------

def addToCompound(compoundAttribute, attribute):
    """Add a dynamic attribute to a dynamic compound attribute.

    Note:
        Dynamic attributes should be married to a single dependency node.
        Callers are responsible for ensuring ``attribute`` and ``compoundAttribute`` have not already been added to a dependency node.
        Failing to do so may produce undefined behaviour.

    Warning:
        This operation is not undoable.

    Args:
        compoundAttribute (:class:`OpenMaya.MObject`): Wrapper of a dynamic compound attribute.
        attribute (:class:`OpenMaya.MObject`): Wrapper of a dynamic attribute.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundAttribute`` does not reference a compound attribute.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` does not reference an attribute.
        :exc:`~exceptions.RuntimeError`: If ``compoundAttribute`` already has a child attribute with the same short name or long name as ``attribute``.
    """
    OM.validateAttributeType(compoundAttribute, attributeType=om2.MFn.kCompoundAttribute)
    OM.validateAttributeType(attribute)

    attrFn = om2.MFnCompoundAttribute(compoundAttribute)
    attrFn.addChild(attribute)


def addToNode(node, attribute):
    """Add a dynamic attribute to a dependency node.

    Note:
        Dynamic attributes should be married to a single dependency node.
        Callers are responsible for ensuring ``attribute`` has not already been added to a dependency node.
        Failing to do so may produce undefined behaviour.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        attribute (:class:`OpenMaya.MObject`): Wrapper of a dynamic attribute. The short and long names must not clash with an existing attribute on ``node``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference an attribute.
        :exc:`~exceptions.RuntimeError`: If ``node`` already has an attribute with the same short name or long name as ``attribute``.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
    """
    OM.validateNodeType(node)
    OM.validateAttributeType(attribute)

    nodeFn = om2.MFnDependencyNode(node)
    if nodeFn.isLocked:
        raise RuntimeError("Cannot add attribute to locked dependency node: {}".format(NAME.getNodeFullName(node)))

    dgMod = OM.MDGModifier()
    dgMod.addAttribute(node, attribute)
    dgMod.doIt()


# --------------------------------------------------------------
# --- Delete ---
# --------------------------------------------------------------

def removeFromNode(node, attribute):
    """Remove a dynamic, non-child attribute from a dependency node.

    Note:
        This function safely handles the issue described by :ref:`warning-1 <warning_1>`.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        attribute (:class:`OpenMaya.MObject`): Wrapper of a dynamic, non-child attribute that exists on ``node``.
            Must correspond to an unlocked plug which has no locked and connected descendant plugs.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attribute`` does not exist on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference an attribute.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` references a static attribute.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` references a child attribute.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
        :exc:`~exceptions.RuntimeError`: If the plug corresponding to ``attribute`` is locked or has a locked and connected descendant plug.
    """
    OM.validateNodeType(node)
    OM.validateAttributeType(attribute)

    nodeFn = om2.MFnDependencyNode(node)
    attrFn = om2.MFnAttribute(attribute)

    if not nodeFn.hasAttribute(attrFn.name):
        raise EXC.MayaLookupError("{}.{}: Attribute does not exist".format(NAME.getNodeFullName(node), attrFn.name))
    if nodeFn.attribute(attrFn.name) != attribute:
        raise EXC.MayaLookupError("{}.{}: Attribute exists but wrapper references a different internal object".format(NAME.getNodeFullName(node), attrFn.name))

    if not attrFn.dynamic:
        raise EXC.MayaTypeError("Cannot delete static attribute: {}.{}".format(NAME.getNodeFullName(node), attrFn.name))
    if not attrFn.parent.isNull():
        raise EXC.MayaTypeError("Cannot delete child attribute: {}.{}".format(NAME.getNodeFullName(node), attrFn.name))

    if nodeFn.isLocked:
        raise RuntimeError("Cannot delete attribute from locked dependency node: {}".format(NAME.getNodeFullName(node)))

    # Since we have checked the attribute has no parent, we can guarantee the plug will not have placeholder indices and its lock state will not be affected by ancestors
    plug = om2.MPlug(node, attribute)

    # Must always check root plugs in case the attribute is an array (causes Maya to crash)
    # Maya should always produce its own errors if a descendant is locked and connected
    if plug.isLocked:
        raise RuntimeError("Cannot delete attribute with locked plug : {}".format(NAME.getPlugFullName(plug)))

    dgMod = OM.MDGModifier()
    dgMod.removeAttribute(node, attribute)
    dgMod.doIt()


def removeFromNodeByName(node, attributeName):
    """Remove a dynamic, non-child attribute from a dependency node.

    Note:
        This function safely handles the issue described by :ref:`warning-1 <warning_1>`.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of an unlocked dependency node.
        attributeName (:class:`basestring`): Name of a dynamic, non-child attribute that exists on ``node``.
            Must correspond to an unlocked plug which has no locked and connected descendant plugs.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attributeName`` does not exist on ``node``.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attributeName`` references a static attribute.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attributeName`` references a child attribute.
        :exc:`~exceptions.RuntimeError`: If ``node`` is locked.
        :exc:`~exceptions.RuntimeError`: If the plug corresponding to ``attributeName`` is locked or has a locked and connected descendant plug.
    """
    OM.validateNodeType(node)

    attr = om2.MFnDependencyNode(node).attribute(attributeName)
    if attr.isNull():
        raise EXC.MayaLookupError("{}.{}: Attribute does not exist".format(NAME.getNodeFullName(node), attributeName))

    attrFn = om2.MFnAttribute(attr)
    if not attrFn.dynamic:
        raise EXC.MayaTypeError("Cannot delete static attribute: {}.{}".format(NAME.getNodeFullName(node), attributeName))
    if not attrFn.parent.isNull():
        raise EXC.MayaTypeError("Cannot delete child attribute: {}.{}".format(NAME.getNodeFullName(node), attributeName))

    nodeFn = om2.MFnDependencyNode(node)
    if nodeFn.isLocked:
        raise RuntimeError("Cannot delete attribute from locked dependency node: {}".format(NAME.getNodeFullName(node)))

    # Since we have checked the attribute has no parent, we can guarantee the plug will not have placeholder indices and its lock state will not be affected by ancestors
    plug = om2.MPlug(node, attr)

    # Must always check root plugs in case the attribute is an array (causes Maya to crash)
    # Maya should always produce its own errors if a descendant is locked and connected
    if plug.isLocked:
        raise RuntimeError("Cannot delete attribute with locked plug : {}".format(NAME.getPlugFullName(plug)))

    dgMod = OM.MDGModifier()
    dgMod.removeAttribute(node, attr)
    dgMod.doIt()
