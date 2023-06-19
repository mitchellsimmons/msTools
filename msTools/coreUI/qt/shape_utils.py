"""
Produce shapes for drawing and interaction within the `Qt`_ framework.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore, QtGui


def getDrawableRect(rect, borderWidth):
    """Return a rectangle adjusted to a given border/pen width.

    The result is designed to be drawn via a :class:`PySide2.QtGui.QPainter` that uses a :class:`PySide2.QtGui.QPen` with the given width.

    Note:
        If ``rect`` represents the geometry of a :class:`PySide2.QtWidgets.QWidget` which is to be used as a container,
        the user should ensure the widget's layout has a uniform margin corresponding to the ``borderWidth``.

    Args:
        rect (:class:`PySide2.QtCore.QRect` | :class:`PySide2.QtCore.QRectF`): Source rectangle representing the drawable geometry.
        borderWidth (:class:`int`): The :class:`PySide2.QtGui.QPen` width that will be used to draw the resulting rectangle.

    Returns:
        :class:`PySide2.QtCore.QRectF`: Drawable rectangle based on the geometry of ``rect`` and adjusted to the ``borderWidth``.
    """
    # A `QPen` border is split onto either side of the geometry, therefore we must provide space for half the pen width
    rect = QtCore.QRectF(rect) if isinstance(rect, QtCore.QRect) else rect
    adjustment = borderWidth / 2.0
    return rect.adjusted(adjustment, adjustment, -adjustment, -adjustment)


def getRoundedRectPath(rect, roundness, roundTopLeft=False, roundTopRight=False, roundBottomRight=False, roundBottomLeft=False):
    """Return a rounded rectangle path based on the geometry of a source rectangle.

    Args:
        rect (:class:`PySide2.QtCore.QRect` | :class:`PySide2.QtCore.QRectF`): Source rectangle.
        roundness (:class:`float`): The radius of each rounded corner.
        roundTopLeft (:class:`bool`, optional): Whether to round the top left corner. Defaults to :data:`False`.
        roundTopRight (:class:`bool`, optional): Whether to round the top right corner. Defaults to :data:`False`.
        roundBottomRight (:class:`bool`, optional): Whether to round the bottom right corner. Defaults to :data:`False`.
        roundBottomLeft (:class:`bool`, optional): Whether to round the bottom left corner. Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.ValueError`: If ``roundLeft`` and ``roundRight`` are :data:`True` but the width of ``rect`` is smaller than twice the ``roundness``.
        :exc:`~exceptions.ValueError`: If ``roundLeft`` or ``roundRight`` is :data:`True` but the width of ``rect`` is smaller than the ``roundness``.
        :exc:`~exceptions.ValueError`: If ``roundTop`` and ``roundBottom`` are :data:`True` but the height of ``rect`` is smaller than twice the ``roundness``.
        :exc:`~exceptions.ValueError`: If ``roundTop`` or ``roundBottom`` is :data:`True` but the height of ``rect`` is smaller than the ``roundness``.

    Returns:
        :class:`QtGui.QPainterPath`: Rounded rectangle path based on the geometry of ``rect``.
    """
    rect = QtCore.QRectF(rect) if isinstance(rect, QtCore.QRect) else rect
    roundLeft = roundTopLeft or roundBottomLeft
    roundRight = roundTopRight or roundBottomRight
    roundTop = roundTopLeft or roundTopRight
    roundBottom = roundBottomLeft or roundBottomRight

    if roundLeft and roundRight and rect.width() < roundness * 2:
        raise ValueError("Rectangle is not horizontally wide enough to round two horizontally opposite corners")
    elif (roundLeft or roundRight) and rect.width() < roundness:
        raise ValueError("Rectangle is not horizontally wide enough to round a single corner")

    if roundTop and roundBottom and rect.height() < roundness * 2:
        raise ValueError("Rectangle is not vertically long enough to round two vertically opposite corners")
    elif (roundTop or roundBottom) and rect.height() < roundness:
        raise ValueError("Rectangle is not vertically long enough to round a single corner")

    cornerArcRect = QtCore.QRectF(0, 0, roundness * 2, roundness * 2)
    cornerWidthVec = QtCore.QPointF(roundness, 0)
    cornerHeightVec = QtCore.QPointF(0, roundness)
    path = QtGui.QPainterPath()

    if roundTopLeft:
        path.moveTo(rect.topLeft() + cornerWidthVec)
    else:
        path.moveTo(rect.topLeft())

    if roundTopRight:
        path.lineTo(rect.topRight() - cornerWidthVec)
        cornerArcRect.moveTopRight(rect.topRight())
        path.arcTo(cornerArcRect, 90, -90)
    else:
        path.lineTo(rect.topRight())

    if roundBottomRight:
        path.lineTo(rect.bottomRight() - cornerHeightVec)
        cornerArcRect.moveBottomRight(rect.bottomRight())
        path.arcTo(cornerArcRect, 0, -90)
    else:
        path.lineTo(rect.bottomRight())

    if roundBottomLeft:
        path.lineTo(rect.bottomLeft() + cornerWidthVec)
        cornerArcRect.moveBottomLeft(rect.bottomLeft())
        path.arcTo(cornerArcRect, 270, -90)
    else:
        path.lineTo(rect.bottomLeft())

    if roundTopLeft:
        path.lineTo(rect.topLeft() + cornerHeightVec)
        cornerArcRect.moveTopLeft(rect.topLeft())
        path.arcTo(cornerArcRect, 180, -90)
    else:
        path.lineTo(rect.topLeft())

    return path
