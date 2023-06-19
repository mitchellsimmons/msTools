"""
Provides read and write access for metadata associations between the internal `layoutTool_associations` registry and the current "MayaNodeEditorSavedTabsInfo" node.

----------------------------------------------------------------

Interface
---------

    The module follows the same principles as Maya's `adsk::Data::Accessor` class which is used to read and write `adsk::Data::Associations` data for a file.
    The concept has been slightly abstracted as our initial implementation was using scene-level metadata but has since been changed to node-level.
    The `layoutTool_associations` module contains a registry of internal metadata relating to entities created by the `layoutTool_controller`.
    The controller ensures metadata is only written to the "MayaNodeEditorSavedTabsInfo" node upon saving since we do not want unsaved changes to persist.

----------------------------------------------------------------

Considerations
--------------

    The MEL metadata commands provide a simple interface into Maya's `adsk::Data` library however they are limited in a few crucial aspects.
    As far as I'm aware there is no way to remove an `adsk::Stream` from scene/node-level `adsk::Associations` using the MEL commands.

    We must take care when writing metadata to the "MayaNodeEditorSavedTabsInfo" node due to the special behaviour Maya implements for this node.
    This node is created/replaced upon saving the file and upon closing the Node Editor.
    Therefore we must intercept the creation of this node if we want to write metadata upon saving the scene.
    Otherwise our data would be written to a node which was then immediately removed and replaced.

----------------------------------------------------------------
"""

import functools
import json
import logging
import re
import uuid
log = logging.getLogger(__name__)

from maya import cmds, mel
from maya.api import OpenMaya as om2

from msTools.core.maya import name_utils as NAME
from msTools.tools import callback_manager
from msTools.tools.nodeEditorExtensions.metadata import layoutTool_associations


# ----------------------------------------------------------------------------
# --- Constants ---
# ----------------------------------------------------------------------------

# Eg. mrs_NodeBox
PLUGIN_COMMAND_FORMAT = "mrs_{qualifier}"
# Eg. mrs_nodeEditor_NodeBox_channel
CHANNEL_FORMAT = "mrs_nodeEditor_{qualifier}_channel"
# Eg. mrs_nodeEditor_NodeBox_structure
STRUCTURE_FORMAT = "mrs_nodeEditor_{qualifier}_structure"
# Eg. mrs_nodeEditor_tab0_NodeBox_3b74182e65f84669adde96466d781909_stream
STREAM_FORMAT = "mrs_nodeEditor_tab{index}_{qualifier}_{UUID}_stream"


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

if "_NODE_ADDED_CALLBACK" not in globals():
    log.debug("Initializing global: _NODE_ADDED_CALLBACK")
    global _NODE_ADDED_CALLBACK
    _NODE_ADDED_CALLBACK = None


# ----------------------------------------------------------------------------
# --- Installation ---
# ----------------------------------------------------------------------------

def isInstalled():
    """Returns:
        :class:`bool`: Whether the `Layout Tool Accessor` is installed.
    """
    return callback_manager.isCallableRegistered(callback_manager.SceneEvent.AfterOpen, read)


def install():
    """Install the `Layout Tool Accessor`.

    - Existing metadata will be read into the internal `layoutTool_associations` registry.
    - Callbacks will be installed to enable automatic reading or clearing of metadata upon `File -> New` and `File -> Open` respectively.
    - Callbacks will be installed to enable automatic writing of metadata from the internal `layoutTool_associations` registry to the `nodeGraphEditorInfo` node.
    """
    log.debug("Installing: Layout Tools Accessor")

    # Metadata should be read upon installing the Accessor with Maya
    # This is the safest option, otherwise we need to rely on the caller also invoking read before write is invoked (which will occur automatically upon saving)
    read()

    # Considering Node Editor data is not affected by imports/references, we do not handle these events
    # - ie. The "MayaNodeEditorSavedTabsInfo" node is not included when importing/referencing

    # Scene new event is registered just to clear `layoutTool_associations`
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterNew, read)
    # Metadata should be read when a file is opened
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterOpen, read)
    # Metadata should always be written upon saving to ensure it persists, however we must wait for the nodeGraphEditorInfo node to be created/replaced
    callback_manager.registerCallable(callback_manager.SceneEvent.BeforeSave, _beforeSave)
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterSave, _afterSave)


def uninstall():
    """Uninstall the `Layout Tool Accessor`.

    - The internal `layoutTool_associations` registry will be cleared.
    - Callbacks that were registered via :func:`install` will be deregistered.
    """
    log.debug("Uninstalling: Layout Tools Accessor")

    layoutTool_associations.clearData()

    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterNew, read)
    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterOpen, read)
    callback_manager.deregisterCallable(callback_manager.SceneEvent.BeforeSave, _beforeSave)
    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterSave, _afterSave)


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _isValidChannelName(channelName):
    """Checks if the channel name has a valid format."""
    tokens = channelName.split("_")

    if not len(tokens) == 4:
        return False

    if not tokens[0] == "mrs":
        return False

    if not tokens[1] == "nodeEditor":
        return False

    if not re.search("^[a-zA-Z]+$", tokens[2]):
        return False

    if not tokens[3] == "channel":
        return False

    return True


def _isValidStructureName(structureName):
    """Checks if the structure name has a valid format."""
    tokens = structureName.split("_")

    if not len(tokens) == 4:
        return False

    if not tokens[0] == "mrs":
        return False

    if not tokens[1] == "nodeEditor":
        return False

    if not re.search("^[a-zA-Z]+$", tokens[2]):
        return False

    if not tokens[3] == "structure":
        return False

    return True


def _isValidStreamName(streamName):
    """Checks if the stream name has a valid format."""
    tokens = streamName.split("_")

    if not len(tokens) == 6:
        return False

    if not tokens[0] == "mrs":
        return False

    if not tokens[1] == "nodeEditor":
        return False

    if not re.search(r"^tab\d+$", tokens[2]):
        return False

    if not re.search(r"^[a-zA-Z]+$", tokens[3]):
        return False

    try:
        uuid.UUID(tokens[4])
    except ValueError:
        return False

    if not tokens[5] == "stream":
        return False

    return True


def _buildPluginCommandName(qualifier):
    """Generates a qualified command name from the `PLUGIN_COMMAND_FORMAT`."""
    return PLUGIN_COMMAND_FORMAT.format(qualifier=qualifier)


def _buildChannelName(qualifier):
    """Generates a qualified channel name from the `CHANNEL_FORMAT`."""
    return CHANNEL_FORMAT.format(qualifier=qualifier)


def _buildStructureName(qualifier):
    """Generates a qualified structure name from the `STRUCTURE_FORMAT`."""
    return STRUCTURE_FORMAT.format(qualifier=qualifier)


def _buildStreamName(index, qualifier, UUID):
    """Generates a qualified stream name from the `STREAM_FORMAT`."""
    return STREAM_FORMAT.format(index=index, qualifier=qualifier, UUID=UUID.hex)


def _parseStreamName(streamName):
    """Extracts interesting data from the given stream name. This includes the index, qualifier and UUID.
    The stream name is assumed to have a format corresponding to `STREAM_FORMAT`.
    """
    nameData = {}
    tokens = streamName.split("_")
    nameData["index"] = int(re.sub("tab", "", tokens[2]))
    nameData["qualifier"] = tokens[3]
    nameData["UUID"] = uuid.UUID(tokens[4])
    return nameData


def _beforeSave():
    """Callback function invoked before saving the scene.
    Responsible for registering the `_nodeAddedCallback` in order to intercept the creation of the "MayaNodeEditorSavedTabsInfo" node.
    """
    global _NODE_ADDED_CALLBACK
    _NODE_ADDED_CALLBACK = om2.MDGMessage.addNodeAddedCallback(_nodeAddedCallback, "nodeGraphEditorInfo")


def _afterSave():
    """Callback function invoked after saving the scene.
    Responsible for deregistering the `_nodeAddedCallback` that was registered by the `_beforeSave` callback.
    """
    global _NODE_ADDED_CALLBACK

    if _NODE_ADDED_CALLBACK is not None:
        om2.MMessage.removeCallback(_NODE_ADDED_CALLBACK)
        _NODE_ADDED_CALLBACK = None


def _nodeAddedCallback(nodeObj, *clientData):
    """Callback function invoked during scene save, directly after the "MayaNodeEditorSavedTabsInfo" node is created.
    Responsible for writing metadata from the internal `layoutTool_associations` registry to the node so that it can be saved with the scene.
    """
    if nodeObj.apiType() == om2.MFn.kNodeGraphEditorInfo and NAME.getNodePartialName(nodeObj) == "MayaNodeEditorSavedTabsInfo":
        write()


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def read():
    """Reads metadata from the "MayaNodeEditorSavedTabsInfo" node and stores the parsed values in the internal `layoutTool_associations` registry.

    This function is called upon installing the `Layout Tool` and will be called for any `File -> New` and `File -> Open` if `install` has been called.
    The `layoutTool_controller` is thereafter responsible for updating the metadata registry.
    """
    # Maya produces warnings when calling the `getMetadata` command with nodes selected (we will need to temporarily clear the selection to prevent these warnings)
    sel = om2.MGlobal.getActiveSelectionList()
    om2.MGlobal.clearSelectionList()

    layoutTool_associations.clearData()

    try:
        allStreams = cmds.getMetadata("MayaNodeEditorSavedTabsInfo", listStreamNames=True)
    except (RuntimeError, ValueError):
        # There is no metadata on this node (RuntimeError) or the node does not exist (ValueError) so return
        return

    for streamName in allStreams:
        if _isValidStreamName(streamName):
            nameData = _parseStreamName(streamName)
            memberData = {}

            structureName = _buildStructureName(nameData["qualifier"])
            memberNames = cmds.dataStructure(name=structureName, q=True, listMemberNames=True)

            for memberName in memberNames:
                # There is a custom plugin command registered for each qualifier
                pluginCommandName = _buildPluginCommandName(nameData["qualifier"])
                memberData[memberName] = mel.eval(pluginCommandName + " -q -" + memberName + " -streamName " + streamName)

            kwargs = memberData
            kwargs.update(nameData)
            layoutTool_associations.registerData(**kwargs)

    layoutTool_associations.setStaleState(False)
    cmds.evalDeferred(functools.partial(om2.MGlobal.setActiveSelectionList, sel))


def write():
    """Writes metadata  from the internal `layoutTool_associations` registry to the "MayaNodeEditorSavedTabsInfo" node.

    This function will be invoked during scene save if `install` has been called."""
    sel = om2.MGlobal.getActiveSelectionList()
    om2.MGlobal.clearSelectionList()

    internalStreamNames = set()
    existingStreamNames = set()

    # Find all Streams which relate to the Layout Manager and have been written to the current "MayaNodeEditorSavedTabsInfo" node
    try:
        allStreamNames = cmds.getMetadata("MayaNodeEditorSavedTabsInfo", listStreamNames=True)
    except RuntimeError:
        allStreamNames = []
    except ValueError:
        # It is probably best not to obstruct the save process even if we get unexpected behaviour
        log.error("`layoutTool_accessor.write()` was called without an existing \"MayaNodeEditorSavedTabsInfo\" node. Unable to write metadata for the `Node Editor Layout Tool`.")
        return

    for streamName in allStreamNames:
        if _isValidStreamName(streamName):
            existingStreamNames.add(streamName)

    # If any set of internal member data associates with an existing Stream, sync the internal data with the written data
    # If there is no Stream that associates with a set of internal member data, create a new stream using the internal data
    for index, channelData in layoutTool_associations.getData().iteritems():
        for qualifier, streamData in channelData.iteritems():
            for UUID, memberData in streamData.iteritems():
                streamName = _buildStreamName(index, qualifier, UUID)
                internalStreamNames.add(streamName)

                pluginCommandName = _buildPluginCommandName(qualifier)
                cmd = pluginCommandName + " -streamName " + streamName

                for memberName, memberValue in memberData.iteritems():
                    if isinstance(memberValue, (list, tuple)):
                        if isinstance(memberValue[0], basestring):
                            cmd += " -{} {}".format(memberName, " ".join(json.dumps(element) for element in memberValue))
                        else:
                            cmd += " -{} {}".format(memberName, " ".join(str(element) for element in memberValue))
                    elif isinstance(memberValue, basestring):
                        cmd += " -{} {}".format(memberName, json.dumps(memberValue))
                    else:
                        cmd += " -{} {}".format(memberName, memberValue)

                if streamName in existingStreamNames:
                    cmd += " -e"

                mel.eval(cmd)

    # Delete any existing Streams which no longer associate with the internal data
    for streamName in existingStreamNames:
        if streamName not in internalStreamNames:
            nameData = _parseStreamName(streamName)
            pluginCommandName = _buildPluginCommandName(nameData["qualifier"])
            mel.eval(pluginCommandName + " -e -delete 1 -streamName " + streamName)

    layoutTool_associations.setStaleState(False)
    cmds.evalDeferred(functools.partial(om2.MGlobal.setActiveSelectionList, sel))
