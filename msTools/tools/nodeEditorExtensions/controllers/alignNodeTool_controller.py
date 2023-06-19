from msTools.vendor.Qt import QtCore

from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import graphicsItem_utils as QT_GRAPHICS_ITEM


class AlignNodeToolController(QtCore.QObject):
    """An interface for aligning graphical node items in the Maya Node Editor.

    Designed to encapsulate the logic for the `AlignNodeToolWidget`.
    """

    def __init__(self, parent=None):
        super(AlignNodeToolController, self).__init__(parent=parent)

    def alignItemsLeft(self):
        QT_GRAPHICS_ITEM.alignLeft(self._getSelectedItems())

    def alignItemsRight(self):
        QT_GRAPHICS_ITEM.alignRight(self._getSelectedItems())

    def alignItemsTop(self):
        QT_GRAPHICS_ITEM.alignTop(self._getSelectedItems())

    def alignItemsBottom(self):
        QT_GRAPHICS_ITEM.alignBottom(self._getSelectedItems())

    def alignItemsHCenter(self):
        QT_GRAPHICS_ITEM.alignHCenter(self._getSelectedItems())

    def alignItemsVCenter(self):
        QT_GRAPHICS_ITEM.alignVCenter(self._getSelectedItems())

    def distributeItemsHGaps(self):
        QT_GRAPHICS_ITEM.distributeHGaps(self._getSelectedItems())

    def distributeItemsVGaps(self):
        QT_GRAPHICS_ITEM.distributeVGaps(self._getSelectedItems())

    def _getSelectedItems(self):
        nodeEditor = UI_NODE_EDITOR.getCurrentNodeEditor()
        nodeItems = UI_NODE_EDITOR.getCurrentNodeEditorGraphicsItemsFromEditor(nodeEditor, itemType=UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE)
        selectedNodeItems = [nodeItem for nodeItem in nodeItems if nodeItem.isSelected()]
        return selectedNodeItems
