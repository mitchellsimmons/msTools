"""
Provides graphical items for organising the Node Editor graph. Designed for use by the `LayoutToolController`.

----------------------------------------------------------------

Items
-----

    There are two primary items:

    1. `NodeBoxItem`: Provides structure to the graph, allowing for visual encapsulation of components.
    2. `StickyItem`: Provides the ability to add comments to the graph.

----------------------------------------------------------------

Issues
------

    The following issues all required some form of specialised implementation:

    1. Calling `QGraphicsItem.parentItem` may cause the internal C++ object to be deleted if the reference is not maintained.
    2. A `QGraphicsLayout` blocks certain events (eg. shift selection) from propagating to items within the layout if its container has a `QGraphicsItem.shape`.
       Giving the container a null sized shape will allow events to be received by items within the layout.
    3. Focus is not automatically cleared upon deselecting an item which has the `QGraphicsItem.ItemIsFocusable` flag set even if `QGraphicsItem.hasFocus` returns `False`.
       For example, selecting a focusable item and replacing the selection prevents `keyPress` events from propagating to the second item since the first item still has focus.
       The `QGraphicsItem.itemChange` method can be used to clear focus when the item is deselected (ie. by checking for `QGraphicsItem.ItemSelectedChange`).
    4. The `QGraphicsItem.hoverLeaveEvent` of a parent item may not be triggered if the cursor moves directly over a child item before leaving the parent shape.
       Therefore it is sometimes necessary for a child item to emit its hover state changes in order for the parent item to respond.
    5. Items may be deleted if a reference to the `QGraphicsScene` is not maintained.
       Overriding `object.__del__` seems strangely to prevent this from occurring however maintaining the reference should definitely be preferred.

----------------------------------------------------------------
"""
import uuid
import logging
log = logging.getLogger(__name__)

from msTools.vendor.enum import Enum
from msTools.vendor.Qt import QtCore, QtGui, QtWidgets

from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.coreUI.qt import animation_utils as QT_ANIM
from msTools.coreUI.qt import application_utils as QT_APP
from msTools.coreUI.qt import context_utils as QT_CONTEXT


# ----------------------------------------------------------------------------
# --- Child QGraphicsItems ---
# ----------------------------------------------------------------------------

class ResizerItem(QtWidgets.QGraphicsObject):
    """Implementation adapted from : https://stackoverflow.com/questions/34429632/resize-a-qgraphicsitem-with-the-mouse

    Instances of this class are designed to interface directly with a parent such that the parent inherits this items geometry.
    Separating the resizing functionality from the parent allows it to be composed/reused with any generic item.

    There are two signals to which the parent can connect in order to receive geometry updates:

    - The `rectChange` signal is emitted interactively as the user drags a handle.
    - The `rectChanged` signal is emitted when the mouse is released and the user has finished resizing the item.

    In both cases a `QRectF` instance will be emitted with the signal, providing the parent with offset geometry in this item's local coordinate space.
    """

    rectChange = QtCore.Signal(QtCore.QRectF)
    rectChanged = QtCore.Signal(QtCore.QRectF)

    class Handle(Enum):
        TopLeft = 1
        TopMiddle = 2
        TopRight = 3
        MiddleLeft = 4
        MiddleRight = 5
        BottomLeft = 6
        BottomMiddle = 7
        BottomRight = 8

    DEFAULT_HANDLE_SIZE = 20.0

    HANDLE_CURSORS = {
        Handle.TopLeft: QtCore.Qt.SizeFDiagCursor,
        Handle.TopMiddle: QtCore.Qt.SizeVerCursor,
        Handle.TopRight: QtCore.Qt.SizeBDiagCursor,
        Handle.MiddleLeft: QtCore.Qt.SizeHorCursor,
        Handle.MiddleRight: QtCore.Qt.SizeHorCursor,
        Handle.BottomLeft: QtCore.Qt.SizeBDiagCursor,
        Handle.BottomMiddle: QtCore.Qt.SizeVerCursor,
        Handle.BottomRight: QtCore.Qt.SizeFDiagCursor,
    }

    def __init__(self, rect, parent=None):
        """Initializes this item to the given `QRectF` geometry which in most cases should be the `boundingRect` of the given parent item."""
        super(ResizerItem, self).__init__(parent)

        self._parent = parent

        # Geometry
        self._rect = rect
        self._minimumSize = QtCore.QSize()
        self._handleSize = ResizerItem.DEFAULT_HANDLE_SIZE
        self._handles = {}

        # Events
        self._selectedHandle = None
        self._mousePressOffset = QtCore.QPoint()

        # Flags/States
        self._isParentSelected = False
        self._isHovered = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)

        self._updateHandles()

    # --- Public ----------------------------------------------------------------------------

    @property
    def rect(self):
        """Returns the `QRectF` instance representing the inner geometry (ignoring the handles) in item coordinate space."""
        return self._rect

    @property
    def isHovered(self):
        """Returns `True` if the mouse is hovering over one of the handles."""
        return self._isHovered

    @property
    def minimumSize(self):
        """Retrieve or set the minimum size constraint for this item as a `QSize` instance.
        When setting the minimum size, the bottom right corner of this item will be adjusted if it currently exceeds the given constraint.
        """
        return self._minimumSize

    @minimumSize.setter
    def minimumSize(self, size):
        self.prepareGeometryChange()
        self._minimumSize = size
        self._rect.setWidth(max(self._rect.width(), size.width()))
        self._rect.setHeight(max(self._rect.height(), size.height()))
        self._updateHandles()

    @property
    def handleSize(self):
        """Retrieve or set the current handle size as a `QSize` instance."""
        return self._handleSize

    @handleSize.setter
    def handleSize(self, size):
        self.prepareGeometryChange()
        self._handleSize = size
        self._updateHandles()

    def conformToParent(self):
        """Conform this item's geometry to its parent item's `boundingRect`."""
        if self._parent is not None:
            self.prepareGeometryChange()
            self._rect = self._parent.boundingRect()
            self._updateHandles()

    # --- Private ----------------------------------------------------------------------------

    def _handleAt(self, point):
        """Return the handle enumeration for the handle containing the given point or `None` if there is no handle at the point."""
        for handle, rect, in self._handles.items():
            if rect.contains(point):
                return handle

    def _updateHandles(self):
        """Update cached handle geometry based on the current `boundingRect` and handle size."""
        s = self._handleSize
        b = self.boundingRect()

        self._handles[ResizerItem.Handle.TopLeft] = QtCore.QRectF(b.left(), b.top(), s, s)
        self._handles[ResizerItem.Handle.TopMiddle] = QtCore.QRectF(b.left() + s, b.top(), b.width() - 2 * s, s)
        self._handles[ResizerItem.Handle.TopRight] = QtCore.QRectF(b.right() - s, b.top(), s, s)
        self._handles[ResizerItem.Handle.MiddleLeft] = QtCore.QRectF(b.left(), b.top() + s, s, b.height() - 2 * s)
        self._handles[ResizerItem.Handle.MiddleRight] = QtCore.QRectF(b.right() - s, b.top() + s, s, b.height() - 2 * s)
        self._handles[ResizerItem.Handle.BottomLeft] = QtCore.QRectF(b.left(), b.bottom() - s, s, s)
        self._handles[ResizerItem.Handle.BottomMiddle] = QtCore.QRectF(b.left() + s, b.bottom() - s, b.width() - 2 * s, s)
        self._handles[ResizerItem.Handle.BottomRight] = QtCore.QRectF(b.right() - s, b.bottom() - s, s, s)

    def _interactiveResize(self, mousePos):
        """Perform interactive shape resizing.

        An offset is determined from the given mouse position and currently selected handle.
        The offset is then applied to this item's geometry and emitted with the `rectChange` signal, allowing the parent to inherit the local offset.
        This item's geometry is then repositioned at the top left corner of its parent.
        """
        self.prepareGeometryChange()

        # Apply offset to this item
        if self._selectedHandle == ResizerItem.Handle.TopLeft:
            mouseWidth = self._rect.right() - mousePos.x()
            mouseHeight = self._rect.bottom() - mousePos.y()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setLeft(self._rect.right() - adjustedWidth)
            self._rect.setTop(self._rect.bottom() - adjustedHeight)
        elif self._selectedHandle == ResizerItem.Handle.TopMiddle:
            mouseHeight = self._rect.bottom() - mousePos.y()
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setTop(self._rect.bottom() - adjustedHeight)
        elif self._selectedHandle == ResizerItem.Handle.TopRight:
            mouseWidth = mousePos.x() - self._rect.left()
            mouseHeight = self._rect.bottom() - mousePos.y()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setRight(self._rect.left() + adjustedWidth)
            self._rect.setTop(self._rect.bottom() - adjustedHeight)
        elif self._selectedHandle == ResizerItem.Handle.MiddleLeft:
            mouseWidth = self._rect.right() - mousePos.x()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            self._rect.setLeft(self._rect.right() - adjustedWidth)
        elif self._selectedHandle == ResizerItem.Handle.MiddleRight:
            mouseWidth = mousePos.x() - self._rect.left()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            self._rect.setRight(self._rect.left() + adjustedWidth)
        elif self._selectedHandle == ResizerItem.Handle.BottomLeft:
            mouseWidth = self._rect.right() - mousePos.x()
            mouseHeight = mousePos.y() - self._rect.top()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setLeft(self._rect.right() - adjustedWidth)
            self._rect.setBottom(self._rect.top() + adjustedHeight)
        elif self._selectedHandle == ResizerItem.Handle.BottomMiddle:
            mouseHeight = mousePos.y() - self._rect.top()
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setBottom(self._rect.top() + adjustedHeight)
        elif self._selectedHandle == ResizerItem.Handle.BottomRight:
            mouseWidth = mousePos.x() - self._rect.left()
            mouseHeight = mousePos.y() - self._rect.top()
            adjustedWidth = max(self._minimumSize.width(), mouseWidth)
            adjustedHeight = max(self._minimumSize.height(), mouseHeight)
            self._rect.setRight(self._rect.left() + adjustedWidth)
            self._rect.setBottom(self._rect.top() + adjustedHeight)

        # Send update to parent
        self.rectChange.emit(QtCore.QRectF(self._rect))

        # Reposition this item's geometry at the parent's new origin
        self._rect.moveTo(0, 0)
        self._updateHandles()

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Executed when the mouse moves over the shape."""
        # We cannot just use `hoverEnterEvent` since the event triggers within a tolerance of an item's shape (may be outside)
        # We cannot set the cursor with `self.setCursor()` as this was not producing a persistent state (something else is overtaking the cursor)
        # Therefore we override the cursor at the application level
        handle = self._handleAt(event.pos())
        self._isHovered = True if handle is not None else False

        if self._isHovered:
            cursor = ResizerItem.HANDLE_CURSORS[handle]
            QT_APP.setCursor(cursor)

        super(ResizerItem, self).hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Executed when the mouse leaves the shape."""
        QT_APP.restoreCursor()
        self._isHovered = False

        super(ResizerItem, self).hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Executed when the mouse is pressed on the item."""
        self._isParentSelected = self._parent.isSelected() if self._parent is not None else False
        self._selectedHandle = self._handleAt(event.pos())

        if self._selectedHandle:
            self._mousePressOffset = event.pos() - self._handles[self._selectedHandle].center()

        super(ResizerItem, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Executed when the mouse is being moved over the item while being pressed."""
        if self._selectedHandle is not None:
            # The offset is maintained to prevent the center of the selected handle from jumping to the mouse position
            self._interactiveResize(event.pos() - self._mousePressOffset)

        super(ResizerItem, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Executed when the mouse is released from the item."""
        self._isParentSelected = False
        self._selectedHandle = None
        self._mousePressOffset = QtCore.QPoint()

        self.update()
        self.rectChanged.emit(self._rect)

        super(ResizerItem, self).mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Ensures the parent item will remain selected when this item is selected for resizing.
        Ensures the cursor is reset if this item is deleted whilst hovered.
        """
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange and value == 1:
            if self._isParentSelected:
                self._parent.setSelected(True)
        elif change == QtWidgets.QGraphicsItem.ItemSceneHasChanged:
            QT_APP.restoreCursor()

        return super(ResizerItem, self).itemChange(change, value)

    def shape(self):
        """Returns the shape of this item as a `QPainterPath` in local coordinates.
        The shape just includes the handle geometry.
        """
        path = QtGui.QPainterPath()

        for shape in self._handles.values():
            path.addRect(shape)

        return path

    # --- Pure Virtual ----------------------------------------------------------------------------

    def boundingRect(self):
        """Returns the bounding rect of the shape as a `QRectF` in local coordinates."""
        offset = self._handleSize / 2
        return self._rect.adjusted(-offset, -offset, offset, offset)

    def paint(self, painter, option, widget=None):
        """Null op."""
        pass


class TitleBarItem(QtWidgets.QGraphicsWidget):
    """Acts as a container for the `TitleItem` and the `ColorPickerItem`.

    This item has a default minimum width and height determined by the geometry of its contents.
    The width will expand to fit its parent's width whilst a fixed height can be set by calling `setFixedHeight`.
    Child items will then be vertically centered within the available space.
    """

    SPACING = 50

    def __init__(self, title, color, parent=None):
        super(TitleBarItem, self).__init__(parent)

        # If we do not keep a reference to the parent, calling QGraphicsItem.parentItem() will fail
        self._parent = parent
        self._title = title
        self._color = color

        # This item will conform to its children by default (we will add stretch to account for this)
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self._createItems()
        self._connectSignals()

    # --- Public ----------------------------------------------------------------------------

    def setFixedHeight(self, height):
        """Set the height of the title bar."""
        self._titleLayoutItem.setFixedHeight(height)
        self._colorPickerLayoutItem.setFixedHeight(height)

    @property
    def colorPickerItem(self):
        """Return a reference to the child `ColorPickerItem`."""
        return self._colorPickerItem

    @property
    def titleItem(self):
        """Return a reference to the child `TitleItem`."""
        return self._titleItem

    # --- Private ----------------------------------------------------------------------------

    def _createItems(self):
        layout = QtWidgets.QGraphicsLinearLayout()
        # Ensures the minimum width always accounts for an extra 50 units between items
        layout.setSpacing(TitleBarItem.SPACING)

        # --- Title ---
        self._titleItem = TitleItem(title=self._title, parent=self)
        self._titleLayoutItem = TitleBarLayoutItem(item=self._titleItem)

        layout.addItem(self._titleLayoutItem)
        layout.setAlignment(self._titleLayoutItem, QtCore.Qt.AlignLeft)

        # Stretch ensures this item's `boundingRect` will expand to the `sizeHint` if its child `QGraphicsLayoutItems` only consume a sub-region
        layout.addStretch()

        # --- Color Picker ---
        self._colorPickerItem = ColorPickerItem(color=self._color, parent=self)
        self._colorPickerLayoutItem = TitleBarLayoutItem(item=self._colorPickerItem)

        layout.addItem(self._colorPickerLayoutItem)
        layout.setAlignment(self._colorPickerLayoutItem, QtCore.Qt.AlignRight)

        self.setLayout(layout)

    def _connectSignals(self):
        # Ensure the geometry of the layout item updates when the text is changed
        self._titleItem.document().documentLayout().documentSizeChanged.connect(self._titleLayoutItem.updateGeometry)
        # Force the layout to reposition its items
        self._titleItem.document().documentLayout().documentSizeChanged.connect(self.layout().invalidate)

    # --- Virtual ----------------------------------------------------------------------------

    def sizeHint(self, which, constraint):
        # Calculate the minimum size of this item (ie. size without any stretch)
        minimumSize = QtWidgets.QGraphicsWidget.sizeHint(self, QtCore.Qt.MinimumSize, constraint)

        # If the minimum width of this item is smaller than its parent's width, conform this item's width to its parent's width
        # If the minimum width is larger, the `TitleItem` `documentSizeChanged` signal will allow the parent to conform to this item
        if self._parent:
            minimumWidth = minimumSize.width()
            parentWidth = self._parent.boundingRect().width()

            if minimumWidth < parentWidth:
                minimumSize.setWidth(parentWidth)

        return minimumSize

    def shape(self):
        """There is an issue whereby `QGraphicsLayout` are preventing certain events from being generated (see module documentation).
        The container does not need to receive events, therefore we can remove its interactive shape to prevent the issue.
        """
        path = QtGui.QPainterPath()
        path.addRect(QtCore.QRectF(0, 0, 0, 0))
        return path


class TitleBarLayoutItem(QtWidgets.QGraphicsLayoutItem):
    """A `QGraphicsLayoutItem` that allows a `QGraphicsItem` to be positioned within a `QGraphicsLayout`.

    This item's geometry is by default constrained to the given `QGraphicsItem` however a fixed height can be set by calling `setFixedHeight`.
    The given `QGraphicsItem` will then be vertically centered within the available space.
    """

    def __init__(self, item=None, parent=None):
        super(TitleBarLayoutItem, self).__init__(parent, isLayout=False)

        self._height = None

        if item is None:
            self._item = None
        else:
            self.setItem(item)

        self.setOwnedByLayout(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    # --- Public ----------------------------------------------------------------------------

    def setFixedHeight(self, height):
        self._height = height
        self.updateGeometry()

    def setItem(self, item):
        self._item = item
        self.setGraphicsItem(item)

    # --- Virtual ----------------------------------------------------------------------------

    def setGeometry(self, rect):
        """Vertically centers the contained `QGraphicsItem` within the given `QGraphicsLayout` region. Called upon activating the `QGraphicsLayout` or by the user."""
        if self._item:
            itemRect = self._item.boundingRect()
            heightDelta = rect.height() - itemRect.height()
            rect.moveTop(rect.y() + heightDelta / 2)
            self._item.setPos(rect.topLeft())

        super(TitleBarLayoutItem, self).setGeometry(rect)

    # --- Pure Virtual ----------------------------------------------------------------------------

    def sizeHint(self, which, constraint):
        """Sets the size of this item to the contained `QGraphicsItem` size. The height will be adjusted if a fixed height has been set."""
        if self._item:
            size = self._item.boundingRect().size()

            if self._height is not None:
                size.setHeight(self._height)

            return size
        else:
            return super(TitleBarLayoutItem, self).sizeHint(which, constraint)


class TitleItem(QtWidgets.QGraphicsTextItem):
    """A graphics item used to display a title.

    The `hoverChanged` signal is emitted whenever the hover state of this item changes.
    """

    # Style
    DEFAULT_FONT_SIZE = 18
    DEFAULT_TEXT_COLOR = (200, 200, 200, 255)

    # Signals
    hoverChanged = QtCore.Signal()

    def __init__(self, title, parent=None):
        super(TitleItem, self).__init__(title, parent)

        self._parent = parent
        self._font = QtGui.QFont()
        self._isHovered = False

        self.fontSize = TitleItem.DEFAULT_FONT_SIZE
        self.textColor = QtGui.QColor(*TitleItem.DEFAULT_TEXT_COLOR)

        # `QGraphicsTextItem` accepts hover events by default
        self.setFlags(QtWidgets.QGraphicsTextItem.ItemIsFocusable)
        self.setFlags(QtWidgets.QGraphicsTextItem.ItemIsSelectable)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

    # --- Public ----------------------------------------------------------------------------

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def fontSize(self):
        return self._font.pointSize()

    @fontSize.setter
    def fontSize(self, size):
        self._font.setPointSize(size)
        self.setFont(self._font)

    @property
    def textColor(self):
        return self.defaultTextColor()

    @textColor.setter
    def textColor(self, color):
        self.setDefaultTextColor(color)

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal if it has changed due to the mouse moving over the shape."""
        # We cannot just use `hoverEnterEvent` since the event triggers within a tolerance of an item's shape (may be outside)
        # We cannot set the cursor with `self.setCursor()` as this was not producing a persistent state (something else is overtaking the cursor)
        # Therefore we override the cursor at the application level
        wasHovered = self._isHovered
        self._isHovered = self.boundingRect().contains(event.pos())

        if self._isHovered != wasHovered:
            self.hoverChanged.emit()

        if self._isHovered:
            QT_APP.setCursor(QtCore.Qt.IBeamCursor)

        super(TitleItem, self).hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal due to the mouse leaving the shape."""
        QT_APP.restoreCursor()
        self._isHovered = False
        self.hoverChanged.emit()

        super(TitleItem, self).hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Enables text editing, selects and sets focus for this item when the mouse is pressed on it."""
        if event.button() == QtCore.Qt.LeftButton and self.textInteractionFlags() == QtCore.Qt.NoTextInteraction:
            self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
            self.setFocus()
            self.setSelected(True)

        super(TitleItem, self).mousePressEvent(event)

    def focusOutEvent(self, event):
        """Disables text editing, restores the cursor and deselects this item when it loses focus."""
        self.setSelected(False)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)

        super(TitleItem, self).focusOutEvent(event)

    def keyPressEvent(self, event):
        """Clears focus when the enter or return key is pressed."""
        if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
            self.clearFocus()
            event.accept()
            return

        super(TitleItem, self).keyPressEvent(event)

    def itemChange(self, change, value):
        """Prevents selection via dragging and clears focus when the item is deselected.
        Ensures the cursor is reset if this item is deleted whilst hovered.
        """
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            if value and not self.hasFocus():
                return False
            elif not value:
                self.clearFocus()
        elif change == QtWidgets.QGraphicsItem.ItemSceneHasChanged:
            QT_APP.restoreCursor()

        return super(TitleItem, self).itemChange(change, value)


class ColorPickerItem(QtWidgets.QGraphicsObject):
    """A graphics item used to display a panel of colors from which the user can select.

    Selecting this item will toggle the visibility of the panel item.
    """

    # Dimensions
    DEFAULT_RADIUS = 20

    # Style
    PEN_COLOR = (200, 200, 200, 255)

    def __init__(self, color, parent=None):
        super(ColorPickerItem, self).__init__(parent)

        # Data
        self._parent = parent
        self._color = color
        self._radius = ColorPickerItem.DEFAULT_RADIUS

        # Flags/States
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)

        # Events
        self._wasSelected = False
        self._isClicked = False

        # Brush
        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.SolidPattern)
        self._brush.setColor(self._color)

        # Pen
        self._pen = QtGui.QPen()
        self._pen.setWidth(2)
        self._pen.setStyle(QtCore.Qt.SolidLine)
        self._pen.setColor(QtGui.QColor(*ColorPickerItem.PEN_COLOR))

        self._createItems()
        self._connectSignals()

        # Animation
        self._opacityAnim = QT_ANIM.opacityAnimation(self._colorPickerPanelItem, startValue=0.0, endValue=1.0, duration=170, play=False)
        self._slideAnim = QT_ANIM.horizontalSlideAnimation(self._colorPickerPanelItem, startOffset=-75, endOffset=0, duration=220, play=False,
                                                           finishCallback=self._colorPickerPanelItem.enableMouseEvents)
        self._colorAnim = QT_ANIM.propertyAnimation(self, propertyName="colorProperty", startValue=color, endValue=color, duration=320, play=False,
                                                    interpolationType=QtCore.QEasingCurve.InQuad)

    # --- Public ----------------------------------------------------------------------------

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color
        self._brush.setColor(self._color)
        self.update()

    # Used to animate the above color property
    colorProperty = QtCore.Property(QtGui.QColor, lambda obj: getattr(obj, 'color'), lambda obj, x: setattr(obj, 'color', x))

    @property
    def colorPickerPanelItem(self):
        """Return a reference to the child `ColorPickerPanelItem`."""
        return self._colorPickerPanelItem

    @property
    def diameter(self):
        return self._radius * 2

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, radius):
        self.prepareGeometryChange()
        self._radius = radius

    # --- Private ----------------------------------------------------------------------------

    def _createItems(self):
        self._colorPickerPanelItem = ColorPickerPanelItem(parent=self)
        self._colorPickerPanelItem.setOpacity(0.0)
        self._colorPickerPanelItem.setPos(75, -self._colorPickerPanelItem.margin)

    def _connectSignals(self):
        self._colorPickerPanelItem.colorPicked.connect(self._updateColor)

    def _updateColor(self, color):
        self._colorAnim.setStartValue(self.color)
        self._colorAnim.setEndValue(color)
        self._colorAnim.start()

        self.setSelected(False)

    def _togglePanel(self):
        # Play backwards if both animations have already begun or finished playing forwards
        if (self._opacityAnim.currentTime() != 0 and self._slideAnim.currentTime() != 0
                and self._opacityAnim.direction() == QtCore.QAbstractAnimation.Forward and self._slideAnim.direction() == QtCore.QAbstractAnimation.Forward):
            self._opacityAnim.setDirection(QtCore.QAbstractAnimation.Backward)
            self._slideAnim.setDirection(QtCore.QAbstractAnimation.Backward)

        # Otherwise play forwards
        elif self._opacityAnim.direction() == QtCore.QAbstractAnimation.Backward and self._slideAnim.direction() == QtCore.QAbstractAnimation.Backward:
            self._opacityAnim.setDirection(QtCore.QAbstractAnimation.Forward)
            self._slideAnim.setDirection(QtCore.QAbstractAnimation.Forward)

        self._colorPickerPanelItem.disableMouseEvents()

        self._opacityAnim.start()
        self._slideAnim.start()

    # --- Virtual ----------------------------------------------------------------------------

    def mousePressEvent(self, event):
        """Records selection states to enable selection toggling and prevent selection via dragging."""
        self._wasSelected = self.isSelected()
        self._isClicked = True

        super(ColorPickerItem, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Records selection states and toggles the selection."""
        self._isClicked = False

        if self._wasSelected:
            self.setSelected(False)
            self._wasSelected = False
            return

        super(ColorPickerItem, self).mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Prevents selection via dragging and toggles panel visibility based on the selection state."""
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            if value and not self._isClicked:
                return False

            self._togglePanel()

        return super(ColorPickerItem, self).itemChange(change, value)

    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    # --- Pure Virtual ----------------------------------------------------------------------------

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.diameter, self.diameter)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawEllipse(0, 0, self.diameter, self.diameter)


class ColorPickerPanelItem(QtWidgets.QGraphicsObject):
    """A graphics item that displays a panel of colors from which the user can select.

    The `colorPicked` signal is emitted whenever a color is selected from the panel.
    The `hoverChanged` signal is emitted whenever the hover state of this item changes.
    """

    # Signals
    colorPicked = QtCore.Signal(QtGui.QColor)
    hoverChanged = QtCore.Signal()

    # Dimensions
    ARROW_WIDTH_RATIO = 0.8
    ARROW_HEIGHT_RATIO = 1.6
    DEFAULT_COLOR_RADIUS = 20
    HOVER_SCALE_RATIO = 0.3
    MARGIN_RATIO = 1.4
    PANEL_RADIUS = 10
    SPACE_RATIO = 0.9

    # Style
    BACKGROUND_COLOR = (230, 230, 230, 255)
    PEN_COLOR = (12, 12, 12, 255)
    SELECTION_COLORS = (
        QtGui.QColor(253, 62, 58), QtGui.QColor(249, 162, 48), QtGui.QColor(255, 222, 83), QtGui.QColor(255, 255, 255),
        QtGui.QColor(228, 54, 132), QtGui.QColor(62, 163, 233), QtGui.QColor(108, 198, 72), QtGui.QColor(170, 170, 170),
        QtGui.QColor(151, 55, 176), QtGui.QColor(57, 106, 172), QtGui.QColor(74, 148, 72), QtGui.QColor(85, 85, 85),
        QtGui.QColor(83, 28, 97), QtGui.QColor(33, 41, 87), QtGui.QColor(36, 89, 39), QtGui.QColor(0, 0, 0)
    )

    def __init__(self, parent=None):
        super(ColorPickerPanelItem, self).__init__(parent)

        # Data
        self._radius = ColorPickerPanelItem.DEFAULT_COLOR_RADIUS
        self._items = {}

        # Brush
        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.SolidPattern)
        self._brush.setColor(QtGui.QColor(*ColorPickerPanelItem.BACKGROUND_COLOR))

        # Pen
        self._pen = QtGui.QPen()
        self._pen.setWidth(3)
        self._pen.setStyle(QtCore.Qt.SolidLine)
        self._pen.setColor(QtGui.QColor(*ColorPickerPanelItem.PEN_COLOR))

        # States
        self._isHovered = False
        self._hoverColorName = None
        self.setAcceptHoverEvents(True)

        self._updateColorItemGeometry()

    # --- Public ----------------------------------------------------------------------------

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, radius):
        self.prepareGeometryChange()
        self._radius = radius
        self._updateColorItemGeometry()

    @property
    def diameter(self):
        return self._radius * 2

    @property
    def margin(self):
        return self._radius * ColorPickerPanelItem.MARGIN_RATIO

    @property
    def space(self):
        return self._radius * ColorPickerPanelItem.SPACE_RATIO

    @property
    def arrowWidth(self):
        return self._radius * ColorPickerPanelItem.ARROW_WIDTH_RATIO

    @property
    def arrowHeight(self):
        return self._radius * ColorPickerPanelItem.ARROW_HEIGHT_RATIO

    @property
    def rect(self):
        """Returns the main geometry in local coordinates (does not include the arrow)."""
        side = self.margin * 2 + self.space * 3 + self.diameter * 4
        return QtCore.QRectF(self.arrowWidth, 0, side, side)

    def disableMouseEvents(self):
        """Disable user interaction with this item. Designed to be called before animating this item."""
        # The panel was triggering a `hoverEnterEvent` as it slides over the `ColorPickerItem` but the `hoverLeaveEvent` was never triggered
        # This was causing `NodeBox` and `Sticky` items to think the panel was hovered, changing how their top rectangle is shaded
        self.setAcceptHoverEvents(False)

        # Because hover events have been disabled, the panel's hover states will not be reset if the panel is being closed after selecting a color
        self._isHovered = False
        self._hoverColorName = None

        # If the user attempted to double click the `ColorPickerItem`, the panel was receiving the `mousePressEvent` as it slides over the `ColorPickerItem`
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    def enableMouseEvents(self):
        """Enable user interaction with this item. Designed to be called after animating this item."""
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(QtCore.Qt.AllButtons)

    # --- Private ----------------------------------------------------------------------------

    def _updateColorItemGeometry(self):
        """Update local color item geometry based on the current dimensions."""
        diameter = self.diameter
        space = self.space
        rect = self.rect

        for row in xrange(4):
            for column in xrange(4):
                index = row * 4 + column
                left = rect.left() + self.margin + column * diameter + column * space
                top = rect.top() + self.margin + row * diameter + row * space
                itemRect = QtCore.QRectF(left, top, diameter, diameter)
                self._items[ColorPickerPanelItem.SELECTION_COLORS[index].name()] = itemRect

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal if it has changed due to the mouse moving over the panel shape.
        Also scales a color shape if it is hovered.
        """
        # We cannot just use `hoverEnterEvent` since the event triggers within a tolerance of an item's shape (may be outside)
        pos = event.pos()
        wasHovered = self._isHovered
        self._isHovered = self.boundingRect().contains(event.pos())

        if self._isHovered != wasHovered:
            self.hoverChanged.emit()

        for colorName, itemRect in self._items.iteritems():
            if itemRect.contains(pos):
                if self._hoverColorName != colorName:
                    self._hoverColorName = colorName
                    self.update()
                break
        else:
            if self._hoverColorName:
                self._hoverColorName = None
                self.update()

        super(ColorPickerPanelItem, self).hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal due to the mouse leaving the panel shape."""
        self._hoverColorName = None
        self._isHovered = False
        self.hoverChanged.emit()
        self.update()

        super(ColorPickerPanelItem, self).hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Emits the `colorPicked` signal if the mouse is pressed on a color shape."""
        pos = event.pos()

        for colorName, itemRect in self._items.iteritems():
            if itemRect.contains(pos):
                self.colorPicked.emit(QtGui.QColor(colorName))

        # Always prevent the event from propagating (this way clicking on the panel will not deselect its parent)
        event.accept()

    # --- Pure Virtual ----------------------------------------------------------------------------

    def boundingRect(self):
        rect = self.rect
        rect.setX(0)
        return rect

    def paint(self, painter, option, widget):
        rect = self.rect
        cornerArcRect = QtCore.QRectF(0, 0, ColorPickerPanelItem.PANEL_RADIUS * 2, ColorPickerPanelItem.PANEL_RADIUS * 2)
        cornerWidthVec = QtCore.QPointF(ColorPickerPanelItem.PANEL_RADIUS, 0)
        cornerHeightVec = QtCore.QPointF(0, ColorPickerPanelItem.PANEL_RADIUS)
        arrowHeightMargin = (self.diameter - self.arrowHeight) / 2

        # To avoid a small gap between the arrow and the rect, both items are drawn as a single path
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + cornerWidthVec)
        path.lineTo(rect.topRight() - cornerWidthVec)
        cornerArcRect.moveTopRight(rect.topRight())
        path.arcTo(cornerArcRect, 90, -90)
        path.lineTo(rect.bottomRight() - cornerHeightVec)
        cornerArcRect.moveBottomRight(rect.bottomRight())
        path.arcTo(cornerArcRect, 0, -90)
        path.lineTo(rect.bottomLeft() + cornerWidthVec)
        cornerArcRect.moveBottomLeft(rect.bottomLeft())
        path.arcTo(cornerArcRect, 270, -90)
        path.lineTo(rect.left(), rect.top() + self.margin + self.diameter - arrowHeightMargin)
        path.lineTo(0, rect.top() + self.margin + arrowHeightMargin + self.arrowHeight / 2)
        path.lineTo(rect.left(), rect.top() + self.margin + arrowHeightMargin)
        path.lineTo(rect.topLeft() + cornerHeightVec)
        cornerArcRect.moveTopLeft(rect.topLeft())
        path.arcTo(cornerArcRect, 180, -90)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawPath(path)

        # Items
        itemBrush = QtGui.QBrush()
        itemBrush.setStyle(QtCore.Qt.SolidPattern)

        for color in ColorPickerPanelItem.SELECTION_COLORS:
            itemBrush.setColor(color)
            painter.setBrush(itemBrush)
            painter.setPen(QtCore.Qt.NoPen)
            rect = self._items[color.name()]

            if color == self._hoverColorName:
                offset = self.radius * ColorPickerPanelItem.HOVER_SCALE_RATIO
                rect = rect.adjusted(-offset, -offset, offset, offset)

            painter.drawEllipse(rect)


class TextBoxItem(QtWidgets.QGraphicsWidget):
    """Acts as a container for the `TextItem`.

    The width of this item will always conform to its parent's width.
    The height of this item will expand to its parent's height if the minimum height is smaller.
    """

    def __init__(self, text, parent=None):
        super(TextBoxItem, self).__init__(parent)

        # If we do not keep a reference to the parent, calling QGraphicsItem.parentItem() will fail
        self._parent = parent
        self._text = text

        self._createItems()
        self._connectSignals()

        # This item will conform to its children by default
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

    # --- Public ----------------------------------------------------------------------------

    @property
    def textItem(self):
        """Return a reference to the child `TextItem`."""
        return self._textItem

    # --- Private ----------------------------------------------------------------------------

    def _createItems(self):
        layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)

        # Text
        self._textItem = TextItem(text=self._text, parent=self)
        self._textLayoutItem = TextLayoutItem(item=self._textItem)
        layout.addItem(self._textLayoutItem)
        layout.setAlignment(self._textLayoutItem, QtCore.Qt.AlignLeft)

        # Stretch ensures this item's boundingRect will consume the entire sizeHint if its contained QGraphicsLayoutItems only consume a sub-region
        layout.addStretch()

        self.setLayout(layout)

    def _connectSignals(self):
        # Ensure the geometry of the layout item updates when the text is changed
        self._textItem.document().documentLayout().documentSizeChanged.connect(self._textLayoutItem.updateGeometry)
        # Force the layout to reposition its items
        self._textItem.document().documentLayout().documentSizeChanged.connect(self.layout().invalidate)

    # --- Virtual ----------------------------------------------------------------------------

    def sizeHint(self, which, constraint):
        """Provides a region for child `QGraphicsLayoutItems` to fill.
        An unconstrained `QGraphicsLayoutItem` will expand to fill this region.
        """
        # Calculate the minimum size of this item
        minimumHeight = self._textLayoutItem.sizeHint(QtCore.Qt.MinimumSize, constraint).height()

        if self.layout():
            margins = self.layout().getContentsMargins()
            minimumHeight = minimumHeight + margins[1] + margins[3]

        constraint.setHeight(minimumHeight)

        # Conform the width to the parent's width
        # If the minimum height of this item is smaller than its parent's height, conform this item's height to its parent's height
        # If the minimum height is larger, the `documentSizeChanged` signal of the `TextItem` will allow the parent to conform to its height
        if self._parent:
            parentWidth = self._parent.boundingRect().width() - self.pos().x()
            parentHeight = self._parent.boundingRect().height() - self.pos().y()

            constraint.setWidth(parentWidth)
            if minimumHeight < parentHeight:
                constraint.setHeight(parentHeight)

        return constraint

    def shape(self):
        """There is an issue whereby `QGraphicsLayout` are preventing certain events from being generated (see module documentation).
        The container does not need to receive events, therefore we can remove its interactive shape to prevent the issue.
        """
        path = QtGui.QPainterPath()
        path.addRect(QtCore.QRectF(0, 0, 0, 0))
        return path


class TextLayoutItem(QtWidgets.QGraphicsLayoutItem):
    """A `QGraphicsLayoutItem` that allows a `TextItem` to be positioned within a `QGraphicsLayout`.

    The width of this item is unconstrained and will therefore expand to the `sizeHint` given by the parent `QGraphicsLayout`.
    The height of this item is constrained to the minimum height of its contained `TextItem`.
    """

    def __init__(self, item=None, parent=None):
        super(TextLayoutItem, self).__init__(parent, isLayout=False)

        self._item = None
        self.setOwnedByLayout(True)

        if item is not None:
            self.setItem(item)

    def setItem(self, item):
        self._item = item
        self.setGraphicsItem(item)

    # --- Virtual ----------------------------------------------------------------------------

    def setGeometry(self, rect):
        """Positions the contained `TextItem` within the given `QGraphicsLayout` region. Called upon activating the `QGraphicsLayout` or by the user."""
        if self._item:
            self._item.setPos(rect.topLeft())

        super(TextLayoutItem, self).setGeometry(rect)

    # --- Pure Virtual ----------------------------------------------------------------------------

    def sizeHint(self, which, constraint):
        """Constrains the height of the this layout item to ensure the entire text of the contained `TextItem` is visible."""
        if self._item:
            # Determine a minimum height for the layout
            # This is only possible because the width of the `TextItem` has been allowed to fill the entire `QGraphicsLayout`
            height = self._item.document().size().height()
            constraint.setHeight(height)

        return constraint


class TextItem(QtWidgets.QGraphicsTextItem):
    """A graphics item used to display text.

    This width of this item will always conform to its parent geometry.
    The height of this item will always expand to fill its parent geometry but will never shrink.
    If the minimum height of this item is larger, the `documentSizeChanged` signal will allow the parent to conform to this item.
    The parent is responsible for invoking `updateTextWidth` whenever its width is changed.
    """

    # Signals
    hoverChanged = QtCore.Signal()

    # Style
    DEFAULT_FONT_SIZE = 12
    DEFAULT_TEXT_COLOR = QtGui.QColor(200, 200, 200, 255)

    def __init__(self, text, parent=None):
        super(TextItem, self).__init__(text, parent)

        self._parent = parent
        self._font = QtGui.QFont()
        self.fontSize = TextItem.DEFAULT_FONT_SIZE
        self.textColor = TextItem.DEFAULT_TEXT_COLOR

        # QGraphicsTextItem accepts hover events by default
        self._isHovered = False
        self.setFlags(QtWidgets.QGraphicsTextItem.ItemIsFocusable)
        self.setFlags(QtWidgets.QGraphicsTextItem.ItemIsSelectable)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

    # --- Public ----------------------------------------------------------------------------

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def fontSize(self):
        return self._font.pointSize()

    @fontSize.setter
    def fontSize(self, size):
        self._font.setPointSize(size)
        self.setFont(self._font)

    @property
    def textColor(self):
        return self.defaultTextColor()

    @textColor.setter
    def textColor(self, color):
        self.setDefaultTextColor(color)

    def updateTextWidth(self):
        """To be called when the width of this item changes to ensure text conforms to the boundingRect"""
        self.setTextWidth(self.boundingRect().width())

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal if it has changed due to the mouse moving over the shape."""
        # We cannot just use `hoverEnterEvent` since the event triggers within a tolerance of an item's shape (may be outside)
        # We cannot set the cursor with `self.setCursor()` as this was not producing a persistent state (something else is overtaking the cursor)
        # Therefore we override the cursor at the application level
        wasHovered = self._isHovered
        self._isHovered = self.boundingRect().contains(event.pos())

        if self._isHovered != wasHovered:
            self.hoverChanged.emit()

        if self._isHovered:
            QT_APP.setCursor(QtCore.Qt.IBeamCursor)

        super(TextItem, self).hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Updates the hover state and emits the `hoverChanged` signal due to the mouse leaving the shape."""
        QT_APP.restoreCursor()
        self._isHovered = False
        self.hoverChanged.emit()

        super(TextItem, self).hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Enables text editing, selects and sets focus for this item when the mouse is pressed on it."""
        if event.button() == QtCore.Qt.LeftButton and self.textInteractionFlags() == QtCore.Qt.NoTextInteraction:
            self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
            self.setFocus()
            self.setSelected(True)

        super(TextItem, self).mousePressEvent(event)

    def focusOutEvent(self, event):
        """Disables text editing, restores the cursor and deselects this item when it loses focus."""
        self.setSelected(False)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)

        super(TextItem, self).focusOutEvent(event)

    def itemChange(self, change, value):
        """Prevents selection via dragging and clears focus when this item is deselected.
        Ensures the cursor is reset if this item is deleted whilst hovered.
        """
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            if value and not self.hasFocus():
                return False
            elif not value:
                self.clearFocus()
        elif change == QtWidgets.QGraphicsItem.ItemSceneHasChanged:
            QT_APP.restoreCursor()

        return super(TextItem, self).itemChange(change, value)

    def boundingRect(self):
        """Conforms the width of this item to the parent geometry and expands the height of this item to fill the height of the `QGraphicsLayout`.

        Note:
            The `TextLayoutItem` enforces a minimum height based on the width of this item.
            The minimum height of this item can only be determined (through the baseclass implementation) after the width has been set by invoking this method.
            Therefore the `TextLayoutItem` relies on this function setting the width in order to determine a minimum height.
        """
        rect = QtWidgets.QGraphicsTextItem.boundingRect(self)

        if self._parent is not None:
            if self._parent.layout():
                rect.setWidth(self._parent.layout().contentsRect().width())
                parentHeight = self._parent.layout().contentsRect().height()
            else:
                rect.setWidth(self._parent.boundingRect().width())
                parentHeight = self._parent.boundingRect().height()

            if rect.height() < parentHeight:
                rect.setHeight(parentHeight)

        return rect

    def shape(self):
        """Adjusts the selectable region."""
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path


# ----------------------------------------------------------------------------
# --- Sticky QGraphicsItem ---
# ----------------------------------------------------------------------------

class StickyItem(QtWidgets.QGraphicsObject):
    """A graphics item designed to display comments in the Node Editor.

    - The `colorChanged` signal is emitted whenever a new color is selected for the item.
    - The `deleteKeyPressed` signal is emitted whenever the delete key is pressed with this item selected.
    - The `rectChanged` signal is emitted whenever the geometry of this item changes after the mouse is released.
    - The `sceneChanged` signal is emitted whenever the `QGraphicsScene` ownership of this item is changed (ie. the item is transferred to or removed from a scene).
      This signal is designed to allow an item to be reloaded from metadata if an unhandled scene change occurs.
    - The `titleChanged` signal is emitted whenever the title of this item is changed.
    - The `textChanged` signal is emitted whenever the text of this item is changed.
    """
    # Signals
    colorChanged = QtCore.Signal(QtGui.QColor)
    deleteKeyPressed = QtCore.Signal()
    textChanged = QtCore.Signal(str)
    titleChanged = QtCore.Signal(str)
    rectChanged = QtCore.Signal(QtCore.QRectF)
    sceneChanged = QtCore.Signal()

    # Types
    Type = QtWidgets.QGraphicsItem.UserType + 501

    # Dimensions
    DEFAULT_WIDTH = 500
    DEFAULT_HEIGHT = 500
    MINIMUM_WIDTH = 300
    MINIMUM_HEIGHT = 200
    RADIUS = 20
    TOP_RECT_HEIGHT = 55

    # Style
    DEFAULT_COLOR = ColorPickerPanelItem.SELECTION_COLORS[2]

    # Contents
    DEFAULT_TITLE = "Note"
    DEFAULT_TEXT = "Click to edit"

    def __init__(self, UUID=None, rect=None, color=None, title=None, text=None, parent=None):
        """Initialise the `StickyItem`.

        Args:
            UUID (`uuid.UUID`, optional): A unique identifier used to load this item from metadata.
                Defaults to `None` - if this item is not being loaded, a new identifier will be assigned.
            rect (`PySide2.QtCore.QRectF`, optional): The shape used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default shape will be assigned.
            color (`PySide2.QtGui.QColor`, optional): The color used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default color will be assigned.
            title (`basestring`, optional): The title used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default title will be assigned.
            text (`basestring`, optional): The text used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default text will be assigned.
            parent (`PySide2.QtWidgets.QGraphicsItem`, optional): The parent item. Defaults to `None`.
        """
        super(StickyItem, self).__init__(parent)

        # If we do not keep a reference to the parent, calling QGraphicsItem.parentItem() leads to odd behaviour (this item is deleted)
        self._parent = parent

        # Given geometry is assumed to be in scene coordinates and the parent positioned at the origin
        # Cached geometry must be in local coordinates
        if rect:
            pos = rect.topLeft()
            rect.moveTo(0, 0)

        # Data
        self._UUID = UUID if UUID is not None else uuid.uuid4()
        self._rect = QtCore.QRectF(rect) if rect is not None else QtCore.QRectF(0, 0, StickyItem.DEFAULT_WIDTH, StickyItem.DEFAULT_HEIGHT)
        color = color if color is not None else StickyItem.DEFAULT_COLOR
        title = title if title is not None else StickyItem.DEFAULT_TITLE
        text = text if text is not None else StickyItem.DEFAULT_TEXT

        # Flags/States
        self._isHovered = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresParentOpacity)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)

        # Children
        self._createItems(color=color, title=title, text=text)
        self._connectSignals()

        # Geometry
        if rect:
            self.setPos(pos)

        self._updateMinimumSize()

        # Style
        self._topRectBrush = QtGui.QBrush()
        self._topRectBrush.setStyle(QtCore.Qt.SolidPattern)

        self._topRectHoverBrush = QtGui.QBrush()
        self._topRectHoverBrush.setStyle(QtCore.Qt.SolidPattern)

        self._bottomRectBrush = QtGui.QBrush()
        self._bottomRectBrush.setStyle(QtCore.Qt.SolidPattern)

        self._rectPen = QtGui.QPen()
        self._rectPen.setWidth(3)
        self._rectPen.setStyle(QtCore.Qt.SolidLine)

        self._selectRectPen = QtGui.QPen()
        self._selectRectPen.setWidth(3)
        self._selectRectPen.setStyle(QtCore.Qt.SolidLine)

        self.color = color

        # Animation
        self._colorAnim = QT_ANIM.propertyAnimation(self, propertyName="colorProperty", startValue=color, endValue=color, duration=320, play=False,
                                                    interpolationType=QtCore.QEasingCurve.InQuad)

    # --- Public ----------------------------------------------------------------------------

    @property
    def UUID(self):
        return self._UUID

    @property
    def title(self):
        return self._titleBarItem.titleItem.toPlainText()

    @title.setter
    def title(self, title):
        self._titleBarItem.titleItem.setPlainText(title)

    @property
    def text(self):
        return self._textBoxItem.textItem.toPlainText()

    @text.setter
    def text(self, text):
        self._textBoxItem.textItem.setPlainText(text)

    @property
    def rect(self):
        return self._rect

    @property
    def topRect(self):
        return QtCore.QRectF(self.rect.topLeft(), QtCore.QSize(self.rect.width(), StickyItem.TOP_RECT_HEIGHT))

    @property
    def bottomRect(self):
        return QtCore.QRectF(QtCore.QPointF(self.rect.x(), self.rect.y() + StickyItem.TOP_RECT_HEIGHT), self.rect.bottomRight())

    @property
    def color(self):
        return QtGui.QColor(self._titleBarItem.colorPickerItem.color)

    @color.setter
    def color(self, color):
        topRectBrushColor = QtGui.QColor(color)
        topRectBrushColor.setAlpha(90)
        self._topRectBrush.setColor(topRectBrushColor)
        topRectHoverBrush = QtGui.QColor(color)
        topRectHoverBrush.setAlpha(140)
        self._topRectHoverBrush.setColor(topRectHoverBrush)
        bottomRectBrush = QtGui.QColor(color)
        bottomRectBrush.setAlpha(30)
        self._bottomRectBrush.setColor(bottomRectBrush)
        rectPenColor = QtGui.QColor(color).darker(170)
        self._rectPen.setColor(rectPenColor)
        selectedRectPenColor = QtGui.QColor().fromHsv(color.hue(), color.saturation(), 200)
        self._selectRectPen.setColor(selectedRectPenColor)
        self.update()

    # Used to animate the above color property
    colorProperty = QtCore.Property(QtGui.QColor, lambda obj: getattr(obj, 'color'), lambda obj, x: setattr(obj, 'color', x))

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def isTitleEditing(self):
        return self._titleBarItem.titleItem.hasFocus()

    # --- Private ----------------------------------------------------------------------------

    def _createItems(self, color, title, text):
        # Resizer
        self._resizerItem = ResizerItem(QtCore.QRectF(self._rect), parent=self)
        self._resizerItem.minimumSize = QtCore.QSize(StickyItem.MINIMUM_WIDTH, StickyItem.MINIMUM_HEIGHT)

        # TitleBar
        self._titleBarItem = TitleBarItem(title=title, color=color, parent=self)
        self._titleBarItem.layout().setContentsMargins(15, 0, 20, 0)
        self._titleBarItem.setFixedHeight(StickyItem.TOP_RECT_HEIGHT)

        # TextItem
        self._textBoxItem = TextBoxItem(text=text, parent=self)
        self._textBoxItem.setPos(0, StickyItem.TOP_RECT_HEIGHT)
        self._textBoxItem.layout().setContentsMargins(15, 15, 15, 15)
        # Ensure the text conforms to the boundingRect (ie. enable word-wrapping)
        self._textBoxItem.updateGeometry()
        self._textBoxItem.textItem.updateTextWidth()

    def _connectSignals(self):
        # Conform the geometry of this item to the child resizer item
        self._resizerItem.rectChange.connect(self._updateGeometry)

        # Update the minimum size based on the title and text items
        self._titleBarItem.titleItem.document().documentLayout().documentSizeChanged.connect(self._updateMinimumSize)
        self._textBoxItem.textItem.document().documentLayout().documentSizeChanged.connect(self._updateMinimumSize)

        # Emit internal state changes
        self._resizerItem.rectChanged.connect(lambda rect: self.rectChanged.emit(self.mapRectToScene(rect)))
        self._titleBarItem.colorPickerItem.colorPickerPanelItem.colorPicked.connect(self.colorChanged)
        self._titleBarItem.titleItem.document().contentsChanged.connect(lambda: self.titleChanged.emit(self._titleBarItem.titleItem.toPlainText()))
        self._textBoxItem.textItem.document().contentsChanged.connect(lambda: self.textChanged.emit(self._textBoxItem.textItem.toPlainText()))

        # Update the color
        self._titleBarItem.colorPickerItem.colorPickerPanelItem.colorPicked.connect(self._updateColor)

        # The hoverLeaveEvent is sometimes prevented from triggering if the mouse moves directly over a child, therefore we use signals for extra tracking
        self._titleBarItem.titleItem.hoverChanged.connect(self.update)
        self._textBoxItem.textItem.hoverChanged.connect(self.update)
        self._titleBarItem.colorPickerItem.colorPickerPanelItem.hoverChanged.connect(self.update)

    def _updateColor(self, color):
        """Animates the color."""
        self._colorAnim.setStartValue(self.color)
        self._colorAnim.setEndValue(color)
        self._colorAnim.start()

    def _updateMinimumSize(self):
        """Enforces a minimum size based on the contents of the `TitleItem` and `TextItem`.

        Designed as a slot for the `documentSizeChanged` signal for each respective `documentLayout`.
        This signal will be emitted under the following circumstances:

        - The width of the `TitleItem` has grown due to the user changing its contents (ie. minimum width needs update).
        - The width of the `StickyItem` has changed due to resizing and `updateTextWidth` has been invoked for the `TextItem` (ie. minimum height needs update).
        """
        self.prepareGeometryChange()

        # Use the baseclass implementations of `sizeHint` to determine the minimum dimensions for the `TitleItem`
        minimumWidth = max(StickyItem.MINIMUM_WIDTH, QtWidgets.QGraphicsWidget.sizeHint(self._titleBarItem, QtCore.Qt.MinimumSize).width())
        minimumHeight = max(StickyItem.MINIMUM_HEIGHT, QtWidgets.QGraphicsWidget.sizeHint(self._titleBarItem, QtCore.Qt.MinimumSize).height()
                            + self._textBoxItem._textLayoutItem.sizeHint(QtCore.Qt.MinimumSize, QtCore.QSizeF(-1, -1)).height() + 30)

        # Update the minimum size of the `ResizerItem` then conform this geometry in case the minimum has grown
        self._resizerItem.minimumSize = QtCore.QSize(minimumWidth, minimumHeight)
        self._rect.setWidth(self._resizerItem.rect.width())
        self._rect.setHeight(self._resizerItem.rect.height())

        # Force child geometry to conform
        self._titleBarItem.updateGeometry()
        self._textBoxItem.updateGeometry()

        # Adjust the width of the `TextItem` which may affect its height (temporarily disconnect this slot to prevent recursion)
        with QT_CONTEXT.DisconnectSignalFromReceiver(self._textBoxItem.textItem.document().documentLayout().documentSizeChanged, self._updateMinimumSize):
            self._textBoxItem.textItem.updateTextWidth()

        # Recalculate the minimum height based on the new text width and again force child geometry to conform
        minimumHeight = max(StickyItem.MINIMUM_HEIGHT, QtWidgets.QGraphicsWidget.sizeHint(self._titleBarItem, QtCore.Qt.MinimumSize).height()
                            + self._textBoxItem._textLayoutItem.sizeHint(QtCore.Qt.MinimumSize, QtCore.QSizeF(-1, -1)).height() + 30)

        self._resizerItem.minimumSize = QtCore.QSize(minimumWidth, minimumHeight)
        self._rect.setHeight(self._resizerItem.rect.height())

        self._titleBarItem.updateGeometry()
        self._textBoxItem.updateGeometry()

    def _updateGeometry(self, rect):
        """Inherit local geometry offsets.

        Designed as a slot for the `rectChange` signal of the child `ResizerItem`.
        """
        self.prepareGeometryChange()

        # Conform this geometry to the resizer item
        rect = self.mapRectToParent(rect)
        self.setPos(rect.topLeft())
        self._rect.setWidth(rect.width())
        self._rect.setHeight(rect.height())

        # Force child geometry to conform
        self._titleBarItem.updateGeometry()
        self._textBoxItem.updateGeometry()

        # Adjust the width of the text item which may affect its height
        # The `documentSizeChanged` signal will be emitted, allowing us to update to the minimum size
        self._textBoxItem.textItem.updateTextWidth()

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Updates the hover state and schedules a redraw if it has changed due to the mouse moving over the shape."""
        # Can't use `hoverEnterEvent` and `hoverLeaveEvent` in case mouse enters/leaves from the bottom
        wasHovered = self._isHovered
        self._isHovered = True if self.topRect.contains(event.pos()) else False

        if wasHovered != self._isHovered:
            self.update()

    def hoverLeaveEvent(self, event):
        """Updates the hover state and schedules a redraw."""
        self._isHovered = False
        self.update()

    def mousePressEvent(self, event):
        """Ignores mouse pressed that do not occur within the `TitleBarItem` geometry."""
        if not self.topRect.contains(event.pos()):
            event.ignore()
            return

        super(StickyItem, self).mousePressEvent(event)

    def itemChange(self, change, value):
        """Tracks positional changes to ensure the parent remains pinned to the origin."""
        # Even though we are pinning the container node, it is possible the user affects the global pin state when all nodes are deselected
        # Therefore as a precaution we ensure the parent was not responsible for the change in position
        if change == QtWidgets.QGraphicsItem.ItemScenePositionHasChanged:
            if self._parent.pos() != QtCore.QPoint(0, 0):
                self._parent.setPos(0, 0)

        elif change == QtWidgets.QGraphicsItem.ItemSceneHasChanged and value is None:
            self.sceneChanged.emit()

        return QtWidgets.QGraphicsItem.itemChange(self, change, value)

    def type(self):
        return StickyItem.Type

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.topRect)
        return path

    # --- Pure Virtual ----------------------------------------------------------------------------

    def boundingRect(self):
        return QtCore.QRectF(self._rect)

    def paint(self, painter, option, widget):
        rect = self._rect
        topRectHeightVec = QtCore.QPointF(0, StickyItem.TOP_RECT_HEIGHT)
        cornerRect = QtCore.QRectF(0, 0, StickyItem.RADIUS * 2, StickyItem.RADIUS * 2)
        cornerWidthVec = QtCore.QPointF(StickyItem.RADIUS, 0)
        cornerHeightVec = QtCore.QPointF(0, StickyItem.RADIUS)

        # Top rect background
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + cornerWidthVec)
        path.lineTo(rect.topRight() - cornerWidthVec)
        cornerRect.moveTopRight(rect.topRight())
        path.arcTo(cornerRect, 90, -90)
        path.lineTo(rect.topRight() + topRectHeightVec)
        path.lineTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topLeft() + cornerHeightVec)
        cornerRect.moveTopLeft(rect.topLeft())
        path.arcTo(cornerRect, 180, -90)
        isHovered = not self._textBoxItem.textItem.isHovered and not self._titleBarItem.colorPickerItem.colorPickerPanelItem.isHovered and (self._titleBarItem.titleItem.isHovered or self.isHovered)
        painter.setBrush(self._topRectHoverBrush if isHovered or self.isSelected() else self._topRectBrush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)

        # Bottom rect background
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topRight() + topRectHeightVec)
        path.lineTo(rect.bottomRight() - cornerHeightVec)
        cornerRect.moveBottomRight(rect.bottomRight())
        path.arcTo(cornerRect, 0, -90)
        path.lineTo(rect.bottomLeft() + cornerWidthVec)
        cornerRect.moveBottomLeft(rect.bottomLeft())
        path.arcTo(cornerRect, 270, -90)
        path.lineTo(rect.topLeft() + topRectHeightVec)
        painter.setBrush(self._bottomRectBrush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)

        # Splitter
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topRight() + topRectHeightVec)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(self._selectRectPen if self.isSelected() else self._rectPen)
        painter.drawPath(path)

        # Border
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(self._selectRectPen if self.isSelected() else self._rectPen)
        painter.drawRoundedRect(self._rect, StickyItem.RADIUS, StickyItem.RADIUS)


# ----------------------------------------------------------------------------
# --- NodeBox QGraphicsItem ---
# ----------------------------------------------------------------------------

class NodeBoxItem(QtWidgets.QGraphicsObject):
    """A graphics item designed to organise nodes in the Node Editor.

    - The `colorChanged` signal is emitted whenever a new color is selected for the item.
    - The `deleteKeyPressed` signal is emitted whenever the delete key is pressed with this item selected.
    - The `rectChanged` signal is emitted whenever the geometry of this item changes after the mouse is released.
    - The `sceneChanged` signal is emitted whenever the `QGraphicsScene` ownership of this item is changed (ie. the item is transferred to or removed from a scene).
      This signal is designed to allow an item to be reloaded from metadata if an unhandled scene change occurs.
    - The `titleChanged` signal is emitted whenever the title of this item is changed.
    """
    # Signals
    colorChanged = QtCore.Signal(QtGui.QColor)
    deleteKeyPressed = QtCore.Signal()
    rectChanged = QtCore.Signal(QtCore.QRectF)
    sceneChanged = QtCore.Signal()
    titleChanged = QtCore.Signal(str)

    # Types
    Type = QtWidgets.QGraphicsItem.UserType + 500
    COMPATIBLE_TYPES = (Type, StickyItem.Type, UI_NODE_EDITOR.NodeEditorGraphicsItem.NODE)

    # Dimensions
    DEFAULT_WIDTH = 500
    DEFAULT_HEIGHT = 500
    MINIMUM_WIDTH = 300
    MINIMUM_HEIGHT = 200
    RADIUS = 20
    TOP_RECT_HEIGHT = 55

    # Style
    DEFAULT_COLOR = ColorPickerPanelItem.SELECTION_COLORS[15]

    # Contents
    DEFAULT_TITLE = "Node Box"

    def __init__(self, UUID=None, rect=None, color=None, title=None, parent=None):
        """Initialise the `NodeBoxItem`.

        Args:
            UUID (`uuid.UUID`, optional): A unique identifier used to load this item from metadata.
                Defaults to `None` - if this item is not being loaded, a new identifier will be assigned.
            rect (`PySide2.QtCore.QRectF`, optional): The shape used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default shape will be assigned.
            color (`PySide2.QtGui.QColor`, optional): The color used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default color will be assigned.
            title (`basestring`, optional): The title used to load this item from the metadata.
                Defaults to `None` - if this item is not being loaded, a default title will be assigned.
            parent (`PySide2.QtWidgets.QGraphicsItem`, optional): The parent item. Defaults to `None`.
        """
        super(NodeBoxItem, self).__init__(parent)

        # If we do not keep a reference to the parent, calling QGraphicsItem.parentItem() leads to odd behaviour (this item is deleted)
        self._parent = parent

        # Given geometry is assumed to be in scene coordinates and the parent positioned at the origin
        # Cached geometry must be in local coordinates
        if rect:
            pos = rect.topLeft()
            rect.moveTo(0, 0)

        # Data
        self._UUID = UUID if UUID is not None else uuid.uuid4()
        self._rect = QtCore.QRectF(rect) if rect is not None else QtCore.QRectF(0, 0, NodeBoxItem.DEFAULT_WIDTH, NodeBoxItem.DEFAULT_HEIGHT)
        color = color if color is not None else NodeBoxItem.DEFAULT_COLOR
        title = title if title is not None else NodeBoxItem.DEFAULT_TITLE

        # Flags/States
        self._isHovered = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresParentOpacity)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)

        # Events
        self._itemRegistry = {}

        # Children
        self._createItems(color=color, title=title)
        self._connectSignals()

        # Geometry
        if rect:
            self.setPos(pos)

        self._updateMinimumSize()

        # Style
        self._topRectBrush = QtGui.QBrush()
        self._topRectBrush.setStyle(QtCore.Qt.SolidPattern)

        self._topRectHoverBrush = QtGui.QBrush()
        self._topRectHoverBrush.setStyle(QtCore.Qt.SolidPattern)

        self._bottomRectBrush = QtGui.QBrush()
        self._bottomRectBrush.setStyle(QtCore.Qt.SolidPattern)

        self._rectPen = QtGui.QPen()
        self._rectPen.setWidth(3)
        self._rectPen.setStyle(QtCore.Qt.SolidLine)

        self._selectRectPen = QtGui.QPen()
        self._selectRectPen.setWidth(3)
        self._selectRectPen.setStyle(QtCore.Qt.SolidLine)

        self.color = color

        # Animation
        self._colorAnim = QT_ANIM.propertyAnimation(self, propertyName="colorProperty", startValue=color, endValue=color, duration=320, play=False,
                                                    interpolationType=QtCore.QEasingCurve.InQuad)

    # --- Public ----------------------------------------------------------------------------

    @property
    def UUID(self):
        return self._UUID

    @property
    def title(self):
        return self._titleBarItem.titleItem.toPlainText()

    @title.setter
    def title(self, title):
        self._titleBarItem.titleItem.setPlainText(title)

    @property
    def rect(self):
        return self._rect

    @property
    def topRect(self):
        return QtCore.QRectF(self.rect.topLeft(), QtCore.QSize(self.rect.width(), NodeBoxItem.TOP_RECT_HEIGHT))

    @property
    def bottomRect(self):
        return QtCore.QRectF(QtCore.QPointF(self.rect.x(), self.rect.y() + NodeBoxItem.TOP_RECT_HEIGHT), self.rect.bottomRight())

    @property
    def color(self):
        return QtGui.QColor(self._titleBarItem.colorPickerItem.color)

    @color.setter
    def color(self, color):
        topRectBrushColor = QtGui.QColor(color)
        topRectBrushColor.setAlpha(90)
        self._topRectBrush.setColor(topRectBrushColor)
        topRectHoverBrush = QtGui.QColor(color)
        topRectHoverBrush.setAlpha(140)
        self._topRectHoverBrush.setColor(topRectHoverBrush)
        bottomRectBrush = QtGui.QColor(color)
        bottomRectBrush.setAlpha(30)
        self._bottomRectBrush.setColor(bottomRectBrush)
        rectPenColor = QtGui.QColor(color).darker(170)
        self._rectPen.setColor(rectPenColor)
        selectedRectPenColor = QtGui.QColor().fromHsv(color.hue(), color.saturation(), 200)
        self._selectRectPen.setColor(selectedRectPenColor)
        self.update()

    # Used to animate the above color property
    colorProperty = QtCore.Property(QtGui.QColor, lambda obj: getattr(obj, 'color'), lambda obj, x: setattr(obj, 'color', x))

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def isTitleEditing(self):
        return self._titleBarItem.titleItem.hasFocus()

    def getItemRegistry(self):
        """Returns a reference to the internal registry which was created by the last call to `buildItemRegistry`."""
        return self._itemRegistry

    def buildItemRegistry(self):
        """Builds an internal registry of items whose geometry is fully contained by this item.

        The registry can contain node items, `NodeBoxItems` and `StickyItems`.
        It maps each item to an offset which is used to restore the relative positions when this item is moved.
        The use of a registry ensures that only the nodes initially contained by the `NodeBoxItem` will be moved during the drag event.
        """
        sceneRect = self.mapRectToScene(self.bottomRect)
        items = [item for item in self.scene().items() if item.type() in NodeBoxItem.COMPATIBLE_TYPES and item is not self._parent]

        for item in items:
            if sceneRect.contains(item.sceneBoundingRect()):
                self._itemRegistry[item] = item.scenePos() - self.scenePos()

    def clearItemRegistry(self):
        """Clears the internal registry of node items, `NodeBoxItems` and `StickyItems`."""
        self._itemRegistry = {}

    # --- Private ----------------------------------------------------------------------------

    def _createItems(self, color, title):
        # Resizer
        self._resizerItem = ResizerItem(QtCore.QRectF(self._rect), parent=self)
        self._resizerItem.minimumSize = QtCore.QSize(NodeBoxItem.MINIMUM_WIDTH, NodeBoxItem.MINIMUM_HEIGHT)

        # TitleBar
        self._titleBarItem = TitleBarItem(title=title, color=color, parent=self)
        self._titleBarItem.layout().setContentsMargins(20, 0, 20, 0)
        self._titleBarItem.setFixedHeight(NodeBoxItem.TOP_RECT_HEIGHT)

    def _connectSignals(self):
        # Conform the geometry of this item to the child resizer item
        self._resizerItem.rectChange.connect(self._updateGeometry)

        # Update the minimum size based on the title item
        self._titleBarItem.titleItem.document().documentLayout().documentSizeChanged.connect(self._updateMinimumSize)

        # Emit internal state changes
        self._resizerItem.rectChanged.connect(lambda rect: self.rectChanged.emit(self.mapRectToScene(rect)))
        self._titleBarItem.colorPickerItem.colorPickerPanelItem.colorPicked.connect(lambda color: self.colorChanged.emit(color))
        self._titleBarItem.titleItem.document().contentsChanged.connect(lambda: self.titleChanged.emit(self._titleBarItem.titleItem.toPlainText()))

        # Update the color
        self._titleBarItem.colorPickerItem.colorPickerPanelItem.colorPicked.connect(self._updateColor)

        # The hoverLeaveEvent is sometimes prevented from triggering if the mouse moves directly over a child, therefore we use signals for extra tracking
        self._titleBarItem.titleItem.hoverChanged.connect(self.update)

    def _updateColor(self, color):
        self._colorAnim.setStartValue(self.color)
        self._colorAnim.setEndValue(color)
        self._colorAnim.start()

    def _updateMinimumSize(self):
        """Enforces a minimum size based on the contents of the `TitleItem`.

        Designed as a slot for the `documentSizeChanged` signal of the respective `documentLayout`.
        This signal will be emitted if the width of the `TitleItem` has grown due to the user changing its contents.
        """
        # Use the baseclass implementations of `sizeHint` to determine the minimum dimensions for the `TitleItem`
        minimumWidth = max(NodeBoxItem.MINIMUM_WIDTH, QtWidgets.QGraphicsWidget.sizeHint(self._titleBarItem, QtCore.Qt.MinimumSize).width())
        minimumHeight = max(NodeBoxItem.MINIMUM_HEIGHT, QtWidgets.QGraphicsWidget.sizeHint(self._titleBarItem, QtCore.Qt.MinimumSize).height())

        # Update the minimum size of the `ResizerItem` then conform this geometry in case the minimum has grown
        self._resizerItem.minimumSize = QtCore.QSize(minimumWidth, minimumHeight)
        self._updateGeometry(self._resizerItem.rect)

    def _updateGeometry(self, rect):
        """Inherit local geometry offsets.

        Designed as a slot for the `rectChange` signal of the child `ResizerItem`.
        """
        self.prepareGeometryChange()

        # Conform this geometry to the resizer item
        rect = self.mapRectToParent(rect)
        self.setPos(rect.topLeft())
        self._rect.setWidth(rect.width())
        self._rect.setHeight(rect.height())

        # Force child geometry to conform
        self._titleBarItem.updateGeometry()

    # --- Virtual ----------------------------------------------------------------------------

    def hoverMoveEvent(self, event):
        """Updates the hover state and schedules a redraw if it has changed due to the mouse moving over the shape."""
        # Can't use `hoverEnterEvent` and `hoverLeaveEvent` in case mouse enters/leaves from the bottom
        wasHovered = self._isHovered
        self._isHovered = True if self.topRect.contains(event.pos()) else False

        if wasHovered != self._isHovered:
            self.update()

    def hoverLeaveEvent(self, event):
        """Updates the hover state and schedules a redraw."""
        self._isHovered = False
        self.update()

    def mousePressEvent(self, event):
        """Ignores mouse pressed that do not occur within the `TitleBarItem` geometry."""
        if not self.topRect.contains(event.pos()):
            event.ignore()
            return

        super(NodeBoxItem, self).mousePressEvent(event)

    def itemChange(self, change, value):
        """Tracks position, selection and scene changes.

        - Positional changes are tracked to ensure the parent remains pinned to the origin.
        - Selectional changes are tracked to build or clear the internal item registry.
        - Scene changes are tracked so that the `sceneChanged` signal can be emitted.
        """
        # This item is responsible for the initial build of its item registry
        # If the item remains selected, subsequent mouse presses will be handled by the `LayoutItemSceneFilter`
        if change == QtWidgets.QGraphicsItem.ItemSelectedHasChanged:
            if value:
                self.buildItemRegistry()
            else:
                self.clearItemRegistry()

        # Even though we are pinning the container node, it is possible the user affects the global pin state when all nodes are deselected
        # Therefore as a precaution we ensure the parent was not responsible for the change in position
        elif change == QtWidgets.QGraphicsItem.ItemScenePositionHasChanged:
            if self._parent.pos() != QtCore.QPoint(0, 0):
                self._parent.setPos(0, 0)

        elif change == QtWidgets.QGraphicsItem.ItemSceneHasChanged and value is None:
            self.sceneChanged.emit()

        elif change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            for item, offset in self._itemRegistry.iteritems():
                parentItem = item.parentItem()
                scenePos = self.scenePos() + offset

                if parentItem is not None:
                    localPos = parentItem.mapFromScene(scenePos)
                    item.setPos(localPos)
                else:
                    item.setPos(scenePos)

        return QtWidgets.QGraphicsItem.itemChange(self, change, value)

    def type(self):
        return NodeBoxItem.Type

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.topRect)
        return path

    # --- Pure Virtual ---

    def boundingRect(self):
        return QtCore.QRectF(self._rect)

    def paint(self, painter, option, widget):
        rect = self._rect
        topRectHeightVec = QtCore.QPointF(0, NodeBoxItem.TOP_RECT_HEIGHT)
        cornerRect = QtCore.QRectF(0, 0, NodeBoxItem.RADIUS * 2, NodeBoxItem.RADIUS * 2)
        cornerWidthVec = QtCore.QPointF(NodeBoxItem.RADIUS, 0)
        cornerHeightVec = QtCore.QPointF(0, NodeBoxItem.RADIUS)

        # Top rect background
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + cornerWidthVec)
        path.lineTo(rect.topRight() - cornerWidthVec)
        cornerRect.moveTopRight(rect.topRight())
        path.arcTo(cornerRect, 90, -90)
        path.lineTo(rect.topRight() + topRectHeightVec)
        path.lineTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topLeft() + cornerHeightVec)
        cornerRect.moveTopLeft(rect.topLeft())
        path.arcTo(cornerRect, 180, -90)
        isHovered = self._titleBarItem.titleItem.isHovered or self.isHovered
        painter.setBrush(self._topRectHoverBrush if isHovered or self.isSelected() else self._topRectBrush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)

        # Bottom rect background
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topRight() + topRectHeightVec)
        path.lineTo(rect.bottomRight() - cornerHeightVec)
        cornerRect.moveBottomRight(rect.bottomRight())
        path.arcTo(cornerRect, 0, -90)
        path.lineTo(rect.bottomLeft() + cornerWidthVec)
        cornerRect.moveBottomLeft(rect.bottomLeft())
        path.arcTo(cornerRect, 270, -90)
        path.lineTo(rect.topLeft() + topRectHeightVec)
        painter.setBrush(self._bottomRectBrush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)

        # Splitter
        path = QtGui.QPainterPath()
        path.moveTo(rect.topLeft() + topRectHeightVec)
        path.lineTo(rect.topRight() + topRectHeightVec)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(self._selectRectPen if self.isSelected() else self._rectPen)
        painter.drawPath(path)

        # Border
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(self._selectRectPen if self.isSelected() else self._rectPen)
        painter.drawRoundedRect(self._rect, NodeBoxItem.RADIUS, NodeBoxItem.RADIUS)


# ----------------------------------------------------------------------------
# --- Event Filters ---
# ----------------------------------------------------------------------------

class LayoutItemSceneFilter(QtCore.QObject):
    """An event filter to be installed on the current Node Editor `QGraphicsScene` to manage scene events relating to layout items.

    - Emits the `deleteKeyPressed` signal for any selected layout item when delete/backspace is pressed.
    - Emits the `rectChanged` signal for any selected or nested layout item when the mouse is released.
    - Manages the internal item registry for each selected `NodeBoxItem` based on mouse press and release events.
    - Resolves the zValue for each layout item upon releasing the mouse, to ensure nested items remain on top.
    """

    DEFAULT_ZVALUE = 10

    def __init__(self, parent):
        super(LayoutItemSceneFilter, self).__init__(parent)

        self._parent = parent
        self._resolveZValues()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyRelease:
            if event.key() == QtCore.Qt.Key_Backspace or event.key() == QtCore.Qt.Key_Delete:
                focusItem = self._parent.focusItem()

                # Ensure the scene's current focus item is not an attribute search field (ie. `QGraphicsProxyWidget`)
                if isinstance(focusItem, QtWidgets.QGraphicsProxyWidget):
                    return QtCore.QObject.eventFilter(self, watched, event)

                # Ensure the scene's current focus item is not one of our custom text items
                if isinstance(focusItem, QtWidgets.QGraphicsTextItem):
                    return QtCore.QObject.eventFilter(self, watched, event)

                # Ensure the user is not editing the name of a Maya node
                # When the user clicks to edit the name of a node, Maya appears to create a widget that is not part of the `QGraphicsScene` but is parented to the viewport
                # This causes the `QGraphicsScene` to loose focus however the key event will still be propagated, therefore we must check the scene has focus
                if not self._parent.hasFocus():
                    return QtCore.QObject.eventFilter(self, watched, event)

                # It is now safe to delete any of our custom items
                selectedItems = [item for item in self._parent.items() if item.isSelected() and (item.type() == NodeBoxItem.Type or item.type() == StickyItem.Type)]
                for selectedItem in selectedItems:
                    selectedItem.deleteKeyPressed.emit()

        elif event.type() == QtCore.QEvent.GraphicsSceneMousePress:
            # Build the registry of any `NodeBoxItem` which is already selected
            # If a NodeBoxItem is selected as the result of the current event being processed, it is that item's own responsibility to build its registry
            nodeBoxItems = [item for item in self._parent.selectedItems() if item.type() == NodeBoxItem.Type]
            for nodeBoxItem in nodeBoxItems:
                nodeBoxItem.buildItemRegistry()

        elif event.type() == QtCore.QEvent.GraphicsSceneMouseRelease:
            # Emit a signal for each of the selected layout items and any layout item nested within a `NodeBoxItem`
            selectedLayoutItems = [item for item in self._parent.selectedItems() if item.type() == NodeBoxItem.Type or item.type() == StickyItem.Type]

            for selectedLayoutItem in selectedLayoutItems:
                selectedLayoutItem.rectChanged.emit(selectedLayoutItem.mapRectToScene(selectedLayoutItem.rect))

                if selectedLayoutItem.type() == NodeBoxItem.Type:
                    for nestedItem in selectedLayoutItem.getItemRegistry():
                        if nestedItem.type() == NodeBoxItem.Type or nestedItem.type() == StickyItem.Type:
                            nestedItem.rectChanged.emit(nestedItem.mapRectToScene(nestedItem.rect))

                    # The registry should only exist temporarily as it is not safe to hold onto items which may be removed from the QGraphicsScene
                    # Therefore clear the registry for any NodeBoxItem which has remained selected after the GraphicsSceneMousePress event
                    # If a NodeBoxItem is deselected as the result of the GraphicsSceneMousePress event being processed, it is that item's own responsibility to clear its registry
                    selectedLayoutItem.clearItemRegistry()

            self._resolveZValues()

        return QtCore.QObject.eventFilter(self, watched, event)

    def _resolveZValues(self):
        layoutItems = [item for item in self._parent.items() if item.type() == NodeBoxItem.Type or item.type() == StickyItem.Type]
        layoutItemGeometry = {layoutItem: layoutItem.sceneBoundingRect() for layoutItem in layoutItems}

        for innerLayoutItem, innerLayoutItemSceneRect in layoutItemGeometry.iteritems():
            zValue = LayoutItemSceneFilter.DEFAULT_ZVALUE

            for outerLayoutItem, outerLayoutItemSceneRect in layoutItemGeometry.iteritems():
                if outerLayoutItem != innerLayoutItem:
                    if outerLayoutItemSceneRect.contains(innerLayoutItemSceneRect):
                        zValue += 1

            innerLayoutItem.setZValue(zValue)
