"""
Context managers relating to the `Qt`_ API.

----------------------------------------------------------------

Usage
-----

    Context managers are used to encapsulate a code block in a specific context.
    They allow for a temporary state to exist while code is being executed and are initialised as follows::

        with Context(args):
            completeActionsWithinContext()

----------------------------------------------------------------
"""


# ----------------------------------------------------------------------------
# --- Context Managers ---
# ----------------------------------------------------------------------------

class BlockObjectSignals(object):
    """Context manager for temporarily blocking signals emitted by an object (ie. an emitted signal will not invoke anything connected to it).

    Blocking is completed via :meth:`PySide2.QtCore.QObject.blockSignals`.
    """

    def __init__(self, obj):
        """Initialise the context.

        Args:
            obj (T <= :class:`PySide2.QtCore.QObject`): The object for which to block signals.
        """
        self._obj = obj

    def __enter__(self):
        self._obj.blockSignals(True)

    def __exit__(self, *_):
        self._obj.blockSignals(False)


class DisableWidget(object):
    """Context manager for temporarily disabling a widget.

    Disabling is completed via :meth:`PySide2.QtWidgets.QWidget.setEnabled`.

    A disabled widget:

    - Does not handle keyboard and mouse events.
    - May render differently (eg. greyed out).
    - Implicitly disables all of its children.
    """

    def __init__(self, widget):
        """Initialise the context.

        Args:
            widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to disable.
        """
        self._widget = widget

    def __enter__(self):
        self._widget.setEnabled(False)

    def __exit__(self, *_):
        self._widget.setEnabled(True)


class DisableWidgetUpdates(object):
    """Context manager for temporarily disabling updates for a widget.

    Disabling is completed via :meth:`PySide2.QtWidgets.QWidget.setUpdatesEnabled`.

    An updates disabled widget:

    - Does not receive paint events.
    - Implicitly disables updates to all of its children.

    Upon exiting the context, a call to :meth:`PySide2.QtWidgets.QWidget.update` will be made for the widget.
    """

    def __init__(self, widget):
        """Initialise the context.

        Args:
            widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget for which to disable updates.
        """
        self._widget = widget

    def __enter__(self):
        self._widget.setUpdatesEnabled(False)

    def __exit__(self, *_):
        self._widget.setUpdatesEnabled(True)


class DisconnectSignalFromReceiver(object):
    """Context manager for temporarily disconnecting a signal from a receiver."""

    def __init__(self, signal, receiver):
        """Initialise the context.

        Args:
            signal (:class:`PySide2.QtCore.Signal`): The emitter of a connection to ``receiver``.
            receiver (callable [..., any] | :class:`PySide2.QtCore.Signal` | :class:`PySide2.QtCore.Slot`): The receiver of a connection from ``signal``.
        """
        self._signal = signal
        self._receiver = receiver

    def __enter__(self):
        self._signal.disconnect(self._receiver)

    def __exit__(self, *_):
        self._signal.connect(self._receiver)
