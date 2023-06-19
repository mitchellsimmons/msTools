import os

from msTools.vendor.Qt import QtCore, QtGui, QtWidgets

from msTools.tools.nodeEditorExtensions.resources import binary_resources  # noqa: F401


class LayoutToolWidget(QtWidgets.QWidget):
    """A view for creating `NodeBox` and `Sticky` items in the Node Editor."""

    nodeBoxClicked = QtCore.Signal()
    stickyClicked = QtCore.Signal()

    HEIGHT = 27
    SPACING = 7
    ICON_SIZE = QtCore.QSize(27, 27)
    COLLAPSE_ICON_SIZE = QtCore.QSize(9, 21)
    NAME = "MRS_layoutToolWidget"

    _STYLESHEET_RESOURCE = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\css\\layoutTool_widget.css"))

    _ICON_RESOURCES = {
        # Maya resources
        "collapseOpen": ":/openBar.png",
        "collapseClose": ":/closeBar.png",
        # Custom resources
        "nodeBox": ":/icons/nodeBox_normal.svg",
        "sticky": ":/icons/sticky_normal.svg",
    }

    _TOOLTIPS = {
        "collapse": "Show/hide layout items icons",
        "nodeBox": "Create a box around selected nodes to help layout the graph",
        "sticky": "Create a sticky note for annotating part of the graph",
    }

    def __init__(self, parent=None):
        super(LayoutToolWidget, self).__init__(parent=parent)

        self.setObjectName(LayoutToolWidget.NAME)
        self.setFixedHeight(LayoutToolWidget.HEIGHT)

        with open(LayoutToolWidget._STYLESHEET_RESOURCE, 'r') as f:
            self.setStyleSheet(f.read())

        self._createIcons()
        self._createWidgets()
        self._connectInternalSignals()

    def _createIcons(self):
        # Pixmaps
        self._collapseOpenPixmap = QtGui.QPixmap(LayoutToolWidget._ICON_RESOURCES["collapseOpen"])
        self._collapseOpenPixmap = self._collapseOpenPixmap.scaledToHeight(LayoutToolWidget.COLLAPSE_ICON_SIZE.height())
        self._collapseClosePixmap = QtGui.QPixmap(LayoutToolWidget._ICON_RESOURCES["collapseClose"])
        self._collapseClosePixmap = self._collapseClosePixmap.scaledToHeight(LayoutToolWidget.COLLAPSE_ICON_SIZE.height())
        # Scaling larger than the icon size is helping to increase quality
        self._nodeBoxPixmap = QtGui.QPixmap(LayoutToolWidget._ICON_RESOURCES["nodeBox"])
        self._nodeBoxPixmap = self._nodeBoxPixmap.scaledToHeight(LayoutToolWidget.ICON_SIZE.height() * 2)
        self._stickyPixmap = QtGui.QPixmap(LayoutToolWidget._ICON_RESOURCES["sticky"])
        self._stickyPixmap = self._stickyPixmap.scaledToHeight(LayoutToolWidget.ICON_SIZE.height() * 2)

        # Icons
        self._collapseIcon = QtGui.QIcon()
        self._collapseIcon.addPixmap(self._collapseOpenPixmap, state=QtGui.QIcon.Off)
        self._collapseIcon.addPixmap(self._collapseClosePixmap, state=QtGui.QIcon.On)
        self._nodeBoxIcon = QtGui.QIcon(self._nodeBoxPixmap)
        self._stickyIcon = QtGui.QIcon(self._stickyPixmap)

    def _createWidgets(self):
        # Main Layout
        self._mainLayout = QtWidgets.QHBoxLayout()
        self._mainLayout.setSpacing(LayoutToolWidget.SPACING)
        self._mainLayout.setContentsMargins(LayoutToolWidget.SPACING, 0, 0, 0)
        self._mainLayout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self._mainLayout)

        # Collapse Button Container
        self._collapseButtonsContainer = QtWidgets.QWidget()
        self._collapseButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._collapseButtonsLayout = QtWidgets.QHBoxLayout()
        self._collapseButtonsLayout.setSpacing(LayoutToolWidget.SPACING)
        self._collapseButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._collapseButtonsContainer.setLayout(self._collapseButtonsLayout)
        self._mainLayout.addWidget(self._collapseButtonsContainer)

        # Layout Items Button Container
        self._layoutItemsButtonsContainer = QtWidgets.QWidget()
        self._layoutItemsButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._layoutItemsButtonsLayout = QtWidgets.QHBoxLayout()
        self._layoutItemsButtonsLayout.setSpacing(LayoutToolWidget.SPACING)
        self._layoutItemsButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._layoutItemsButtonsContainer.setLayout(self._layoutItemsButtonsLayout)
        self._mainLayout.addWidget(self._layoutItemsButtonsContainer)

        # Collapse Button
        self._collapseButton = QtWidgets.QToolButton()
        self._collapseButton.setAutoRaise(True)
        self._collapseButton.setCheckable(True)
        self._collapseButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._collapseButton.setIcon(self._collapseIcon)
        self._collapseButton.setToolTip(LayoutToolWidget._TOOLTIPS["collapse"])
        self._collapseButton.setIconSize(LayoutToolWidget.COLLAPSE_ICON_SIZE)
        self._collapseButtonsLayout.addWidget(self._collapseButton)

        # Layout Items Buttons
        self._nodeBoxButton = QtWidgets.QToolButton()
        self._nodeBoxButton.setAutoRaise(True)
        self._nodeBoxButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._nodeBoxButton.setIcon(self._nodeBoxIcon)
        self._nodeBoxButton.setToolTip(LayoutToolWidget._TOOLTIPS["nodeBox"])
        self._nodeBoxButton.setIconSize(LayoutToolWidget.ICON_SIZE)
        self._layoutItemsButtonsLayout.addWidget(self._nodeBoxButton)

        self._stickyButton = QtWidgets.QToolButton()
        self._stickyButton.setAutoRaise(True)
        self._stickyButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._stickyButton.setIcon(self._stickyIcon)
        self._stickyButton.setToolTip(LayoutToolWidget._TOOLTIPS["sticky"])
        self._stickyButton.setIconSize(LayoutToolWidget.ICON_SIZE)
        self._layoutItemsButtonsLayout.addWidget(self._stickyButton)

    def _connectInternalSignals(self):
        # --- View -> View ---
        self._collapseButton.toggled.connect(lambda selected: self._layoutItemsButtonsContainer.setVisible(not selected))
        self._nodeBoxButton.clicked.connect(self.nodeBoxClicked)
        self._stickyButton.clicked.connect(self.stickyClicked)
