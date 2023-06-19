"""
General purpose utility functions relating to `Qt`_ widgets.

----------------------------------------------------------------

.. _windows:

Windows
-------

    A widget that has the :attr:`PySide2.QtCore.Qt.Window` flag set is considered a window.

    - A widget that has no parent will always have this flag set.
    - A widget that is constructed with a parent will not have this flag set,
      unless the widget is a special window type such as :class:`PySide2.QtWidgets.QDialog` or :class:`PySide2.QtWidgets.QMainWindow`.
    - This flag will always be unset upon reparenting a widget.
    - It is possible to manually set this flag on any widget via :meth:`PySide2.QtWidgets.QWidget.setWindowFlag`.

----------------------------------------------------------------

Coordinates
-----------

    The local coordinates of a window are always defined relative to the primary screen (ie. global coordinates) even if it has a parent.
    The local coordinates of a non-window are always defined relative to its parent.
    This behaviour must be considered when making use of the following methods:

    - :meth:`PySide2.QtWidgets.QWidget.x`
    - :meth:`PySide2.QtWidgets.QWidget.y`
    - :meth:`PySide2.QtWidgets.QWidget.pos`
    - :meth:`PySide2.QtWidgets.QWidget.move`
    - :meth:`PySide2.QtWidgets.QWidget.geometry`
    - :meth:`PySide2.QtWidgets.QWidget.frameGeometry`
    - :meth:`PySide2.QtWidgets.QWidget.setGeometry`
    - :meth:`PySide2.QtWidgets.QWidget.mapFromParent`
    - :meth:`PySide2.QtWidgets.QWidget.mapToParent`

----------------------------------------------------------------

.. _references:

References
----------

    When referencing c++ widgets (ie. those not created by the `Qt`_ Python bindings), it is necessary to take certain precautions:

    - The reference should be retrieved dynamically when needed (never cache a reference).
    - If an ancestor is accessed, its reference must be retained until the descendant reference is no longer needed. See :func:`retain`.
    - If a utility function requires access to the ancestors of an input, it should consider whether it is invalidating the input within the calling scope.

    When referencing a descendant of a c++ ancestor widget, the lifetime of **any** reference to the descendant becomes dependant upon the lifetime of the ancestor reference.
    It appears that the lifetime of references to descendants are managed through some kind of shared pointer held by the ancestor.

    Example:
        The following demonstrates the necessity for dynamically retrieving references to c++ widgets between idle states.

        .. code-block:: python

            def foo():
                # The lifetime of any `menu` reference is now dependant upon the below `window` reference
                window = msTools.coreUI.maya.inspect_utils.getMainWindow()
                menu = window.findChild(QtWidgets.QMenu)

            window = msTools.coreUI.maya.inspect_utils.getMainWindow()
            menu = window.findChild(QtWidgets.QMenu) # <- Cach a reference

            # idle...... (the user invokes `foo`)

            menu.objectName() # <- ERROR, the `foo` references were not retained

----------------------------------------------------------------
"""
import importlib
import logging
log = logging.getLogger(__name__)

from msTools.vendor.Qt import __binding__, QtCompat, QtCore, QtGui

# `QDesktopWidget` (ie. `QApplication.desktop`) is deprecated for Qt5
try:
    _QtGui = importlib.import_module(".".join([__binding__, "QtGui"]))
    QGuiApplication = _QtGui.QGuiApplication
    QScreen = _QtGui.QScreen
    _IS_QT5 = True
except ImportError:
    _QtWidgets = importlib.import_module(".".join([__binding__, "QtWidgets"]))
    QApplication = _QtWidgets.QApplication
    _IS_QT5 = False


# ----------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------

if "_WIDGET_REGISTRY" not in globals():
    log.debug("Initializing global: _WIDGET_REGISTRY")
    _WIDGET_REGISTRY = {}


# ----------------------------------------------------------------------------
# --- Position ---
# ----------------------------------------------------------------------------

def centerWidgetOnCursor(widget, xOffset=0, yOffset=0):
    """Center a widget on the cursor.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    cursorPos_global = QtGui.QCursor.pos()

    # If the widget is a window, `mapToParent` will simply map back into global coordinates (used later by `frameGeometry` and `move`)
    if widget.windowFlags() & QtCore.Qt.Window:
        cursorPos_widgetLocalOrGlobal = cursorPos_global
    else:
        cursorPos_widgetObject = widget.mapFromGlobal(cursorPos_global)
        cursorPos_widgetLocalOrGlobal = widget.mapToParent(cursorPos_widgetObject)

    widgetGeometry_localOrGlobal = widget.frameGeometry()
    widgetGeometry_localOrGlobal.moveCenter(cursorPos_widgetLocalOrGlobal)
    widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnParentContents(widget, xOffset=0, yOffset=0):
    """Center a widget on the contents of its parent (this excludes the window frame of the parent).

    If the widget does not have a parent, it will be centered on its current screen.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    parentWidget = retainAndReturn(widget.parentWidget())

    if parentWidget is None:
        centerWidgetOnCurrentScreen(widget, xOffset=xOffset, yOffset=yOffset)
    else:
        # Exclude the parent's window frame (ie. use its contents center)
        parentGeometry_localOrGlobal = parentWidget.geometry()
        parentCenterPos_localOrGlobal = parentGeometry_localOrGlobal.center()

        if parentWidget.windowFlags() & QtCore.Qt.Window:
            if widget.windowFlags() & QtCore.Qt.Window:
                # If both are windows, we are dealing with the global frame only
                widgetCenterPos_localOrGlobal = parentCenterPos_localOrGlobal
            else:
                # If only the parent is a window, we need to map from global into the widget local frame
                widgetCenterPos_localOrGlobal = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)
        else:
            if widget.windowFlags() & QtCore.Qt.Window:
                # If only the widget is a window, we need to map from the parent local frame into the global frame
                parentCenterPos_local = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)
                widgetCenterPos_localOrGlobal = parentWidget.mapToGlobal(parentCenterPos_local)
            else:
                # If neither are windows, we need to map from the parent local frame into the widget local frame
                widgetCenterPos_localOrGlobal = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)

        widgetGeometry_localOrGlobal = widget.frameGeometry()
        widgetGeometry_localOrGlobal.moveCenter(widgetCenterPos_localOrGlobal)
        widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnParentFrame(widget, xOffset=0, yOffset=0):
    """Center a widget on its parent (this includes the window frame of the parent).

    If the widget does not have a parent, it will be centered on its current screen (the screen which contains its center position).

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    parentWidget = retainAndReturn(widget.parentWidget())

    if parentWidget is None:
        centerWidgetOnCurrentScreen(widget, xOffset=xOffset, yOffset=yOffset)
    else:
        # Include the parent's window frame
        parentGeometry_localOrGlobal = parentWidget.frameGeometry()
        parentCenterPos_localOrGlobal = parentGeometry_localOrGlobal.center()

        if parentWidget.windowFlags() & QtCore.Qt.Window:
            if widget.windowFlags() & QtCore.Qt.Window:
                # If both are windows, we are dealing with the global frame only
                widgetCenterPos_localOrGlobal = parentCenterPos_localOrGlobal
            else:
                # If only the parent is a window, we need to map from global into the widget local frame
                widgetCenterPos_localOrGlobal = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)
        else:
            if widget.windowFlags() & QtCore.Qt.Window:
                # If only the widget is a window, we need to map from the parent local frame into the global frame
                parentCenterPos_local = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)
                widgetCenterPos_localOrGlobal = parentWidget.mapToGlobal(parentCenterPos_local)
            else:
                # If neither are windows, we need to map from the parent local frame into the widget local frame
                widgetCenterPos_localOrGlobal = parentWidget.mapFromParent(parentCenterPos_localOrGlobal)

        widgetGeometry_localOrGlobal = widget.frameGeometry()
        widgetGeometry_localOrGlobal.moveCenter(widgetCenterPos_localOrGlobal)
        widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnScreen(widget, screen, xOffset=0, yOffset=0):
    """Center a widget on a given screen.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        screen (:class:`int` | :class:`PySide2.QtGui.QScreen`): Screen represented by either:

            - A screen number if the available Qt bindings reference a version < Qt5.
            - A screen object if the available Qt bindings reference a version >= Qt5.

        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.

    Raises:
        :exc:`~exceptions.TypeError`: If the available Qt bindings reference a version < Qt5 and ``screen`` is not an :class:`int`.
        :exc:`~exceptions.TypeError`: If the available Qt bindings reference a version >= Qt5 and ``screen`` is not a :class:`PySide2.QtGui.QScreen` object.
    """
    if _IS_QT5:
        if not isinstance(screen, QScreen):
            raise TypeError("Expected {} for `screen` argument".format(QScreen))

        screenGeometry_global = screen.geometry()
    else:
        if not isinstance(screen, int):
            raise TypeError("Expected {} for `screen` argument".format(int))

        screenGeometry_global = QApplication.desktop().screenGeometry(screen)

    screenCenterPos_global = screenGeometry_global.center()
    widgetGeometry_localOrGlobal = widget.frameGeometry()

    if widget.windowFlags() & QtCore.Qt.Window:
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_global)
    else:
        screenCenterPos_widgetObject = widget.mapFromGlobal(screenCenterPos_global)
        screenCenterPos_widgetLocal = widget.mapToParent(screenCenterPos_widgetObject)
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_widgetLocal)

    widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnCurrentScreen(widget, xOffset=0, yOffset=0):
    """Center a widget on its current screen (the screen which contains its center position).

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    widgetGeometry_localOrGlobal = widget.frameGeometry()

    if _IS_QT5:
        if widget.windowFlags() & QtCore.Qt.Window:
            widgetCenterPos_global = widgetGeometry_localOrGlobal.center()
        else:
            widgetCenterPos_local = widgetGeometry_localOrGlobal.center()
            widgetCenterPos_object = widget.mapFromParent(widgetCenterPos_local)
            widgetCenterPos_global = widget.mapToGlobal(widgetCenterPos_object)

        # In Qt >= 5.10 we can use `screenAt`
        try:
            screen = QGuiApplication.screenAt(widgetCenterPos_global)
            screenGeometry_global = screen.geometry()
        except AttributeError:
            screens = QGuiApplication.screens()
            for screen in screens:
                screenGeometry_global = screen.geometry()
                if screenGeometry_global.contains(widgetCenterPos_global):
                    break
    else:
        screenGeometry_global = QApplication.desktop().screenGeometry(widget)

    screenCenterPos_global = screenGeometry_global.center()

    if widget.windowFlags() & QtCore.Qt.Window:
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_global)
    else:
        screenCenterPos_widgetObject = widget.mapFromGlobal(screenCenterPos_global)
        screenCenterPos_widgetLocal = widget.mapToParent(screenCenterPos_widgetObject)
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_widgetLocal)

    widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnPrimaryScreen(widget, xOffset=0, yOffset=0):
    """Center a widget on the primary (or default) screen.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    if _IS_QT5:
        screen = QGuiApplication.primaryScreen()
        screenGeometry_global = screen.geometry()
    else:
        screenGeometry_global = QApplication.desktop().screenGeometry(QApplication.desktop().primaryScreen())

    screenCenterPos_global = screenGeometry_global.center()
    widgetGeometry_localOrGlobal = widget.frameGeometry()

    if widget.windowFlags() & QtCore.Qt.Window:
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_global)
    else:
        screenCenterPos_widgetObject = widget.mapFromGlobal(screenCenterPos_global)
        screenCenterPos_widgetLocal = widget.mapToParent(screenCenterPos_widgetObject)
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_widgetLocal)

    widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


def centerWidgetOnScreenWithCursor(widget, xOffset=0, yOffset=0):
    """Center a widget on the screen which contains the cursor.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to center.
        xOffset (:class:`int`, optional): Horizontal offset from the center. Defaults to ``0``.
        yOffset (:class:`int`, optional): Vertical offset from the center. Defaults to ``0``.
    """
    cursorPos_global = QtGui.QCursor.pos()

    if _IS_QT5:
        # In Qt >= 5.10 we can use `screenAt`
        try:
            screen = QGuiApplication.screenAt(cursorPos_global)
            screenGeometry_global = screen.geometry()
        except AttributeError:
            screens = QGuiApplication.screens()
            for screen in screens:
                screenGeometry_global = screen.geometry()
                if screenGeometry_global.contains(cursorPos_global):
                    break
    else:
        screenGeometry_global = QApplication.desktop().screenGeometry(cursorPos_global)

    screenCenterPos_global = screenGeometry_global.center()
    widgetGeometry_localOrGlobal = widget.frameGeometry()

    if widget.windowFlags() & QtCore.Qt.Window:
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_global)
    else:
        screenCenterPos_widgetObject = widget.mapFromGlobal(screenCenterPos_global)
        screenCenterPos_widgetLocal = widget.mapToParent(screenCenterPos_widgetObject)
        widgetGeometry_localOrGlobal.moveCenter(screenCenterPos_widgetLocal)

    widget.move(widgetGeometry_localOrGlobal.topLeft() + QtCore.QPoint(xOffset, yOffset))


# ----------------------------------------------------------------
# --- Retain ---
# ----------------------------------------------------------------

def retain(widget):
    """Retain a reference to a `Qt`_ widget within a global registry.

    Note:
        It is sometimes necessary to retain a reference to an ancestral widget to ensure the descendant reference is not invalidated.
        See :ref:`references` and the below example.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): Widget to retain.

    Example:
        .. code-block:: python

            def foo():
                window = msTools.coreUI.maya.inspect_utils.getMainWindow()
                widget = window.findChildren(QtWidgets.QMenu)[0] # <- Descendant widget created via c++
                accessParent(widget)
                widget.objectName() # <- ERROR (`widget` reference is invalidated)

            def accessParent(widget):
                widget.parent() # <- We have not taken ownership of the parent

            foo()

            # ---------------------------------------------------------------------

            def foo():
                window = msTools.coreUI.maya.inspect_utils.getMainWindow()
                widget = window.findChildren(QtWidgets.QMenu)[0] # <- Descendant widget created via c++
                accessParent(widget)
                widget.objectName() # <- NO ERROR

            def accessParent(widget):
                retain(widget.parent()) # <- We have taken ownership of the parent reference

            foo()
    """
    global _WIDGET_REGISTRY

    ptr = QtCompat.getCppPointer(widget)
    if ptr not in _WIDGET_REGISTRY:
        _WIDGET_REGISTRY[ptr] = widget
        widget.destroyed.connect(lambda: _WIDGET_REGISTRY.pop(ptr))


def retainAndReturn(widget):
    """Wrapper of :func:`retain` that returns the given widget after retaining a global reference."""
    retain(widget)
    return widget
