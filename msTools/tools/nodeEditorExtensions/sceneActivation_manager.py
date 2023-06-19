"""
Manage installation of the `Scene Activation Manager` to a Node Editor editor within the current Maya session.

The `Scene Activation Manager` implements a fix for a bug which prevents a Node Editor :class:`PySide2.QtWidgets.QGraphicsScene` from becoming active.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Scene Activation Managers` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------

Activation Bug
--------------

    The following behaviour was observed in Maya 2019 (Qt version 5.6.1):

    When a scene with multiple Node Editor tabs is loaded, a :class:`PySide2.QtWidgets.QGraphicsScene` is created for each tab.
    The :class:`PySide2.QtWidgets.QGraphicsScene` of the visible (last) tab will be activated.
    Upon selecting the first tab, the associated :class:`PySide2.QtWidgets.QGraphicsScene` will not be activated.

    A :class:`PySide2.QtWidgets.QGraphicsScene` which is not activated will prevent any parented :class:`PySide2.QtWidgets.QGraphicsItem` from gaining focus.
    Certain items such as :class:`PySide2.QtWidgets.QGraphicsTextItem` rely heavily upon the correct propagation of focus events.

    This issue may have some relation to the following bug report (opened and closed for Qt version 4.6) https://bugreports.qt.io/browse/QTBUG-8188.

----------------------------------------------------------------
"""
import collections
import logging
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCompat, QtCore, QtWidgets

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.coreUI.qt import widget_utils as QT_WIDGET


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register a `Scene Activation Manager` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Scene Activation Manager"
""":class:`str`: The tool name used to register a `Scene Activation Manager` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Scene Activation Manager` to a given Node Editor editor widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QTabWidget`): A Node Editor editor, to be used as the parent for the `Scene Activation Manager`.
        force (:class:`bool`): Whether to reinstall the `Scene Activation Manager` if one already exists under ``parent``.
            If :data:`False`, skip installation if a `Scene Activation Manager` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor editor.

    Returns:
        The `Scene Activation Manager` tool parented under ``parent``. If ``force`` is :data:`False`, this could be an existing tool.
    """
    return _SceneActivationManager(parent)


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Scene Activation Manager`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: A `Scene Activation Manager` tool to uninstall.
    """
    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

class _SceneActivationManager(QtCore.QObject):

    def __init__(self, parent):
        if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.EDITOR):
            raise UI_EXC.MayaUILookupError("Expected a Node Editor editor widget for the parent")

        super(_SceneActivationManager, self).__init__(parent=parent)

        # Activate the current scene (initialisation is deferred, therefore the `currentIndex` is assumed valid)
        self._tabChangeQueue = collections.deque([], maxlen=1)
        self._queueSceneActivation(self.currentIndex)

        self._connectInternalSignals()

    # --- Public ----------------------------------------------------------------------------------------

    @property
    def nodeEditor(self):
        """Returns the parent Node Editor."""
        # Careful not to invalidate `self`
        return QT_WIDGET.retainAndReturn(self.parent())

    @property
    def nodeEditorPageArea(self):
        """Returns the parent Node Editor page area."""
        return UI_NODE_EDITOR.getNodeEditorPageAreaFromEditor(self.nodeEditor)

    @property
    def nodeEditorGraphicsScene(self):
        """Returns the current graphics scene of the parent Node Editor."""
        return UI_NODE_EDITOR.getCurrentNodeEditorGraphicsSceneFromEditor(self.nodeEditor)

    @property
    def currentIndex(self):
        """Returns the current index of the parent Node Editor."""
        # We use the `QStackedWidget` to get the current index because it is possible to select the last "Add a new tab" button for the `QTabBar`/`QTabWidget` with `ctrl + tab`
        return self.nodeEditorPageArea.currentIndex()

    # --- Private ----------------------------------------------------------------------------------------

    def _connectInternalSignals(self):
        self.nodeEditor.currentChanged.connect(self._queueSceneActivation)

    def _queueSceneActivation(self, index):
        self._tabChangeQueue.append(index)
        cmds.evalDeferred(self._activateScene)

    def _activateScene(self):
        # Invocation is deferred, therefore the Node Editor may be closed before idle
        if not QtCompat.isValid(self):
            return

        # Queue ensures execution of the function only occurs once (a call will be deferred for every tab change upon loading a scene)
        try:
            index = self._tabChangeQueue.pop()
        except IndexError:
            return

        # This can occur when a tab is ripped off from the main panel
        if index == -1:
            return

        activationEvent = QtCore.QEvent(QtCore.QEvent.WindowActivate)
        QtWidgets.QApplication.sendEvent(self.nodeEditorGraphicsScene, activationEvent)
