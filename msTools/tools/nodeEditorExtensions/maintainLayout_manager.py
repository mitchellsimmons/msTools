"""
Manage installation of the `Maintain Layout Manager` within the current Maya session.

The `Maintain Layout Manager` maintains the layout of nodes in existing Node Editors when a connection is made.
Designed specifically to handle connections between non-homogeneous data types which result in the creation of a unit conversion node.

The `Maintain Layout Manager` uses the value of the ``"MRS_NEExtensions_OptionVar_UCP"`` :func:`cmds.optionVar` to determine how new unit conversion nodes will be positioned.

----------------------------------------------------------------
"""
import functools
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.vendor.Qt import QtCompat, QtCore

from msTools.core.py import decorator_utils as PY_DECORATOR
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import callback_manager
from msTools.tools.nodeEditorExtensions import constants as EXT_CONSTANTS


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

if "_RUN_SINCE_IDLE" not in globals():
    log.debug("Initializing global: _RUN_SINCE_IDLE")
    _RUN_SINCE_IDLE = False


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def isInstalled():
    """
    Returns:
        :class:`bool`: :data:`True` if the `Maintain Layout Manager` is installed, :data:`False` otherwise.
    """
    return callback_manager.isCallableRegistered(callback_manager.DGEvent.PreConnectionChange, _preConnectionCallback)


def install():
    """Install the `Maintain Layout Manager` if not already installed.

    Note:
        A callable will be registered to the message event corresponding to :meth:`OpenMaya.MDGMessage.addPreConnectionCallback`.
        A callback for this event will be installed by the :mod:`msTools.tools.callback_manager` if it does not yet exist.
    """
    if isInstalled():
        return

    log.debug("Installing: Node Editor Maintain Layout Manager")
    callback_manager.registerCallable(callback_manager.DGEvent.PreConnectionChange, _preConnectionCallback, receivesCallbackArgs=True)


def uninstall():
    """Uninstall the `Maintain Layout Manager` if installed.

    Note:
        A callable will be deregistered from the message event corresponding to :meth:`OpenMaya.MDGMessage.addPreConnectionCallback`.
        The callback for this event will be uninstalled by the :mod:`msTools.tools.callback_manager` if no other callables are registered.
    """
    if isInstalled():
        log.debug("Uninstalling: Node Editor Maintain Layout Manager")
        callback_manager.deregisterCallable(callback_manager.DGEvent.PreConnectionChange, _preConnectionCallback)


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def _preConnectionCallback(sourcePlug, destPlug, isConnecting, *clientData):
    """A callback which maintains the layout of nodes in existing Node Editors when a connection is made.

    Designed to be installed via :meth:`OpenMaya.MDGMessage.addPreConnectionCallback`. Implemented as follows:

    1. Cache a description of the graph before a connection is made (between disimiliar attribute types only).
    2. Check if any unit conversion node was created as a result of the connection.
    3. Position the unit conversion node based on the current value of the ``"MRS_NEExtensions_OptionVar_UCP"`` :func:`cmds.optionVar`.
    4. Restore the position of each node in the graph using the cached graph description.
    """
    # WARNING: We must retain references to any (c++) widgets retrieved within this callback procedure to ensure existing references are not invalidated
    # For example it is reasonable for a procedure to expect that its reference to the Node Editor widget will remain valid after making a connection

    # This callback is executed multiple times during new scene, scene open, graph duplication (we want to exit as early as possible)
    if _RUN_SINCE_IDLE:
        return

    # Ignore disconnections (before the safeguard is enabled in case the user is making a new connection to a connected plug)
    if not isConnecting:
        return

    # Enable the safeguard and disable it at next idle event
    _enableSafeguard()
    cmds.evalDeferred(_disableSafeguard)

    # Ignore message attributes (except when a default node is being connected as this causes the layout to change if the node is visible)
    isDefaultNode = om2.MFnDependencyNode(sourcePlug.node()).isDefaultNode or om2.MFnDependencyNode(destPlug.node()).isDefaultNode
    sourceAttrType = sourcePlug.attribute().apiType()
    destAttrType = destPlug.attribute().apiType()

    if not isDefaultNode and (sourceAttrType == om2.MFn.kMessageAttribute or destAttrType == om2.MFn.kMessageAttribute):
        return

    nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")
    graphicsViews = []

    # Retrieve the current `QGraphicsView` for each panel
    for nodeEditorPanelName in nodeEditorPanelNames:
        try:
            nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)
            nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
        except UI_EXC.MayaUILookupError:
            continue

        graphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        graphicsViews.append(graphicsView)

    # Ignore non-user connections (eg. import/opening scenes)
    if not isDefaultNode:
        for graphicsView in graphicsViews:
            if graphicsView.scene().hasFocus():
                break
        else:
            return

    for graphicsView in graphicsViews:
        if isDefaultNode:
            # Always restore after connecting to a default node
            preGraphNodeItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE]
            preGraphNodeDescription = {item: item.pos() for item in preGraphNodeItems}
            graphicsView.setUpdatesEnabled(False)
            cmds.evalDeferred("cmds.refresh()")
            cmds.evalDeferred(functools.partial(_restoreGraph, graphicsView, preGraphNodeDescription))
        else:
            # Ignore if there is not at least one unit conversion node
            sourceNodeType = sourcePlug.node().apiType()
            destNodeType = destPlug.node().apiType()

            if sourceNodeType != om2.MFn.kUnitConversion and destNodeType != om2.MFn.kUnitConversion:
                return

            # Store a description of the graph before the connection is made
            # The unit conversion node has already been created but will not be added to the graph until Maya is idle
            preGraphNodeItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE]
            preGraphNodeDescription = {item: item.pos() for item in preGraphNodeItems}
            preGraphPathItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.PATH]

            # We disable paint events to the view so that when Maya lays out the nodes, its changes are not visible to the user
            graphicsView.setUpdatesEnabled(False)

            # We defer evaluation, allowing Maya to add any new unitConversion node item to the QGraphicsScene and position items as it chooses
            # We then reset the positions of the nodes, however Maya seems to schedule another update with the same positions (overriding our changes)
            # To prevent this extra update from scheduling we can refresh before repositioning (must be deferred)
            # Another option was to run the restore function once with updates on the view disabled then once with updates enabled
            cmds.evalDeferred("cmds.refresh()")
            cmds.evalDeferred(functools.partial(_restoreGraphAndPositionNew, graphicsView, preGraphNodeDescription, preGraphPathItems, sourcePlug.node(), destPlug.node()))


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _enableSafeguard():
    global _RUN_SINCE_IDLE
    _RUN_SINCE_IDLE = True


def _disableSafeguard():
    global _RUN_SINCE_IDLE
    _RUN_SINCE_IDLE = False


def _resetGraphicsView(graphicsView=None):
    if graphicsView is None:
        nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

        for nodeEditorPanelName in nodeEditorPanelNames:
            try:
                nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)
                nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
            except UI_EXC.MayaUILookupError:
                continue

            graphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
            graphicsView.setUpdatesEnabled(True)
    else:
        graphicsView.setUpdatesEnabled(True)


@PY_DECORATOR.callOnError(_resetGraphicsView, Exception)
def _restoreGraph(graphicsView, preGraphNodeDescription):
    """Restores the positions of node `QGraphicsItems` in the `QGraphicsScene` of the given `QGraphicsView`.

    Positions are based on the pre-connection graph description.
    """
    # The callback can be invoked upon closing the nodeEditor due to saving bookmarks (connects visible nodes to default Maya bookmark node)
    if not QtCompat.isValid(graphicsView):
        return

    postGraphNodeItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE]

    # Reset items to their previous positions
    for graphicsItem in postGraphNodeItems:
        try:
            previousPos = preGraphNodeDescription[graphicsItem]
        except KeyError:
            pass
        else:
            graphicsItem.setPos(previousPos)

    graphicsView.setUpdatesEnabled(True)


@PY_DECORATOR.callOnError(_resetGraphicsView, Exception)
def _restoreGraphAndPositionNew(graphicsView, preGraphNodeDescription, preGraphPathItems, sourceNode, destNode):
    """Restores the positions of node `QGraphicsItems` in the `QGraphicsScene` of the given `QGraphicsView`.

    Positions are based on the pre-connection graph description.
    If a new `unitConversion` node was created, it will be repositioned based on the value of the "MRS_NEExtensions_OptionVar_UCP" `optionVar`.
    """
    # The callback can be invoked upon closing the nodeEditor due to saving bookmarks (connects visible nodes to default Maya bookmark node)
    if not QtCompat.isValid(graphicsView):
        return

    graphicsScene = graphicsView.scene()
    preGraphNodeItems = preGraphNodeDescription.keys()
    postGraphNodeItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE]
    postGraphPathItems = [item for item in graphicsView.items() if item.type() == UI_NODE_EDITOR.NodeEditorGraphicsItem.PATH]

    if len(postGraphNodeItems) > len(preGraphNodeItems) + 1:
        log.info("More than one new node was created as the result of the current connection. This situation is not handled, aborting `maintain layout` procedure.")
        _resetGraphicsView(graphicsView)
        return

    # Retrieve the new unitConversion node if one was created
    newNodeItem = next((item for item in postGraphNodeItems if item not in preGraphNodeItems), None)
    if newNodeItem is None:
        _resetGraphicsView(graphicsView)
        return

    newNode = UI_NODE_EDITOR.getNodeFromGraphicsItem(newNodeItem)
    if newNode.apiType() != om2.MFn.kUnitConversion:
        log.info("A non-unitConversion type node was created as the result of the current connection. This situation is not handled, aborting `maintain layout` procedure.")
        _resetGraphicsView(graphicsView)
        return

    # Retrieve the input and output items of the new unitConversion node
    if newNode == sourceNode:
        unitConversionDestPlug = om2.MFnDependencyNode(newNode).findPlug("input", False)
        userSourceNode = unitConversionDestPlug.sourceWithConversion().node()
        userSourceNodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(userSourceNode, graphicsScene)
        userDestNodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(destNode, graphicsScene)
    elif newNode == destNode:
        unitConversionSourcePlug = om2.MFnDependencyNode(newNode).findPlug("output", False)
        userDestNode = unitConversionSourcePlug.destinationsWithConversions()[0].node()
        userSourceNodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(sourceNode, graphicsScene)
        userDestNodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(userDestNode, graphicsScene)

    # Retrieve the new QGraphicsPathItems
    try:
        sourcePathItem, destPathItem = _retrieveAndVerifyNewPaths(preGraphPathItems, postGraphPathItems, userSourceNodeItem)
    except RuntimeError:
        _resetGraphicsView(graphicsView)
        return

    # Determine (post-graph) plug positions
    userSourcePlugPos, unitConversionDestPlugPos = _getPathEndpoints(sourcePathItem)
    unitConversionSourcePlugPos, userDestPlugPos = _getPathEndpoints(destPathItem)
    # Determine relative offsets of plugs from their respective (post-graph) node position
    userSourcePlugOffset = userSourcePlugPos - userSourceNodeItem.pos()
    userDestPlugOffset = userDestPlugPos - userDestNodeItem.pos()
    newNodeSourcePlugOffset = unitConversionSourcePlugPos - newNodeItem.pos()
    newNodeDestPlugOffset = unitConversionDestPlugPos - newNodeItem.pos()

    # Reset the original items to their previous positions
    for graphicsItem in postGraphNodeItems:
        try:
            previousPos = preGraphNodeDescription[graphicsItem]
        except KeyError:
            pass
        else:
            graphicsItem.setPos(previousPos)

    # The user's settings determine where to position the new unitConversion node based on the current input and output positions
    unitConversionPosition = cmds.optionVar(q=EXT_CONSTANTS.UCP_OPTIONVAR[0])
    userSourceNodePreGraphPos = preGraphNodeDescription[userSourceNodeItem]
    userDestNodePreGraphPos = preGraphNodeDescription[userDestNodeItem]
    newNodeRect = newNodeItem.boundingRect()

    # Localize the plug offsets to the pre-graph node positions to get pre-graph plug positions
    userSourcePlugPreGraphPos = userSourceNodePreGraphPos + userSourcePlugOffset
    userDestPlugPreGraphPos = userDestNodePreGraphPos + userDestPlugOffset

    # Center
    if unitConversionPosition == 0:
        interpPos = (userSourcePlugPreGraphPos + userDestPlugPreGraphPos) / 2
        interpPos += QtCore.QPointF(-newNodeRect.width() / 2, -newNodeRect.height() / 2)
    # Next to source
    elif unitConversionPosition == 1:
        interpPos = QtCore.QPointF(userSourcePlugPreGraphPos.x() + 50, userSourcePlugPreGraphPos.y() - newNodeDestPlugOffset.y())
    # Next to destination
    elif unitConversionPosition == 2:
        interpPos = QtCore.QPointF(userDestPlugPreGraphPos.x() - newNodeRect.width() - 50, userDestPlugPreGraphPos.y() - newNodeSourcePlugOffset.y())
    # Random
    elif unitConversionPosition == 3:
        _resetGraphicsView(graphicsView)
        return

    newNodeItem.setPos(interpPos)

    graphicsView.setUpdatesEnabled(True)


def _retrieveAndVerifyNewPaths(preGraphPathItems, postGraphPathItems, userSourceNodeItem):
    newPathItems = [item for item in postGraphPathItems if item not in preGraphPathItems]

    if len(newPathItems) != 2:
        log.info("{} connections to the new node were found, expected two. This situation is not handled, aborting `maintain layout` procedure.".format(len(newPathItems)))
        raise RuntimeError

    # The path goes into the node by 1.5 units (the top plug is larger by this amount, causing a margin to the smaller plugs)
    userSourceNodeOutputPosX = userSourceNodeItem.x() + userSourceNodeItem.boundingRect().width() - 1.5

    # The source path is the one whose source position is closest to the user source node's source side
    if abs(newPathItems[0].path().elementAt(0).x - userSourceNodeOutputPosX) < abs(newPathItems[1].path().elementAt(0).x - userSourceNodeOutputPosX):
        return newPathItems[0], newPathItems[1]
    else:
        return newPathItems[1], newPathItems[0]


def _getPathEndpoints(pathItem):
    # Each path may contain multiple subpaths (consisting of the main path and zero or more arrows)
    # The drawing of a path depends on the Node Editor path style (meaning the index corresponding to the end of the main path will vary)
    # We can be certain that the index of the end position will occur before the second move
    painterPath = pathItem.path()
    sourcePos = QtCore.QPointF(painterPath.elementAt(0))

    for elementIndex in xrange(1, painterPath.elementCount()):
        if painterPath.elementAt(elementIndex).isMoveTo():
            break
    else:
        elementIndex = painterPath.elementCount()

    destPos = QtCore.QPointF(painterPath.elementAt(elementIndex - 1))

    return sourcePos, destPos
