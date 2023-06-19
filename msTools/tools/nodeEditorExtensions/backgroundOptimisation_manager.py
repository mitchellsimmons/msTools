"""
Manage installation of the `Background Optimisation Manager` to a Node Editor editor within the current Maya session.

The `Background Optimisation Manager` optimises the background rendering for each :class:`PySide2.QtWidgets.QGraphicsView` of a Node Editor.
Specifically it toggles background caching at a specific scaling (zoom) threshold.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Background Optimisation Managers` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCompat, QtCore, QtWidgets

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import event_utils as QT_EVENT
from msTools.coreUI.qt import widget_utils as QT_WIDGET
from msTools.tools import tool_manager


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register a `Background Optimisation Manager` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Background Optimisation Manager"
""":class:`str`: The tool name used to register a `Background Optimisation Manager` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Background Optimisation Manager` to a given Node Editor editor widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QTabWidget`): A Node Editor editor, to be used as the parent for the `Background Optimisation Manager`.
        force (:class:`bool`): Whether to reinstall the `Background Optimisation Manager` if one already exists under ``parent``.
            If :data:`False`, skip installation if a `Background Optimisation Manager` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor editor.

    Returns:
        The `Background Optimisation Manager` tool parented under ``parent``. If ``force`` is :data:`False`, this could be an existing tool.
    """
    return _BackgroundOptimisationManager(parent)


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Background Optimisation Manager`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: A `Background Optimisation Manager` tool to uninstall.
    """
    nodeEditor = QT_WIDGET.retainAndReturn(tool.parent())
    nodeEditorGraphicsViews = UI_NODE_EDITOR.getNodeEditorGraphicsViewsFromEditor(nodeEditor)

    for nodeEditorGraphicsView in nodeEditorGraphicsViews:
        nodeEditorGraphicsView.setCacheMode(QtWidgets.QGraphicsView.CacheNone)

    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

class _BackgroundOptimisationManager(QtCore.QObject):
    """Manages installation of event filters for a given Node Editor editor in order to optimise the background rendering for each `QGraphicsView`."""

    def __init__(self, parent):
        if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.EDITOR):
            raise UI_EXC.MayaUILookupError("Expected a Node Editor editor widget for the parent")

        super(_BackgroundOptimisationManager, self).__init__(parent=parent)

        self._installAddChildListener()
        self._connectOptimisersToExisting()

    def _installAddChildListener(self):
        """Installs an event filter on the Node Editor editor widget which listens for events that indicate a child has been added.
        If the child was a new tab, the `_backgroundOptimiser` slot will be connected to the new `QGraphicsView`.

        Note:
            The Node Editor replaces `QGraphicsViews` when opening a scene or creating a new scene or when a new tab is added.
        """
        # Careful not to invalidate `self`
        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())

        self._childAddedListener = QT_EVENT.SignalEventFilter(eventType=QtCore.QEvent.ChildAdded, parent=self)
        nodeEditor.installEventFilter(self._childAddedListener)

        # When Maya creates a new QGraphicsView it first parents it to the editor before reparenting it to a page once an idle state is reached
        self._childAddedListener.eventTriggered.connect(lambda: cmds.evalDeferred(self._connectOptimiserToCurrent))

    def _connectOptimisersToExisting(self):
        """Connects the `_backgroundOptimiser` slot to the `QScrollBar.rangeChanged` signal of each existing Node Editor `QGraphicsView`."""
        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())
        nodeEditorGraphicsViews = UI_NODE_EDITOR.getNodeEditorGraphicsViewsFromEditor(nodeEditor)

        # It is best to check validity for the initial installation
        for nodeEditorGraphicsView in nodeEditorGraphicsViews:
            if QtCompat.isValid(nodeEditorGraphicsView):
                self._connectOptimiser(nodeEditorGraphicsView)

    def _connectOptimiserToCurrent(self):
        """Connects the `_backgroundOptimiser` slot to the `QScrollBar.rangeChanged` signal of the current Node Editor `QGraphicsView`."""
        # Because invocation is deferred, it is possible this object has been deleted
        if not QtCompat.isValid(self):
            return

        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())
        nodeEditorGraphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        self._connectOptimiser(nodeEditorGraphicsView)

    def _connectOptimiser(self, nodeEditorGraphicsView):
        """Connects the `_backgroundOptimiser` slot to the `QScrollBar.rangeChanged` signal of the given Node Editor `QGraphicsView`."""
        try:
            nodeEditorGraphicsView.horizontalScrollBar().rangeChanged.disconnect(self._backgroundOptimiser)
        except RuntimeError:
            pass

        # Update the current cache mode
        nodeEditorGraphicsViewScale = nodeEditorGraphicsView.transform().m11()
        cacheMode = QtWidgets.QGraphicsView.CacheBackground if nodeEditorGraphicsViewScale < 1.0 else QtWidgets.QGraphicsView.CacheNone

        if not nodeEditorGraphicsView.cacheMode() & cacheMode:
            nodeEditorGraphicsView.setCacheMode(cacheMode)

        # Connect the optimiser
        nodeEditorGraphicsView.horizontalScrollBar().rangeChanged.connect(self._backgroundOptimiser)

    def _backgroundOptimiser(self, min_, max_):
        """Slot designed for the `QScrollBar.rangeChanged` signal of a Node Editor `QGraphicsView`, designed to optimise the rendering of the view's background.

        By default each Node Editor `QGraphicsView` uses the `CacheNone` mode to paint its background.
        This mode has an adverse impact on performance but prevents artifacting when zoomed in (ie. `QGraphicsView` scaling transform > 1.0).
        The `CacheBackground` mode improves performance significantly (especially when zoomed out) but produces artifacting when zoomed in.
        By dynamically changing the caching mode based on the scaling transform, we can optimise for performance when zoomed out and prevent artifacting when zoomed in.
        """
        # A signal is emitted when the Node Editor is being closed
        if min_ == 0 and max_ == 0:
            return

        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())
        nodeEditorGraphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        nodeEditorGraphicsViewScale = nodeEditorGraphicsView.transform().m11()
        cacheMode = QtWidgets.QGraphicsView.CacheBackground if nodeEditorGraphicsViewScale < 1.0 else QtWidgets.QGraphicsView.CacheNone

        if not nodeEditorGraphicsView.cacheMode() & cacheMode:
            nodeEditorGraphicsView.setCacheMode(cacheMode)
