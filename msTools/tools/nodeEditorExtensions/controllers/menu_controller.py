from maya import cmds

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions import constants
from msTools.tools.nodeEditorExtensions import backgroundOptimisation_manager
from msTools.tools.nodeEditorExtensions import maintainLayout_manager
from msTools.tools.nodeEditorExtensions import shakeToDisconnect_manager
from msTools.tools.nodeEditorExtensions.views.proxy_menu import ProxyMenu


class MenuController(object):

    def updateSetting(self, optionVar, value):
        cmds.optionVar(intValue=(optionVar, value))

    def updateMaintainLayout(self, state):
        self.updateSetting(constants.ML_OPTIONVAR[0], state)

        if state:
            maintainLayout_manager.install()
        else:
            maintainLayout_manager.uninstall()

    def updateOptimiseBackground(self, state):
        self.updateSetting(constants.OB_OPTIONVAR[0], state)

        nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

        for nodeEditorPanelName in nodeEditorPanelNames:
            try:
                nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)
                nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
            except UI_EXC.MayaUILookupError:
                continue

            if state:
                backgroundOptimisation_manager.install(parent=nodeEditor)
            else:
                tool_manager.uninstall(namespace=backgroundOptimisation_manager.TOOL_NAMESPACE, name=backgroundOptimisation_manager.TOOL_NAME, parent=nodeEditor)

    def updateShakeToDisconnect(self, state):
        self.updateSetting(constants.STD_OPTIONVAR[0], state)

        nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

        for nodeEditorPanelName in nodeEditorPanelNames:
            try:
                nodeEditorPanel = UI_INSPECT.getWidget(nodeEditorPanelName)
                nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
            except UI_EXC.MayaUILookupError:
                continue

            if state:
                shakeToDisconnect_manager.install(parent=nodeEditor)
            else:
                tool_manager.uninstall(namespace=shakeToDisconnect_manager.TOOL_NAMESPACE, name=shakeToDisconnect_manager.TOOL_NAME, parent=nodeEditor)

    def refreshMenu(self, menu):
        """Set items to current optionVar values and disable or enable items as necessary."""
        menuName = UI_INSPECT.getFullName(menu)

        # --- Create Node Tool ---
        cntValue = cmds.optionVar(q=constants.CNT_OPTIONVAR[0])

        item = "|".join([menuName, ProxyMenu.CNTI_NAME])
        cmds.menuItem(item, e=True, checkBox=cntValue)

        # --- Shake To Disconnect ---
        stdValue = cmds.optionVar(q=constants.STD_OPTIONVAR[0])
        stValue = cmds.optionVar(q=constants.ST_OPTIONVAR[0])
        emValue = cmds.optionVar(q=constants.EM_OPTIONVAR[0])

        item = "|".join([menuName, ProxyMenu.STDI_NAME])
        cmds.menuItem(item, e=True, checkBox=stdValue)
        item = "|".join([menuName, ProxyMenu.LSTI_NAME])
        cmds.menuItem(item, e=True, radioButton=stValue == 0)
        item = "|".join([menuName, ProxyMenu.MSTI_NAME])
        cmds.menuItem(item, e=True, radioButton=stValue == 1)
        item = "|".join([menuName, ProxyMenu.HSTI_NAME])
        cmds.menuItem(item, e=True, radioButton=stValue == 2)
        item = "|".join([menuName, ProxyMenu.EMI_NAME])
        cmds.menuItem(item, e=True, checkBox=emValue)

        item = "|".join([menuName, ProxyMenu.STI_NAME])
        cmds.menuItem(item, e=True, enable=stdValue)
        item = "|".join([menuName, ProxyMenu.EMI_NAME])
        cmds.menuItem(item, e=True, enable=stdValue)

        # --- Maintain Layout ---
        mlValue = cmds.optionVar(q=constants.ML_OPTIONVAR[0])
        ucpValue = cmds.optionVar(q=constants.UCP_OPTIONVAR[0])

        item = "|".join([menuName, ProxyMenu.MLI_NAME])
        cmds.menuItem(item, e=True, checkBox=mlValue)
        item = "|".join([menuName, ProxyMenu.CI_NAME])
        cmds.menuItem(item, e=True, radioButton=ucpValue == 0)
        item = "|".join([menuName, ProxyMenu.NTSI_NAME])
        cmds.menuItem(item, e=True, radioButton=ucpValue == 1)
        item = "|".join([menuName, ProxyMenu.NTDI_NAME])
        cmds.menuItem(item, e=True, radioButton=ucpValue == 2)
        item = "|".join([menuName, ProxyMenu.RI_NAME])
        cmds.menuItem(item, e=True, radioButton=ucpValue == 3)

        item = "|".join([menuName, ProxyMenu.UCPI_NAME])
        cmds.menuItem(item, e=True, enable=mlValue)

        # --- Optimise Background ---
        obValue = cmds.optionVar(q=constants.OB_OPTIONVAR[0])

        item = "|".join([menuName, ProxyMenu.OBI_NAME])
        cmds.menuItem(item, e=True, checkBox=obValue)
