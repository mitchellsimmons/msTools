"""
Manage installation of the `Create Node Tool` to the page area of a Node Editor panel within the current Maya session.

The `Create Node Tool` provides a view for creating nodes within the Node Editor.
It is designed to replace the default tool that is shown upon pressing the `tab` key in the Node Editor.

The :mod:`msTools.tools.tool_manager` can be used to retrieve existing `Create Node Tools` using the :data:`TOOL_NAMESPACE` and :data:`TOOL_NAME`.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore

from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import widget_utils as QT_WIDGET

from msTools.tools import tool_manager
from msTools.tools.nodeEditorExtensions.controllers import nodeType_controller
from msTools.tools.nodeEditorExtensions.controllers.createNodeTool_controller import CreateNodeToolController
from msTools.tools.nodeEditorExtensions.models import nodeType_model
from msTools.tools.nodeEditorExtensions.views.createNodeTool_window import CreateNodeToolWindow


# ----------------------------------------------------------------------------
# --- Identifiers ---
# ----------------------------------------------------------------------------

TOOL_NAMESPACE = "MRS:Node Editor"
""":class:`str`: The tool namespace used to register an `Create Node Tool` with the :mod:`msTools.tools.tool_manager`."""

TOOL_NAME = "Create Node Tool"
""":class:`str`: The tool name used to register an `Create Node Tool` with the :mod:`msTools.tools.tool_manager`."""


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def preInstall():
    """Complete pre-installation of the `Create Node Tool` to ensure the internal `Node Type Model` and `Node Type Controller` are built.

    Building the `Node Type Model` is a resource intensive operation which should be completed before installation.

    Note:
        Pre-installation is recommended but not required.
    """
    # Install the global NodeTypeController for the global NodeTypeModel
    nodeType_controller.getGlobalNodeTypeController()


@tool_manager.installer(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def install(parent, force=False):
    """Install the `Create Node Tool` to a given Node Editor page-area widget.

    The tool will be registered with the :mod:`msTools.tools.tool_manager`.

    Args:
        parent (:class:`PySide2.QtWidgets.QStackedWidget`): A Node Editor page area, to be used as the parent for the `Create Node Tool`.
        force (:class:`bool`): Whether to reinstall the `Create Node Tool` if one already exists under ``parent``.
            If :data:`False`, skip installation if a `Create Node Tool` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``parent`` is not a Node Editor page-area.

    Returns:
        The `Create Node Tool` parented under ``parent``. If ``force`` is :data:`False`, this could be an existing view.
    """
    if not UI_NODE_EDITOR.isNodeEditorObject(parent, UI_NODE_EDITOR.NodeEditorObject.PAGE_AREA):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor page area widget for the parent")

    preInstall()

    proxyModel = nodeType_model.NodeTypeProxyModel()
    window = CreateNodeToolWindow(proxyModel, parent=parent)
    controller = CreateNodeToolController(proxyModel, parent=window)

    # Ensure model is deleted with window (otherwise model signals will try to update the deleted window)
    proxyModel.setParent(window)

    _connectExternalSignals(window, controller)
    _positionWindow(window, parent)
    window.show()

    return window


@tool_manager.uninstaller(namespace=TOOL_NAMESPACE, name=TOOL_NAME)
def uninstall(tool):
    """Uninstall a given `Create Node Tool`.

    The tool will be deregistered from the :mod:`msTools.tools.tool_manager`.

    Args:
        tool: A `Create Node Tool` to uninstall.
    """
    tool.deleteLater()


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _connectExternalSignals(window, controller):
    """Connect implementation dependent signals (ie. those which are unknown to the view).

    Externally connected signals are designed to maintain encapsulation between the view and controller classes.
    """
    # --- View -> Controller ---
    window.nodeTypeSelected.connect(controller.createNode)
    window.searchTextChanged.connect(controller.setModelFilter)

    # --- Controller -> View ---
    controller.nodeCreated.connect(window.close)


def _positionWindow(window, parent):
    # Ensure the window's top left corner is bounded by the Node Editor page area
    QT_WIDGET.centerWidgetOnCursor(window, xOffset=window.width() / 2 + 30, yOffset=0)

    parentTopLeftPos_global = parent.mapToGlobal(QtCore.QPoint(0.0, 0.0))
    parentBottomRightPos_global = parent.mapToGlobal(QtCore.QPoint(parent.width(), parent.height()))

    # Window coordinates are already global
    windowTopLeftPos_global = window.geometry().topLeft()
    windowBottomRightPos_global = windowTopLeftPos_global + QtCore.QPoint(window.width(), window.height())

    leftOverflow = parentTopLeftPos_global.x() - windowTopLeftPos_global.x()
    topOverflow = parentTopLeftPos_global.y() - windowTopLeftPos_global.y()
    rightOverflow = parentBottomRightPos_global.x() - windowBottomRightPos_global.x()
    bottomOverflow = parentBottomRightPos_global.y() - windowBottomRightPos_global.y()

    if parent.width() < window.width():
        window.move(parentTopLeftPos_global.x(), window.y())
    elif leftOverflow > 0:
        window.move(window.x() + leftOverflow, window.y())
    elif (rightOverflow < 0):
        window.move(window.x() + rightOverflow, window.y())

    if parent.height() < window.height():
        window.move(window.x(), parentTopLeftPos_global.y())
    elif topOverflow > 0:
        window.move(window.x(), window.y() + topOverflow)
    elif bottomOverflow < 0:
        window.move(window.x(), window.y() + bottomOverflow)
