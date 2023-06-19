import bisect
import logging
import os
import sys
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCore, QtGui


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

log.debug('Initializing global: _NODE_TYPE_MODEL')
_NODE_TYPE_MODEL = None


# ----------------------------------------------------------------------------
# --- Setup ---
# ----------------------------------------------------------------------------

def getGlobalNodeTypeModel():
    """Access a global instance of the :class:`NodeTypeModel`. The instance is defined globally for two reasons:

    - The model is relatively expensive to build.
    - The model should be managed by a global controller, one which responds to changes in the data source (internal Maya node type registry).

    Note:
        The global :class:`~msTools.tools.nodeEditorExtensions.controllers.nodeType_controller.NodeTypeController` returned from
        :meth:`~msTools.tools.nodeEditorExtensions.controllers.nodeType_controller.getGlobalNodeTypeController` has been designed specifically for this model.
    """
    global _NODE_TYPE_MODEL
    if _NODE_TYPE_MODEL is None:
        _NODE_TYPE_MODEL = NodeTypeModel()

    return _NODE_TYPE_MODEL


# ----------------------------------------------------------------------------
# --- Proxy Model ---
# ----------------------------------------------------------------------------

class NodeTypeProxyModel(QtCore.QSortFilterProxyModel):

    DELEGATE_BOLD_FONT_FAMILY = "Helvetica"
    DELEGATE_BOLD_FONT_SIZE = 16
    DELEGATE_BOLD_FONT_WEIGHT = QtGui.QFont.Bold
    DELEGATE_BOLD_TEXT_COLOR = (255, 255, 255, 190)

    def __init__(self, parent=None):
        super(NodeTypeProxyModel, self).__init__(parent=parent)

        # Provide default styling for delegates
        self._boldFont = QtGui.QFont(NodeTypeProxyModel.DELEGATE_BOLD_FONT_FAMILY)
        self._boldFont.setPixelSize(NodeTypeProxyModel.DELEGATE_BOLD_FONT_SIZE)
        self._boldFont.setStyleHint(QtGui.QFont.StyleHint.__dict__[NodeTypeProxyModel.DELEGATE_BOLD_FONT_FAMILY])
        self._boldFont.setWeight(NodeTypeProxyModel.DELEGATE_BOLD_FONT_WEIGHT)
        self._boldTextPen = QtGui.QPen(QtGui.QColor(*NodeTypeProxyModel.DELEGATE_BOLD_TEXT_COLOR))

        self.setSourceModel(getGlobalNodeTypeModel())
        self.sort(0)

    @property
    def source(self):
        return self.sourceModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.FontRole:
                text = index.data(QtCore.Qt.DisplayRole)
                filterPattern = self.filterRegExp().pattern()

                if text.startswith(filterPattern):
                    return self._boldFont
            elif role == QtCore.Qt.ForegroundRole:
                text = index.data(QtCore.Qt.DisplayRole)
                filterPattern = self.filterRegExp().pattern()

                if text.startswith(filterPattern):
                    return self._boldTextPen

        return super(NodeTypeProxyModel, self).data(index, role=role)

    def filterAcceptsRow(self, sourceRow, sourceParent):
        filterPattern = self.filterRegExp().pattern()

        # Filter everything by default
        if not filterPattern:
            return False

        sourceIndex = self.source.index(sourceRow, 0, sourceParent)
        nodeType = self.source.data(sourceIndex, role=QtCore.Qt.DisplayRole)

        return filterPattern.lower() in nodeType.lower()

    def lessThan(self, leftIndex, rightIndex):
        """Sorts filtered data using the following order:

        1. Items which start with the case sensitive filter pattern.
        2. Items which start with the case insensitive filter pattern.
        3. Items which contain the case insensitive filter pattern.

        Note:
            Each group of items will be sorted in a case insensitive order (ie. based on the default order of the source model).
        """
        filterPattern = self.filterRegExp().pattern()
        leftData = self.sourceModel().data(leftIndex, role=QtCore.Qt.DisplayRole)
        rightData = self.sourceModel().data(rightIndex, role=QtCore.Qt.DisplayRole)
        leftRow = leftIndex.row()
        rightRow = rightIndex.row()

        leftStartswith_caseSensitive = leftData.startswith(filterPattern)
        rightStartswith_caseSensitive = rightData.startswith(filterPattern)

        # If a single item starts with the case sensitive pattern, return whether the left item should come first
        if leftStartswith_caseSensitive != rightStartswith_caseSensitive:
            return leftStartswith_caseSensitive

        # If both items start with the case sensitive pattern, use the default (case insensitive) source model order
        if leftStartswith_caseSensitive and rightStartswith_caseSensitive:
            return leftRow < rightRow

        leftStartswith_caseInsensitive = leftData.lower().startswith(filterPattern.lower())
        rightStartswith_caseInsensitive = rightData.lower().startswith(filterPattern.lower())

        # If a single item starts with the case insensitive pattern, return whether the left item should come first
        if leftStartswith_caseInsensitive != rightStartswith_caseInsensitive:
            return leftStartswith_caseInsensitive

        # If both items start with the case insensitive pattern, use the default (case insensitive) source model order
        if leftStartswith_caseInsensitive and rightStartswith_caseInsensitive:
            return leftRow < rightRow

        # Fallback - use the default (case insensitive) source model order
        return leftRow < rightRow


# ----------------------------------------------------------------------------
# --- Model ---
# ----------------------------------------------------------------------------

class NodeTypeModel(QtCore.QAbstractListModel):

    BLACKLISTED_NODE_TYPES = ("applyAbsOverride", "applyOverride", "applyRelOverride", "childNode", "lightItemBase",
                              "listItem", "override", "selector", "valueOverride", "xgmConnectivity", "xgmGuide", "xgmModifierBase", "xgmPatch")

    BLACKLISTED_INHERITED_NODE_TYPES = ("manip2D", "manip3D")

    BLACKLISTED_FILE_EXTENSIONS = ("tdi", "iff")

    DELEGATE_FONT_FAMILY = "Helvetica"
    DELEGATE_FONT_SIZE = 16
    DELEGATE_FONT_WEIGHT = QtGui.QFont.Normal
    DELEGATE_TEXT_COLOR = (255, 255, 255, 150)

    # --- Special ----------------------------------------------------------------------------------------

    def __init__(self):
        super(NodeTypeModel, self).__init__()

        self._defaultPixmapResource = ":/default.svg"
        self._defaultPixmap = QtGui.QPixmap(self._defaultPixmapResource)
        self._nodeTypes = []
        self._nodeTypes_lower = []
        self._nodeTypeSet = set()
        self._nodeTypeData = []

        # Provide default styling for delegates
        self._font = QtGui.QFont(NodeTypeModel.DELEGATE_FONT_FAMILY)
        self._font.setPixelSize(NodeTypeModel.DELEGATE_FONT_SIZE)
        self._font.setStyleHint(QtGui.QFont.StyleHint.__dict__[NodeTypeModel.DELEGATE_FONT_FAMILY])
        self._font.setWeight(NodeTypeModel.DELEGATE_FONT_WEIGHT)
        self._textPen = QtGui.QPen(QtGui.QColor(*NodeTypeModel.DELEGATE_TEXT_COLOR))

        # Update with current node types
        self.addNodeTypes(cmds.allNodeTypes())

    # --- Pure Vitual ------------------------------------------------------------------------------------

    def rowCount(self, parent=QtCore.QModelIndex()):
        # If parent is not the root index
        if parent.isValid():
            return 0

        return len(self._nodeTypeData)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return self._nodeTypeData[index.row()]["type"]
            elif role == QtCore.Qt.DecorationRole:
                # Build pixmap data upon request and cache the result
                pixmap = self._nodeTypeData[index.row()]["pixmap"] or QtGui.QPixmap(self._nodeTypeData[index.row()]["pixmapResource"])
                self._nodeTypeData[index.row()]["pixmap"] = pixmap
                return pixmap
            elif role == QtCore.Qt.FontRole:
                return self._font
            elif role == QtCore.Qt.ForegroundRole:
                return self._textPen

    # --- Private ----------------------------------------------------------------------------------------

    def _nodeTypeFilter(self, nodeType):
        """Filter out blacklisted node types (ie. abstract types which might cause Maya to crash)."""
        if nodeType in NodeTypeModel.BLACKLISTED_NODE_TYPES:
            return False

        for blacklistedNodeType in NodeTypeModel.BLACKLISTED_INHERITED_NODE_TYPES:
            if blacklistedNodeType in cmds.nodeType(nodeType, isTypeName=True, inherited=True):
                return False

        return True

    def _resourceFilter(self, resourceName):
        """Filter out blacklisted resources."""
        for blacklistedFileExtension in NodeTypeModel.BLACKLISTED_FILE_EXTENSIONS:
            if resourceName.endswith(blacklistedFileExtension):
                return False
            elif "." not in resourceName:
                return False

        return True

    def _getInternalResources(self):
        """Return a mapping of internal resource names to resource paths."""
        internalResources = filter(self._resourceFilter, cmds.resourceManager(nameFilter="*.*"))

        return {internalResource.rsplit(".", 1)[0]: ":/{}".format(internalResource) for internalResource in internalResources}

    def _getFileResources(self):
        """Return a mapping of file file resource names to file paths."""
        # See Maya documentation, search for "Maya File path variables"
        iconDirPaths = [os.path.abspath(path) for path in os.environ['XBMLANGPATH'].split(os.pathsep)]

        # Clean Linux paths
        if sys.platform.startswith('linux'):
            iconDirPaths = [os.path.dirname(path) for path in iconDirPaths if path.endswith('%B')]

        # Remove Maya defaults that do not exist
        iconDirPaths = [path for path in iconDirPaths if os.path.isdir(path)]

        return {fileResource.rsplit(".", 1)[0]: os.path.join(iconDirPath, fileResource) for iconDirPath in iconDirPaths for fileResource in os.listdir(iconDirPath)}

    # --- Public ----------------------------------------------------------------------------------------

    def addNodeTypes(self, nodeTypes):
        """Insert node type data within the model.

        Note:
            Calls to this function should be minimised as resources are retrieved dynamically for each call.
            Retrieving internal Maya resources takes approximately 250ms.

        Args:
            nodeTypes (iterable [:class:`basestring`]): Sequence of node type names to insert.
        """
        # Provide a default (case insensitive) sort order for the proxy model
        nodeTypes = sorted(filter(self._nodeTypeFilter, nodeTypes), key=lambda s: s.lower())

        # Retrieve dynamically in case new resources have been added
        internalResourceMapping = self._getInternalResources()
        fileResourceMapping = self._getFileResources()

        # NOTE: Building QPixmaps is slow. We will defer instantiation until the data is requested (eg. the paint event of the view/item delegate)
        # Instantiating a pixmap for every default node type in Maya takes me approx 600ms
        for nodeType in nodeTypes:
            if nodeType not in self._nodeTypeSet:
                nodeTypeData = {"type": nodeType}

                if nodeType in internalResourceMapping:
                    nodeTypeData["pixmapResource"] = internalResourceMapping[nodeType]
                    nodeTypeData["pixmap"] = None
                elif nodeType in fileResourceMapping:
                    nodeTypeData["pixmapResource"] = fileResourceMapping[nodeType]
                    nodeTypeData["pixmap"] = None
                else:
                    nodeTypeData["pixmapRespource"] = self._defaultPixmapResource
                    nodeTypeData["pixmap"] = self._defaultPixmap

                # Ensure we are bisecting the case insensitive list
                nodeType_lower = nodeType.lower()
                insertionIndex = bisect.bisect_left(self._nodeTypes_lower, nodeType_lower)
                self.beginInsertRows(QtCore.QModelIndex(), insertionIndex, insertionIndex)
                self._nodeTypes.insert(insertionIndex, nodeType)
                self._nodeTypes_lower.insert(insertionIndex, nodeType_lower)
                self._nodeTypeData.insert(insertionIndex, nodeTypeData)
                self._nodeTypeSet.add(nodeType)
                self.endInsertRows()

    def removeNodeTypes(self, nodeTypes):
        """Remove node type data from the model.

        Args:
            nodeTypes (iterable [:class:`basestring`]): Sequence of node type names to remove.
        """
        for nodeType in nodeTypes:
            if nodeType in self._nodeTypeSet:
                removalIndex = bisect.bisect_left(self._nodeTypes, nodeType)
                self.beginRemoveRows(QtCore.QModelIndex(), removalIndex, removalIndex)
                del self._nodeTypes[removalIndex]
                del self._nodeTypes_lower[removalIndex]
                del self._nodeTypeData[removalIndex]
                self._nodeTypeSet.remove(nodeType)
                self.endRemoveRows()
