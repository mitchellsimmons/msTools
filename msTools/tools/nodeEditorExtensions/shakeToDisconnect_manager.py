"""
Manage installation of the `Shake To Disconnect Manager` to a Node Editor editor within the current Maya session.

The `Shake To Disconnect Manager` listens for custom "shake" events in order to completely disconnect any nodes which are being shook within a Node Editor tab.

The are two settings which affect the behaviour of the `Shake To Disconnect Manager`:

- The ``"MRS_NEExtensions_OptionVar_ST"`` :func:`cmds.optionVar` controls the `shake tolerance`.
- The ``"MRS_NEExtensions_OptionVar_EM"`` :func:`cmds.optionVar` controls whether to `exclude message` type attributes when a disconnection is triggered by a "shake" event.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Shake To Disconnect Managers` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
import collections
import itertools
import time
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.vendor.Qt import QtCompat, QtCore

from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import om_utils as OM
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import event_utils as QT_EVENT
from msTools.coreUI.qt import widget_utils as QT_WIDGET
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions import constants as EXT_CONSTANTS


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register a `Shake To Disconnect Manager` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Shake To Disconnect Manager"

""":class:`str`: The tool name used to register a `Shake To Disconnect Manager` with the :mod:`msTools.tools.tool_manager`."""

# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------


@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Shake To Disconnect Manager` to a given Node Editor editor widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QTabWidget`): A Node Editor editor, to be used as the parent for the `Shake To Disconnect Manager`.
        force (:class:`bool`): Whether to reinstall the `Shake To Disconnect Manager` if one already exists under ``parent``.
            If :data:`False`, skip installation if a `Shake To Disconnect Manager` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor editor.

    Returns:
        The `Shake To Disconnect Manager` parented under ``parent``. If ``force`` is :data:`False`, this could be an existing tool.
    """
    return _ShakeToDisconnectManager(parent)


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Shake To Disconnect Manager`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: A `Shake To Disconnect Manager` tool to uninstall.
    """
    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

class _ShakeToDisconnectManager(QtCore.QObject):
    """Manages installation of event filters for a given Node Editor editor in order to provide "shake to disconnect" functionality in each of its tabs."""

    def __init__(self, parent):
        if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.EDITOR):
            raise UI_EXC.MayaUILookupError("Expected a Node Editor editor widget for the parent")

        super(_ShakeToDisconnectManager, self).__init__(parent=parent)

        self._installAddChildListener()
        self._installShakeListenersToExisting()

    def _installAddChildListener(self):
        """Installs an event filter on the Node Editor editor widget which listens for events that indicate a child has been added.
        If the child was a new tab, an event filter will be installed on its viewport so that it can listen for user "shake" events.

        Note:
            The Node Editor replaces `QGraphicsViews` when opening a scene or creating a new scene or when a new tab is added.
        """
        # Careful not to invalidate `self`
        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())

        self._childAddedListener = QT_EVENT.SignalEventFilter(eventType=QtCore.QEvent.ChildAdded, parent=self)
        nodeEditor.installEventFilter(self._childAddedListener)

        # When Maya creates a new QGraphicsView it first parents it to the editor before reparenting it to a page once an idle state is reached
        self._childAddedListener.eventTriggered.connect(lambda: cmds.evalDeferred(self._installShakeListenerToCurrent))

    def _installShakeListenersToExisting(self):
        """Installs an event filter on each existing existing Node Editor viewport widget so that it can listen for user "shake" events."""
        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())
        nodeEditorGraphicsViews = UI_NODE_EDITOR.getNodeEditorGraphicsViewsFromEditor(nodeEditor)

        # It is best to check validity for the initial installation
        for nodeEditorGraphicsView in nodeEditorGraphicsViews:
            if QtCompat.isValid(nodeEditorGraphicsView):
                nodeEditorViewport = nodeEditorGraphicsView.viewport()
                self._installShakeListener(nodeEditorViewport)

    def _installShakeListenerToCurrent(self):
        """Installs an event filter on the current Node Editor viewport widget so that it can listen for user "shake" events."""
        # Because invocation is deferred, it is possible this object has been deleted
        if not QtCompat.isValid(self):
            return

        nodeEditor = QT_WIDGET.retainAndReturn(self.parent())
        nodeEditorGraphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        nodeEditorViewport = nodeEditorGraphicsView.viewport()
        self._installShakeListener(nodeEditorViewport)

    def _installShakeListener(self, nodeEditorViewport):
        """Installs an event filter on the given Node Editor viewport widget so that it can listen for user "shake" events."""
        # If the child added event was triggered by something other than a tab, there may already be a `_ShakeEventFilter` installed
        for childWidget in nodeEditorViewport.children():
            if isinstance(childWidget, _ShakeEventFilter):
                return

        nodeEditorViewport.installEventFilter(_ShakeEventFilter(parent=self))


class _ShakeEventFilter(QtCore.QObject):
    """An event filter that will listen for user "shake" events after being installed on a Node Editor viewport widget.

    A "shake" event occurs when a node is shook fast enough to reach a certain threshold.
    When this occurs, the node will be disconnected from all of its inputs and outputs unless the connection is to a default node.
    """

    # Acts as a global tolerance, affecting how hard the user has to shake a node for it to disconnect
    QUEUE_SIZE = 25

    # Defines the minimum amount of time (in milliseconds) that needs to pass before a change in direction can be recorded (helps produce a stable tolerance)
    # Designed to elide changes in direction that occur when the `QGraphicsScene` is zoomed in since the mouse polling rate will be increased (increasing the event emission rate)
    MINIMUM_QUEUE_TIME = 10

    def __init__(self, parent):
        super(_ShakeEventFilter, self).__init__(parent)

        self._reset()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Type.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            shakeManager = QT_WIDGET.retainAndReturn(self.parent())
            nodeEditor = QT_WIDGET.retainAndReturn(shakeManager.parent())
            feedbackNodeName = cmds.nodeEditor(nodeEditor.objectName(), q=True, feedbackNode=True)

            if feedbackNodeName:
                self._previousMousePos = event.pos()
                self._feedbackNodeHandle = om2.MObjectHandle(OM.getNodeByName(feedbackNodeName))
                self._previousTime = time.time() * 1000
                self._shakeTolerance = cmds.optionVar(q=EXT_CONSTANTS.ST_OPTIONVAR[0])
                self._excludeMessages = cmds.optionVar(q=EXT_CONSTANTS.EM_OPTIONVAR[0])

        elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            self._reset()

        elif event.type() == QtCore.QEvent.Type.MouseMove:
            if self._previousMousePos is not None:
                # The rate at which move events occur is limited by the polling rate of the mouse which is limited by how much of the `QGraphicsScene` is visible
                # We need to linearize the rate at which we check for changes in direction otherwise the tolerance values will feel inconsistent
                currentTime = time.time() * 1000
                timeSinceMove = currentTime - self._previousTime
                self._previousTime = currentTime

                # Elide any changes that occur between the minimum amount of time
                self._timeSinceAppend += timeSinceMove
                if self._timeSinceAppend < _ShakeEventFilter.MINIMUM_QUEUE_TIME:
                    return super(_ShakeEventFilter, self).eventFilter(watched, event)
                self._timeSinceAppend = 0

                # Reset the queue if the user has stopped moving the mouse for a significant period of time
                if timeSinceMove > 300:
                    self._dotProductQueue = collections.deque(_ShakeEventFilter.QUEUE_SIZE * [0], maxlen=_ShakeEventFilter.QUEUE_SIZE)

                directionVec = event.pos() - self._previousMousePos
                self._previousMousePos = event.pos()

                # We disconnect if the total number of changes in direction over the last `QUEUE_SIZE` number of move events is greater than a threshold
                # We want to avoid using distance as a threshold as we would probably need to determine values relative to the current zoom
                if self._previousMouseDirectionVector is None:
                    self._previousMouseDirectionVector = directionVec
                else:
                    dotProduct = directionVec.x() * self._previousMouseDirectionVector.x() + directionVec.y() * self._previousMouseDirectionVector.y()
                    self._dotProductQueue.append(dotProduct)
                    self._previousMouseDirectionVector = directionVec

                    # Ensure zero is included in the positive grouping (slow movement causes a lot of zero results due to the polling rate)
                    # These are likely not perpendicular movements, they are either null movements or have just been rounded down
                    numSignChange = len(list(itertools.groupby(self._dotProductQueue, lambda x: x >= 0)))

                    if self._dotProductQueue[0] < 0 or self._dotProductQueue[-1] < 0:
                        numDirectionChanged = numSignChange / 2
                    else:
                        numDirectionChanged = (numSignChange - 1) / 2

                    if numDirectionChanged > self._shakeTolerance + 2:
                        self._disconnect()

        elif event.type() == QtCore.QEvent.Type.FocusOut or event.type() == QtCore.QEvent.Type.WindowDeactivate:
            self._reset()

        return super(_ShakeEventFilter, self).eventFilter(watched, event)

    def _disconnect(self):
        if self._feedbackNodeHandle is not None and self._feedbackNodeHandle.isValid():
            fnDep = om2.MFnDependencyNode(self._feedbackNodeHandle.object())
            connectedPlugs = fnDep.getConnections()
            dgMod = OM.MDGModifier()

            with CONTEXT.UndoItOnError(dgMod, StandardError):
                disconnectionsMade = False

                for connectedPlug in connectedPlugs:
                    if connectedPlug.attribute().apiType() != om2.MFn.kMessageAttribute or not self._excludeMessages:
                        if connectedPlug.isSource:
                            destPlugs = connectedPlug.destinationsWithConversions()

                            for destPlug in destPlugs:
                                if destPlug.attribute().apiType() != om2.MFn.kMessageAttribute or not self._excludeMessages:
                                    if not om2.MFnDependencyNode(destPlug.node()).isDefaultNode:
                                        dgMod.disconnect(connectedPlug, destPlug)
                                        disconnectionsMade = True

                        if connectedPlug.isDestination:
                            sourcePlug = connectedPlug.sourceWithConversion()
                            if sourcePlug.attribute().apiType() != om2.MFn.kMessageAttribute or not self._excludeMessages:
                                if not om2.MFnDependencyNode(sourcePlug.node()).isDefaultNode:
                                    dgMod.disconnect(sourcePlug, connectedPlug)
                                    disconnectionsMade = True

                if disconnectionsMade:
                    dgMod.doIt()

        self._reset()

    def _reset(self):
        self._feedbackNodeHandle = None
        self._previousMousePos = None
        self._previousMouseDirectionVector = None
        self._previousTime = None
        self._timeSinceAppend = 0
        self._dotProductQueue = collections.deque(_ShakeEventFilter.QUEUE_SIZE * [0], maxlen=_ShakeEventFilter.QUEUE_SIZE)
