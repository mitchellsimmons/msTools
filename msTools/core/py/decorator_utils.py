"""
General purpose decorators.

----------------------------------------------------------------
"""
from msTools.vendor import decorator


class abstractclassmethod(classmethod):
    """Decorator for wrapping a callable in a :func:`classmethod` such that it exhibits the behaviour of an :func:`abc.abstractmethod`.

    Args:
        callable_ (callable[[cls], any]): Callable to decorate.
    """

    __isabstractmethod__ = True

    def __init__(self, callable_):
        callable_.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable_)


class abstractstaticmethod(staticmethod):
    """Decorator for wrapping a callable in a :func:`staticmethod` such that it exhibits the behaviour of an :func:`abc.abstractmethod`.

    Args:
        callable_ (callable[[], any]): Callable to decorate.
    """

    __isabstractmethod__ = True

    def __init__(self, callable_):
        callable_.__isabstractmethod__ = True
        super(abstractstaticmethod, self).__init__(callable_)


def callOnError(callable_, *exceptionTypes):
    """Decorator factory for producing a decorator which will call a given callable if certain types of unhandled exceptions are raised by the decorated function.

    Args:
        callable_ (callable[[], any]): Callable to call if an unhandled exception corresponding to one of the ``exceptionTypes`` is raised by the decorated function.
        *exceptionTypes: Sequence of class types which are (non-strict) subclasses of :exc:`~exceptions.Exception`.
            Unhandled exceptions of these types will result in ``callable_`` being called before the exception is propagated further.
    """
    def caller(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except exceptionTypes:
            callable_()
            raise

    return decorator.decorator(caller)
