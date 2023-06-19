"""
Developer module containing custom data structures.

----------------------------------------------------------------
"""
import abc

from msTools.vendor import decorator


class _EqualitySetMetaClass(abc.ABCMeta):

    def __setattr__(cls, attr, value):
        """Prevents the EqualitySet.DATA_TYPE attribute from being overridden."""
        if attr == "DATA_TYPE":
            raise AttributeError("DATA_TYPE attribute is read-only")

        return super(_EqualitySetMetaClass, cls).__setattr__(attr, value)


class EqualitySet(object):
    """Abstract baseclass for compiling an ordered set of non-equivalent data, designed specifically for non-hashable types.

    Provides a templated interface to each subclass based on the abstract :attr:`DATA_TYPE` property.
    This property must be overridden in order to specify the type of accepted input data.

    Designed to mimic a :class:`set` whilst internally data is compiled through equality testing instead of a hash table.
    Expect operations to run in O(n) time compared to their :class:`set` counterparts which are likely to run in O(1) time.

    ..  Subclassing
        -----------
        The `_formatInput` and `_formatIterableInput` methods can be overridden to modify input data before it is received by the interface.
        For example it may be useful to encapsulate input data in order to modify the behaviour of the equality testing used internally.
        In case these methods are implemented the `_formatOutput` method should also be overridden to ensure outputs are converted back to the `DATA_TYPE`.
    """

    __metaclass__ = _EqualitySetMetaClass

    # --- Private : Utilities ----------------------------------------------------------------------------

    def _validateInput(iterable=False):
        """Decorator factory for generating a decorator which will validate the data type of all non-iterable and iterable input data passed to bound methods.
        The generated decorator is also responsible for formatting this input data if the subclass overrides `_formatInput` or `_formatIterableInput`.

        Args:
            iterable (:class:`bool`): Whether the generated decorator should expect iterable input data.

        Raises:
            :exc:`~exceptions.TypeError`: If the data type of any input data does not match the abstract :attr:`DATA_TYPE`.
        """
        def caller(func, *args, **kwargs):
            self = args[0]
            dataType = self.__class__.DATA_TYPE

            arg = (list(args[1:]) + kwargs.values())[0]
            if iterable:
                for obj in arg:
                    if not isinstance(obj, dataType):
                        raise TypeError("Iterable of {} instances expected".format(dataType))
            else:
                if not isinstance(arg, dataType):
                    raise TypeError("{} instance expected".format(dataType))

            arg = self._formatIterableInput(arg) if iterable else self._formatInput(arg)

            return func(self, arg)

        return decorator.decorator(caller)

    def _formatInput(self, arg):
        """Allows a subclass to format non-iterable input data before it is received by the interface."""
        return arg

    def _formatIterableInput(self, arg):
        """Allows a subclass to format iterable input data before it is received by the interface."""
        return arg

    def _formatOutput(self, arg):
        """Allows a subclass to format non-iterable output data before it is received by the caller."""
        return arg

    # --- Private : Special ----------------------------------------------------------------------------

    def __init__(self, iterable=None):
        """Initialize the set.

        Args:
            iterable (iterable [:attr:`DATA_TYPE`], optional): Initialize the set with :attr:`DATA_TYPE` objects.
        """
        self._data = []

        if iterable is not None:
            self.update(iterable)

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Returns:
            :class:`str`: A string representation of the set.
        """
        return "{}({})".format(type(self).__name__, list(iter(self)))

    def __eq__(self, other):
        """``x.__eq__(y)`` <==> ``x == y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: If ``other`` has an equivalent type, return whether its contents are equivalent.
            Otherwise swap the operands and return the result, unless the operands have already been swapped in which case the result is :data:`False`.
        """
        if type(other) is type(self):
            if len(self) == len(other):
                for obj, otherObj in zip(self._data, other._data):
                    if obj != otherObj:
                        break
                else:
                    return True

        return NotImplemented

    def __ne__(self, other):
        """``x.__ne__(y)`` <==> ``x != y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: The negation of :meth:`__eq__`.
        """
        return not self == other

    @_validateInput()
    def __contains__(self, obj):
        """``x.__contains__(y)`` <==> ``y in x``.

        Args:
            obj (any): Any object.

        Raises:
            :exc:`~exceptions.TypeError`: If the data type of ``obj`` does not match the abstract :attr:`DATA_TYPE`.

        Returns:
            :class:`bool`: :data:`True` if ``obj`` is contained by this set, otherwise :data:`False`.
        """
        return obj in self._data

    def __len__(self):
        """``x.__len__()`` <==> ``len(x)``.

        Returns:
            :class:`int`: The number of :attr:`DATA_TYPE` objects contained within the set.
        """
        return len(self._data)

    def __iter__(self):
        """``x.__iter__()`` <==> ``iter(x)``.

        Yields:
            :attr:`DATA_TYPE`: Object contained within the set.
        """
        for obj in self._data:
            yield self._formatOutput(obj)

    def __setattr__(self, attr, value):
        """``x.__setattr__(attr, value)`` <==> ``setattr(x, attr, value)``.

        Args:
            attr (:class:`basestring`): Name of an attribute binding.
            value (any): Value to set.

        Raises:
            :exc:`~exceptions.AttributeError`: If attempting to set the abstract :attr:`DATA_TYPE`.
        """
        if attr == "DATA_TYPE":
            raise AttributeError("DATA_TYPE attribute is read-only")

        return super(EqualitySet, self).__setattr__(attr, value)

    # --- Public : Interface ----------------------------------------------------------------------------

    @abc.abstractproperty
    def DATA_TYPE(self):
        """Template property which defines the accepted data type for the interface.

        Note:
            Abstract property - must be overriden by each subclass.

        :access: R
        """

    @_validateInput()
    def add(self, obj):
        """Add an object to the set.

        Args:
            obj (:attr:`DATA_TYPE`): Object of the abstract template type.

        Raises:
            :exc:`~exceptions.TypeError`: If the data type of ``obj`` does not match the abstract :attr:`DATA_TYPE`.

        Returns:
            :class:`bool`: :data:`True` if ``obj`` was added to the set, otherwise :data:`False` if an equivalent object exists in the set.
        """
        if obj not in self._data:
            self._data.append(obj)
            return True

        return False

    @_validateInput(iterable=True)
    def update(self, iterable):
        """Add objects to the set.

        Args:
            iterable (iterable [:attr:`DATA_TYPE`]): Objects of the abstract template type.

        Raises:
            :exc:`~exceptions.TypeError`: If the data type of any of the objects in ``iterable`` does not match the abstract :attr:`DATA_TYPE`.

        Returns:
            :class:`bool`: :data:`True` if all objects from ``iterable`` were added to the set,
            otherwise :data:`False` if an equivalent object exists in the set for any of the objects in ``iterable``.
        """
        count = len(self) + len(iterable)

        for obj in iterable:
            if obj not in self._data:
                self._data.append(obj)

        return len(self) == count

    @_validateInput()
    def remove(self, obj):
        """Remove an equivalent object from the set.

        Args:
            obj (:attr:`DATA_TYPE`): Object of the abstract template type.

        Raises:
            :exc:`~exceptions.ValueError`: If an object equivalent to ``obj`` does not exist in the set.
            :exc:`~exceptions.TypeError`: If the data type of ``obj`` does not match the abstract :attr:`DATA_TYPE`.
        """
        self._data.remove(obj)

    @_validateInput()
    def discard(self, obj):
        """Remove an equivalent object from the set if one exists.

        Args:
            obj (:attr:`DATA_TYPE`): Object of the abstract template type.

        Raises:
            :exc:`~exceptions.TypeError`: If the data type of ``obj`` does not match the abstract :attr:`DATA_TYPE`.

        Returns:
            :class:`bool`: :data:`True` if an object equivalent to ``obj`` was removed from the set, otherwise :data:`False`.
        """
        try:
            self.remove(obj)
            return True
        except ValueError:
            return False

    def pop(self):
        """Remove and return the last element from the set.

        Raises:
            :exc:`~exceptions.IndexError`: If the set is empty.

        Returns:
            :attr:`DATA_TYPE`: The last element in the set.
        """
        return self._formatOutput(self._data.pop())

    def clear(self):
        """Remove all elements from the set"""
        self._data = []
