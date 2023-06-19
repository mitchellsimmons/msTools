"""
Utility functions for animating `Qt`_ objects.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtWidgets, QtCore


# ----------------------------------------------------------------------------
# --- Animate Widgets ---
# ----------------------------------------------------------------------------

def opacityAnimation(target, startValue=0.0, endValue=1.0, duration=200, interpolationType=None, finishCallback=None, play=True):
    """Animate the opacity of a `Qt`_ widget or graphics item.

    Args:
        target (T <= :class:`PySide2.QtWidgets.QWidget` | T <= :class:`PySide2.QtWidgets.QGraphicsItem`): The widget or graphics item to animate.
        startValue (:class:`float`, optional): The opacity for ``target`` when the animation starts. Defaults to ``0.0``.
        endValue (:class:`float`, optional): The opacity for ``target`` when the animation ends. Defaults to ``1.0``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation.
            Defaults to :data:`None` - the interpolation type will be determined by the direction of change in opacity,
            either ``InQuad`` for decreasing opacity or ``OutQuad`` for increasing opacity.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``target``.
    """
    # Widgets use "windowOpacity", graphics items use "opacity"
    propertyName = "opacity" if isinstance(target, QtWidgets.QGraphicsItem) else "windowOpacity"
    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if startValue < endValue else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(target, propertyName, target)
    animation.setEasingCurve(style)
    animation.setStartValue(startValue)
    animation.setEndValue(endValue)
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def slideAnimation(target, startVectorOffset=QtCore.QPoint(-100, -100), endVectorOffset=QtCore.QPoint(0, 0), duration=200, interpolationType=None, finishCallback=None, play=True):
    """Animate the local coordinates of a `Qt`_ widget or graphics item relative to its current position.

    Args:
        target (T <= :class:`PySide2.QtWidgets.QWidget` | T <= :class:`PySide2.QtWidgets.QGraphicsItem`): The widget or graphics item to animate.
        startVectorOffset (:class:`PySide2.QtCore.QPoint` | :class:`PySide2.QtCore.QPointF`, optional): The local coordinate offset from the current position of ``target`` to be used when the animation starts.
            If ``target`` is a :class:`PySide2.QtWidgets.QWidget`, the type must be a :class:`PySide2.QtCore.QPoint`.
            Defaults to ``QtCore.QPoint(-100, -100)``.
        endVectorOffset (:class:`PySide2.QtCore.QPoint` | :class:`PySide2.QtCore.QPointF`, optional): The local coordinate offset from the current position of ``target`` to be used when the animation ends.
            If ``target`` is not a :class:`PySide2.QtWidgets.QGraphicsItem`, the type must be a :class:`PySide2.QtCore.QPoint`.
            Defaults to ``QtCore.QPoint(0, 0)``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation.
            Defaults to :data:`None` - the interpolation type will be determined by the magnitude of the start and end offsets,
            either ``InQuad`` for decreasing displacement or ``OutQuad`` for increasing displacement.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.TypeError`: If ``target`` is a :class:`PySide2.QtWidgets.QWidget` and ``startVectorOffset`` or ``endVectorOffset`` is a :class:`PySide2.QtCore.QPointF`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``target``.
    """
    pos = target.pos()
    startOffsetLengthSquared = startVectorOffset.x * startVectorOffset.x + startVectorOffset.y * startVectorOffset.y
    endOffsetLengthSquared = endVectorOffset.x * endVectorOffset.x + endVectorOffset.y * endVectorOffset.y

    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if startOffsetLengthSquared > endOffsetLengthSquared else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(target, "pos", target)
    animation.setEasingCurve(style)
    animation.setStartValue(pos + startVectorOffset)
    animation.setEndValue(pos + endVectorOffset)
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def verticalSlideAnimation(target, startOffset=-100, endOffset=0, duration=200, interpolationType=None, finishCallback=None, play=True):
    """Animate the local y-coordinate of a `Qt`_ widget or graphics item relative to its current position.

    Args:
        target (T <= :class:`PySide2.QtWidgets.QWidget` | T <= :class:`PySide2.QtWidgets.QGraphicsItem`): The widget or graphics item to animate.
        startOffset (:class:`float`, optional): The local y-coordinate offset from the current position of ``target`` to be used when the animation starts.
            Defaults to ``-100``.
        endOffset (:class:`float`, optional): The local y-coordinate offset from the current position of ``target`` to be used when the animation ends.
            Defaults to ``0``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation.
            Defaults to :data:`None` - the interpolation type will be determined by the magnitude of the start and end offsets,
            either ``InQuad`` for decreasing displacement or ``OutQuad`` for increasing displacement.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``target``.
    """
    # If `target` is a QWidget, `pos` will be a QPoint otherwise pos will be a QPointF if `target` is a QGraphicsItem
    pos = target.pos()
    pointType = type(pos)

    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if abs(startOffset) > abs(endOffset) else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    # We cannot animate the "y" property since it is only writable for QGraphicsItem
    animation = QtCore.QPropertyAnimation(target, "pos", target)
    animation.setEasingCurve(style)
    animation.setStartValue(pointType(pos.x(), pos.y() + startOffset))
    animation.setEndValue(pointType(pos.x(), pos.y() + endOffset))
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def horizontalSlideAnimation(target, startOffset=-100, endOffset=0, duration=200, interpolationType=None, finishCallback=None, play=True):
    """Animate the local x-coordinate of a `Qt`_ widget or graphics item relative to its current position.

    Args:
        target (T <= :class:`PySide2.QtWidgets.QWidget` | T <= :class:`PySide2.QtWidgets.QGraphicsItem`): The widget or graphics item to animate.
        startOffset (:class:`float`, optional): The local x-coordinate offset from the current position of ``target`` to be used when the animation starts.
            Defaults to ``-100``.
        endOffset (:class:`float`, optional): The local x-coordinate offset from the current position of ``target`` to be used when the animation ends.
            Defaults to ``0``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation.
            Defaults to :data:`None` - the interpolation type will be determined by the magnitude of the start and end offsets,
            either ``InQuad`` for decreasing displacement or ``OutQuad`` for increasing displacement.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``target``.
    """
    # If `target` is a QWidget, `pos` will be a QPoint otherwise pos will be a QPointF if `target` is a QGraphicsItem
    pos = target.pos()
    pointType = type(pos)

    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if abs(startOffset) > abs(endOffset) else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    # We cannot animate the "x" property since it is only writable for QGraphicsItem
    animation = QtCore.QPropertyAnimation(target, "pos", target)
    animation.setEasingCurve(style)
    animation.setStartValue(pointType(pos.x() + startOffset, pos.y()))
    animation.setEndValue(pointType(pos.x() + endOffset, pos.y()))
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def resizeAnimation(widget, startSize=QtCore.QSize(0, 0), endSize=QtCore.QSize(400, 400), duration=200, interpolationType=QtCore.QEasingCurve.OutQuad, finishCallback=None, play=True):
    """Animate the size of a `Qt`_ widget.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to animate.
        startSize (:class:`float`, optional): The size of ``widget`` when the animation starts. Defaults to ``PySide2.QtCore.QSize(0, 0)``.
        endSize (:class:`float`, optional): The size of ``widget`` when the animation ends. Defaults to ``PySide2.QtCore.QSize(400, 400)``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation. Defaults to ``OutQuad``.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``widget``.
    """
    style = QtCore.QEasingCurve()
    style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(widget, "size", widget)
    animation.setEasingCurve(style)
    animation.setStartValue(startSize)
    animation.setEndValue(endSize)
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def heightAnimation(widget, startHeight=0, endHeight=480, duration=200, interpolationType=QtCore.QEasingCurve.OutQuad, finishCallback=None, play=True):
    """Animate the height of a `Qt`_ widget.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to animate.
        startHeight (:class:`float`, optional): The height of ``widget`` when the animation starts. Defaults to ``0``.
        endHeight (:class:`float`, optional): The height of ``widget`` when the animation ends. Defaults to ``480``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation. Defaults to ``OutQuad``.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``widget``.
    """
    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if startHeight < endHeight else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(widget, "size", widget)
    animation.setEasingCurve(style)
    animation.setStartValue(QtCore.QSize(widget.width(), startHeight))
    animation.setEndValue(QtCore.QSize(widget.width(), endHeight))
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def widthAnimation(widget, startWidth=0, endWidth=640, duration=200, interpolationType=QtCore.QEasingCurve.OutQuad, finishCallback=None, play=True):
    """Animate the width of a `Qt`_ widget.

    Args:
        widget (T <= :class:`PySide2.QtWidgets.QWidget`): The widget to animate.
        startWidth (:class:`float`, optional): The width of ``widget`` when the animation starts. Defaults to ``0``.
        endWidth (:class:`float`, optional): The width of ``widget`` when the animation ends. Defaults to ``640``.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation. Defaults to ``OutQuad``.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``widget``.
    """
    style = QtCore.QEasingCurve()
    if interpolationType is None:
        # OutQuad slows down as we arrive at the destination, then InQuad speeds up as we leave the destination
        style.setType(QtCore.QEasingCurve.OutQuad if startWidth < endWidth else QtCore.QEasingCurve.InQuad)
    else:
        style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(widget, "size", widget)
    animation.setEasingCurve(style)
    animation.setStartValue(QtCore.QSize(startWidth, widget.height()))
    animation.setEndValue(QtCore.QSize(endWidth, widget.height()))
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation


def propertyAnimation(target, propertyName, startValue, endValue, duration=200, interpolationType=QtCore.QEasingCurve.OutQuad, finishCallback=None, play=True):
    """Animate a property of a `Qt`_ widget or graphics item.

    Args:
        target (T <= :class:`PySide2.QtWidgets.QWidget` | T <= :class:`PySide2.QtWidgets.QGraphicsItem`): The widget or graphics item to animate.
        propertyName (:class:`basestring`): The name of a writable property on ``target``.
            For a list of writable properties on ``target`` see :meth:`msToolsUI.qt.inspect_utils.getWritablePropertiesFromObject`.
            For additional information on `Qt`_ properties see :ref:`the-property-system`.
        startValue (any): The value for the property on ``target`` when the animation starts.
        endValue (any): The value for the property on ``target`` when the animation ends.
        duration (:class:`int`, optional): The duration of the animation in milliseconds. Defaults to ``200``.
        interpolationType (:attr:`PySide2.QtCore.QEasingCurve.Type`, optional): The type of interpolation for the animation. Defaults to ``OutQuad``.
        finishCallback (callable [[], any], optional): A callable to execute when the animation finishes. Defaults to :data:`None`.
        play (:class:`bool`, optional): Whether to play the animation. Defaults to :data:`True`.

    Returns:
        :class:`PySide2.QtCore.QPropertyAnimation`: The animation object used to animate ``target``.
    """
    style = QtCore.QEasingCurve()
    style.setType(interpolationType)

    animation = QtCore.QPropertyAnimation(target, propertyName, target)
    animation.setEasingCurve(style)
    animation.setStartValue(startValue)
    animation.setEndValue(endValue)
    animation.setDuration(duration)

    if play:
        animation.start()

    if finishCallback is not None:
        animation.finished.connect(finishCallback)

    return animation
