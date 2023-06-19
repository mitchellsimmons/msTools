"""
Manage installation of the `Layout Tool` to the icon-bar of the **primary** Node Editor panel within the current Maya session.

The `Layout Tool` provides a view for creating the following custom layout items within the Node Editor:

- `NodeBoxItem`: Provides structure to the graph, allowing for visual encapsulation of components.
- `StickyItem`: Provides the ability to add comments to the graph.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Layout Tools` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from maya import mel

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions import nodeGraphEditorInfo_manager
from msTools.tools.nodeEditorExtensions.controllers.layoutTool_controller import LayoutToolController
from msTools.tools.nodeEditorExtensions.views.layoutTool_widget import LayoutToolWidget


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register a `Layout Tool` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Layout Tool"
""":class:`str`: The tool name used to register a `Layout Tool` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Layout Tool` to the icon-bar of the **primary** Node Editor.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QWidget`): The icon-bar of the **primary** Node Editor, to be used as the parent for the `Layout Tool`.
        force (:class:`bool`): Whether to reinstall the `Layout Tool` if one already exists under ``parent``.
            If :data:`False`, skip installation if a `Layout Tool` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor icon-bar.
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not the icon-bar of the **primary** Node Editor.

    Returns:
        The `Layout Tool` parented under ``parent``. If ``force`` is :data:`False`, this could be an existing view.
    """
    if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.ICON_BAR):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor icon bar widget for the parent")

    nodeEditorPanel = UI_NODE_EDITOR.getNodeEditorPanelFromDescendant(parent)
    nodeEditor = UI_NODE_EDITOR.getNodeEditorFromPanel(nodeEditorPanel)
    primaryNodeEditorName = mel.eval("getPrimaryNodeEditor")

    if nodeEditor.objectName() != primaryNodeEditorName:
        raise UI_EXC.MayaUITypeError("Expected the Node Editor icon bar widget for the primary Node Editor panel")

    # This tool makes use of non-writable nodes which can cause issues when saving and reloading the scene with the Node Editor open
    nodeGraphEditorInfo_manager.install()

    # Ensure the widget is added to the icon bar layout
    widget = LayoutToolWidget()
    controller = LayoutToolController(parent=widget)
    parent.layout().addWidget(widget)

    _connectExternalSignals(widget, controller)
    widget.show()

    return widget


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool, clearMetadata=False):
    """Uninstall a given `Layout Tool`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Note:
        The `Layout Tool Accessor` will remain installed to ensure metadata changes can be written to file when the scene is saved.

    Args:
        tool: A `Layout Tool` to uninstall.
        clearMetadata (:class:`bool`): Whether to clear metadata associated with the `Layout Tool`.
            If :data:`False`, items will be reloaded from existing metadata next time the `Layout Tool` is installed.
            This is essentially what occurs when the Node Editor is closed, the tool is uninstalled but metadata is retained by the `Layout Tool Associations`.
            Defaults to :data:`False`.
    """
    controller = tool.findChild(LayoutToolController)
    controller.clearItems(clearMetadata=clearMetadata)

    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _connectExternalSignals(widget, controller):
    """Connect implementation dependent signals (ie. those which are unknown to the view).

    Externally connected signals are designed to maintain encapsulation between the view and controller classes.
    """
    # --- View -> Controller ---
    widget.nodeBoxClicked.connect(controller.createNodeBox)
    widget.stickyClicked.connect(controller.createSticky)
