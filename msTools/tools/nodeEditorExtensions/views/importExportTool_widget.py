import logging
import os
log = logging.getLogger(__name__)

from msTools.vendor.Qt import QtCore, QtGui, QtWidgets

from msTools.tools.nodeEditorExtensions.resources import binary_resources  # noqa: F401


class ImportExportToolWidget(QtWidgets.QFrame):
    """Provides a view for operations which translate dependency node and `Layout Tool` data between the Maya Node Editor and external resources."""

    importClicked = QtCore.Signal()
    exportClicked = QtCore.Signal()

    HEIGHT = 27
    SPACING = 7
    PIXMAP_HEIGHT = 20
    ICON_SIZE = QtCore.QSize(27, 27)
    COLLAPSE_ICON_SIZE = QtCore.QSize(9, 21)
    NAME = "MRS_layoutToolTranslatorWidget"

    _STYLESHEET_RESOURCE = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\css\\importExportTool_widget.css"))

    # Licence for "file-import-solid.svg" and "file-export-solid.svg" : https://fontawesome.com/license/free
    _ICON_RESOURCES = {
        # Maya resources
        "collapseOpen": ":/openBar.png",
        "collapseClose": ":/closeBar.png",
        # FontAwesome resources
        "import": ":/icons/file-import-solid.svg",
        "export": ":/icons/file-export-solid.svg",
    }

    _TOOLTIPS = {
        "collapse": "Show/hide alignment icons",
        "import": "Import layout item data into the current tab",
        "export": "Export layout item data from the current tab",
    }

    def __init__(self, parent=None):
        super(ImportExportToolWidget, self).__init__(parent)

        self.setObjectName(ImportExportToolWidget.NAME)
        self.setFixedHeight(ImportExportToolWidget.HEIGHT)

        with open(ImportExportToolWidget._STYLESHEET_RESOURCE, 'r') as f:
            self.setStyleSheet(f.read())

        self._createIcons()
        self._createWidgets()
        self._connectInternalSignals()

    def _createIcons(self):
        # Pixmaps
        self._collapseOpenPixmap = QtGui.QPixmap(ImportExportToolWidget._ICON_RESOURCES["collapseOpen"])
        self._collapseOpenPixmap = self._collapseOpenPixmap.scaledToHeight(ImportExportToolWidget.COLLAPSE_ICON_SIZE.height())
        self._collapseClosePixmap = QtGui.QPixmap(ImportExportToolWidget._ICON_RESOURCES["collapseClose"])
        self._collapseClosePixmap = self._collapseClosePixmap.scaledToHeight(ImportExportToolWidget.COLLAPSE_ICON_SIZE.height())
        self._importPixmap = QtGui.QPixmap(ImportExportToolWidget._ICON_RESOURCES["import"])
        self._importPixmap = self._importPixmap.scaledToHeight(ImportExportToolWidget.PIXMAP_HEIGHT)
        self._exportPixmap = QtGui.QPixmap(ImportExportToolWidget._ICON_RESOURCES["export"])
        self._exportPixmap = self._exportPixmap.scaledToHeight(ImportExportToolWidget.PIXMAP_HEIGHT)

        # Icons
        self._collapseIcon = QtGui.QIcon()
        self._collapseIcon.addPixmap(self._collapseOpenPixmap, state=QtGui.QIcon.Off)
        self._collapseIcon.addPixmap(self._collapseClosePixmap, state=QtGui.QIcon.On)
        self._importIcon = QtGui.QIcon(self._importPixmap)
        self._exportIcon = QtGui.QIcon(self._exportPixmap)

    def _createWidgets(self):
        # Main Layout
        self._mainLayout = QtWidgets.QHBoxLayout()
        self._mainLayout.setSpacing(ImportExportToolWidget.SPACING)
        self._mainLayout.setContentsMargins(ImportExportToolWidget.SPACING, 0, 0, 0)
        self._mainLayout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self._mainLayout)

        # Collapse Button Container
        self._collapseButtonsContainer = QtWidgets.QWidget()
        self._collapseButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._collapseButtonsLayout = QtWidgets.QHBoxLayout()
        self._collapseButtonsLayout.setSpacing(ImportExportToolWidget.SPACING)
        self._collapseButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._collapseButtonsContainer.setLayout(self._collapseButtonsLayout)
        self._mainLayout.addWidget(self._collapseButtonsContainer)

        # Import/Export Buttons Container
        self._importExportButtonsContainer = QtWidgets.QWidget()
        self._importExportButtonsContainer.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._importExportButtonsLayout = QtWidgets.QHBoxLayout()
        self._importExportButtonsLayout.setSpacing(ImportExportToolWidget.SPACING)
        self._importExportButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self._importExportButtonsContainer.setLayout(self._importExportButtonsLayout)
        self._mainLayout.addWidget(self._importExportButtonsContainer)

        # Collapse Button
        self._collapseButton = QtWidgets.QToolButton()
        self._collapseButton.setAutoRaise(True)
        self._collapseButton.setCheckable(True)
        self._collapseButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._collapseButton.setIcon(self._collapseIcon)
        self._collapseButton.setToolTip(ImportExportToolWidget._TOOLTIPS["collapse"])
        self._collapseButton.setIconSize(ImportExportToolWidget.COLLAPSE_ICON_SIZE)
        self._collapseButtonsLayout.addWidget(self._collapseButton)

        # Import/Export Buttons
        self._importButton = QtWidgets.QToolButton()
        self._importButton.setAutoRaise(True)
        self._importButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._importButton.setIcon(self._importIcon)
        self._importButton.setToolTip(ImportExportToolWidget._TOOLTIPS["import"])
        self._importButton.setIconSize(ImportExportToolWidget.ICON_SIZE)
        self._importExportButtonsLayout.addWidget(self._importButton)

        self._exportButton = QtWidgets.QToolButton()
        self._exportButton.setAutoRaise(True)
        self._exportButton.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self._exportButton.setIcon(self._exportIcon)
        self._exportButton.setToolTip(ImportExportToolWidget._TOOLTIPS["export"])
        self._exportButton.setIconSize(ImportExportToolWidget.ICON_SIZE)
        self._importExportButtonsLayout.addWidget(self._exportButton)

    def _connectInternalSignals(self):
        # --- View -> View ---
        self._collapseButton.toggled.connect(lambda selected: self._importExportButtonsContainer.setVisible(not selected))
        self._importButton.clicked.connect(self.importClicked)
        self._exportButton.clicked.connect(self.exportClicked)
