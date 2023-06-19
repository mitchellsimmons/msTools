"""
Manage installation of the `Doc Explorer` tool within the current Maya session.

The `Doc Explorer` provides a view for exploring the documentation of various APIs including:

- Maya Python API 2.0
- Maya Python Commands
- PySide2

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Doc Explorer` tools using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.maya import widget_utils as UI_WIDGET

from msTools.tools import tool_manager
from msTools.tools.docExplorer.models.url_model import UrlProxyModel
from msTools.tools.docExplorer.controllers.url_controller import UrlController
from msTools.tools.docExplorer.views.main_window import MainWindow


# --------------------------------------------------------------
# --- Identifiers ---
# --------------------------------------------------------------

DOCK_NAME = "DocExplorer_WorkspaceControl"
""":class:`str`: The widget name given to the :func:`cmds.workspaceControl` when docking a `Doc Explorer` tool."""

TOOL_NAMESPACE = "MRS"
""":class:`str`: The tool namespace used to register a `Doc Explorer` tool with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Doc Explorer"
""":class:`str`: The tool name used to register a `Doc Explorer` tool with the :mod:`msTools.tools.tool_manager`."""


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

def _uiScript():
    # The installation is deferred to allow any userScript.py scripts to setup the Maya environment (ie. add to sys.path)
    installScript = "import {moduleName}\\nview={moduleName}.install(dock=True)".format(moduleName=__name__)

    editScript = "cmds.workspaceControl(\\\"{dockName}\\\", e=True, uiScript={moduleName}._uiScript())".format(dockName=DOCK_NAME, moduleName=__name__)

    return "cmds.evalDeferred(\"{installScript}\\n{editScript}\", lowestPriority=True)".format(installScript=installScript, editScript=editScript)


def _connectExternalSignals(window, controller):
    """Connect implementation dependent signals (ie. those which are unknown to the view).

    Externally connected signals are designed to maintain encapsulation between the view and controller classes.
    """
    # --- View -> Controller ---

    # Requests a url if it is not already loaded (we pass the current url for comparison)
    window.treeViewIndexChanged.connect(lambda index: controller.requestUrl(index, window.getUrl()))

    # Requests an anchor script in case the url is already loaded
    window.treeViewIndexChanged.connect(controller.requestAnchorScript)

    # Update proxy model filtering
    window.searchTextChanged.connect(controller.setModelFilter)

    # Open the current page in a browser
    window.browserButtonPressed.connect(lambda: controller.openBrowser(window.getTreeViewIndex()))

    # Modify the css to hide unnecessary elements in the main document
    window.webViewLoadFinished.connect(lambda ok: controller.requestLoadFinishedScript(window.getTreeViewIndex()))
    # Modify the css to hide unnecessary elements in embedded documents (webViewLoadFinished occurs before embedded elements have loaded)
    window.webViewLoadProgress.connect(lambda progress: controller.requestLoadProgressScript(window.getTreeViewIndex()))

    # Ensures a url with an anchor will scroll to the correct location if the anchor is within the main document
    window.webViewLoadFinished.connect(lambda ok: controller.requestAnchorScript(window.getTreeViewIndex()))
    # Ensures a url with an anchor will scroll to the correct location if the anchor is within an embedded document (webViewLoadFinished occurs before embedded elements have loaded)
    window.webViewLoadProgress.connect(lambda progress: controller.requestAnchorScript(window.getTreeViewIndex()))

    # --- Controller -> View ---

    # Load urls and run scripts
    controller.urlResponse.connect(window.loadUrl)
    controller.scriptResponse.connect(window.runScript)


@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def _install(parent):
    # Manually force uninstall (instead of through the `tool_manager`) since the parent may be the dock control or main window
    uninstall()

    proxyModel = UrlProxyModel()
    window = MainWindow(proxyModel, parent=parent)
    controller = UrlController(proxyModel, parent=window)

    _connectExternalSignals(window, controller)
    window.setTreeViewIndex(proxyModel.index(0, 0))

    return window


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def _uninstall(tool):
    UI_WIDGET.delete(tool)


# --------------------------------------------------------------
# --- Installation ---
# --------------------------------------------------------------

def install(dock=True):
    """Force install a `Doc Explorer` tool to the Maya main window or a dock control.

    Forced installation means that any existing `Doc Explorer` tool will be uninstalled before installation.
    The new tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        dock (:class:`bool`): Whether to dock the `Doc Explorer` tool. If :data:`False`, the tool will be parented to the Maya main window.
            Defaults to :data:`True`.

    Returns:
        The new `Doc Explorer` tool.
    """
    parent = UI_INSPECT.getMainWindow()

    window = _install(parent)
    window.show()

    if dock:
        UI_WIDGET.dock(window, dockName=DOCK_NAME, uiScript=_uiScript())

    return window


def uninstall():
    """Uninstall all existing `Doc Explorer` tools.

    Any uninstalled tool will be deregistered from the :mod:`msTools.tools.tool_manager`.
    """
    tool_manager.uninstallFromAll(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
