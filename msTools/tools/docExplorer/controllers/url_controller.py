import os
import webbrowser

from msTools.vendor.Qt import QtCore

from msTools.tools.docExplorer.models.url_model import UrlModel


class UrlController(QtCore.QObject):
    """Controller for interfacing with the :class:`msTools.tools.docExplorer.models.url_model.UrlProxyModel`."""

    # Responds to url requests
    urlResponse = QtCore.Signal(QtCore.QUrl)

    # Responds to script requests
    scriptResponse = QtCore.Signal(str)

    # Script resources
    _SCRIPT_RESOURCES = {
        "Maya Python API 2.0": os.path.abspath(os.path.join(__file__, "..\\..\\resources\\js\\mayaApiDoc.js")),
        "PySide2": os.path.abspath(os.path.join(__file__, "..\\..\\resources\\js\\PySide2Doc.js")),
    }

    def __init__(self, proxyModel, parent=None):
        """Initialise the controller.

        Args:
            proxyModel (:class:`msTools.tools.docExplorer.models.url_model.UrlProxyModel`): Proxy model from which to query data.
        """
        super(UrlController, self).__init__(parent=parent)

        self._proxyModel = proxyModel

        with open(UrlController._SCRIPT_RESOURCES["Maya Python API 2.0"], 'r') as openMayaScriptsResource:
            self._openMayaScripts = openMayaScriptsResource.read()

        with open(UrlController._SCRIPT_RESOURCES["PySide2"], 'r') as pySideScriptsResource:
            self._pySideScripts = pySideScriptsResource.read()

    def getInitialIndex(self):
        sourceIndex = self._proxyModel.source.index(0, 0)
        return self._proxyModel.mapFromSource(sourceIndex)

    def openBrowser(self, proxyIndex):
        if proxyIndex.isValid():
            itemUrl = self._proxyModel.data(proxyIndex, role=UrlModel.Role.URL)
            itemAnchorId = self._proxyModel.data(proxyIndex, role=UrlModel.Role.ANCHOR_ID)

            if itemAnchorId is None:
                webbrowser.open(itemUrl)
            else:
                webbrowser.open("#".join([itemUrl, itemAnchorId]))

    def requestUrl(self, proxyIndex, previousUrl):
        itemUrl = self._proxyModel.data(proxyIndex, role=UrlModel.Role.URL)
        itemAnchorId = self._proxyModel.data(proxyIndex, role=UrlModel.Role.ANCHOR_ID)

        if itemUrl != previousUrl or itemAnchorId is None:
            self.urlResponse.emit(QtCore.QUrl(itemUrl))

    def requestAnchorScript(self, proxyIndex):
        itemAnchorId = self._proxyModel.data(proxyIndex, role=UrlModel.Role.ANCHOR_ID)
        rootItemText = self._proxyModel.getSourceDataTree(proxyIndex, role=QtCore.Qt.DisplayRole)[0]

        if itemAnchorId is not None:
            if rootItemText == "Maya Python API 2.0":
                self.scriptResponse.emit(self._openMayaScripts + "scrollToAnchor(\"{}\");".format(itemAnchorId))
            elif rootItemText == "PySide2":
                self.scriptResponse.emit(self._pySideScripts + "scrollToAnchor(\"{}\");".format(itemAnchorId))

    def requestLoadFinishedScript(self, proxyIndex):
        rootItemText = self._proxyModel.getSourceDataTree(proxyIndex, role=QtCore.Qt.DisplayRole)[0]

        if rootItemText == "Maya Python API 2.0":
            self.scriptResponse.emit(self._openMayaScripts + "updateBaseCss();")
        elif rootItemText == "PySide2":
            self.scriptResponse.emit(self._pySideScripts + "updateCss();")

    def requestLoadProgressScript(self, proxyIndex):
        rootItemText = self._proxyModel.getSourceDataTree(proxyIndex, role=QtCore.Qt.DisplayRole)[0]

        if rootItemText == "Maya Python API 2.0":
            self.scriptResponse.emit(self._openMayaScripts + "updateEmbeddedCss();")

    def setModelFilter(self, text):
        self._proxyModel.setFilterRegExp(QtCore.QRegExp(text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString))
