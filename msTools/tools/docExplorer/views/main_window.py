import importlib
import os

from msTools.vendor.Qt import __binding__, QtCore, QtWidgets

try:
    QtWebEngineWidgets = importlib.import_module(".".join([__binding__, "QtWebEngineWidgets"]))
    _IS_WEB_ENGINE_AVAILABLE = True
except ImportError:
    _IS_WEB_ENGINE_AVAILABLE = False


# ----------------------------------------------------------------------------
# --- Child Views ---
# ----------------------------------------------------------------------------

class TreeView(QtWidgets.QTreeView):
    """Provides a custom signal for when the mouse is released and the selected item has changed."""

    indexChangedOnMouseRelease = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, *args, **kwargs):
        super(TreeView, self).__init__()

        self._mousePressIndex = None

    def mousePressEvent(self, event):
        # NOTE: The mousePressEvent only occurs on the first click of a mouseDoubleClickEvent
        self._mousePressIndex = self.currentIndex()
        super(TreeView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # NOTE: The mouseReleaseEvent will occur for each click of a mouseDoubleClickEvent
        # Only refresh if the selected item has actually changed (ie. ignore release events over the expand arrow)
        if self._mousePressIndex != self.currentIndex():
            self.indexChangedOnMouseRelease.emit(self.currentIndex())

        super(TreeView, self).mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Ensure the current index is recorded before the second mouseReleaseEvent for a mouseDoubleClickEvent (ie. prevent two signals from emitting)
        self._mousePressIndex = self.currentIndex()
        super(TreeView, self).mouseDoubleClickEvent(event)


# ----------------------------------------------------------------------------
# --- Main Window ---
# ----------------------------------------------------------------------------

class MainWindow(QtWidgets.QWidget):

    TITLE = "Doc Explorer"
    NAME = "MRS_docExplorer"

    MINIMUM_WIDTH = 300
    DEFAULT_WIDTH = 360
    DEFAULT_HEIGHT = 550
    MARGIN = 10
    SPACING = 10

    treeViewIndexChanged = QtCore.Signal(QtCore.QModelIndex)
    searchTextChanged = QtCore.Signal(str)
    browserButtonPressed = QtCore.Signal()
    webViewLoadFinished = QtCore.Signal(bool)
    webViewLoadProgress = QtCore.Signal(int)

    _STYLESHEET_RESOURCE = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\css\\main_window.css"))

    def __init__(self, model, parent=None):
        super(MainWindow, self).__init__(parent=parent)

        self._model = model

        self.setObjectName(MainWindow.NAME)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle(MainWindow.TITLE)
        self.setMinimumWidth(MainWindow.MINIMUM_WIDTH)
        self.resize(MainWindow.DEFAULT_WIDTH, MainWindow.DEFAULT_HEIGHT)

        with open(MainWindow._STYLESHEET_RESOURCE, 'r') as f:
            self.setStyleSheet(f.read())

        self._createWidgets()
        self._setModel()
        self._connectInternalSignals()

    def _createWidgets(self):
        # Main Layout
        self._mainLayout = QtWidgets.QVBoxLayout()
        self._mainLayout.setContentsMargins(MainWindow.MARGIN, MainWindow.MARGIN, MainWindow.MARGIN, MainWindow.MARGIN)
        self._mainLayout.setSpacing(MainWindow.SPACING)
        self._mainLayout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self._mainLayout)

        # Containers
        self._searchContainer = QtWidgets.QWidget()
        self._searchContainer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._searchLayout = QtWidgets.QHBoxLayout()
        self._searchLayout.setContentsMargins(0, 0, 0, 0)
        self._searchLayout.setSpacing(0)
        self._searchContainer.setLayout(self._searchLayout)
        self._mainLayout.addWidget(self._searchContainer)

        self._treeViewContainer = QtWidgets.QWidget()
        self._treeViewContainer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._treeViewLayout = QtWidgets.QHBoxLayout()
        self._treeViewLayout.setContentsMargins(0, 0, 0, 0)
        self._treeViewLayout.setSpacing(0)
        self._treeViewContainer.setLayout(self._treeViewLayout)

        if _IS_WEB_ENGINE_AVAILABLE:
            self._webViewContainer = QtWidgets.QWidget()
            self._webViewContainer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self._webViewLayout = QtWidgets.QHBoxLayout()
            self._webViewLayout.setContentsMargins(0, 0, 0, 0)
            self._webViewLayout.setSpacing(0)
            self._webViewContainer.setLayout(self._webViewLayout)

            self._splitter = QtWidgets.QSplitter()
            self._splitter.setOrientation(QtCore.Qt.Vertical)
            self._splitter.setHandleWidth(MainWindow.SPACING)
            self._splitter.addWidget(self._treeViewContainer)
            self._splitter.addWidget(self._webViewContainer)
            self._splitter.setStretchFactor(0, 0.25)
            self._splitter.setStretchFactor(1, 0.75)
            self._mainLayout.addWidget(self._splitter)
        else:
            self._mainLayout.addWidget(self._treeViewContainer)

        self._openBrowserContainer = QtWidgets.QWidget()
        self._openBrowserContainer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._openBrowserLayout = QtWidgets.QHBoxLayout()
        self._openBrowserLayout.setContentsMargins(0, 0, 0, 0)
        self._openBrowserLayout.setSpacing(0)
        self._openBrowserContainer.setLayout(self._openBrowserLayout)
        self._mainLayout.addWidget(self._openBrowserContainer)

        # Container children
        self._searchLineEdit = QtWidgets.QLineEdit()
        self._searchLineEdit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._searchLineEdit.setFixedHeight(24)
        self._searchLineEdit.setPlaceholderText("Search: <class> or <class>.<method>")
        self._searchLayout.addWidget(self._searchLineEdit)

        self._treeView = TreeView()
        self._treeView.setMinimumHeight(110)
        self._treeView.setHeaderHidden(True)
        self._treeView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._treeViewLayout.addWidget(self._treeView)

        if _IS_WEB_ENGINE_AVAILABLE:
            self._webView = QtWebEngineWidgets.QWebEngineView()
            self._webView.setMinimumHeight(110)
            self._webViewLayout.addWidget(self._webView)

        self._openBrowserButton = QtWidgets.QPushButton("Open Browser")
        self._openBrowserButton.setFixedHeight(24)
        self._openBrowserLayout.addWidget(self._openBrowserButton)

    def _connectInternalSignals(self):
        """Connect implementation independent signals (ie. those which are known to the view)."""
        # --- View -> View ---
        self._treeView.indexChangedOnMouseRelease.connect(self.treeViewIndexChanged)
        self._searchLineEdit.textChanged.connect(self.searchTextChanged)
        self._openBrowserButton.pressed.connect(self.browserButtonPressed)

        if _IS_WEB_ENGINE_AVAILABLE:
            self._webView.loadFinished.connect(self.webViewLoadFinished)
            self._webView.loadProgress.connect(self.webViewLoadProgress)

    def _setModel(self):
        self._treeView.setModel(self._model)

    @property
    def hasWebView(self):
        return _IS_WEB_ENGINE_AVAILABLE

    def getTreeViewIndex(self):
        return self._treeView.currentIndex()

    def setTreeViewIndex(self, index):
        self._treeView.setCurrentIndex(index)
        self.treeViewIndexChanged.emit(index)

    def getUrl(self, removeFragment=True):
        options = QtCore.QUrl.FormattingOptions(QtCore.QUrl.RemoveFragment if removeFragment else QtCore.QUrl.PrettyDecoded)
        return self._webView.url().toString(options)

    def loadUrl(self, url):
        self._webView.load(url)

    def runScript(self, script):
        self._webView.page().runJavaScript(script)
