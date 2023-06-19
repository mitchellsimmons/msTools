"""
General purpose utility functions relating to `Qt`_ graphical items.

----------------------------------------------------------------
"""
from msTools.vendor.Qt import QtCore


# ----------------------------------------------------------------------------
# --- Retrieve ---
# ----------------------------------------------------------------------------

def getUnitedBoundingRect(graphicsItems):
    """Returns the bounding rectangle in scene coordinates of the given items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items from which to calculate a united bounding rectangle.

    Returns:
        :class:`PySide2.QtCore.QRectF`: The united bounding rectangle of ``graphicalItems``.
    """
    boundingRect = QtCore.QRectF()

    for graphicsItem in graphicsItems:
        boundingRect = boundingRect.united(graphicsItem.sceneBoundingRect())

    return boundingRect


# ----------------------------------------------------------------------------
# --- Align ---
# ----------------------------------------------------------------------------

def alignVCenter(graphicsItems):
    """Align the vertical center of each graphical item to the average vertical center position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumCenterY = 0

    for graphicsItem in graphicsItems:
        sumCenterY += graphicsItem.y() + graphicsItem.boundingRect().height() / 2

    averageCenterY = sumCenterY / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(graphicsItem.x(), averageCenterY - graphicsItem.boundingRect().height() / 2)


def alignTop(graphicsItems):
    """Align the top edge of each graphical item to the average top edge position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumTopY = 0

    for graphicsItem in graphicsItems:
        sumTopY += graphicsItem.y()

    averageTopY = sumTopY / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(graphicsItem.x(), averageTopY)


def alignBottom(graphicsItems):
    """Align the bottom edge of each graphical item to the average bottom edge position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumBottomY = 0

    for graphicsItem in graphicsItems:
        sumBottomY += graphicsItem.y() + graphicsItem.boundingRect().height()

    averageBottomY = sumBottomY / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(graphicsItem.x(), averageBottomY - graphicsItem.boundingRect().height())


def alignHCenter(graphicsItems):
    """Align the horizontal center of each graphical item to the average horizontal center position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumCenterX = 0

    for graphicsItem in graphicsItems:
        sumCenterX += graphicsItem.x() + graphicsItem.boundingRect().width() / 2

    averageCenterX = sumCenterX / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(averageCenterX - graphicsItem.boundingRect().width() / 2, graphicsItem.y())


def alignLeft(graphicsItems):
    """Align the left edge of each graphical item to the average left edge position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumLeftX = 0

    for graphicsItem in graphicsItems:
        sumLeftX += graphicsItem.x()

    averageLeftX = sumLeftX / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(averageLeftX, graphicsItem.y())


def alignRight(graphicsItems):
    """Align the right edge of each graphical item to the average right edge position of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to align.
    """
    numItems = len(graphicsItems)
    if numItems < 2:
        return

    sumRightX = 0

    for graphicsItem in graphicsItems:
        sumRightX += graphicsItem.x() + graphicsItem.boundingRect().width()

    averageRightX = sumRightX / numItems

    for graphicsItem in graphicsItems:
        graphicsItem.setPos(averageRightX - graphicsItem.boundingRect().width(), graphicsItem.y())


def distributeHGaps(graphicsItems):
    """Distribute each graphical item so that the horizontal gaps are made equidistant.
    Distribution occurs between the furthest left edge and furthest right edge of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to distribute.
    """
    numItems = len(graphicsItems)
    if numItems < 3:
        return

    sortedGraphicsItems = sorted(graphicsItems, key=lambda graphicsItem: graphicsItem.x())
    innerLength = sortedGraphicsItems[-1].x() - (sortedGraphicsItems[0].x() + sortedGraphicsItems[0].boundingRect().width())
    sumInnerWidth = 0

    for graphicsItem in sortedGraphicsItems[1:-1]:
        sumInnerWidth += graphicsItem.boundingRect().width()

    gap = (innerLength - sumInnerWidth) / (numItems - 1)

    for i in xrange(1, numItems - 1):
        sortedGraphicsItems[i].setPos(sortedGraphicsItems[i - 1].x() + sortedGraphicsItems[i - 1].boundingRect().width() + gap, sortedGraphicsItems[i].y())


def distributeVGaps(graphicsItems):
    """Distribute each graphical item so that the vertical gaps are made equidistant.
    Distribution occurs between the furthest top edge and furthest bottom edge of all items.

    Args:
        graphicalItems (:class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]): Graphical items to distribute.
    """
    numItems = len(graphicsItems)
    if numItems < 3:
        return

    sortedGraphicsItems = sorted(graphicsItems, key=lambda graphicsItem: graphicsItem.y())
    innerLength = sortedGraphicsItems[-1].y() - (sortedGraphicsItems[0].y() + sortedGraphicsItems[0].boundingRect().height())
    sumInnerHeight = 0

    for graphicsItem in sortedGraphicsItems[1:-1]:
        sumInnerHeight += graphicsItem.boundingRect().height()

    gap = (innerLength - sumInnerHeight) / (numItems - 1)

    for i in xrange(1, numItems - 1):
        sortedGraphicsItems[i].setPos(sortedGraphicsItems[i].x(), sortedGraphicsItems[i - 1].y() + sortedGraphicsItems[i - 1].boundingRect().height() + gap)
