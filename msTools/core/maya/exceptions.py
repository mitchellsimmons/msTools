"""
General exception classes designed to provide specificity to errors produced by the `OpenMaya`_ API.

----------------------------------------------------------------
"""


class MayaLookupError(RuntimeError):
    """Raised when trying to access a Maya object that does not exist or is not unique.

    Inherits :exc:`~exceptions.RuntimeError` to encompass the default behaviour of :meth:`OpenMaya.MSelectionList.add` for object lookups.

    Examples:
        - Raise if attempting to access an :class:`OpenMaya.MPlug` for a dependency node plug that does not exist.
        - Raise if attempting to access an :class:`OpenMaya.MObject` for a dependency node that does not exist.
        - Raise if attempting to access an :class:`OpenMaya.MObject` for a dependency node using a UUID that is not unique.
    """


class MayaObjectError(RuntimeError):
    """Raised when a Maya object reference becomes invalid.

    Examples:
        - Raise if an :class:`OpenMaya.MPlug` references a dependency node plug which has been removed.
        - Raise if an :class:`OpenMaya.MObject` references a dependency node which has been deleted.
    """


class MayaTypeError(TypeError, RuntimeError):
    """Raised when a Maya object is referenced using a valid class type but is incompatible due to its internal type.

    Inherits :exc:`~exceptions.TypeError` to encompass the default behaviour of :class:`OpenMaya.MPlug` when a plug operation is incompatible with the internal plug type.

    Inherits :exc:`~exceptions.RuntimeError` to encompass the default behaviour of operating on an :class:`OpenMaya.MObject` which has an incompatible internal object type.

    Note:
        This error should only be raised for exceptional behaviour relating to Maya objects whose internal type is defined statically.
        Any exceptional behaviour relating to dynamic Maya object properties should produce a :exc:`~exceptions.RuntimeError`.

    Examples:
        - Raise if an :class:`OpenMaya.MPlug` is expected to reference a certain type of dependency node plug such as an array.
        - Raise if an :class:`OpenMaya.MObject` is expected to reference a certain type of dependency node such as a transform.
    """
