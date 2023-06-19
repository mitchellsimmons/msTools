"""
Utility functions for operating on the current `Qt`_ application.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore, QtWidgets


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

_OVERRIDE_DELAY = 5
_OVERRIDE_TYPE = QtCore.Qt.ArrowCursor
_OVERRIDE_TIMER = QtCore.QTimer()
_OVERRIDE_TIMER.setSingleShot(True)
_OVERRIDE_TIMER.timeout.connect(lambda: _setCursor())


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _setCursor():
    if QtWidgets.QApplication.overrideCursor() is None:
        QtWidgets.QApplication.setOverrideCursor(_OVERRIDE_TYPE)
    else:
        QtWidgets.QApplication.changeOverrideCursor(_OVERRIDE_TYPE)


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def setCursor(cursorShape):
    """Modifies the application's global cursor override given by :meth:`PySide2.QtGui.QGuiApplication.overrideCursor`.

    The frequency at which the cursor can be changed is limited in order to reduce graphical artifacting.
    Meaning modifications are scheduled at a small delay so that sequential calls can be ellided.

    Note:
        By calling this method, the user takes ownership of the global cursor state.
        The user is then responsible for restoring the cursor state by calling :func:`restoreCursor`.

    Args:
        cursorShape (T <= :attr:`PySide2.QtCore.Qt.CursorShape`): Cursor shape to set as the current application's cursor override.
    """
    global _OVERRIDE_TYPE

    overrideCursor_ = QtWidgets.QApplication.overrideCursor()

    if overrideCursor_ is None or overrideCursor_.shape() != cursorShape:
        # The timer prevents sequential calls from updating the cursor at a rate which might produce graphical artifacting
        # It will wait for the GUI to reach idle before invoking the callback, allowing us to update the scheduled change before idle is reached
        _OVERRIDE_TIMER.start(_OVERRIDE_DELAY)
        _OVERRIDE_TYPE = cursorShape


def restoreCursor():
    """Restores the application's global cursor override given by :meth:`PySide2.QtGui.QGuiApplication.overrideCursor`.

    This method is designed to be called in conjunction with :func:`setCursor` in order to undo changes.
    """
    global _OVERRIDE_TYPE

    _OVERRIDE_TIMER.stop()

    while QtWidgets.QApplication.overrideCursor() is not None:
        QtWidgets.QApplication.restoreOverrideCursor()

    _OVERRIDE_TYPE = QtCore.Qt.ArrowCursor
