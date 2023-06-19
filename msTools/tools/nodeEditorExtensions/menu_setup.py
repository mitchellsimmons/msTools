"""
Manage installation of the `Extensions Menu` to the menu-bar of a Node Editor panel within the current Maya session.

The `Extensions Menu` provides quick access to various operations and settings relating to the collection of `Node Editor Extensions`.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Extensions Menus` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions.controllers.menu_controller import MenuController
from msTools.tools.nodeEditorExtensions.views.proxy_menu import ProxyMenu


# --------------------------------------------------------------
# --- Identifiers ---
# --------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register an `Extensions Menu` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Extensions Menu"
""":class:`str`: The tool name used to register an `Extensions Menu` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Extensions Menu` to the menu-bar of a Node Editor.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QMenuBar`): A Node Editor menu-bar, to be used as the parent for the `Extensions Menu`.
        force (:class:`bool`): Whether to reinstall the `Extensions Menu` if one already exists under ``parent``.
            If :data:`False`, skip installation if an `Extensions Menu` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor menu-bar.

    Returns:
        :class:`PySide2.QtWidgets.QMenu`: The `Extensions Menu` widget.
    """
    if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.MENU_BAR):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor menu bar widget for the parent")

    # Pass the name of a `menuBarLayout` as the parent
    nodeEditorPanel = UI_NODE_EDITOR.getNodeEditorPanelFromDescendant(parent)

    # The view is so specialised that there is no point in completely encapsulating it from the controller logic
    # Instead we can just pass the view a reference to the controller and allow it to connect directly
    controller = MenuController()
    proxyMenu = ProxyMenu(controller, nodeEditorPanel.objectName())
    menu = proxyMenu.menu

    return menu


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Extensions Menu`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool (:class:`PySide2.QtWidgets.QMenu`): An `Extensions Menu` to uninstall.
    """
    tool.deleteLater()
