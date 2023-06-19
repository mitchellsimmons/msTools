"""
Manage installation of the `Import Export Tool` to the icon-bar of a Node Editor panel within the current Maya session.

The `Import Export Tool` provides a view for importing and exporting layout data relating to graphical items within the Node Editor.

- Exporting provides the ability to save the current state of a Node Editor tab.
- Importing allows the state to be restored or duplicated within another tab.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Import Export Tools` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions.controllers.importExportTool_controller import ImportExportToolController
from msTools.tools.nodeEditorExtensions.views.importExportTool_widget import ImportExportToolWidget


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register an `Import Export Tool` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Import Export Tool"
""":class:`str`: The tool name used to register an `Import Export Tool` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Import Export Tool` to a given Node Editor icon-bar widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QWidget`): A Node Editor icon-bar, to be used as the parent for the `Import Export Tool`.
        force (:class:`bool`): Whether to reinstall the `Import Export Tool` if one already exists under ``parent``.
            If :data:`False`, skip installation if an `Import Export Tool` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor icon-bar.

    Returns:
        The `Import Export Tool` parented under ``parent``. If ``force`` is :data:`False`, this could be an existing view.
    """
    if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.ICON_BAR):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor icon bar widget for the parent")

    # Ensure the widget is added to the icon bar layout
    widget = ImportExportToolWidget()
    controller = ImportExportToolController(parent=widget)
    parent.layout().addWidget(widget)

    _connectExternalSignals(widget, controller)
    widget.show()

    return widget


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Import Export Tool`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: An `Import Export Tool` to uninstall.
    """
    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _connectExternalSignals(widget, controller):
    """Connect implementation dependent signals (ie. those which are unknown to the view).

    Externally connected signals are designed to maintain encapsulation between the view and controller classes.
    """
    # --- View -> Controller ---
    widget.importClicked.connect(controller.importData)
    widget.exportClicked.connect(controller.exportData)
