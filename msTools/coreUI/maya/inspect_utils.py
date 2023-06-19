"""
Inspect UI elements for the current interactive Maya session.

----------------------------------------------------------------
"""
from maya import cmds
from maya.OpenMayaUI import MQtUtil

from msTools.vendor.Qt import QtWidgets, QtCompat

from msTools.coreUI.maya import exceptions as UI_EXC


# ----------------------------------------------------------------
# --- Retrieve ---
# ----------------------------------------------------------------

def getFullName(obj):
    """Return the full hierarchical name of a `Qt`_ object.

    This is the name which uniquely identifies the element within Maya and can be passed to Maya's UI commands.

    Args:
        obj (T <= :class:`PySide2.QtCore.QObject`): A `Qt`_ object.

    Returns:
        :class:`str`: The full hierarchical name of ``obj``.
    """
    return MQtUtil.fullName(QtCompat.getCppPointer(obj))


def getWidget(widgetName, widgetClass=None):
    """Return a `Qt`_ widget identified by name. Implicitly cast to the most suitable class or explicitly cast to a given class.

    Args:
        widgetName (:class:`basestring`): Name of the widget such as ``'myButton'`` or a hierarchical path to the widget such as ``'myWindow|myButton'``.
            If the name corresponds to an element created using Maya commands, the names of any child layouts (placeholder widgets) must be included within the hierarchy.
        widgetClass (:class:`type`, optional): A (non-strict) subclass of :class:`PySide2.QtCore.QObject` used as the explicit casting type for the underlying `Qt`_ widget.
            Defaults to :data:`None` - implicitly cast to the most suitable class, guaranteed to be a (non-strict) subclass of :class:`PySide2.QtWidgets.QWidget`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``widgetName`` does not correspond to an existing `Qt`_ widget.

    Returns:
        T <= :class:`PySide2.QtCore.QObject`: Widget corresponding to ``widgetName``, with type given by ``widgetClass`` or determined implicitly if :data:`None`.
    """
    ptr = MQtUtil.findControl(widgetName)
    if ptr is None:
        raise UI_EXC.MayaUILookupError("Unable to identify widget by name: {}".format(widgetName))

    widget = QtCompat.wrapInstance(long(ptr), widgetClass)

    # NOTE: For some reason the code which determines an implicit cast type sometimes produces a less stable widget (see Qt._wrapinstance)
    # - Issues arose when attempting to cache descendant Node Editor widgets (not advised), whereby the internal C++ object was being deleted
    # - The following prevented this issue in this specific case and is therefore included (though cause of issue is unclear)
    return QtCompat.wrapInstance(long(ptr), type(widget)) if widgetClass is None else widget


def getMainWindow():
    """Return a `Qt`_ widget for the main Maya window.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If the main Maya window could not be identified.

    Returns:
        :class:`PySide2.QtWidgets.QMainWindow`: Widget for the main Maya window.
    """
    ptr = MQtUtil.mainWindow()
    if ptr is None:
        raise UI_EXC.MayaUILookupError("Unable to identify the main Maya window")

    return QtCompat.wrapInstance(long(ptr), QtWidgets.QMainWindow)


def getPanelUnderCursor():
    """Return a `Qt`_ widget for the Maya panel under the current cursor position.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If there is no Maya panel under the current cursor position.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`: Widget for the Maya panel under the current cursor position.
    """
    panelName = cmds.getPanel(underPointer=True)
    if panelName is None:
        raise UI_EXC.MayaUILookupError("There is no panel under the cursor")

    return getWidget(panelName, QtWidgets.QWidget)
