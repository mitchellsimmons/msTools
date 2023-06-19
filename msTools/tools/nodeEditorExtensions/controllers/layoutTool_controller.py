import collections
import functools
import logging
import os
log = logging.getLogger(__name__)

from maya import cmds, mel

from msTools.vendor.Qt import QtCore, QtGui, QtWidgets, QtCompat

from msTools.core.maya import exceptions as EXC
from msTools.core.maya import dg_utils as DG
from msTools.core.maya import om_utils as OM
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import graphicsItem_utils as QT_GRAPHICS_ITEM
from msTools.coreUI.qt import widget_utils as QT_WIDGET
from msTools.tools import callback_manager
from msTools.tools.nodeEditorExtensions.views import layoutTool_items
from msTools.tools.nodeEditorExtensions.metadata import layoutTool_accessor
from msTools.tools.nodeEditorExtensions.metadata import layoutTool_associations


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

if "_IS_SCENE_OPENING" not in globals():
    log.debug('Initializing global: _IS_SCENE_OPENING')
    _IS_SCENE_OPENING = False


# ----------------------------------------------------------------------------
# --- Callbacks ---
# ----------------------------------------------------------------------------

def _setIsSceneOpening(state):
    global _IS_SCENE_OPENING
    _IS_SCENE_OPENING = state


def _installCallbacks():
    callback_manager.registerCallable(callback_manager.SceneEvent.BeforeOpen, functools.partial(_setIsSceneOpening, True))
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterOpen, functools.partial(_setIsSceneOpening, False))
    callback_manager.registerCallable(callback_manager.SceneEvent.BeforeNew, functools.partial(_setIsSceneOpening, True))
    callback_manager.registerCallable(callback_manager.SceneEvent.AfterNew, functools.partial(_setIsSceneOpening, False))


def _uninstallCallbacks():
    callback_manager.deregisterCallable(callback_manager.SceneEvent.BeforeOpen, functools.partial(_setIsSceneOpening, True))
    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterOpen, functools.partial(_setIsSceneOpening, False))
    callback_manager.deregisterCallable(callback_manager.SceneEvent.BeforeNew, functools.partial(_setIsSceneOpening, True))
    callback_manager.deregisterCallable(callback_manager.SceneEvent.AfterNew, functools.partial(_setIsSceneOpening, False))


# ----------------------------------------------------------------------------
# --- Controller ---
# ----------------------------------------------------------------------------

class LayoutToolController(QtCore.QObject):
    """An interface for creating `NodeBox` and `Sticky` items in the primary Node Editor and managing their metadata.

    Designed to encapsulate the logic for the `LayoutToolWidget`.

    Metadata:

        Item metadata is registered to a global variable within the `layoutTool_associations` module.
        When an item is created, deleted or modified, the `layoutTool_associations` registry will be updated with the relevant changes.
        Signals for each item are connected to the `layoutTool_associations` interface to ensure metadata updates occur automatically.
        When the scene is saved, the `layoutTool_accessor` is responsible for writing metadata from the registry to the current "MayaNodeEditorSavedTabsInfo" node.

    Item Removal:

        Whenever a `NodeBox` or `Sticky` item is created this interface will ensure an event filter has been installed on the current `QGraphicsScene`.
        One of the responsibilities of this event filter is to listen for kepresses and signal when an item should be deleted.

    Limitations:

        Whenever a Node Editor bookmark is selected, the `QGraphicsScene` of the current tab will be replaced and all native items will be reloaded.
        Because our `NodeBox` and `Sticky` items are non-native, we must track scene changes and manually reload items.
        This essentially means the user will always see the same items no matter which bookmark is selected.
        Mitigation of scene changes is applied to all removal actions, meaning:

        - Items will be automatically reloaded if the user accidentally removes a hidden container node from the current `QGraphicsScene`.
        - It is necessary to implement an override of the `NodeEditorGraphClearGraph` MEL procedure to intercept clearing events and prevent items from being reloaded.
    """

    _CLEAR_GRAPH_SCRIPT_PATH = os.path.abspath(os.path.join(__file__, "..", "..", "resources", "scripts", "MRS_nodeEditorGraphClearCallback.mel")).replace("\\", "/")

    # Always draw Sticky items on top of NodeBox items
    NODEBOX_CONTAINER_ZVALUE = 10
    STICKY_CONTAINER_ZVALUE = 11

    def __init__(self, parent=None):
        super(LayoutToolController, self).__init__(parent=parent)

        # Ensure the `layoutTool_accessor` is installed with Maya (ie. metadata read for the current scene and scene open callback registered)
        # The `layoutTool_accessor` must not read metadata on subsequent instantiations, otherwise the internal `layoutTool_associations` registry will be reset
        if not layoutTool_accessor.isInstalled():
            layoutTool_accessor.install()

        # Load metadata for the current tab (initialisation is deferred, therefore the `currentIndex` is assumed valid)
        self._tabChangeQueue = collections.deque([], maxlen=1)
        self._queueLoadTabMetadata(self.currentIndex)

        # We are tracking when a scene is opening to make the _validateItem/_removeTabMetadata methods more robust
        _installCallbacks()

        # Link the Node Editor to the `layoutTool_associations` registry
        self._connectNodeEditor()

        # Ensure items are removed before the Node Editor graph is cleared
        mel.eval("source \"{}\"".format(LayoutToolController._CLEAR_GRAPH_SCRIPT_PATH))

    # --- Public ----------------------------------------------------------------------------------------

    @property
    def nodeEditor(self):
        """Returns the primary Node Editor."""
        return UI_NODE_EDITOR.getPrimaryNodeEditor()

    @property
    def nodeEditorPanel(self):
        """Returns the primary Node Editor panel."""
        return UI_NODE_EDITOR.getNodeEditorPanelFromDescendant(self.nodeEditor)

    @property
    def nodeEditorTabBar(self):
        """Returns the primary Node Editor tab bar."""
        return UI_NODE_EDITOR.getNodeEditorTabBarFromEditor(self.nodeEditor)

    @property
    def nodeEditorPageArea(self):
        """Returns the primary Node Editor page area."""
        return UI_NODE_EDITOR.getNodeEditorPageAreaFromEditor(self.nodeEditor)

    @property
    def nodeEditorGraphicsView(self):
        """Returns the current graphics view of the primary Node Editor."""
        return UI_NODE_EDITOR.getCurrentNodeEditorGraphicsViewFromEditor(self.nodeEditor)

    @property
    def nodeEditorGraphicsScene(self):
        """Returns the current graphics scene of the primary Node Editor."""
        return UI_NODE_EDITOR.getCurrentNodeEditorGraphicsSceneFromEditor(self.nodeEditor)

    @property
    def tabCount(self):
        """Returns the number of tabs for the primary Node Editor."""
        # We use the `QStackedWidget` to get the tab count because the `QTabBar`/`QTabWidget` count decrements when a tab is being dragged
        return self.nodeEditorPageArea.count()

    @property
    def currentIndex(self):
        """Returns the current index of the primary Node Editor."""
        # We use the `QStackedWidget` to get the current index because it is possible to select the last "Add a new tab" button for the `QTabBar`/`QTabWidget` with `ctrl + tab`
        return self.nodeEditorPageArea.currentIndex()

    def createNodeBox(self, UUID=None, rect=None, color=None, title=None, register=True):
        """Loads the `mrs_NodeBoxContainer` type node into the current tab of the Node Editor then creates a child `NodeBox` item using the given data.

        A `NodeBox` can be loaded from metadata by providing parsed values.
        A `NodeBox` can be created from scratch and registered with the internal `layoutTool_associations` metadata by ignoring the function parameters.
        If `rect` is `None`, the `NodeBox` will be sized to encapsulate any selected nodes in the current Node Editor tab.
        """
        if rect is None:
            selectedNodeItems = [item for item in UI_NODE_EDITOR.getCurrentNodeEditorGraphicsItemsFromEditor(
                self.nodeEditor, itemType=UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE) if item.isSelected()]

            if selectedNodeItems:
                rect = QT_GRAPHICS_ITEM.getUnitedBoundingRect(selectedNodeItems)
                rect.adjust(-100, -100 - layoutTool_items.NodeBoxItem.TOP_RECT_HEIGHT, 100, 100)

        callback = functools.partial(self._createNodeBoxAfterLoad, UUID=UUID, rect=rect, color=color, title=title, register=register)
        self._loadContainer(qualifier="NodeBox", callback=callback)

    def createSticky(self, UUID=None, rect=None, color=None, title=None, text=None, register=True):
        """Loads the `mrs_StickyContainer` type node into the current tab of the Node Editor then creates a child `Sticky` item using the given data.

        A `Sticky` can be loaded from metadata by providing parsed values.
        A `Sticky` can be created from scratch and registered with the internal `layoutTool_associations` metadata by ignoring the function parameters.
        """
        if rect is None:
            selectedNodeItems = [item for item in UI_NODE_EDITOR.getCurrentNodeEditorGraphicsItemsFromEditor(
                self.nodeEditor, itemType=UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE) if item.isSelected()]

            if selectedNodeItems:
                rect = QT_GRAPHICS_ITEM.getUnitedBoundingRect(selectedNodeItems)
                rect.adjust(-100, -100 - layoutTool_items.StickyItem.TOP_RECT_HEIGHT, 100, 100)

        callback = functools.partial(self._createStickyAfterLoad, UUID=UUID, rect=rect, color=color, title=title, text=text, register=register)
        self._loadContainer(qualifier="Sticky", callback=callback)

    def getVisibleNodeBoxes(self):
        """Returns existing `NodeBox` items for the current Node Editor tab."""
        return [item for item in self.nodeEditorGraphicsView.items() if item.type() == layoutTool_items.NodeBoxItem.Type]

    def getVisibleStickies(self):
        """Returns existing `Sticky` items for the current Node Editor tab."""
        return [item for item in self.nodeEditorGraphicsView.items() if item.type() == layoutTool_items.StickyItem.Type]

    def clearVisibleItems(self, clearMetadata=False):
        nodeEditorGraphicsScene = self.nodeEditorGraphicsScene
        nodeBoxes = [item for item in nodeEditorGraphicsScene.items() if item.type() == layoutTool_items.NodeBoxItem.Type]
        stickies = [item for item in nodeEditorGraphicsScene.items() if item.type() == layoutTool_items.StickyItem.Type]

        for nodeBox in nodeBoxes:
            nodeBox.sceneChanged.disconnect()
            nodeEditorGraphicsScene.removeItem(nodeBox)

        for sticky in stickies:
            sticky.sceneChanged.disconnect()
            nodeEditorGraphicsScene.removeItem(sticky)

        if clearMetadata:
            try:
                layoutTool_associations.removeTab(self.currentIndex)
            except KeyError:
                # There is no registered metadata for the current tab
                pass

    def clearItems(self, clearMetadata=False):
        """Manually remove all `NodeBox` and `Sticky` items from each `QGraphicsScene` of the primary Node Editor.

        Optionally, clear associated metadata from the internal `layoutTool_associations` registry to prevent items from being reloaded when metadata is next requested.
        """
        for nodeEditorGraphicsScene in UI_NODE_EDITOR.getNodeEditorGraphicsScenesFromEditor(self.nodeEditor):
            nodeBoxes = [item for item in nodeEditorGraphicsScene.items() if item.type() == layoutTool_items.NodeBoxItem.Type]
            stickies = [item for item in nodeEditorGraphicsScene.items() if item.type() == layoutTool_items.StickyItem.Type]

            for nodeBox in nodeBoxes:
                nodeBox.sceneChanged.disconnect()
                nodeEditorGraphicsScene.removeItem(nodeBox)

            for sticky in stickies:
                sticky.sceneChanged.disconnect()
                nodeEditorGraphicsScene.removeItem(sticky)

        if clearMetadata:
            layoutTool_associations.clearData()

    # --- Private : (Setup) ----------------------------------------------------------------------------------------

    def _connectNodeEditor(self):
        self.nodeEditorTabBar.currentChanged.connect(self._queueLoadTabMetadata)
        self.nodeEditorTabBar.tabMoved.connect(self._reindexTabMetadata)
        # We can either use the Node Editor `QTabWidget.tabCloseRequested` signal or the page area `QStackedWidget.widgetRemoved` signal to respond to a closed tab
        # We cannot use the `QTabBar.tabCloseRequested` signal (it is blocked because the `QTabWidget.tabsClosable` property is disabled)
        self.nodeEditorPageArea.widgetRemoved.connect(self._removeTabMetadata)

    # --- Private : (Load / Create) ----------------------------------------------------------------------------------------

    def _loadContainer(self, qualifier, callback, _runs=0):
        """Load a custom node into the primary Node Editor, providing a native parent `QGraphicsItem` for our custom `QGraphicsItem`.

        This node is non-writable and will not be saved with the scene.
        Its associated `QGraphicsItem` may only become available after processing idle events.
        Therefore this function will recursively defer until the `QGraphicsItem` is loaded (necessary for when idle events spawn other idle events).
        """
        # Invocation is deferred, therefore the Node Editor may be closed before idle
        if not QtCompat.isValid(self):
            return

        containerType = "mrs_{}Container".format(qualifier)
        containerName = "mrs_{}Container1".format(qualifier)

        # Track the level of recursion
        _runs += 1
        if _runs > 100:
            log.error("Could not create {} item as parent QGraphicsItem for {} node was not found".format(qualifier, containerName))
            return

        # This step is crucial to prevent crashing as interaction (eg. zooming/panning) can cause the `QGraphicsView` to rebuild
        # Crashing occurs if the view changes whilst we are holding a reference to a `QGraphicsItem` that existed in the old view
        nodeEditorGraphicsView = self.nodeEditorGraphicsView
        nodeEditorGraphicsView.setInteractive(False)

        try:
            containerNode = OM.getNodeByName(containerName)
        except EXC.MayaLookupError:
            containerNode = DG.createNode(containerType)
            DG.renameNode(containerNode, containerName)
            DG.lockNode(containerNode)

        nodeEditorName = self.nodeEditor.objectName()
        cmds.nodeEditor(nodeEditorName, e=True, addNode=containerName)

        try:
            containerItem = UI_NODE_EDITOR.getGraphicsItemFromNode(containerNode, self.nodeEditorGraphicsScene)
        except UI_EXC.MayaUILookupError:
            cmds.evalDeferred(functools.partial(self._loadContainer, qualifier, callback, _runs=_runs))
            return
        else:
            containerItem.setOpacity(0)
            containerItem.setPos(0, 0)
            # Children are always drawn after their parent, therefore we must ensure the parent has a lower stacking order than its siblings (ie. Maya nodes)
            zValue = LayoutToolController.NODEBOX_CONTAINER_ZVALUE if qualifier == "NodeBox" else LayoutToolController.STICKY_CONTAINER_ZVALUE
            containerItem.setZValue(zValue)

            callback(parentItem=containerItem)
        finally:
            # Ensure the default state of the Node Editor is restored
            nodeEditorGraphicsView.setInteractive(True)

    def _prepareScene(self):
        """Install an event filter on the Node Editor's current `QGraphicsScene` which manages scene events relating to layout items.

        It provides support for item removal via the delete or backspace keys.
        It manages the internal item registries of any selected `NodeBoxItem` for mouse press and mouse release events.
        """
        nodeEditorGraphicsScene = self.nodeEditorGraphicsScene

        for child in nodeEditorGraphicsScene.children():
            if isinstance(child, layoutTool_items.LayoutItemSceneFilter):
                child.deleteLater()
            else:
                QT_WIDGET.retain(child)

        nodeEditorGraphicsScene.installEventFilter(layoutTool_items.LayoutItemSceneFilter(parent=nodeEditorGraphicsScene))

    def _createNodeBoxAfterLoad(self, parentItem, UUID=None, rect=None, color=None, title=None, register=True):
        """Create a `NodeBox` item and parent it to the container item.

        Designed to be called from `_loadContainer` via the callback argument to ensure the parent `QGraphicsItem` is available.
        """
        # Create NodeBox item and parent to the container item
        nodeBox = layoutTool_items.NodeBoxItem(UUID=UUID, rect=rect, color=color, title=title, parent=parentItem)

        # Connect NodeBox item
        nodeBox.rectChanged.connect(functools.partial(self._updateItemMetadata, memberName="rect", qualifier="NodeBox", UUID=nodeBox.UUID))
        nodeBox.colorChanged.connect(functools.partial(self._updateItemMetadata, memberName="color", qualifier="NodeBox", UUID=nodeBox.UUID))
        nodeBox.titleChanged.connect(functools.partial(self._updateItemMetadata, memberName="title", qualifier="NodeBox", UUID=nodeBox.UUID))
        nodeBox.sceneChanged.connect(functools.partial(self._reloadItem, qualifier="NodeBox", UUID=nodeBox.UUID))
        nodeBox.deleteKeyPressed.connect(functools.partial(self._removeItem, qualifier="NodeBox", UUID=nodeBox.UUID))

        # Register metadata
        if register:
            nodeBoxRect = nodeBox.sceneBoundingRect()
            layoutTool_associations.registerData(index=self.currentIndex, qualifier="NodeBox", UUID=nodeBox.UUID,
                                                 rect=(nodeBoxRect.x(), nodeBoxRect.y(), nodeBoxRect.width(), nodeBoxRect.height()),
                                                 color=(nodeBox.color.red(), nodeBox.color.green(), nodeBox.color.blue(), nodeBox.color.alpha()),
                                                 title=nodeBox.title)

        # Ensure our items can be deleted
        self._prepareScene()

    def _createStickyAfterLoad(self, parentItem, UUID=None, rect=None, color=None, title=None, text=None, register=True, _runs=0):
        """Create a `Sticky` item and parent it to the container item.

        Designed to be called from `_loadContainer` via the callback argument to ensure the parent `QGraphicsItem` is available.
        """
        sticky = layoutTool_items.StickyItem(UUID=UUID, rect=rect, color=color, title=title, text=text, parent=parentItem)

        sticky.rectChanged.connect(functools.partial(self._updateItemMetadata, memberName="rect", qualifier="Sticky", UUID=sticky.UUID))
        sticky.colorChanged.connect(functools.partial(self._updateItemMetadata, memberName="color", qualifier="Sticky", UUID=sticky.UUID))
        sticky.titleChanged.connect(functools.partial(self._updateItemMetadata, memberName="title", qualifier="Sticky", UUID=sticky.UUID))
        sticky.textChanged.connect(functools.partial(self._updateItemMetadata, memberName="text", qualifier="Sticky", UUID=sticky.UUID))
        sticky.sceneChanged.connect(functools.partial(self._reloadItem, qualifier="Sticky", UUID=sticky.UUID))
        sticky.deleteKeyPressed.connect(functools.partial(self._removeItem, qualifier="Sticky", UUID=sticky.UUID))

        if register:
            stickyRect = sticky.sceneBoundingRect()
            layoutTool_associations.registerData(index=self.currentIndex, qualifier="Sticky", UUID=sticky.UUID,
                                                 rect=(stickyRect.x(), stickyRect.y(), stickyRect.width(), stickyRect.height()),
                                                 color=(sticky.color.red(), sticky.color.green(), sticky.color.blue(), sticky.color.alpha()),
                                                 title=sticky.title, text=sticky.text)

        self._prepareScene()

    def _reloadItem(self, qualifier, UUID):
        """Slot designed for the `sceneChanged` signal of `NodeBox` and `Sticky` items, ensuring they are reloaded when their `QGraphicsScene` changes.

        Items corresponding to the `qualifier` and `UUID` are reloaded from metadata retrieved from the internal `layoutTool_associations` registry.
        Reloading is designed to mitigate removal resulting from actions such as selecting a bookmark.
        """
        if not self.nodeEditorPanel.isAncestorOf(QtWidgets.QApplication.focusWidget()) or _IS_SCENE_OPENING:
            return

        memberMetadata = layoutTool_associations.getData()[self.currentIndex][qualifier][UUID]
        memberMetadata["rect"] = QtCore.QRectF(*memberMetadata["rect"])
        memberMetadata["color"] = QtGui.QColor(*memberMetadata["color"])

        if qualifier == "NodeBox":
            self.createNodeBox(UUID=UUID, register=False, **memberMetadata)
        else:
            self.createSticky(UUID=UUID, register=False, **memberMetadata)

    def _removeItem(self, qualifier, UUID):
        """Slot designed for the `deleteKeyPressed` signal of `NodeBox` and `Sticky` items, ensuring the item and its associated metadata are removed."""
        visibleItems = self.getVisibleNodeBoxes() if qualifier == "NodeBox" else self.getVisibleStickies()

        for visibleItem in visibleItems:
            if visibleItem.UUID == UUID:
                # Ensure the item's sceneChanged signal is disconnected so that it won't be reloaded
                visibleItem.sceneChanged.disconnect()
                self.nodeEditorGraphicsScene.removeItem(visibleItem)

        layoutTool_associations.removeData(self.currentIndex, qualifier, UUID)

    # --- Private : (Metadata) ----------------------------------------------------------------------------------------

    def _queueLoadTabMetadata(self, index):
        """Slot designed for the `currentChanged` signal of the Node Editor `tab bar`, ensuring `NodeBox` and `Sticky` items are loaded at idle after the tab index changes.

        Loading of items is deferred until idle to ensure all tabs have been created.
        Items corresponding to the `index` of the current tab will then be loaded from metadata retrieved from the internal `layoutTool_associations` registry.
        """
        self._tabChangeQueue.append(index)
        cmds.evalDeferred(self._validateAndLoadTabMetadata)

    def _validateAndLoadTabMetadata(self):
        """Translate metadata from the internal `layoutTool_associations` registry into `NodeBox` and `Sticky` items for the primary Node Editor.

        The initial call to this function relies upon the `layoutTool_accessor` having read "MayaNodeEditorSavedTabsInfo" node metadata into the internal `layoutTool_associations` registry.

        Note:
            This function must be invoked from Maya's idle queue to ensure all tabs have been created.
            When opening a scene, Maya will remove all the existing tabs causing the physical tab count to drop to 0.
            It will then sequentially add new tabs to the `QTabBar` until it reaches the total number saved with the scene.
            If there is a discrepency between the registered metadata and the physical tab count, the relevant data will be removed from the registry.
        """
        # Invocation is deferred, therefore the Node Editor may be closed before idle
        if not QtCompat.isValid(self):
            return

        # Queue ensures execution of the function only occurs once (a call will be deferred for every tab change upon loading a scene)
        try:
            index = self._tabChangeQueue.pop()
        except IndexError:
            return

        if not layoutTool_associations.hasData():
            return

        # This can occur when a tab is ripped off from the main panel
        if index == -1:
            return

        # Check that the registered tabCount is not greater than the physical tabCount
        physicalTabCount = self.tabCount
        metaTabCount = layoutTool_associations.tabCount()

        if physicalTabCount < metaTabCount:
            for indexToRemove in xrange(physicalTabCount, metaTabCount):
                try:
                    layoutTool_associations.removeTab(indexToRemove)
                except KeyError:
                    # The registry is sparse at this index
                    pass

        # Create NodeBoxItems for the current tab from the existing metadata
        try:
            nodeBoxMetadata = layoutTool_associations.getData()[index]["NodeBox"]
        except KeyError:
            pass
        else:
            visibleNodeBoxes = self.getVisibleNodeBoxes()

            for registeredUUID, memberMetadata in nodeBoxMetadata.iteritems():
                for visibleNodeBox in visibleNodeBoxes:
                    if visibleNodeBox.UUID == registeredUUID:
                        break
                else:
                    # We do not need to register the item since we are creating it from existing metadata
                    self.createNodeBox(UUID=registeredUUID, rect=QtCore.QRectF(*memberMetadata["rect"]),
                                       color=QtGui.QColor(*memberMetadata["color"]), title=memberMetadata["title"], register=False)

        # Create StickyItems for the current tab from the existing metadata
        try:
            stickyMetadata = layoutTool_associations.getData()[index]["Sticky"]
        except KeyError:
            pass
        else:
            visibleStickies = self.getVisibleStickies()

            for registeredUUID, memberMetadata in stickyMetadata.iteritems():
                for visibleSticky in visibleStickies:
                    if visibleSticky.UUID == registeredUUID:
                        break
                else:
                    self.createSticky(UUID=registeredUUID, rect=QtCore.QRectF(*memberMetadata["rect"]),
                                      color=QtGui.QColor(*memberMetadata["color"]), title=memberMetadata["title"], text=memberMetadata["text"], register=False)

    def _reindexTabMetadata(self, fromIndex, toIndex):
        """Slot designed for the `tabMoved` signal of the Node Editor `tab bar`, ensuring metadata for existing `NodeBox` and `Sticky` items are reindexed when a tab is moved.

        Metadata will be updated for the internal `layoutTool_associations` registry.
        Changes will be written to the "MayaNodeEditorSavedTabsInfo" node upon saving the scene.
        """
        # Reindex any data at the fromIndex with a temporary index to ensure it is not overwritten
        try:
            layoutTool_associations.reindexTab(fromIndex, -1)
            fromIndexHasData = True
        except KeyError:
            fromIndexHasData = False

        # Increment indices in the adjustment range, going in reverse order (ie. from endAdjust to beginAdjust)
        if fromIndex > toIndex:
            beginAdjust = toIndex
            endAdjust = fromIndex - 1

            for indexToIncrement in xrange(endAdjust, beginAdjust - 1, -1):
                try:
                    layoutTool_associations.reindexTab(indexToIncrement, indexToIncrement + 1)
                except KeyError:
                    pass

        # Decrement indices in the adjustment range, going in forward order (ie. from beginAdjust to endAdjust)
        elif toIndex > fromIndex:
            beginAdjust = fromIndex + 1
            endAdjust = toIndex

            for indexToDecrement in xrange(beginAdjust, endAdjust + 1):
                try:
                    layoutTool_associations.reindexTab(indexToDecrement, indexToDecrement - 1)
                except KeyError:
                    pass

        # Finally reindex the original fromIndex data to the toIndex
        if fromIndexHasData:
            layoutTool_associations.reindexTab(-1, toIndex)

    def _updateItemMetadata(self, memberValue, memberName, qualifier, UUID):
        """Slot designed for `NodeBox` and `Sticky` item member signals, ensuring metadata is updated whenever a relevant item value changes.

        Metadata will be updated for the internal `layoutTool_associations` registry.
        Changes will be written to the "MayaNodeEditorSavedTabsInfo" node upon saving the scene.
        """
        if isinstance(memberValue, QtCore.QRectF):
            memberValue = (memberValue.x(), memberValue.y(), memberValue.width(), memberValue.height())
        elif isinstance(memberValue, QtGui.QColor):
            memberValue = (memberValue.red(), memberValue.green(), memberValue.blue(), memberValue.alpha())

        layoutTool_associations.updateDataMember(self.currentIndex, qualifier, UUID, memberName, memberValue)

    def _removeTabMetadata(self, index):
        """Slot designed for the `widgetRemoved` signal of the Node Editor `page area`, ensuring metadata is removed when the user closes a tab (ignores non-user actions).

        Metadata will be removed from the internal `layoutTool_associations` registry.
        Changes will be written to the "MayaNodeEditorSavedTabsInfo" node upon saving the scene.
        """
        if not self.nodeEditorPanel.isAncestorOf(QtWidgets.QApplication.focusWidget()) or _IS_SCENE_OPENING:
            return

        try:
            layoutTool_associations.removeTab(index)
        except KeyError:
            # There is no registered metadata for the current tab
            pass

        # Decrement the index of all higher indexed registered tabs
        metaTabCount = layoutTool_associations.tabCount()
        for indexToDecrement in xrange(index + 1, metaTabCount):
            try:
                layoutTool_associations.reindexTab(indexToDecrement, indexToDecrement - 1)
            except KeyError:
                pass
