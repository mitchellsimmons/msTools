"""
Utility functions relating to Maya widgets.

----------------------------------------------------------------

Terminology
-----------

    The following terminology is adopted by this module and other modules within this package.

    .. list-table::
       :widths: 25 75
       :header-rows: 1

       * - Term
         - Description
       * - `Window`
         - A widget which which has the :attr:`PySide2.QtCore.Qt.Window` flag set.
       * - `Docked Widget`
         - A widget which which is parented to a :func:`cmds.workspaceControl`.

----------------------------------------------------------------
"""
import logging
import uuid
log = logging.getLogger(__name__)

from maya import cmds

from msTools.vendor.Qt import QtCore, QtWidgets

from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.qt import constants as QT_CONST
from msTools.coreUI.qt import widget_utils as QT_WIDGET


# ----------------------------------------------------------------
# --- Windows / Docking ---
# ----------------------------------------------------------------

def isDocked(widget):
    """Return whether a widget is docked.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to query.

    Returns:
        :class:`bool`: :data:`True` if ``widget`` is docked to a :func:`cmds.workspaceControl`, otherwise :data:`False`.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())
    return cmds.workspaceControl(parent.objectName(), q=True, exists=True) if parent is not None else False


def isFloating(widget):
    """Return whether a widget is floating.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to query.

    Returns:
        :class:`bool`: :data:`True` if ``widget`` is a window or is docked to a :func:`cmds.workspaceControl` which is floating, otherwise :data:`False`.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        return cmds.workspaceControl(parent.objectName(), q=True, floating=True)

    if not widget.windowFlags() & QtCore.Qt.Window:
        return False

    return True


def show(widget):
    """Show a widget or its :func:`cmds.workspaceControl`.

    - If the widget is unparented, it will be parented to the Maya main window as a standalone window.
    - If the widget is undocked but parented, it will be restored if minimized, raised if covered and shown if hidden.
    - If the widget is docked, the :func:`cmds.workspaceControl` will be restored.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to show.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is None:
        mayaWindow = QT_WIDGET.retainAndReturn(UI_INSPECT.getMainWindow())
        widget.setParent(mayaWindow)
        widget.setWindowFlags(QtCore.Qt.Window)
    else:
        if cmds.workspaceControl(parent.objectName(), q=True, exists=True):
            # If the widget is docked, restore the workspaceControl
            cmds.workspaceControl(parent.objectName(), e=True, restore=True)
        else:
            # If the widget is a minimised window, restore it
            if widget.isMinimized():
                widget.showNormal()

            # If the widget is a covered window, raise it to the top of its parent widget's stack
            widget.raise_()

    # If the widget has just been parented but is not yet visible
    widget.show()


def hide(widget):
    """Hide an undocked widget or the :func:`cmds.workspaceControl` of a docked widget.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to hide.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None:
        if cmds.workspaceControl(parent.objectName(), q=True, exists=True):
            cmds.workspaceControl(parent.objectName(), e=True, visible=False)
            return

    widget.hide()


def dock(widget, dockName=None, retain=None, uiScript=None):
    """Dock a widget to a :func:`cmds.workspaceControl`.

    If the :func:`cmds.workspaceControl` already exists it will be restored (ie. expanded if collapsed, restored if minimized, shown if hidden).
    Otherwise a new :func:`cmds.workspaceControl` will be created.

    If the ``dockName`` is :data:`None`, the widget will be assigned a :meth:`PySide2.QtCore.QObject.objectName` if it does not already have one.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to dock.
        dockName (:class:`basestring`): Name of an existing :func:`cmds.workspaceControl` or name for the new :func:`cmds.workspaceControl`.
            Defaults to :data:`None` - use the :meth:`PySide2.QtCore.QObject.objectName` of ``widget`` to determine a name for the :func:`cmds.workspaceControl`.
        retain (:class:`bool`): Whether the :func:`cmds.workspaceControl` will be hidden instead of deleted when it is closed.
            Defaults to :data:`None` - retain behaviour is based on the :attr:`PySide2.QtCore.Qt.WA_DeleteOnClose` attribute of the ``widget``.
        uiScript (:class:`basestring`, optional): Script to use when creating the :func:`cmds.workspaceControl`.
            Responsible for docking a new instance of the widget. Defaults to :data:`None` - no script.
    """
    if not dockName:
        if not widget.objectName():
            widget.setObjectName("{}_{}".format(widget.__class__.__name__, uuid.uuid4()))

        dockName = widget.objectName() + "_WorkspaceControl"

    if not cmds.workspaceControl(dockName, q=True, exists=True):
        retain = retain if retain is not None else not widget.testAttribute(QtCore.Qt.WA_DeleteOnClose)

        # If the widget has a default size, it is likely uninitializised (ie. has not yet been shown)
        # In this case use its sizeHint unless it has no contents in which case use the default size
        widgetSize = widget.size()
        widgetSizeHint = widget.sizeHint()

        if widgetSize == QT_CONST.DEFAULT_WIDGET_SIZE:
            if widgetSizeHint != QT_CONST.DEFAULT_WIDGET_SIZE_HINT and widgetSizeHint != QT_CONST.DEFAULT_MAIN_WINDOW_SIZE_HINT:
                widgetSize = widgetSizeHint

        # NOTE: The 'heightProperty' and 'widthProperty' must be set to "free" otherwise:
        # - When the workspaceControl gets undocked (ie. becomes floating), the minimum dimensions of its grandparent gets set to the current dimensions
        # - This prevents us from resizing the workspaceControl
        # - The grandparent widget can be retrieved via dockWidget.parent().parent(), verify using minimumSize()
        cmds.workspaceControl(dockName, label=widget.windowTitle(), retain=retain, initialWidth=widgetSize.width(), widthProperty="free", initialHeight=widgetSize.height(), heightProperty="free")

        # NOTE: The uiScript is a required flag, we will encounter strange issues such as the workspace control disappearing when the workspace is changed (eg. on ctrl+space) if not set
        # - It is called upon starting a new session, if the workspace control was not deleted before ending the last session (allows us to reinstall the contents)
        # - Ensure it is set after creation otherwise it will be executed
        cmds.workspaceControl(dockName, e=True, uiScript=uiScript or "")

    dockWidget = QT_WIDGET.retainAndReturn(UI_INSPECT.getWidget(dockName, QtWidgets.QWidget))

    # Ensure the objectName is set so Maya cmds will recognise paths to its children
    dockWidget.setObjectName(dockName)
    # Dock the widget
    dockWidget.layout().addWidget(widget)
    # Ensure the control is maximized if it is collapsed or minimized otherwise if the control is hidden ensure it is visible
    cmds.workspaceControl(dockName, e=True, restore=True)


def undock(widget, closeWorkspaceControl=True):
    """Undock a widget from its :func:`cmds.workspaceControl` and parent it to the Maya main window as a standalone window.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to undock.
        closeWorkspaceControl (:class:`bool`, optional): Whether the :func:`cmds.workspaceControl` should be closed. Defaults to :data:`True`.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        mayaWindow = QT_WIDGET.retainAndReturn(UI_INSPECT.getMainWindow())
        widget.setParent(mayaWindow)
        widget.setWindowFlags(QtCore.Qt.Window)
        widget.show()

        # Only delete the workspaceControl if the user specifies (in case they have docked other windows they want to keep)
        if closeWorkspaceControl:
            cmds.workspaceControl(parent.objectName(), e=True, close=True)


def float_(widget):
    """Display a widget as a window or float its :func:`cmds.workspaceControl` if it is docked.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to float.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        cmds.workspaceControl(parent.objectName(), e=True, floating=True)
    else:
        widget.setWindowFlags(QtCore.Qt.Window)
        widget.show()


def raise_(widget):
    """Raise a widget to the top of its parent widget's stack or raise its :func:`cmds.workspaceControl` if it is docked.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to raise.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        cmds.workspaceControl(parent.objectName(), e=True, restore=True)
    else:
        widget.raise_()


def close(widget):
    """Close a widget or its :func:`cmds.workspaceControl` if it is docked.

    Note:
        An undocked widget will be deleted if it has the :attr:`PySide2.QtCore.Qt.WA_DeleteOnClose` attribute set.
        A docked widget will be deleted if the retain state of its :func:`cmds.workspaceControl` is disabled.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to close.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        # NOTE : If a workspaceControl is closed when in a collapsed state, it will leave a visual artifact in the tab-widget it was docked to
        # - We must restore the control (ensuring it is maximized) before closing it
        cmds.workspaceControl(parent.objectName(), e=True, restore=True)
        cmds.workspaceControl(parent.objectName(), e=True, close=True)
        return

    widget.close()


def delete(widget):
    """Delete a widget and close its :func:`cmds.workspaceControl` if it is docked.

    Note:
        This function differs to :func:`close` in that it ensures the widget will always be deleted.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to close.
    """
    parent = QT_WIDGET.retainAndReturn(widget.parent())

    widget.deleteLater()

    if parent is not None and cmds.workspaceControl(parent.objectName(), q=True, exists=True):
        # NOTE : If a workspaceControl is closed when in a collapsed state, it will leave a visual artifact in the tab-widget it was docked to
        # - We must restore the control (ensuring it is maximized) before closing it
        cmds.workspaceControl(parent.objectName(), e=True, restore=True)
        cmds.workspaceControl(parent.objectName(), e=True, close=True)
