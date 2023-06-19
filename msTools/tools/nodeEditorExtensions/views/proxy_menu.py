import logging
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCore

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.qt import widget_utils as QT_WIDGET
from msTools.tools.nodeEditorExtensions import constants as EXT_CONSTANTS


class ProxyMenu(QtCore.QObject):

    # Proxy
    NAME = "MRS_nodeEditorExtensionsProxyMenu"

    # Menu
    MENU_NAME = "MRS_nodeEditorExtensionsMenu"

    # Items
    CNTI_NAME = "CNTI"
    STDI_NAME = "STDI"
    STI_NAME = "STI"
    LSTI_NAME = "LSTI"
    MSTI_NAME = "MSTI"
    HSTI_NAME = "HSTI"
    EMI_NAME = "EMI"
    MLI_NAME = "MLI"
    UCPI_NAME = "UCPI"
    CI_NAME = "CI"
    NTSI_NAME = "NTSI"
    NTDI_NAME = "NTDI"
    RI_NAME = "RI"
    OBI_NAME = "OBI"

    _ANNOTATIONS = {
        CNTI_NAME: "Replace Maya's default \"tab\" to create tool with a custom tool",
        STDI_NAME: "Shake nodes to disconnect all connections to non-default nodes",
        STI_NAME: "Specify how hard a node needs to be shook for it to disconnect",
        EMI_NAME: "Specify whether message type connections should be broken",
        MLI_NAME: "Prevent Maya from automatically laying out the graph when a connection is made",
        UCPI_NAME: "Specify where unit conversion nodes should be positioned on creation",
        CI_NAME: "Unit conversion nodes will be positioned between the source and destination nodes",
        NTSI_NAME: "Unit conversion nodes will be positioned next to the source node",
        NTDI_NAME: "Unit conversion nodes will be positioned next to the destination node",
        RI_NAME: "Let Maya decide where to position unit conversion nodes",
        OBI_NAME: "Optimise painting of the Node Editor background",
    }

    def __init__(self, controller, parentName):
        self._parentName = parentName
        self._controller = controller

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
        self._menuPath = cmds.menu(ProxyMenu.MENU_NAME, allowOptionBoxes=True, tearOff=True, parent=self._parentName, label="Extensions")

        # --- Create Node Tool ---
        self._cntiPath = cmds.menuItem(ProxyMenu.CNTI_NAME, checkBox=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.CNTI_NAME], label="Create Node Tool")
        cmds.menuItem(divider=True)

        # --- Shake To Disconnect ---
        self._stdiPath = cmds.menuItem(ProxyMenu.STDI_NAME, checkBox=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.STDI_NAME], label="Shake To Disconnect")
        self._stiPath = cmds.menuItem(ProxyMenu.STI_NAME, subMenu=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.STI_NAME], label="Shake Tolerance")
        cmds.radioMenuItemCollection()
        self._lstiPath = cmds.menuItem(ProxyMenu.LSTI_NAME, radioButton=False, label="Low")
        self._mstiPath = cmds.menuItem(ProxyMenu.MSTI_NAME, radioButton=True, label="Medium")
        self._hstiPath = cmds.menuItem(ProxyMenu.HSTI_NAME, radioButton=False, label="High")
        cmds.setParent("..", menu=True)
        self._emiPath = cmds.menuItem(ProxyMenu.EMI_NAME, checkBox=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.EMI_NAME], label="Exclude Messages")
        cmds.menuItem(divider=True)

        # --- Maintain Layout ---
        self._mliPath = cmds.menuItem(ProxyMenu.MLI_NAME, checkBox=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.MLI_NAME], label="Maintain Layout")
        self._ucpiPath = cmds.menuItem(ProxyMenu.UCPI_NAME, subMenu=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.UCPI_NAME], label="Unit Conversion Position")
        cmds.radioMenuItemCollection()
        self._ciPath = cmds.menuItem(ProxyMenu.CI_NAME, radioButton=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.MLI_NAME], label="Center")
        self._ntsiPath = cmds.menuItem(ProxyMenu.NTSI_NAME, radioButton=False, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.NTSI_NAME], label="Next To Source")
        self._ntdiPath = cmds.menuItem(ProxyMenu.NTDI_NAME, radioButton=False, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.NTDI_NAME], label="Next To Destination")
        self._riPath = cmds.menuItem(ProxyMenu.RI_NAME, radioButton=False, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.RI_NAME], label="Random [Disabled]")
        cmds.setParent("..", menu=True)
        cmds.menuItem(divider=True)

        # --- Optimise Background ---
        self._obiPath = cmds.menuItem(ProxyMenu.OBI_NAME, checkBox=True, annotation=ProxyMenu._ANNOTATIONS[ProxyMenu.OBI_NAME], label="Optimise Background")
        cmds.setParent("..", menu=True)

    def _parentProxy(self):
        self.setParent(UI_INSPECT.getWidget(self._menuPath))

    def _connectController(self):
        cmds.menu(self._menuPath, edit=True, postMenuCommand=lambda *args: self._controller.refreshMenu(self.menu))

        # --- Create Node Tool ---
        cmds.menuItem(self._cntiPath, edit=True, command=lambda state: self._controller.updateSetting(EXT_CONSTANTS.CNT_OPTIONVAR[0], state))

        # --- Shake To Disconnect ---
        cmds.menuItem(self._stdiPath, edit=True, command=self._controller.updateShakeToDisconnect)
        cmds.menuItem(self._lstiPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.ST_OPTIONVAR[0], 0))
        cmds.menuItem(self._mstiPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.ST_OPTIONVAR[0], 1))
        cmds.menuItem(self._hstiPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.ST_OPTIONVAR[0], 2))
        cmds.menuItem(self._emiPath, edit=True, command=lambda state: self._controller.updateSetting(EXT_CONSTANTS.EM_OPTIONVAR[0], state))

        # --- Maintain Layout ---
        cmds.menuItem(self._mliPath, edit=True, command=self._controller.updateMaintainLayout)
        cmds.menuItem(self._ciPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.UCP_OPTIONVAR[0], 0))
        cmds.menuItem(self._ntsiPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.UCP_OPTIONVAR[0], 1))
        cmds.menuItem(self._ntdiPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.UCP_OPTIONVAR[0], 2))
        cmds.menuItem(self._riPath, edit=True, command=lambda *args: self._controller.updateSetting(EXT_CONSTANTS.UCP_OPTIONVAR[0], 3))

        # --- Optimise Background ---
        cmds.menuItem(self._obiPath, edit=True, command=self._controller.updateOptimiseBackground)
