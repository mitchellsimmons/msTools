"""
Manage installation of the `Doc Explorer` tool.

The `Doc Explorer` provides a view for exploring the documentation of various APIs including:

- Maya Python API 2.0
- Maya Python Commands
- PySide2

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Doc Explorer` tools using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
import sys

from msTools.vendor.Qt import QtWidgets

from msTools.tools import tool_manager
from msTools.tools.docExplorer.models.url_model import UrlProxyModel
from msTools.tools.docExplorer.controllers.url_controller import UrlController
from msTools.tools.docExplorer.views.main_window import MainWindow


# --------------------------------------------------------------
# --- Identifiers ---
# --------------------------------------------------------------

TOOL_NAMESPACE = "MRS"
""":class:`str`: The tool namespace used to register a `Doc Explorer` tool with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Doc Explorer"
""":class:`str`: The tool name used to register a `Doc Explorer` tool with the :mod:`msTools.tools.tool_manager`."""


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

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
def install(parent=None, force=False):
    """Install the `Doc Explorer` tool to a given parent.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (T <= :class:`PySide2.QtCore.QObject`, optional): Parent for the `Doc Explorer` tool. Defaults to :data:`None`.
        force (:class:`bool`): Whether to force the installation by removing any existing `Doc Explorer` tools from the given ``parent``.
            If :data:`False`, an existing `Doc Explorer` tool will be returned if one already exists under ``parent``.
            Defaults to :data:`False` - return any existing instance.

    Returns:
        The `Doc Explorer` tool parented under ``parent``. If ``force`` is :data:`False`, this could be an existing tool.
    """
    proxyModel = UrlProxyModel()
    window = MainWindow(proxyModel, parent=parent)
    controller = UrlController(proxyModel, parent=window)

    _connectExternalSignals(window, controller)
    window.setTreeViewIndex(proxyModel.index(0, 0))
    window.show()

    return window


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Doc Explorer` tool.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: A `Doc Explorer` tool to uninstall.
    """
    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Main ---
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = install()
    sys.exit(app.exec_())
