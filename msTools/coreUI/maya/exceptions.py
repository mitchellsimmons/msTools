"""
General exception classes relating to the Maya user interface.

----------------------------------------------------------------
"""


class MayaUILookupError(RuntimeError):
    """Raised when trying to access a Maya UI element that does not exist."""


class MayaUIObjectError(RuntimeError):
    """Raised when a Maya UI element reference becomes invalid."""


class MayaUITypeError(RuntimeError, TypeError):
    """Raised when a UI element is referenced using a valid class type but is incompatible due to its internal type."""
