import functools
import json
import logging
import uuid
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.vendor.Qt import QtCore, QtGui

from msTools.core.maya import om_utils as OM
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions import layoutTool_setup
from msTools.tools.nodeEditorExtensions.views import layoutTool_items
from msTools.tools.nodeEditorExtensions.controllers import layoutTool_controller


class ImportExportToolController(QtCore.QObject):
    """An interface for translating between graphical items within the Maya Node Editor and their corresponding serialisations.

    Designed to encapsulate the logic for the `ImportExportToolWidget`.
    """

    def __init__(self, parent=None):
        super(ImportExportToolController, self).__init__(parent=parent)

    # --- Public ----------------------------------------------------------------------------------------

    @property
    def nodeEditor(self):
        """Returns the primary Node Editor."""
        return UI_NODE_EDITOR.getPrimaryNodeEditor()

    @property
    def nodeEditorGraphicsView(self):
        """Returns the primary Node Editor graphics view."""
        return UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(self.nodeEditor)

    @property
    def nodeEditorGraphicsScene(self):
        """Returns the primary Node Editor graphics scene."""
        return UI_NODE_EDITOR.getCurrentNodeEditorGraphicsSceneFromEditor(self.nodeEditor)

    def getVisibleNodeBoxes(self):
        """Returns existing `NodeBox` items for the current Node Editor tab."""
        return [item for item in self.nodeEditorGraphicsView.items() if item.type() == layoutTool_items.NodeBoxItem.Type]

    def getVisibleStickies(self):
        """Returns existing `Sticky` items for the current Node Editor tab."""
        return [item for item in self.nodeEditorGraphicsView.items() if item.type() == layoutTool_items.StickyItem.Type]

    def importData(self, filePath=None):
        """Prompt the user or directly provide an existing `.tab` file from which to import and deserialise tab data into the current Node Editor tab.

        Deserialisation involves extracting and translating `JSON` data into `QGraphicsItems`. Translation may occur for:

        - Default Maya dependency nodes.
        - Custom `Layout Tool` items including `NodeBoxItems` and StickyItems`.

        If one ore more default Maya nodes from the serialisation do not exist within the current scene, the user will be prompted on whether to continue or abort.

        Args:
            filePath(:class:`basestring`, optional): An existing `.tab` file from which to import and deserialise tab data into the current Node Editor tab.
                Defaults to :data:`None` - Prompts the user to locate an existing `tab` file via a file dialog.

        Raises:
            :exc:`~exceptions.ValueError`: If ``filePath`` is given but is not a `.tab` file.
            :exc:`~exceptions.IOError`: If ``filePath`` is given but does not exist.
        """
        if filePath is None:
            filePaths = cmds.fileDialog2(fileFilter="*.tab", fileMode=1, dialogStyle=2)

            if filePaths is None:
                return
            else:
                filePath = filePaths[0]
        elif not filePath.endswith(".tab"):
            raise ValueError("{}: File path does not reference a `.tab` file".format(filePath))

        with open(filePath, 'r') as f:
            data = json.load(f)

        allNodeData = data["DG"]
        allNodeBoxData = data["NodeBox"]
        allStickyData = data["Sticky"]

        foundNodes = []
        missingNodes = []

        for nodeName, nodeData in allNodeData.iteritems():
            try:
                cmds.nodeEditor(self.nodeEditor.objectName(), e=True, addNode=nodeName)
            except RuntimeError:
                missingNodes.append(nodeName)
            else:
                foundNodes.append(nodeName)

        if missingNodes:
            response = cmds.layoutDialog(uiScript=functools.partial(self._prompt, missingNodes), title="Import Tab")

            if response == "dismiss" or response == "Abort":
                return

        for nodeName in foundNodes:
            cmds.evalDeferred(functools.partial(self._loadNode, nodeName=nodeName, nodeData=allNodeData[nodeName]))

        layoutToolWidgets = list(tool_manager.iterInstalled(namespace=layoutTool_setup.TOOL_NAMESPACE, name=layoutTool_setup.TOOL_NAME))

        if len(layoutToolWidgets) != 1:
            log.warning("Unable to import `LayoutTool` data since a single `LayoutToolWidget` instance could not be identified")
            return

        layoutToolController = layoutToolWidgets[0].findChild(layoutTool_controller.LayoutToolController)

        for UUID, nodeBoxData in allNodeBoxData.iteritems():
            layoutToolController.createNodeBox(
                UUID=uuid.UUID(UUID), title=nodeBoxData["title"],
                rect=QtCore.QRect(nodeBoxData["rect"][0], nodeBoxData["rect"][1], nodeBoxData["rect"][2], nodeBoxData["rect"][3]),
                color=QtGui.QColor(nodeBoxData["color"][0], nodeBoxData["color"][1], nodeBoxData["color"][2], nodeBoxData["color"][3]))

        for UUID, stickyData in allStickyData.iteritems():
            layoutToolController.createSticky(
                UUID=uuid.UUID(UUID), title=stickyData["title"], text=stickyData["text"],
                rect=QtCore.QRect(stickyData["rect"][0], stickyData["rect"][1], stickyData["rect"][2], stickyData["rect"][3]),
                color=QtGui.QColor(stickyData["color"][0], stickyData["color"][1], stickyData["color"][2], stickyData["color"][3]))

    def exportData(self, filePath=None):
        """Prompt the user or directly provide a `.tab` file which will be used to export a serialisation of relevant data from the current Node Editor tab.

        Serialisation involves translating object data for `QGraphicsItems` into a `JSON` format. Translation will occur for:

        - Default Maya dependency nodes.
        - Custom `Layout Tool` items including `NodeBoxItems` and StickyItems`.

        Object data may include position, geometry, style, object identifiers such as names or `UUIDs`.

        Args:
            filePath(:class:`basestring`, optional): A new or existing `.tab` file which will be used to export a serialisation of relevant data from the current Node Editor tab.
                Defaults to :data:`None` - Prompts the user to specify a new or existing `tab` file via a file dialog.

        Raises:
            :exc:`~exceptions.ValueError`: If ``filePath`` is given but is not a `.tab` file.
            :exc:`~exceptions.IOError`: If ``filePath`` is given but its leaf directory does not exist.
        """
        if filePath is None:
            filePaths = cmds.fileDialog2(fileFilter="*.tab", fileMode=0, dialogStyle=2)

            if filePaths is None:
                return
            else:
                filePath = filePaths[0]
        elif not filePath.endswith(".tab"):
            raise ValueError("{}: File path does not reference a `.tab` file".format(filePath))

        data = {"DG": {}, "NodeBox": {}, "Sticky": {}}
        nodeNames = cmds.nodeEditor(self.nodeEditor.objectName(), getNodeList=True, q=True)
        nodeBoxItems = self.getVisibleNodeBoxes()
        stickyItems = self.getVisibleStickies()

        if nodeNames is not None:
            for nodeName in nodeNames:
                node = OM.getNodeByName(nodeName)
                nodeFn = om2.MFnDependencyNode(node)

                # Only export data for writable, non-default nodes (since these are not included with an export)
                if nodeFn.canBeWritten() and not nodeFn.isDefaultNode:
                    try:
                        nodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(node, self.nodeEditorGraphicsScene)
                    except UI_EXC.MayaUILookupError:
                        log.warning("Unable to identify a `QGraphicsItem` for current Node Editor node: {!r}".format(nodeName))
                    else:
                        data["DG"][nodeName] = {"positionX": nodeItem.x(), "positionY": nodeItem.y()}

        for nodeBoxItem in nodeBoxItems:
            nodeBoxRect = nodeBoxItem.sceneBoundingRect()
            data["NodeBox"][nodeBoxItem.UUID.hex] = {
                "rect": (nodeBoxRect.x(), nodeBoxRect.y(), nodeBoxRect.width(), nodeBoxRect.height()),
                "color": (nodeBoxItem.color.red(), nodeBoxItem.color.green(), nodeBoxItem.color.blue(), nodeBoxItem.color.alpha()),
                "title": nodeBoxItem.title}

        for stickyItem in stickyItems:
            stickyRect = stickyItem.sceneBoundingRect()
            data["Sticky"][stickyItem.UUID.hex] = {
                "rect": (stickyRect.x(), stickyRect.y(), stickyRect.width(), stickyRect.height()),
                "color": (stickyItem.color.red(), stickyItem.color.green(), stickyItem.color.blue(), stickyItem.color.alpha()),
                "title": stickyItem.title, "text": stickyItem.text}

        with open(filePath, 'w') as f:
            json.dump(data, f)

    # --- Private ----------------------------------------------------------------------------------------

    def _loadNode(self, nodeName, nodeData, _runs=0):
        # Track the level of recursion
        _runs += 1
        if _runs > 100:
            log.error("Could not find a `QGraphicsItem` for {!r}".format(nodeName))
            return

        node = OM.getNodeByName(nodeName)

        try:
            nodeItem = UI_NODE_EDITOR.getGraphicsItemFromNode(node, self.nodeEditorGraphicsScene)
        except UI_EXC.MayaUILookupError:
            cmds.evalDeferred(functools.partial(self._loadNode, nodeName, nodeData, _runs=_runs))
            return
        else:
            nodeItem.setX(nodeData["positionX"])
            nodeItem.setY(nodeData["positionY"])

    def _prompt(self, missingNodes):
        formLayout_outer = cmds.setParent(q=True)

        cmds.formLayout(formLayout_outer, e=True, width=500, height=315)

        # The top border gets cutoff (fix applied later)
        tabLayout_main = cmds.tabLayout(tabsVisible=False)

        # Attach the tabLayout at the given offsets
        cmds.formLayout(formLayout_outer, e=True,
                        attachForm=[
                            (tabLayout_main, "top", 7),
                            (tabLayout_main, "left", 7),
                            (tabLayout_main, "bottom", 40),  # Offset (7) + button height (25) + button offset (7)
                            (tabLayout_main, "right", 7)])

        formLayout_inner = cmds.formLayout()

        scrollLayout_main = cmds.scrollLayout(childResizable=True)

        # Attach the scroll layout at the given offsets
        cmds.formLayout(formLayout_inner, e=True,
                        attachForm=[
                            (scrollLayout_main, "top", 7),
                            (scrollLayout_main, "left", 7),
                            (scrollLayout_main, "bottom", 7),
                            (scrollLayout_main, "right", 7)])

        cmds.columnLayout(adjustableColumn=True, rowSpacing=7)

        cmds.text(label="The following nodes could not be found.\nHow would you like to proceed?")

        cmds.frameLayout(label="Missing Nodes", collapsable=True, backgroundShade=True, marginHeight=7, marginWidth=7)

        cmds.columnLayout(adjustableColumn=True, rowSpacing=7)

        msg = ""
        for missingNode in missingNodes:
            msg += missingNode + "\n"
        cmds.scrollField(height=170, editable=False, text=msg)

        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        formLayout_bottomButtons = cmds.formLayout(numberOfDivisions=2)
        button_skip = cmds.button(height=25, label="Skip",
                                  command='cmds.layoutDialog( dismiss="Skip" )')
        button_abort = cmds.button(height=25, label="Abort",
                                   command='cmds.layoutDialog( dismiss="Abort" )')

        # Attach the buttons at the given offsets
        cmds.formLayout(formLayout_bottomButtons, e=True,
                        attachPosition=[
                            (button_skip, "left", 0, 0),
                            (button_skip, "right", 2, 1),
                            (button_abort, "left", 2, 1),
                            (button_abort, "right", 0, 2)])

        # Attach the form layout at the given offsets
        cmds.formLayout(formLayout_outer, e=True,
                        attachForm=[
                            (formLayout_bottomButtons, "left", 7),
                            (formLayout_bottomButtons, "bottom", 7),
                            (formLayout_bottomButtons, "right", 7)])

        cmds.setParent("..")

        # Trick to get the top border back
        tabLayout_topFix = cmds.tabLayout(borderStyle="top", tabsVisible=False)
        cmds.formLayout(formLayout_outer, e=True,
                        attachForm=[
                            (tabLayout_topFix, "top", 7),
                            (tabLayout_topFix, "left", 7),
                            (tabLayout_topFix, "right", 7)])
