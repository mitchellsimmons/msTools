"""
Constant data relating to the `Qt`_ API.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore, QtWidgets


DEFAULT_WIDGET_SIZE_HINT = QtCore.QSize(-1, -1)
""":class:`PySide2.QtCore.QSize`: Default value returned from the :meth:`PySide2.QtWidgets.QWidget.sizeHint` of a widget that does not have a layout.

Note:
    This size is invalid.
"""


DEFAULT_MAIN_WINDOW_SIZE_HINT = QtCore.QSize(0, 0)
""":class:`PySide2.QtCore.QSize`: Default value returned from the :meth:`PySide2.QtWidgets.QWidget.sizeHint` of a :class:`PySide2.QtWidgets.QMainWindow`.

Note:
    This size is valid since a :class:`PySide2.QtWidgets.QMainWindow` has a default `QMainWindowLayout`.
"""


def _getDefaultWidgetSize():
    app = QtWidgets.QApplication.instance()

    # If an application has not been instantiated or the user is running a non-GUI (QCoreApplication) or non-QWidget (QGuiApplication) app
    if not isinstance(app, QtWidgets.QApplication):
        return QtCore.QSize(640, 480)

    widget = QtWidgets.QWidget()
    size = widget.size()
    widget.deleteLater()
    return size


DEFAULT_WIDGET_SIZE = _getDefaultWidgetSize()
""":class:`PySide2.QtCore.QSize`: Default value returned from the :meth:`PySide2.QtWidgets.QWidget.size` of a widget.

Note:
    This value depends on the user's platform and screen geometry. It is usually set to ``640`` x ``480``.
"""
