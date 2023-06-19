import os

from msTools.vendor.Qt import QtCore, QtGui, QtWidgets

from msTools.tools.nodeEditorExtensions.resources import binary_resources  # noqa: F401


class AlignNodeToolWidget(QtWidgets.QWidget):
    """Provides a view for operations which align graphics items in the Maya Node Editor."""

    alignLeftClicked = QtCore.Signal()
    alignRightClicked = QtCore.Signal()
    alignTopClicked = QtCore.Signal()
    alignBottomClicked = QtCore.Signal()
    alignHCenterClicked = QtCore.Signal()
    alignVCenterClicked = QtCore.Signal()
    distributeHGapsClicked = QtCore.Signal()
    distributeVGapsClicked = QtCore.Signal()

    HEIGHT = 27
    SPACING = 7
    ICON_SIZE = QtCore.QSize(27, 27)
    COLLAPSE_ICON_SIZE = QtCore.QSize(9, 21)
    DIVIDER_ICON_SIZE = QtCore.QSize(9, 23)
    NAME = "MRS_alignNodeToolWidget"

    _STYLESHEET_RESOURCE = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\css\\alignNodeTool_widget.css"))

    _ICON_RESOURCES = {
        # Maya resources
        "collapseOpen": ":/openBar.png",
        "collapseClose": ":/closeBar.png",
        "divider": ":/clip_divider.png",
        # Custom resources
        "alignLeft": ":/icons/align_left_normal.svg",
        "alignRight": ":/icons/align_right_normal.svg",
        "alignTop": ":/icons/align_top_normal.svg",
        "alignBottom": ":/icons/align_bottom_normal.svg",
        "alignHCenter": ":/icons/align_h_center_normal.svg",
        "alignVCenter": ":/icons/align_v_center_normal.svg",
        "distributeHGaps": ":/icons/distribute_h_gaps_normal.svg",
        "distributeVGaps": ":/icons/distribute_v_gaps_normal.svg",
    }

    _TOOLTIPS = {
        "collapse": "Show/hide alignment icons",
        "alignLeft": "Align the left edge of each selected node to the centroid left edge position",
        "alignRight": "Align the right edge of each selected node to the centroid right edge position",
        "alignTop": "Align the top edge of each selected node to the centroid top edge position",
        "alignBottom": "Align the bottom edge of each selected node to the centroid bottom edge position",
        "alignHCenter": "Align the horizontal center of each selected node to the horizontal centroid position",
        "alignVCenter": "Align the vertical center of each selected node to the vertical centroid position",
        "distributeHGaps": "Distribute each selected node so that the horizontal gaps are made equidistant",
        "distributeVGaps": "Distribute each selected node so that the vertical gaps are made equidistant",
    }

    def __init__(self, parent=None):
        super(AlignNodeToolWidget, self).__init__(parent=parent)

        self.setObjectName(AlignNodeToolWidget.NAME)
        self.setFixedHeight(AlignNodeToolWidget.HEIGHT)

        with open(AlignNodeToolWidget._STYLESHEET_RESOURCE, 'r') as f:
            self.setStyleSheet(f.read())

        self._createIcons()
        self._createWidgets()
        self._connectInternalSignals()

    def _createIcons(self):
        # Pixmaps
        self._collapseOpenPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["collapseOpen"])
        self._collapseOpenPixmap = self._collapseOpenPixmap.scaledToHeight(AlignNodeToolWidget.COLLAPSE_ICON_SIZE.height())
        self._collapseClosePixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["collapseClose"])
        self._collapseClosePixmap = self._collapseClosePixmap.scaledToHeight(AlignNodeToolWidget.COLLAPSE_ICON_SIZE.height())
        self._dividerPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["divider"])
        self._dividerPixmap = self._dividerPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignLeftPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignLeft"])
        self._alignLeftPixmap = self._alignLeftPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignHCenterPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignHCenter"])
        self._alignHCenterPixmap = self._alignHCenterPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignRightPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignRight"])
        self._alignRightPixmap = self._alignRightPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignTopPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignTop"])
        self._alignTopPixmap = self._alignTopPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignVCenterPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignVCenter"])
        self._alignVCenterPixmap = self._alignVCenterPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._alignBottomPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["alignBottom"])
        self._alignBottomPixmap = self._alignBottomPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._distributeHGapsPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["distributeHGaps"])
        self._distributeHGapsPixmap = self._distributeHGapsPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())
        self._distributeVGapsPixmap = QtGui.QPixmap(AlignNodeToolWidget._ICON_RESOURCES["distributeVGaps"])
        self._distributeVGapsPixmap = self._distributeVGapsPixmap.scaledToHeight(AlignNodeToolWidget.ICON_SIZE.height())

        # Icons
        self._collapseIcon = QtGui.QIcon()
        self._collapseIcon.addPixmap(self._collapseOpenPixmap, state=QtGui.QIcon.Off)
        self._collapseIcon.addPixmap(self._collapseClosePixmap, state=QtGui.QIcon.On)
        self._alignLeftIcon = QtGui.QIcon(self._alignLeftPixmap)
        self._alignHCenterIcon = QtGui.QIcon(self._alignHCenterPixmap)
        self._alignRightIcon = QtGui.QIcon(self._alignRightPixmap)
        self._alignTopIcon = QtGui.QIcon(self._alignTopPixmap)
        self._alignVCenterIcon = QtGui.QIcon(self._alignVCenterPixmap)
        self._alignBottomIcon = QtGui.QIcon(self._alignBottomPixmap)
        self._dividerIcon = QtGui.QIcon(self._dividerPixmap)
        self._distributeHGapsIcon = QtGui.QIcon(self._distributeHGapsPixmap)
        self._distributeVGapsIcon = QtGui.QIcon(self._distributeVGapsPixmap)

    def _createWidgets(self):
        # Main Layout
        self._mainLayout = QtWidgets.QHBoxLayout()
        self._mainLayout.setSpacing(AlignNodeToolWidget.SPACING)
        self._mainLayout.setContentsMargins(AlignNodeToolWidget.SPACING, 0, 0, 0)
        self._mainLayout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self._mainLayout)

        # Collapse Button Container
        self._collapseButtonsContainer = QtWidgets.QWidget()
        self._collapseButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._collapseButtonsLayout = QtWidgets.QHBoxLayout()
        self._collapseButtonsLayout.setSpacing(AlignNodeToolWidget.SPACING)
        self._collapseButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._collapseButtonsContainer.setLayout(self._collapseButtonsLayout)
        self._mainLayout.addWidget(self._collapseButtonsContainer)

        # Alignment Button Container
        self._alignmentButtonsContainer = QtWidgets.QWidget()
        self._alignmentButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._alignmentButtonsLayout = QtWidgets.QHBoxLayout()
        self._alignmentButtonsLayout.setSpacing(AlignNodeToolWidget.SPACING)
        self._alignmentButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._alignmentButtonsContainer.setLayout(self._alignmentButtonsLayout)
        self._mainLayout.addWidget(self._alignmentButtonsContainer)

        # Collapse Button
        self._collapseButton = QtWidgets.QToolButton()
        self._collapseButton.setAutoRaise(True)
        self._collapseButton.setCheckable(True)
        self._collapseButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._collapseButton.setIcon(self._collapseIcon)
        self._collapseButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["collapse"])
        self._collapseButton.setIconSize(AlignNodeToolWidget.COLLAPSE_ICON_SIZE)
        self._collapseButtonsLayout.addWidget(self._collapseButton)

        # Alignment Buttons
        self._alignLeftButton = QtWidgets.QToolButton()
        self._alignLeftButton.setAutoRaise(True)
        self._alignLeftButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignLeftButton.setIcon(self._alignLeftIcon)
        self._alignLeftButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignLeft"])
        self._alignLeftButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignLeftButton)

        self._alignHCenterButton = QtWidgets.QToolButton()
        self._alignHCenterButton.setAutoRaise(True)
        self._alignHCenterButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignHCenterButton.setIcon(self._alignHCenterIcon)
        self._alignHCenterButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignHCenter"])
        self._alignHCenterButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignHCenterButton)

        self._alignRightButton = QtWidgets.QToolButton()
        self._alignRightButton.setAutoRaise(True)
        self._alignRightButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignRightButton.setIcon(self._alignRightIcon)
        self._alignRightButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignRight"])
        self._alignRightButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignRightButton)

        self._dividerButton1 = QtWidgets.QToolButton()
        self._dividerButton1.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._dividerButton1.setIcon(self._dividerIcon)
        self._dividerButton1.setIconSize(AlignNodeToolWidget.DIVIDER_ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._dividerButton1)

        self._alignTopButton = QtWidgets.QToolButton()
        self._alignTopButton.setAutoRaise(True)
        self._alignTopButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignTopButton.setIcon(self._alignTopIcon)
        self._alignTopButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignTop"])
        self._alignTopButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignTopButton)

        self._alignVCenterButton = QtWidgets.QToolButton()
        self._alignVCenterButton.setAutoRaise(True)
        self._alignVCenterButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignVCenterButton.setIcon(self._alignVCenterIcon)
        self._alignVCenterButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignVCenter"])
        self._alignVCenterButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignVCenterButton)

        self._alignBottomButton = QtWidgets.QToolButton()
        self._alignBottomButton.setAutoRaise(True)
        self._alignBottomButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._alignBottomButton.setIcon(self._alignBottomIcon)
        self._alignBottomButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["alignBottom"])
        self._alignBottomButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._alignBottomButton)

        self._dividerButton2 = QtWidgets.QToolButton()
        self._dividerButton2.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._dividerButton2.setIcon(self._dividerIcon)
        self._dividerButton2.setIconSize(AlignNodeToolWidget.DIVIDER_ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._dividerButton2)

        self._distributeHGapsButton = QtWidgets.QToolButton()
        self._distributeHGapsButton.setAutoRaise(True)
        self._distributeHGapsButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._distributeHGapsButton.setIcon(self._distributeHGapsIcon)
        self._distributeHGapsButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["distributeHGaps"])
        self._distributeHGapsButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._distributeHGapsButton)

        self._distributeVGapsButton = QtWidgets.QToolButton()
        self._distributeVGapsButton.setAutoRaise(True)
        self._distributeVGapsButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._distributeVGapsButton.setIcon(self._distributeVGapsIcon)
        self._distributeVGapsButton.setToolTip(AlignNodeToolWidget._TOOLTIPS["distributeVGaps"])
        self._distributeVGapsButton.setIconSize(AlignNodeToolWidget.ICON_SIZE)
        self._alignmentButtonsLayout.addWidget(self._distributeVGapsButton)

    def _connectInternalSignals(self):
        # --- View -> View ---
        self._collapseButton.toggled.connect(lambda selected: self._alignmentButtonsContainer.setVisible(not selected))
        self._alignLeftButton.clicked.connect(self.alignLeftClicked)
        self._alignRightButton.clicked.connect(self.alignRightClicked)
        self._alignTopButton.clicked.connect(self.alignTopClicked)
        self._alignBottomButton.clicked.connect(self.alignBottomClicked)
        self._alignHCenterButton.clicked.connect(self.alignHCenterClicked)
        self._alignVCenterButton.clicked.connect(self.alignVCenterClicked)
        self._distributeHGapsButton.clicked.connect(self.distributeHGapsClicked)
        self._distributeVGapsButton.clicked.connect(self.distributeVGapsClicked)
