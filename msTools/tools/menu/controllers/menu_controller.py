import os

from maya import mel

import msTools
from msTools.core.py import module_utils as PY_MODULE
from msTools.core.py import path_utils as PY_PATH
from msTools.coreUI.qt import resource_utils as QT_RESOURCE
from msTools.tools.docExplorer import maya_setup


class MenuController(object):

    def installDocsExplorer(self):
        maya_setup.install(dock=True)

    def installNodeEditorExtensions(self):
        raise NotImplementedError

    def openPackageDirectory(self):
        PY_PATH.openFile(msTools.__path__[0])

    def openComponentDirectory(self):
        raise NotImplementedError

    def reloadPackage(self):
        PY_MODULE.reloadPackage(msTools.__name__)

    def rebuildQtResources(self):
        mayaInstallPath = os.path.normpath(mel.eval("getenv MAYA_LOCATION"))
        mayaBinaryPath = os.path.join(mayaInstallPath, "bin")
        compilerPath = os.path.join(mayaBinaryPath, "pyside2-rcc.exe")

        if not os.path.exists(compilerPath):
            raise RuntimeError("Could not find a Qt Resource compiler within the Maya install location")

        for qrcFilePath in PY_PATH.iterFiles(msTools.__path__[0], ext="qrc", walk=True):
            qrcFileName = os.path.basename(qrcFilePath).split(".qrc")[0]
            resourcesDirPath = os.path.dirname(qrcFilePath)
            resourcesDirName = os.path.basename(resourcesDirPath)

            if qrcFileName == "resources" and resourcesDirName == "resources":
                # Rebuild the Qt Resource Collection file
                QT_RESOURCE.buildResourceCollection(resourcesDirPath)

                # Recompile binary data from the rebuilt Qt Resource Collection file
                QT_RESOURCE.compileResourceCollection(qrcFilePath, compilerPath)

    def loadDocumentation(self):
        raise NotImplementedError

    def loadReleaseLog(self):
        raise NotImplementedError

    def loadGithub(self):
        raise NotImplementedError

    def loadAbout(self):
        raise NotImplementedError
