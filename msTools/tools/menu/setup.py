"""
Manage installation of the `msTools Menu` within the current Maya session.

The `msTools Menu` provides quick access to various tools and operations relating to the :doc:`msTools <../../index>` package.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `msTool Menus` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtWidgets

from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.tools import tool_manager
from msTools.tools.menu.controllers.menu_controller import MenuController
from msTools.tools.menu.views.proxy_menu import ProxyMenu


# --------------------------------------------------------------
# --- Identifiers ---
# --------------------------------------------------------------

TOOL_NAMESPACE = "MRS"
""":class:`str`: The tool namespace used to register a `msTools Menu` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "msTools Menu"
""":class:`str`: The tool name used to register a `msTools Menu` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def _install(parent, force=False):
    window = parent.parent()

    # The view is so specialised that there is no point in completely encapsulating it from the controller logic
    # Instead we can just pass the view a reference to the controller and allow it to connect directly
    controller = MenuController()
    proxyMenu = ProxyMenu(controller, window.objectName())
    return proxyMenu.menu


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def install(force=False):
    """Install the `msTools Menu` to the menu-bar of the Maya main window.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        force (:class:`bool`): Whether to force the installation by removing any existing `msTools Menu` from the menu-bar.
            If :data:`False`, an existing `msTools Menu` widget will be returned if one already exists under the menu-bar.
            Defaults to :data:`False` - return any existing instance.

    Returns:
        :class:`PySide2.QtWidgets.QMenu`: The `msTools Menu` widget.
    """
    mainWindow = UI_INSPECT.getMainWindow()
    parent = mainWindow.findChild(QtWidgets.QMenuBar)
    menu = _install(parent, force=force)
    return menu


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `msTools Menu`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool (:class:`PySide2.QtWidgets.QMenu`): An `msTools Menu` widget to uninstall.
    """
    tool.deleteLater()
