"""
Manage installation of `Node Editor Extensions`.

----------------------------------------------------------------

Tools
-----

    The following tools are applied to any existing or future Node Editor panels upon calling :func:`install`:

    - **Align Node Tool**: Adds buttons to the `icon bar` for aligning selected nodes.

    - **Background Optimisation Manager**: Optimises background rendering for each tab (increases performance).

    - **Create Node Tool**: Replaces the default dialog used for creating nodes when the tab key is pressed.

    - **Extensions Menu**: Adds a menu to the panel, providing tool related settings.

    - **Import Export Tool**: Adds buttons to the `icon bar` for exporting and importing graph layouts, including custom `Layout Tool` items.

    - **Maintain Layout Manager**: Maintains the graph layout when a `unitConversion` type node is created or a default connection is made.

    - **NodeGraphEditorInfo Manager**: Prevents bugs relating to `nodeGraphEditorInfo` type nodes.

    - **Scene Activation Manager**: Prevents a bug relating to the activation of Node Editor `graphics scenes`.

    - **Shake To Disconnect Manager**: Adds the ability to completely disconnect a node by shaking it.

    The following tools are applied to any existing or future **primary** Node Editor panels upon calling :func:`install`:

    - **Layout Tool**: Adds buttons to the `icon bar` for creating custom `NodeBoxItems` and `StickyItems`. Designed to add structure to the graph layout.

----------------------------------------------------------------

Global State
------------

    The following global MEL procedures are overridden upon calling :func:`install`.
    Extension functionality is disabled upon calling :func:`uninstall` but procedures will remain overridden.

    - **NodeEditorGraphClearGraph** (:func:`cmds.runTimeCommand`): Removes (non-native) `Layout Tool` items before clearing the graph.

    - **nodeEdKeyPressCommand**: Overrides the default tab key press behaviour so that the `Create Node Tool` can be shown.

    The following global command states are overridden upon calling :func:`install`. Overridden states are reinstated upon calling :func:`uninstall`.

    - `addCallback` for the ``"nodeEditorPanel"`` type :func:`cmds.scriptedPanelType`: The default `nodeEdAddCallback` procedure will be overridden.
      The override invokes the default `nodeEdAddCallback` procedure then installs extensions to the new panel.

    - `removeCallback` for the ``"nodeEditorPanel"`` type :func:`cmds.scriptedPanelType`: The default `nodeEdRemoveCallback` procedure will be overridden.
      The override deselects the "MayaNodeEditorSavedTabsInfo" node if it exists then invokes the default `nodeEdRemoveCallback` procedure.

----------------------------------------------------------------
"""
import os
import logging
log = logging.getLogger(__name__)

from maya import cmds, mel

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR

from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions import alignNodeTool_setup
from msTools.tools.nodeEditorExtensions import backgroundOptimisation_manager
from msTools.tools.nodeEditorExtensions import constants
from msTools.tools.nodeEditorExtensions import createNodeTool_setup
from msTools.tools.nodeEditorExtensions import importExportTool_setup
from msTools.tools.nodeEditorExtensions import layoutTool_setup
from msTools.tools.nodeEditorExtensions import maintainLayout_manager
from msTools.tools.nodeEditorExtensions import menu_setup
from msTools.tools.nodeEditorExtensions import nodeGraphEditorInfo_manager
from msTools.tools.nodeEditorExtensions import sceneActivation_manager
from msTools.tools.nodeEditorExtensions import shakeToDisconnect_manager


# --------------------------------------------------------------
# --- Global ---
# --------------------------------------------------------------

# Tracks the overridden `nodeEdKeyPressCommand`
if "_NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN" not in globals():
    log.debug("Initializing global: _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN")
    _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN = None


# --------------------------------------------------------------
# --- Public ---
# --------------------------------------------------------------

# NOTE: The public interface enforces installation to all Node Editor panels (ie. the user should have consistent expectations that their changes are applied and saved globally)

def install(force=False):
    """Install `Node Editor Extensions` to existing Node Editor panels and enable automatic installation for future Node Editor panels.

    Args:
        force (:class:`bool`): Whether to reinstall existing tools. If :data:`False`, skip installation if a tool already exists.
            Defaults to :data:`False`.

    Note:
        Only the primary panel will receive the ability to create `NodeBoxItems` and `StickyItems` via the `Layout Tool`.
    """
    # --- Global ------------------------------------------------------------------------------------------------------------

    _enableAutomaticSetup()

    # --- Load Plugin ---
    pluginPath = os.path.abspath(os.path.join(__file__, "..", "resources", "plugins", "mrs_nodeEditor_collection.mll")).replace("\\", "/")

    if not cmds.pluginInfo(pluginPath, q=True, loaded=True):
        log.debug("Loading Plugin: mrs_nodeEditor_collection")
        cmds.loadPlugin(pluginPath)

    # --- Install optionVars ---
    if not cmds.optionVar(exists=constants.CNT_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.CNT_OPTIONVAR)
    if not cmds.optionVar(exists=constants.STD_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.STD_OPTIONVAR)
    if not cmds.optionVar(exists=constants.ST_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.ST_OPTIONVAR)
    if not cmds.optionVar(exists=constants.EM_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.EM_OPTIONVAR)
    if not cmds.optionVar(exists=constants.ML_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.ML_OPTIONVAR)
    if not cmds.optionVar(exists=constants.UCP_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.UCP_OPTIONVAR)
    if not cmds.optionVar(exists=constants.OB_OPTIONVAR[0]):
        cmds.optionVar(intValue=constants.OB_OPTIONVAR)

    # --- Create Node Tool ---
    # The Node Editor `keyPressCommand` needs to be reset for each new tab (this is possible but annoying, just hard override the proc)
    global _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN

    if not _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN:
        # Cache the current proc name before sourcing the override (so that we can re-source upon uninstalling)
        whatIsNodeEdKeypressCommand = mel.eval("whatIs nodeEdKeyPressCommand")

        if whatIsNodeEdKeypressCommand.startswith("Mel procedure found in: "):
            _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN = whatIsNodeEdKeypressCommand.split("Mel procedure found in: ")[1]

            keyPressCommandPath = os.path.abspath(os.path.join(__file__, "..", "resources", "scripts", "MRS_nodeEditorKeyPressCommand.mel")).replace("\\", "/")
            mel.eval("source \"{}\"".format(keyPressCommandPath))
        else:
            log.info("Unable to identify the location of the current Node Editor keypress procedure. Aborting installation of the `Create Node Tool`")

    # Ensure the global NodeTypeController and NodeTypeModel are installed
    createNodeTool_setup.preInstall()

    # --- Maintain Layout Manager ---
    if cmds.optionVar(q=constants.ML_OPTIONVAR[0]):
        maintainLayout_manager.install()

    # --- NodeGraphEditorInfo Manager ---
    nodeGraphEditorInfo_manager.install()

    # --- Panel ------------------------------------------------------------------------------------------------------------

    nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

    for nodeEditorPanelName in nodeEditorPanelNames:
        try:
            UI_INSPECT.getWidget(nodeEditorPanelName)
        except UI_EXC.MayaUILookupError:
            continue

        _installToPanel(nodeEditorPanelName, force=force)


def uninstall(excludeNodeGraphInfoManager=True):
    """Uninstall `Node Editor Extensions` from existing Node Editor panels and disable automatic installation for future Node Editor panels.

    Args:
        excludeNodeGraphInfoManager (:class:`bool`): Whether to leave the `NodeGraphEditorInfo Manager` installed.
            This tool is considered essential to preventing certain bugs that occur within the Node Editor.
    """
    # --- Global ------------------------------------------------------------------------------------------------------------

    _disableAutomaticSetup()

    # --- Create Node Tool ---
    global _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN

    if _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN:
        mel.eval("source \"{}\"".format(_NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN))

        _NODE_EDITOR_KEYPRESS_COMMAND_OVERRIDDEN = None

    # --- Maintain Layout Manager ---
    maintainLayout_manager.uninstall()

    # --- NodeGraphEditorInfo Manager ---
    if not excludeNodeGraphInfoManager:
        nodeGraphEditorInfo_manager.uninstall()

    # --- Panel ------------------------------------------------------------------------------------------------------------

    nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

    for nodeEditorPanelName in nodeEditorPanelNames:
        try:
            UI_INSPECT.getWidget(nodeEditorPanelName)
        except UI_EXC.MayaUILookupError:
            continue

        _uninstallFromPanel(nodeEditorPanelName)


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

def _enableAutomaticSetup():
    """Enable automatic installation of Node Editor Extensions upon creating a new Node Editor panel.

    This overrides the procedure that gets called when a new Node Editor panel is created.
    Our procedure executes the previously registered procedure before installing the extensions.

    Note:
        Directly overriding the ``addCallback`` of a `"nodeEditorPanel"` type :func:`cmds.scriptedPanel` will break this setup.
    """
    # --- Install or enable optionVars ---
    cmds.optionVar(intValue=constants.NEAC_OPTIONVAR)

    # --- New Panel Script ---
    addCallbackProc = cmds.scriptedPanelType("nodeEditorPanel", q=True, addCallback=True).strip()
    if addCallbackProc != "MRS_NodeEditor_AddCallback":
        # Cache the current proc name before installing the override (so that we can call it)
        mel.eval("global string $MRS_NodeEditor_AddCallback_Overridden = \"{}\";".format(addCallbackProc))

        # Source the override
        addCallbackScriptPath = os.path.abspath(os.path.join(__file__, "..", "resources", "scripts", "MRS_nodeEditorAddCallback.mel")).replace("\\", "/")
        mel.eval("source \"{}\"".format(addCallbackScriptPath))

        # Install the override
        cmds.scriptedPanelType("nodeEditorPanel", e=True, addCallback="MRS_NodeEditor_AddCallback")


def _disableAutomaticSetup():
    """Disable automatic installation of Node Editor Extensions upon creating a new Node Editor panel."""
    cmds.optionVar(intValue=(constants.NEAC_OPTIONVAR[0], 0))


def _installToPanel(nodeEditorPanelName, force=False):
    nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)

    try:
        nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
    except UI_EXC.MayaUILookupError:
        log.info("{}: Node Editor panel does not have an editor. Aborting installation".format(nodeEditorPanelName))
        return

    isPrimaryNodeEditor = cmds.nodeEditor(nodeEditor.objectName(), q=True, primary=True)
    nodeEditorMenuBar = UI_NODE_EDITOR.getNodeEditorMenuBarFromPanel(nodeEditorPanel)
    nodeEditorIconBar = UI_NODE_EDITOR.getNodeEditorIconBarFromPanel(nodeEditorPanel)

    # --- Menu ---
    menu_setup.install(nodeEditorMenuBar)

    # --- Layout Tool ---
    if isPrimaryNodeEditor:
        layoutTool_setup.install(parent=nodeEditorIconBar, force=force)

    # --- Import Export Tool ---
    importExportTool_setup.install(parent=nodeEditorIconBar, force=force)

    # --- Align Node Tool ---
    alignNodeTool_setup.install(parent=nodeEditorIconBar, force=force)

    # --- Background Optimisation Manager ---
    if cmds.optionVar(q=constants.OB_OPTIONVAR[0]):
        backgroundOptimisation_manager.install(parent=nodeEditor, force=force)

    # --- Shake To Disconnect Manager ---
    if cmds.optionVar(q=constants.STD_OPTIONVAR[0]):
        shakeToDisconnect_manager.install(parent=nodeEditor, force=force)

    # --- Scene Activation Manager ---
    sceneActivation_manager.install(parent=nodeEditor, force=force)


def _uninstallFromPanel(nodeEditorPanelName):
    nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)

    try:
        nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
    except UI_EXC.MayaUILookupError:
        log.info("{}: Node Editor panel does not have an editor. Aborting uninstallation".format(nodeEditorPanelName))
        return

    isPrimaryNodeEditor = cmds.nodeEditor(nodeEditor.objectName(), q=True, primary=True)
    nodeEditorMenuBar = UI_NODE_EDITOR.getNodeEditorMenuBarFromPanel(nodeEditorPanel)
    nodeEditorIconBar = UI_NODE_EDITOR.getNodeEditorIconBarFromPanel(nodeEditorPanel)

    # --- Menu ---
    tool_manager.uninstall(namespace=menu_setup.TOOL_NAMESPACE, name=menu_setup.TOOL_NAME, parent=nodeEditorMenuBar)

    # --- Layout Tool ---
    if isPrimaryNodeEditor:
        tool_manager.uninstall(namespace=layoutTool_setup.TOOL_NAMESPACE, name=layoutTool_setup.TOOL_NAME, parent=nodeEditorIconBar)

    # --- Import Export Tool ---
    tool_manager.uninstall(namespace=importExportTool_setup.TOOL_NAMESPACE, name=importExportTool_setup.TOOL_NAME, parent=nodeEditorIconBar)

    # --- Align Node Tool ---
    tool_manager.uninstall(namespace=alignNodeTool_setup.TOOL_NAMESPACE, name=alignNodeTool_setup.TOOL_NAME, parent=nodeEditorIconBar)

    # --- Background Optimisation Manager ---
    tool_manager.uninstall(namespace=backgroundOptimisation_manager.TOOL_NAMESPACE, name=backgroundOptimisation_manager.TOOL_NAME, parent=nodeEditor)

    # --- Shake To Disconnect Manager ---
    tool_manager.uninstall(namespace=shakeToDisconnect_manager.TOOL_NAMESPACE, name=shakeToDisconnect_manager.TOOL_NAME, parent=nodeEditor)

    # --- Scene Activation Manager ---
    tool_manager.uninstall(namespace=sceneActivation_manager.TOOL_NAMESPACE, name=sceneActivation_manager.TOOL_NAME, parent=nodeEditor)
