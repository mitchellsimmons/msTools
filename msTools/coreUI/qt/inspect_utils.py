"""
Utility functions for inspecting `Qt`_ objects

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCompat, QtWidgets


# ----------------------------------------------------------------------------
# --- Retrieve ---
# ----------------------------------------------------------------------------

def getWidget(widgetName, widgetClass=None):
    """Retrieve a widget by name and class.

    Note:
        Name hierarchies such as ``"parent|child"`` are not supported.
        Therefore the first widget with the given name will be returned.

    Args:
        widgetName (:class:`basestring`): A non-hierarchical widget name.
        widgetClass (T <= :class:`type`): A non-strict subclass of :class:`PySide2.QtWidgets.QWidget`.

    Raises:
        :exc:`~exceptions.RuntimeError`: If a widget could not be identified for the given ``widgetName`` and ``widgetClass``.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`: A widget which was found to have a name corresponding to ``widgetName`` and type corresponding to ``widgetClass``.
    """
    for widget in QtWidgets.QApplication.allWidgets():
        if widget.objectName() == widgetName:
            if widgetClass is not None and isinstance(widget, widgetClass):
                return widget
            else:
                ptr = QtCompat.getCppPointer(widget)
                return QtCompat.wrapInstance(long(ptr), widgetClass)

    raise RuntimeError("Unable to identify widget by name: {}".format(widgetName))


def getReadablePropertiesFromClass(qtClass):
    """Return readable properties from a given `Qt`_ class.

    Readable properties are those which can be accessed via :meth:`PySide2.QtCore.QObject.property`.
    Refer to :doc:`The Property System <PySide2:overviews/properties>` for details.

    Args:
        qtClass (T <= :class:`type`): A non-strict subclass of :class:`PySide2.QtCore.QObject`.

    Returns:
        :class:`list` [:class:`basestring`]: The readable properties for objects of ``qtClass``.
    """
    metaObject = qtClass.staticMetaObject
    count = metaObject.propertyCount()
    return [metaObject.property(index).name() for index in xrange(count) if metaObject.property(index).isReadable()]


def getWritablePropertiesFromClass(qtClass):
    """Return writable properties from a given `Qt`_ class.

    Writable properties are those which can be modified via :meth:`PySide2.QtCore.QObject.setProperty`.
    Refer to :doc:`The Property System <PySide2:overviews/properties>` for details.

    Args:
        qtClass (T <= :class:`type`): A non-strict subclass of :class:`PySide2.QtCore.QObject`.

    Returns:
        :class:`list` [:class:`basestring`]: The writable properties for objects of ``qtClass``.
    """
    metaObject = qtClass.staticMetaObject
    count = metaObject.propertyCount()
    return [metaObject.property(index).name() for index in xrange(count) if metaObject.property(index).isWritable()]


def getReadablePropertiesFromObject(qtObject):
    """Return readable properties from a given `Qt`_ object.

    Readable properties are those which can be accessed via :meth:`PySide2.QtCore.QObject.property`.
    Refer to :doc:`The Property System <PySide2:overviews/properties>` for details.

    Args:
        qtObject (T <= :class:`PySide2.QtCore.QObject`): A `Qt`_ object.

    Returns:
        :class:`list` [:class:`basestring`]: The readable properties from ``qtObject``.
    """
    metaObject = qtObject.metaObject()
    count = metaObject.propertyCount()
    return [metaObject.property(index).name() for index in xrange(count) if metaObject.property(index).isReadable()]


def getWritablePropertiesFromObject(qtObject):
    """Return writable properties from a given `Qt`_ object.

    Writable properties are those which can be modified via :meth:`PySide2.QtCore.QObject.setProperty`.
    Refer to :doc:`The Property System <PySide2:overviews/properties>` for details.

    Args:
        qtObject (T <= :class:`PySide2.QtCore.QObject`): A `Qt`_ object.

    Returns:
        :class:`list` [:class:`basestring`]: The writable properties from ``qtObject``.
    """
    metaObject = qtObject.metaObject()
    count = metaObject.propertyCount()
    return [metaObject.property(index).name() for index in xrange(count) if metaObject.property(index).isWritable()]
