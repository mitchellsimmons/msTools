"""
Install callbacks to manage bugs relating to nodeGraphEditorInfo nodes.

----------------------------------------------------------------

Background Info
---------------

    When saving the scene or closing the Node Editor, Maya creates a new nodeGraphEditorInfo node named ``'MayaNodeEditorSavedTabsInfo'``.
    This new node replaces any existing nodeGraphEditorInfo node which has the name ``'MayaNodeEditorSavedTabsInfo'``.
    Maya uses the node to cache the layout of nodes within each of the Node Editor's tabs so that it can rebuild the layout.

----------------------------------------------------------------

Selection Bug
-------------

    .. warning:: The following sequence of events causes Maya to crash and occasionally corrupts the current file:

    #. Open the Node Editor and save the scene, allowing the ``'MayaNodeEditorSavedTabsInfo'`` to be created.
    #. Select the ``'MayaNodeEditorSavedTabsInfo'`` node.
    #. Close the Node Editor with the ``'MayaNodeEditorSavedTabsInfo'`` node still selected or optionally save the scene again.

----------------------------------------------------------------

Non-Writable Node Bug
---------------------

    Maya relies upon contiguous connections to the ``'MayaNodeEditorSavedTabsInfo'`` in order to rebuild the node layout.
    However Maya allows non-writable nodes to connect to the nodeGraphEditorInfo node.
    Because these nodes are not saved with the scene, they result in a non-contiguous array of connections.

----------------------------------------------------------------

Installation
------------

    The following functionality is provided upon installing this tool:

    - The ``'MayaNodeEditorSavedTabsInfo'`` node will be deselected before closing the Node Editor and before saving the scene.
    - Contiguous connections to the ``'MayaNodeEditorSavedTabsInfo'`` node will be enforced by ensuring non-writable nodes are disconnected upon saving the scene.

    .. note::
        Because we are updating connections at the same time as Maya is making them, this can produce visual bugs in the Node Editor.
        For instance, plugs on the ``'MayaNodeEditorSavedTabsInfo'`` may appear to have multiple connections.

.. -------------------------------------------------------------

    Globals
    -------

    The following global scope variables are used to store session state:

    - _NODE_ADDED_CALLBACK
        * Manages the MCallbackId for the _nodeAddedCallback() callback (prevents reset on reload)
    - _ATTRIBUTE_CHANGED_CALLBACK
        * Manages the MCallbackId for the _attributeChangedCallback() callback (prevents reset on reload)

    The following MEL globals are used to store session state and interact with the Node Editor:

    - MRS_NodeEditor_RemoveCallback_Overridden
        * Caches the previous `removeCallback` procedure used by scripted panels of type `nodeEditorPanel`
        * Allows this tool to be non-destructively uninstalled
    - MRS_NodeEditor_RemoveCallback
        * Procedure used to override the previous `removeCallback` proc for scripted panels of type `nodeEditorPanel`
        * Usually this will be the default `nodeEdRemoveCallback` proc found at `<drive>:/Program Files/Autodesk/Maya<version>/script/others/nodeEditorPanel.mel`
        * Procedure ensures the `MayaNodeEditorSavedTabsInfo` node is deselected before the Node Editor is closed

----------------------------------------------------------------
"""
import logging
import os
log = logging.getLogger(__name__)

from maya import cmds, mel
from maya.api import OpenMaya as om2

from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM
from msTools.tools import callback_manager


# --------------------------------------------------------------
# --- Globals ---
# --------------------------------------------------------------

if "_NODE_ADDED_CALLBACK" in globals():
    log.debug("Initializing global: _NODE_ADDED_CALLBACK")
    _NODE_ADDED_CALLBACK = None


if "_ATTRIBUTE_CHANGED_CALLBACK" in globals():
    log.debug("Initializing global: _ATTRIBUTE_CHANGED_CALLBACK")
    _ATTRIBUTE_CHANGED_CALLBACK = None


# --------------------------------------------------------------
# --- Public ---
# --------------------------------------------------------------

def isInstalled():
    """
    Returns:
        :class:`bool`: :data:`True` if the `NodeGraphEditorInfo Manager` is installed, :data:`False` otherwise.
    """
    return callback_manager.isCallableRegistered(callback_manager.SceneEvent.BeforeSave, _beforeSaveCallback) \
        and cmds.scriptedPanelType("nodeEditorPanel", q=True, removeCallback=True).strip() == "MRS_NodeEditor_RemoveCallback"


def install():
    """Install the `NodeGraphEditorInfo Manager`.

    Note:
        Two callables will be registered to the following message events.
        Callbacks for these events will be installed by the :mod:`msTools.tools.callback_manager` if they do not yet exist.

        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kBeforeSave` message.
        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kAfterSave` message.

        The ``removeCallback`` procedure for scripted panels of type ``'nodeEditorPanel'`` will be non-destructively overridden (akin to overloaded).
    """
    if isInstalled():
        return

    log.debug("Installing: NodeGraphEditorInfo Manager")

    callback_manager.registerCallable(callback_manager.SceneEvent.BeforeSave, _beforeSaveCallback)
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterSave, _afterSaveCallback)

    # Source `removeCallback` override
    keyPressCommandPath = os.path.abspath(os.path.join(__file__, "..", "resources", "scripts", "MRS_nodeEditorRemoveCallback.mel")).replace("\\", "/")
    mel.eval("source \"{}\"".format(keyPressCommandPath))

    # Install `removeCallback` override
    removeCallbackProc = cmds.scriptedPanelType("nodeEditorPanel", q=True, removeCallback=True).strip()
    if removeCallbackProc != "MRS_NodeEditor_RemoveCallback":
        mel.eval("global string $MRS_NodeEditor_RemoveCallback_Overridden = \"" + removeCallbackProc + "\";")
        cmds.scriptedPanelType("nodeEditorPanel", e=True, removeCallback="MRS_NodeEditor_RemoveCallback")


def uninstall():
    """Uninstall the `NodeGraphEditorInfo Manager`.

    Note:
        Two callables will be deregistered from the following message events.
        Callbacks for these events will be uninstalled by the :mod:`msTools.tools.callback_manager` if no other callables are registered.

        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kBeforeSave` message.
        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kAfterSave` message.

        The ``removeCallback`` procedure for scripted panels of type ``'nodeEditorPanel'`` will be reverted to the overridden procedure.
    """
    if not isInstalled():
        return

    log.debug("Uninstalling: NodeGraphEditorInfo Manager")

    callback_manager.deregisterCallable(callback_manager.SceneEvent.BeforeSave, _beforeSaveCallback)
    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterSave, _afterSaveCallback)
    # Just to be sure..
    _removeNodeAddedCallback()
    _removeAttributeChangedCallback()

    # Install previous `removeCallback` (if registered)
    if mel.eval("whatIs \"$MRS_NodeEditor_RemoveCallback_Overridden\"") != "Unknown":
        previousRemoveCallbackProc = mel.eval("$_=$MRS_NodeEditor_RemoveCallback_Overridden;")
        cmds.scriptedPanelType("nodeEditorPanel", e=True, removeCallback=previousRemoveCallbackProc)


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

def _beforeSaveCallback():
    global _NODE_ADDED_CALLBACK

    # Prevent the selection bug described above
    try:
        tabsInfoNode = OM.getNodeByName("MayaNodeEditorSavedTabsInfo")
    except EXC.MayaLookupError:
        pass
    else:
        om2.MGlobal.unselect(tabsInfoNode)

    _NODE_ADDED_CALLBACK = om2.MDGMessage.addNodeAddedCallback(_nodeAddedCallback, "nodeGraphEditorInfo")


def _afterSaveCallback():
    _removeNodeAddedCallback()
    _removeAttributeChangedCallback()


def _nodeAddedCallback(node, *clientData):
    global _ATTRIBUTE_CHANGED_CALLBACK

    if node.apiType() == om2.MFn.kNodeGraphEditorInfo and NAME.getNodeFullName(node) == "MayaNodeEditorSavedTabsInfo":
        _ATTRIBUTE_CHANGED_CALLBACK = om2.MNodeMessage.addAttributeChangedCallback(node, _attributeChangedCallback)


def _attributeChangedCallback(msg, plug, otherPlug, *clientData):
    if not (msg & om2.MNodeMessage.kConnectionMade):
        return

    # If a non-writable node was connected, disconnect it
    sourceNodeFn = om2.MFnDependencyNode(otherPlug.node())
    if not sourceNodeFn.canBeWritten():
        DGMod = om2.MDGModifier()
        DGMod.disconnect(otherPlug, plug)
        DGMod.doIt()
        return

    # Ensure the current connections to the nodeInfo plug are contiguous
    attr = plug.attribute()
    destNodeFn = om2.MFnDependencyNode(plug.node())
    if om2.MFnAttribute(attr).name == "dependNode":
        nodeInfoElementPlug = plug.parent()
        nodeInfoArrayPlug = nodeInfoElementPlug.array()
        currentLogicalIndex = nodeInfoElementPlug.logicalIndex()

        if currentLogicalIndex == 0:
            return

        # Find the smallest logical index which does not have a connection
        disconnectedLogicalIndex = currentLogicalIndex - 1
        while (disconnectedLogicalIndex >= 0):
            disconnectedNodeInfoElementPlug = nodeInfoArrayPlug.elementByLogicalIndex(disconnectedLogicalIndex)
            disconnectedDependNodePlug = disconnectedNodeInfoElementPlug.child(attr)
            if disconnectedDependNodePlug.isConnected:
                disconnectedLogicalIndex += 1
                break
            else:
                disconnectedLogicalIndex -= 1

        if disconnectedLogicalIndex == -1:
            disconnectedLogicalIndex += 1

        if disconnectedLogicalIndex == currentLogicalIndex:
            return

        previousNodeInfoElementPlug = nodeInfoArrayPlug.elementByLogicalIndex(disconnectedLogicalIndex)
        previousDependNodePlug = previousNodeInfoElementPlug.child(attr)
        if not previousDependNodePlug.isConnected:
            previousPositionXPlug = previousNodeInfoElementPlug.child(destNodeFn.attribute("positionX"))
            previousPositionYPlug = previousNodeInfoElementPlug.child(destNodeFn.attribute("positionY"))
            previousNodeVisualStatePlug = previousNodeInfoElementPlug.child(destNodeFn.attribute("nodeVisualState"))
            positionXPlug = nodeInfoElementPlug.child(destNodeFn.attribute("positionX"))
            positionYPlug = nodeInfoElementPlug.child(destNodeFn.attribute("positionY"))
            nodeVisualStatePlug = nodeInfoElementPlug.child(destNodeFn.attribute("nodeVisualState"))

            # Reconnect and replace values
            DGMod = om2.MDGModifier()
            DGMod.disconnect(otherPlug, plug)
            DGMod.doIt()
            DGMod.connect(otherPlug, previousDependNodePlug)
            DGMod.doIt()
            previousPositionXPlug.setFloat(positionXPlug.asFloat())
            previousPositionYPlug.setFloat(positionYPlug.asFloat())
            previousNodeVisualStatePlug.setInt(nodeVisualStatePlug.asInt())


def _removeNodeAddedCallback():
    global _NODE_ADDED_CALLBACK

    if _NODE_ADDED_CALLBACK is not None:
        om2.MMessage.removeCallback(_NODE_ADDED_CALLBACK)
        _NODE_ADDED_CALLBACK = None


def _removeAttributeChangedCallback():
    global _ATTRIBUTE_CHANGED_CALLBACK

    if _ATTRIBUTE_CHANGED_CALLBACK is not None:
        om2.MMessage.removeCallback(_ATTRIBUTE_CHANGED_CALLBACK)
        _ATTRIBUTE_CHANGED_CALLBACK = None
