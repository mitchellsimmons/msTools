import logging
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCore

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.qt import widget_utils as QT_WIDGET


class ProxyMenu(QtCore.QObject):

    NAME = "MRS_msToolsProxyMenu"
    MENU_NAME = "MRS_msToolsMenu"

    def __init__(self, controller, parentName):
        self._controller = controller
        self._parentName = parentName

        if not (cmds.window(self._parentName, exists=True) and cmds.window(self._parentName, q=True, menuBar=True)) and not cmds.menuBarLayout(self._parentName, exists=True):
            raise UI_EXC.MayaUITypeError("Expected the name of a `window` with a `menuBar` or the name of a `menuBarLayout` to use as the parent")

        super(ProxyMenu, self).__init__()

        self.setObjectName(ProxyMenu.NAME)

        self._createMenu()
        self._parentProxy()
        self._connectController()

    @property
    def menu(self):
        return QT_WIDGET.retainAndReturn(self.parent())

    def _createMenu(self):
        self._menuPath = cmds.menu(ProxyMenu.MENU_NAME, parent=self._parentName, tearOff=True, allowOptionBoxes=True, label="msTools")

        # Tools
        self._toolsMenuPath = cmds.menuItem(parent=self._menuPath, subMenu=True, tearOff=True, label="Tools")
        self._docsExplorerMenuPath = cmds.menuItem(label="Doc Explorer")
        self._nodeEditorExtMenuPath = cmds.menuItem(label="Node Editor Extensions")
        cmds.setParent(self._menuPath, menu=True)
        cmds.menuItem(divider=True)

        # Open
        self._openMenuPath = cmds.menuItem(parent=self._menuPath, subMenu=True, tearOff=True, label="Open")
        self._packageDirMenuPath = cmds.menuItem(label="Package Directory")
        self._componentDirMenuPath = cmds.menuItem(label="Component Directory")
        cmds.setParent(self._menuPath, menu=True)
        cmds.menuItem(divider=True)

        # Dev
        self._devMenuPath = cmds.menuItem(parent=self._menuPath, subMenu=True, tearOff=True, label="Dev")
        self._reloadMenuPath = cmds.menuItem(label="Reload")
        cmds.menuItem(divider=True)
        self._rebuildQtResourcesMenuPath = cmds.menuItem(label="Rebuild Qt Resources")
        cmds.setParent(self._menuPath, menu=True)
        cmds.menuItem(divider=True)

        # Help
        self._helpMenuPath = cmds.menuItem(parent=self._menuPath, subMenu=True, tearOff=True, label="Help")
        self._docsMenuPath = cmds.menuItem(label="Documentation")
        self._releaseLogMenuPath = cmds.menuItem(label="Release Log")
        cmds.menuItem(divider=True)
        self._githubMenuPath = cmds.menuItem(label="GitHub")
        cmds.menuItem(divider=True)
        self._aboutMenuPath = cmds.menuItem(label="About")

    def _parentProxy(self):
        self.setParent(UI_INSPECT.getWidget(self._menuPath))

    def _connectController(self):
        # Tools
        cmds.menuItem(self._docsExplorerMenuPath, edit=True, command=lambda *args: self._controller.installDocsExplorer())
        cmds.menuItem(self._nodeEditorExtMenuPath, edit=True, command=lambda *args: self._controller.installNodeEditorExtensions())

        # Open
        cmds.menuItem(self._packageDirMenuPath, edit=True, command=lambda *args: self._controller.openPackageDirectory())
        cmds.menuItem(self._componentDirMenuPath, edit=True, command=lambda *args: self._controller.openComponentDirectory())

        # Dev
        cmds.menuItem(self._reloadMenuPath, edit=True, command=lambda *args: self._controller.reloadPackage())
        cmds.menuItem(self._rebuildQtResourcesMenuPath, edit=True, command=lambda *args: self._controller.rebuildQtResources())

        # Help
        cmds.menuItem(self._docsMenuPath, edit=True, command=lambda *args: self._controller.loadDocumentation())
        cmds.menuItem(self._releaseLogMenuPath, edit=True, command=lambda *args: self._controller.loadReleaseLog())
        cmds.menuItem(self._githubMenuPath, edit=True, command=lambda *args: self._controller.loadGithub())
        cmds.menuItem(self._aboutMenuPath, edit=True, command=lambda *args: self._controller.loadAbout())
