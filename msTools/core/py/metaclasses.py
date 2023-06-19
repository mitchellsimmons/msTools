"""
Developer module containing custom metaclasses.

----------------------------------------------------------------
"""

import abc
import itertools
import types

from msTools.vendor import decorator


class AbstractAccessWrapper(object):
    """Abstract baseclass that provides an interface for ``MetaAccessWrapper`` metaclasses that are produced by the :func:`MetaAccessWrapperFactory`.

    The interface is composed of two abstract methods:

    - :meth:`_preAccess`: Invoked by the ``MetaAccessWrapper`` before an initial subclass instance method is placed on the call stack.
    - :meth:`_postAccess`: Invoked by the ``MetaAccessWrapper`` after the initial subclass instance method is removed from the call stack.

    The specific functionality of the interface must be defined within the subclass overrides of the abstract methods.

    One intended use case for this interface is to track the state of a data oject referenced by a subclass instance.
    The :meth:`_preAccess` method could be implemented to check the validity of the data object in order to regulate access to the instance.

    Example:
        .. code-block:: python

            class AccessWrapper(AbstractAccessWrapper):
                \"""Safely encapsulate an object that is not guaranteed to remain valid.\"""

                __metaclass__ = MetaAccessWrapperFactory(
                    wrapFunctions=True,
                    wrapPropertyGetters=True,
                    wrapPropertySetters=True,
                    wrapPropertyDeleters=True,
                    wrapExclusions=("__init__", "_validate", "isValid")
                )

                def _preAccess(self):
                    self._validate()

                def _postAccess(self):
                    pass

                def __init__(self, obj):
                    self._obj = obj

                def _validate(self):
                    if not self.isValid():
                        raise RuntimeError("Encapsulation is invalid, access is denied")

                def isValid(self):
                    return self._obj.isValid()

                @property
                def obj(self):
                    return self._obj
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _preAccess(self):
        """Invoked by the ``MetaAccessWrapper`` before an initial subclass instance method is placed on the call stack.

        Note:
            Abstract method - must be overriden by each subclass.
        """
        pass

    @abc.abstractmethod
    def _postAccess(self):
        """Invoked by the ``MetaAccessWrapper`` after the initial subclass instance method is removed from the call stack.

        Note:
            Abstract method - must be overriden by each subclass.
        """
        pass


class _MetaAccessWrapper(abc.ABCMeta):

    # State variable used by the metaclass wrapper to track the calling stack of each instance
    # An alternative approach could be to bind a state tracking variable to each instance from the metaclass __call__ method
    __accessRegistry = set()

    def __new__(metaCls, clsName, bases, namespace):
        if AbstractAccessWrapper not in itertools.chain(*[base.__mro__ for base in bases]):
            raise TypeError("{}: metaclass is designed for {} subclasses".format(metaCls, AbstractAccessWrapper))

        # By default _preAccess, _postAccess and __getattribute__ are excluded to prevent recursive invocations
        # We must also exclude the static __new__ method since it appears as a function before being decorated by the base metaclass constructor (ie. type.__new__ has not been called yet)
        wrapExclusions = list(itertools.chain(AbstractAccessWrapper.__abstractmethods__, metaCls._wrapExclusions)) + ["_preAccess", "_postAccess", "__getattribute__", "__new__"]
        wrapProperties = any([metaCls._wrapPropertyGetters, metaCls._wrapPropertySetters, metaCls._wrapPropertyDeleters])

        for attrName, attrValue in namespace.items():
            if metaCls._wrapFunctions and isinstance(attrValue, types.FunctionType) and attrName not in wrapExclusions:
                namespace[attrName] = metaCls._classFunctionWrapperFactory()(attrValue)
            elif wrapProperties and isinstance(attrValue, property) and attrName not in wrapExclusions:
                fget = metaCls._classFunctionWrapperFactory()(attrValue.fget) if attrValue.fget is not None and metaCls._wrapPropertyGetters else attrValue.fget
                fset = metaCls._classFunctionWrapperFactory()(attrValue.fset) if attrValue.fset is not None and metaCls._wrapPropertySetters else attrValue.fset
                fdel = metaCls._classFunctionWrapperFactory()(attrValue.fdel) if attrValue.fdel is not None and metaCls._wrapPropertyDeleters else attrValue.fdel
                namespace[attrName] = property(fget=fget, fset=fset, fdel=fdel)

        return super(_MetaAccessWrapper, metaCls).__new__(metaCls, clsName, bases, namespace)

    # The decorator package wont work with classmethods, instead we implement a decorator factory
    @classmethod
    def _classFunctionWrapperFactory(metaCls):
        """Decorator factory for producing decorators which will retain the function signature of their wrapped function."""
        def classFunctionWrapper(func, *args, **kwargs):
            """Decorator for wrapping class functions in a pre and post access interface."""
            obj = args[0]
            objId = id(obj)
            isOuterScope = False

            if objId not in metaCls.__accessRegistry:
                obj._preAccess()
                isOuterScope = True
                metaCls.__accessRegistry.add(objId)

            try:
                return func(*args, **kwargs)
            finally:
                if isOuterScope:
                    metaCls.__accessRegistry.remove(objId)
                    obj._postAccess()

        return decorator.decorator(classFunctionWrapper)


def MetaAccessWrapperFactory(wrapFunctions=True, wrapPropertyGetters=True, wrapPropertySetters=True, wrapPropertyDeleters=True, wrapExclusions=None):
    """Metaclass factory for generating ``MetaAccessWrapper`` metaclasses that are designed to take control of the :class:`AbstractAccessWrapper` interface.

    Generated metaclasses are responsible for wrapping :class:`AbstractAccessWrapper` subclass functions in a decorator that will be bound to instances of the subclass.
    The bound decorators are responsible for managing the invocation of the abstract method overrides for the :class:`AbstractAccessWrapper` subclass.

    Note:
        In order to prevent recursive invocation of instance methods,
        subclass :meth:`~AbstractAccessWrapper._preAccess`, :meth:`~AbstractAccessWrapper._postAccess` and ``__getattribute__`` methods are excluded from the metaclass decorator by default.

        If the :meth:`~AbstractAccessWrapper._preAccess` method requires an initialised instance, it is necessary for the user to exclude ``__init__`` via the ``wrapExclusions``.

    Args:
        wrapFunctions (:class:`bool`, optional): Whether the generated metaclass should be used to wrap standard class functions in the :class:`AbstractAccessWrapper` interface. Defaults to :data:`True`.
        wrapPropertyGetters (:class:`bool`, optional): Whether the generated metaclass should be used to wrap property descriptor getter functions in the :class:`AbstractAccessWrapper` interface. Defaults to :data:`True`.
        wrapPropertySetters (:class:`bool`, optional): Whether the generated metaclass should be used to wrap property descriptor setter functions in the :class:`AbstractAccessWrapper` interface. Defaults to :data:`True`.
        wrapPropertyDeleters (:class:`bool`, optional): Whether the generated metaclass should be used to wrap property descriptor deleter functions in the :class:`AbstractAccessWrapper` interface. Defaults to :data:`True`.
        wrapExclusions (iterable [:class:`basestring`], optional): Names of functions the generated metaclass should exclude from the :class:`AbstractAccessWrapper` interface. Defaults to :data:`None`.

    Returns:
        :class:`type`: ``MetaAccessWrapper`` metaclass designed for use by :class:`AbstractAccessWrapper` subclasses.
    """
    return type('MetaAccessWrapper', (_MetaAccessWrapper,), {
        '_wrapFunctions': wrapFunctions,
        '_wrapPropertyGetters': wrapPropertyGetters,
        '_wrapPropertySetters': wrapPropertySetters,
        '_wrapPropertyDeleters': wrapPropertyDeleters,
        '_wrapExclusions': wrapExclusions or (),
    })
