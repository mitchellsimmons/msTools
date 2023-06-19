"""
Manage installation of the `Align Node Tool` to an icon-bar of a Node Editor panel within the current Maya session.

The `Align Node Tool` provides a view for aligning selected graphical node items within the Node Editor.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Align Node Tools` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR

from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions.controllers.alignNodeTool_controller import AlignNodeToolController
from msTools.tools.nodeEditorExtensions.views.alignNodeTool_widget import AlignNodeToolWidget


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register an `Align Node Tool` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Align Node Tool"
""":class:`str`: The tool name used to register an `Align Node Tool` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Align Node Tool` to a given Node Editor icon-bar widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QWidget`): A Node Editor icon-bar, to be used as the parent for the `Align Node Tool`.
        force (:class:`bool`): Whether to reinstall the `Align Node Tool` if one already exists under ``parent``.
            If :data:`False`, skip installation if an `Align Node Tool` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor icon-bar.

    Returns:
        The `Align Node Tool` parented under ``parent``. If ``force`` is :data:`False`, this could be an existing view.
    """
    if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.ICON_BAR):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor icon bar widget for the parent")

    # Ensure the widget is added to the icon bar layout
    widget = AlignNodeToolWidget()
    parent.layout().addWidget(widget)
    controller = AlignNodeToolController(parent=widget)

    _connectExternalSignals(widget, controller)
    widget.show()

    return widget


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Align Node Tool`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: An `Align Node Tool` to uninstall.
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
    widget.alignLeftClicked.connect(controller.alignItemsLeft)
    widget.alignRightClicked.connect(controller.alignItemsRight)
    widget.alignTopClicked.connect(controller.alignItemsTop)
    widget.alignBottomClicked.connect(controller.alignItemsBottom)
    widget.alignHCenterClicked.connect(controller.alignItemsHCenter)
    widget.alignVCenterClicked.connect(controller.alignItemsVCenter)
    widget.distributeHGapsClicked.connect(controller.distributeItemsHGaps)
    widget.distributeVGapsClicked.connect(controller.distributeItemsVGaps)
