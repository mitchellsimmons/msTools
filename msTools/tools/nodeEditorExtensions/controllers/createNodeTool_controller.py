import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2
from maya.app.general import nodeEditor as maya_nodeEditor
from maya import cmds

from msTools.vendor.Qt import QtCore, QtGui

from msTools.core.maya import callback_utils as CALLBACK
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR


class CreateNodeToolController(QtCore.QObject):

    nodeCreated = QtCore.Signal()

    def __init__(self, proxyModel, parent=None):
        super(CreateNodeToolController, self).__init__(parent=parent)

        self._proxyModel = proxyModel
        self._cursorPos_global = QtGui.QCursor.pos()

    def setModelFilter(self, filterPattern):
        previousFilterPattern = self._proxyModel.filterRegExp().pattern()
        self._proxyModel.setFilterRegExp(QtCore.QRegExp(filterPattern, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString))

        # NOTE: Sorting of the QSortFilterProxyModel is optimised to ignore rows which have already been sorted
        # Therefore when the previous filter pattern is suffixed, existing rows will not be resorted (we need to trigger sorting manually when this happens)
        # This is necessary because our sorting algorithm implements different behaviour for rows which start with the pattern vs rows which contain the pattern
        if previousFilterPattern and filterPattern.startswith(previousFilterPattern):
            self._proxyModel.invalidate()

    def createNode(self, nodeType):
        nodeEditor = UI_NODE_EDITOR.getCurrentNodeEditor()
        isAddNewNodesEnabled = cmds.nodeEditor(nodeEditor.objectName(), q=True, addNewNodes=True)

        # Temporarily override the user's setting whilst creating
        cmds.nodeEditor(nodeEditor.objectName(), e=True, addNewNodes=True)

        # Maya uses the nodeEditor module when creating nodes in the nodeEditor (it has special create commands for certain node types)
        try:
            nodes, _ = CALLBACK.getNodesCreatedBy(maya_nodeEditor.createNode, nodeType)
        except Exception:
            raise
        finally:
            cmds.nodeEditor(nodeEditor.objectName(), e=True, addNewNodes=isAddNewNodesEnabled)

        if len(nodes) == 0:
            log.info("Failed to create node for node type: {}".format(nodeType))
            return

        self.nodeCreated.emit()

        # Allow the node to enter the node editor before positioning it
        nodeEditor.setUpdatesEnabled(False)
        cmds.evalDeferred(lambda: self._positionNodeAndRestoreUpdates(nodes[0]))

    def _positionNodeAndRestoreUpdates(self, node):
        nodeEditor = UI_NODE_EDITOR.getCurrentNodeEditor()

        try:
            self._positionNode(node, nodeEditor)
        except Exception:
            raise
        finally:
            nodeEditor.setUpdatesEnabled(True)

    def _positionNode(self, node, nodeEditor):
        """Position a node under the cursor using Graphviz coordinates."""
        nodeName = om2.MFnDependencyNode(node).name()
        graphicsView = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        viewport = graphicsView.viewport()

        # Determine the cursor position in QGraphicsView viewport coordinates
        cursorPos_viewport = viewport.mapFromGlobal(self._cursorPos_global)
        # The QGraphicsView is used to map viewport coordinates to QGraphicsScene coordinates
        cursorPos_scene = graphicsView.mapToScene(cursorPos_viewport)
        # Offset the position so that the node title is centered on the cursor
        nodePos_scene = QtCore.QPointF(cursorPos_scene.x() - 67.5, cursorPos_scene.y())
        # Determine the node position in Graphviz coordinates
        nodePos_graphviz = nodePos_scene * UI_NODE_EDITOR.GRAPHICS_SCENE_TO_GRAPHVIZ_TRANSFORM

        # Generate a plain formatted DOT language graph description
        graph = "graph {graphScale} {graphWidth} {graphHeight}\nnode {nodeName} {nodeX} {nodeY} {nodeWidth} {nodeHeight}\nstop".format(
            graphScale=1.0, graphWidth=0.0, graphHeight=0.0,
            nodeName=nodeName, nodeX=nodePos_graphviz.x(), nodeY=nodePos_graphviz.y(), nodeWidth=0.0, nodeHeight=0.0)

        cmds.nodeEditor(nodeEditor.objectName(), e=True, dotFormat=graph)
