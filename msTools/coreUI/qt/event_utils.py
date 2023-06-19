"""
Utility functions relating to `Qt`_ events.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore


# ----------------------------------------------------------------------------
# --- Event Priorities ---
# ----------------------------------------------------------------------------

class EventPriority(object):
    """A namespace for custom `Qt`_ event priority constants."""

    IDLE = QtCore.Qt.LowEventPriority - 1
    """:class:`int`: Less important than status events. Executes after idle events have processed.

    :access: R
    """

    LOW = int(QtCore.Qt.LowEventPriority)
    """:class:`int`: A status event.

    :access: R
    """

    NORMAL = int(QtCore.Qt.NormalEventPriority)
    """:class:`int`: A normal event.

    :access: R
    """

    IMPORTANT = int(QtCore.Qt.HighEventPriority)
    """:class:`int`: An important event.

    :access: R
    """

    VERY_IMPORTANT = IMPORTANT + 1
    """:class:`int`: A more important event.

    :access: R
    """

    CRITICAL = 100 * VERY_IMPORTANT
    """:class:`int`: A critical event.

    :access: R
    """


# ----------------------------------------------------------------------------
# --- Events ---
# ----------------------------------------------------------------------------

class _Event(QtCore.QEvent):
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self, func, *args, **kwargs):
        QtCore.QEvent.__init__(self, _Event.EVENT_TYPE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class _EventInvoker(QtCore.QObject):
    def event(self, event):
        # cmds.evalDeferred(functools.partial(event.func, *event.args, **event.kwargs))
        event.func(*event.args, **event.kwargs)
        return True


_invoker = _EventInvoker()


def postAsEvent(callable_, *args, **kwargs):
    """Post a callable on the `Qt`_ event queue via :meth:`PySide2.QtCore.QCoreApplication.postEvent`.

    Args:
        callable_ (callable [[\\*args, \\**kwargs], any]): The callable to post. Must be compatible with ``*args`` and ``**kwargs``.
        *args: Sequence of positional arguments for ``callable_``.
        **kwargs: Keyword arguments for ``callable_``.

    Other Parameters:
        priority (:class:`int`, optional): The priority used to post ``callable_`` on the event queue. Defaults to :attr:`EventPriority.NORMAL`.

    Example:
        .. code-block:: python

            # Executes `foo` after idle events have processed
            postAsEvent(foo, priority=EventPriority.IDLE)
    """
    priority = kwargs.pop("priority", EventPriority.NORMAL)
    QtCore.QCoreApplication.postEvent(_invoker, _Event(callable_, *args, **kwargs), priority=priority)


# ----------------------------------------------------------------------------
# --- Event Filters ---
# ----------------------------------------------------------------------------

class SignalEventFilter(QtCore.QObject):
    """An event filter that will listen for a specific :attr:`PySide2.QtCore.QEvent.Type`, emitting a signal when it occurs."""

    eventTriggered = QtCore.Signal()

    def __init__(self, eventType, parent=None):
        """Initialize the event filter.

        Args:
            eventType (:attr:`PySide2.QtCore.QEvent.Type`): The event type to listen for.
            parent (:class:`PySide2.QtCore.QObject`, optional): Parent object for the event filter. Defaults to :data:`None`.
        """
        super(SignalEventFilter, self).__init__(parent)

        self._eventType = eventType

    @property
    def eventType(self):
        """:attr:`PySide2.QtCore.QEvent.Type`: The event type to listen for.

        :access: RW
        """
        return self._eventType

    @eventType.setter
    def eventType(self, eventType):
        self._eventType = eventType

    def eventFilter(self, watched, event):
        if event.type() == self._eventType:
            self.eventTriggered.emit()

        return super(SignalEventFilter, self).eventFilter(watched, event)
