"""
General purpose utility functions relating to classes.

----------------------------------------------------------------
"""


def iterSubclasses(cls, strict=True, _seen=None):
    """iterSubclasses(cls)

    Yield subclasses of a given class in depth first order.

    Args:
        cls (:class:`type`): A new-style class.
        strict (:class:`bool`): Whether to generate strict or non-strict subclasses of ``cls``.
            If :data:`False`, ``cls`` itself will be generated.

    Yields:
        :class:`type`: Subclasses of ``cls``, generated in in depth first order.
    """
    if _seen is None:
        _seen = set()

        if not strict:
            _seen.add(cls)
            yield cls

    try:
        subs = cls.__subclasses__()
    except TypeError:  # fails only when cls is type
        subs = cls.__subclasses__(cls)

    for subclass in subs:
        _seen.add(subclass)
        yield subclass

        for subclass in iterSubclasses(subclass, _seen):
            yield subclass
