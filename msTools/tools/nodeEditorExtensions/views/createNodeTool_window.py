import os

from msTools.vendor.Qt import QtCore, QtGui, QtWidgets

from msTools.coreUI.qt import animation_utils as QT_ANIM
from msTools.coreUI.qt import shape_utils as QT_SHAPE


class CreateNodeToolWindow(QtWidgets.QWidget):

    nodeTypeSelected = QtCore.Signal(str)
    searchTextChanged = QtCore.Signal(str)

    MINIMUM_WIDTH = 420
    BORDER_WIDTH = 3
    SCROLLBAR_WIDTH = 8
    SEARCH_HEIGHT = 40
    SEARCH_LEFT_MARGIN = 25
    SEARCH_RIGHT_MARGIN = 28
    SEARCH_PLACEHOLDER_TEXT = "Create Node..."
    MAXIMUM_LISTVIEW_ITEMS = 8
    NAME = "MRS_createNodeToolWindow"

    _STYLESHEET_RESOURCE = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\css\\createNodeTool_window.css"))

    def __init__(self, model, parent=None):
        super(CreateNodeToolWindow, self).__init__(parent)

        self._model = model

        self.setObjectName(CreateNodeToolWindow.NAME)

        # --- Window (display, close behaviour, modality) ---
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool)

        # --- Style ---
        with open(CreateNodeToolWindow._STYLESHEET_RESOURCE, 'r') as f:
            self.setStyleSheet(f.read())

        # --- Anim ---
        self._heightAnim = QT_ANIM.heightAnimation(self, startHeight=0, endHeight=0, duration=200, interpolationType=QtCore.QEasingCurve.OutQuad, finishCallback=None, play=False)

        # --- Widgets, signals, events ---
        self._createWidgets()
        self._connectInternalSignals()
        self._installEventFilters()

        # --- Size ---
        self.resize(CreateNodeToolWindow.MINIMUM_WIDTH, CreateNodeToolWindow.SEARCH_HEIGHT + CreateNodeToolWindow.BORDER_WIDTH * 2)

    def _createWidgets(self):
        # --- Main Layout ---
        self._mainLayout = QtWidgets.QVBoxLayout()
        self._mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._mainLayout)

        # --- Frame ---
        self._backgroundFrame = BackgroundFrame()
        self._backgroundFrameLayout = QtWidgets.QVBoxLayout()
        self._backgroundFrameLayout.setAlignment(QtCore.Qt.AlignTop)
        self._backgroundFrameLayout.setContentsMargins(CreateNodeToolWindow.BORDER_WIDTH, CreateNodeToolWindow.BORDER_WIDTH, CreateNodeToolWindow.BORDER_WIDTH, CreateNodeToolWindow.BORDER_WIDTH)
        self._backgroundFrameLayout.setSpacing(0)
        self._backgroundFrame.setLayout(self._backgroundFrameLayout)
        self._mainLayout.addWidget(self._backgroundFrame)

        # --- Containers ---
        self._searchContainer = QtWidgets.QWidget()
        self._searchLayout = QtWidgets.QHBoxLayout()
        self._searchLayout.setContentsMargins(CreateNodeToolWindow.SEARCH_LEFT_MARGIN, 0, CreateNodeToolWindow.SEARCH_RIGHT_MARGIN, 0)
        self._searchContainer.setLayout(self._searchLayout)
        self._backgroundFrameLayout.addWidget(self._searchContainer)

        self._listViewContainer = QtWidgets.QWidget()
        self._listViewLayout = QtWidgets.QStackedLayout()
        self._listViewLayout.setContentsMargins(0, 0, 0, 0)
        self._listViewLayout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        self._listViewContainer.setLayout(self._listViewLayout)
        self._backgroundFrameLayout.addWidget(self._listViewContainer)

        self._scrollBarContainer = ScrollBarContainer()
        self._scrollBarLayout = QtWidgets.QHBoxLayout()
        self._scrollBarLayout.setAlignment(QtCore.Qt.AlignRight)
        self._scrollBarLayout.setContentsMargins(0, 0, 0, 0)
        self._scrollBarContainer.setLayout(self._scrollBarLayout)
        self._listViewLayout.addWidget(self._scrollBarContainer)

        # --- Container children ---
        self._searchLineEdit = LineEdit()
        self._searchLineEdit.setPlaceholderText(CreateNodeToolWindow.SEARCH_PLACEHOLDER_TEXT)
        self._searchLineEdit.setAlignment(QtCore.Qt.AlignLeft)
        self._searchLineEdit.setFixedHeight(CreateNodeToolWindow.SEARCH_HEIGHT)
        self._searchLineEdit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._searchLayout.addWidget(self._searchLineEdit)

        self._listView = ListView()
        self._listView.setModel(self._model)
        self._listView.setItemDelegate(NodeTypeItemDelegate(self._listView))
        self._listView.setMouseTracking(True)
        self._listView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self._listView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._listView.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._listViewLayout.addWidget(self._listView)

        # We layout the scrollbar within a QStackedLayout so that there is no gutter
        self._scrollBar = ScrollBar(self._listView)
        self._scrollBar.setFixedWidth(CreateNodeToolWindow.SCROLLBAR_WIDTH)
        self._scrollBar.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self._listView.setVerticalScrollBar(self._scrollBar)
        self._listView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self._scrollBarLayout.addWidget(self._scrollBar)

    def _connectInternalSignals(self):
        """Connect implementation independent signals (ie. those which are known to the view)."""
        # --- View -> View ---
        self._searchLineEdit.textChanged.connect(self.searchTextChanged)
        self._searchLineEdit.textChanged.connect(lambda text: self._syncListViewSelectionToLineEdit())
        self._searchLineEdit.textChanged.connect(lambda text: self._adjustWidth())
        self._listView.selectionModel().currentChanged.connect(
            lambda currentIndex, previousIndex: self._searchLineEdit.setSuggestionText(currentIndex.data(role=QtCore.Qt.DisplayRole)))

        # --- Model -> View ---
        self._model.rowsInserted.connect(lambda parent, firstRow, lastRow: self._adjustHeight(firstRow, lastRow))
        self._model.rowsInserted.connect(lambda parent, firstRow, lastRow: self._scrollBar.setDocumentLength(self._model.rowCount()))
        self._model.rowsRemoved.connect(lambda parent, firstRow, lastRow: self._adjustHeight(firstRow, lastRow))
        self._model.rowsRemoved.connect(lambda parent, firstRow, lastRow: self._scrollBar.setDocumentLength(self._model.rowCount()))

    def _installEventFilters(self):
        self._searchLineEdit.installEventFilter(self)
        self._listView.viewport().installEventFilter(self)

    def _adjustWidth(self):
        # The cursor rectangle is horizontally centered at the end of the text (around 5px space is required for half the rectangle)
        cursorRectOffset = self._searchLineEdit.cursorRect().width() / 2.0
        textWidth = QtGui.QFontMetrics(self._searchLineEdit.font()).width(self._searchLineEdit.text())
        searchWidth = textWidth + cursorRectOffset
        contentsWidth = searchWidth + CreateNodeToolWindow.SEARCH_LEFT_MARGIN + CreateNodeToolWindow.SEARCH_RIGHT_MARGIN + CreateNodeToolWindow.BORDER_WIDTH * 2
        width = max(CreateNodeToolWindow.MINIMUM_WIDTH, contentsWidth)
        self.setFixedWidth(width)

    def _adjustHeight(self, firstRow, lastRow):
        # Optimising this method helps performance (it is called for every model insertion/removal, not just visible items)
        if firstRow >= CreateNodeToolWindow.MAXIMUM_LISTVIEW_ITEMS and lastRow >= CreateNodeToolWindow.MAXIMUM_LISTVIEW_ITEMS:
            return

        itemCount = min(CreateNodeToolWindow.MAXIMUM_LISTVIEW_ITEMS, self._model.rowCount())
        height = CreateNodeToolWindow.SEARCH_HEIGHT + NodeTypeItemDelegate.HEIGHT * itemCount + CreateNodeToolWindow.BORDER_WIDTH * 2

        self._listView.setVisible(itemCount > 0)
        self._scrollBar.setVisible(self._model.rowCount() > CreateNodeToolWindow.MAXIMUM_LISTVIEW_ITEMS)

        if self._heightAnim.state() == QtCore.QAbstractAnimation.Running:
            if self._heightAnim.endValue().height() == height:
                return
        elif self.size().height() == height:
            return

        self._heightAnim.setStartValue(QtCore.QSize(self.width(), self.size().height()))
        self._heightAnim.setEndValue(QtCore.QSize(self.width(), height))
        self._heightAnim.setCurrentTime(0)
        self._heightAnim.start()

    def _syncListViewSelectionToLineEdit(self):
        if self._searchLineEdit.hasFocus() and self._model.rowCount():
            self._listView.setCurrentIndex(self._model.index(0, 0))
        else:
            self._listView.clearSelection()

    def _offsetListViewSelection(self, rowOffset):
        currentRow = self._listView.currentIndex().row()
        nextIndex = self._model.index(currentRow + rowOffset, 0)

        if nextIndex.isValid():
            self._listView.setCurrentIndex(nextIndex)

    def show(self):
        # Show transparent
        self.setWindowOpacity(0)
        super(CreateNodeToolWindow, self).show()

        # Give keyboard input focus to this window and make opaque
        self.activateWindow()
        QT_ANIM.opacityAnimation(self, startValue=0.0, endValue=1.0, duration=120)
        QT_ANIM.verticalSlideAnimation(self, startOffset=30, endOffset=0, duration=200)

    def close(self):
        QT_ANIM.opacityAnimation(self, startValue=1.0, endValue=0.0, duration=160)
        QT_ANIM.verticalSlideAnimation(self, startOffset=0, endOffset=50, duration=160, finishCallback=super(CreateNodeToolWindow, self).close)

    def event(self, event):
        if event.type() == QtCore.QEvent.WindowDeactivate:
            self.close()
            return True

        return super(CreateNodeToolWindow, self).event(event)

    def eventFilter(self, obj, event):
        if obj == self._searchLineEdit:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Down:
                    self._offsetListViewSelection(1)
                    return True
                elif event.key() == QtCore.Qt.Key_Up:
                    self._offsetListViewSelection(-1)
                    return True
                elif event.key() == QtCore.Qt.Key_Right:
                    if self._searchLineEdit.suggestionText() and self._searchLineEdit.cursorPosition() == len(self._searchLineEdit.text()):
                        self._searchLineEdit.acceptSuggestionText()
                        return True
                elif event.key() == QtCore.Qt.Key_Enter or event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Space:
                    currentIndex = self._listView.currentIndex()

                    if currentIndex.isValid():
                        self.nodeTypeSelected.emit(self._listView.currentIndex().data(role=QtCore.Qt.DisplayRole))
                        return True
                elif event.key() == QtCore.Qt.Key_Escape:
                    # Alternatively we could inherit from `QDialog` which would call `QDialog.reject` upon pressing escape
                    self.close()
                    return True
        elif obj == self._listView.viewport():
            # The default `QListView.itemPressed` does not emit when the user drags the selected cursor across items
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton:
                    self.nodeTypeSelected.emit(self._listView.currentIndex().data(role=QtCore.Qt.DisplayRole))
                    return True

        return super(CreateNodeToolWindow, self).eventFilter(obj, event)


class BackgroundFrame(QtWidgets.QFrame):

    BORDER_WIDTH = CreateNodeToolWindow.BORDER_WIDTH
    BORDER_COLOR = (17, 17, 17, 255)
    BACKGROUND_COLOR = (30, 30, 30, 255)
    ROUNDNESS = 20

    assert ROUNDNESS <= CreateNodeToolWindow.SEARCH_HEIGHT / 2.0

    def __init__(self, parent=None):
        super(BackgroundFrame, self).__init__(parent=parent)

        self._pen = QtGui.QPen(QtGui.QColor(*BackgroundFrame.BORDER_COLOR), BackgroundFrame.BORDER_WIDTH)
        self._brush = QtGui.QBrush(QtGui.QColor(*BackgroundFrame.BACKGROUND_COLOR))

    def paintEvent(self, event):
        super(BackgroundFrame, self).paintEvent(event)

        # This event is also triggered by child widget regions that require repainting (ie. don't use `event.rect`)
        rect = QT_SHAPE.getDrawableRect(self.geometry(), BackgroundFrame.BORDER_WIDTH)
        rectPath = QT_SHAPE.getRoundedRectPath(rect, BackgroundFrame.ROUNDNESS, roundTopLeft=True, roundTopRight=True, roundBottomRight=True, roundBottomLeft=True)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        painter.drawPath(rectPath)


class LineEdit(QtWidgets.QLineEdit):
    """A QLineEdit which emits custom signals for certain keypress events of interest"""

    PLACEHOLDER_TEXT_COLOR = (255, 255, 255, 170)
    SUGGESTION_TEXT_COLOR = (255, 255, 255, 110)

    def __init__(self, parent=None):
        super(LineEdit, self).__init__(parent)

        self._placeholderText = ""
        self._suggestionText = ""

        self._placeholderTextColor = QtGui.QColor(*LineEdit.PLACEHOLDER_TEXT_COLOR)
        self._suggestionTextColor = QtGui.QColor(*LineEdit.SUGGESTION_TEXT_COLOR)

    def suggestionText(self):
        return self._suggestionText

    def setSuggestionText(self, suggestionText):
        self._suggestionText = suggestionText
        self.update()

    def acceptSuggestionText(self):
        self.setText(self._suggestionText)

    def setPlaceholderText(self, placeholderText):
        self._placeholderText = placeholderText
        self.update()

    def paintEvent(self, event):
        super(LineEdit, self).paintEvent(event)

        if not self.text() and not self.placeholderText() and self._placeholderText:
            # Start drawing from the horizontal center of the cursorRect
            cursorRect = self.cursorRect()
            fontHeight = QtGui.QFontMetrics(self.font()).height()

            placeholderTopLeftPos = QtCore.QPointF(cursorRect.left() + cursorRect.width() / 2.0, cursorRect.top())
            placeholderBottomRightPos = QtCore.QPointF(self.width(), cursorRect.top() + fontHeight)
            placeholderRect = QtCore.QRectF(placeholderTopLeftPos, placeholderBottomRightPos)

            placeholderPainter = QtGui.QPainter(self)
            placeholderPainter.setFont(self.font())
            placeholderPainter.setPen(self._placeholderTextColor)
            placeholderPainter.drawText(placeholderRect, self._placeholderText)
        else:
            if not self._suggestionText:
                return

            if not self.hasFocus():
                return

            if self.cursorPosition() < len(self.text()):
                return

            if not self._suggestionText.startswith(self.text()) or len(self._suggestionText) == len(self.text()):
                return

            # The horizontal center of the cursorRect is position at the end of text
            # Alternatively we could use QTextLayout: https://stackoverflow.com/a/50425331
            cursorRect = self.cursorRect()
            fontMetrics = QtGui.QFontMetrics(self.font())
            fontHeight = fontMetrics.height()
            suggestionText = self._suggestionText[len(self.text()):]

            # The text width is not always accurate, usually if a lower case letter is next to an upper case letter, there will be an offset
            # The offset can be determined by comparing the actual letter width with the text widths
            currentTextWidth = fontMetrics.width(self.text())
            nextTextWidth = fontMetrics.width(self._suggestionText[:len(self.text()) + 1])
            nextLetterWidth = fontMetrics.width(self._suggestionText[len(self.text())])
            offset = nextLetterWidth - (nextTextWidth - currentTextWidth)

            suggestionTopLeftPos = QtCore.QPointF(cursorRect.left() + cursorRect.width() / 2.0 - offset, cursorRect.top())
            suggestionBottomRightPos = QtCore.QPointF(self.width(), cursorRect.top() + fontHeight)
            suggestionRect = QtCore.QRectF(suggestionTopLeftPos, suggestionBottomRightPos)

            suggestionPainter = QtGui.QPainter(self)
            suggestionPainter.setFont(self.font())
            suggestionPainter.setPen(self._suggestionTextColor)
            suggestionPainter.drawText(suggestionRect, suggestionText)


class NodeTypeItemDelegate(QtWidgets.QAbstractItemDelegate):

    HEIGHT = 30
    SPACING = 0
    LEFT_MARGIN = 25
    RIGHT_MARGIN = 20
    ICON_MARGIN = 2
    MINIMUM_TEXT_WIDTH = 250

    TOP_BORDER_COLOR = (20, 20, 20, 250)
    TOP_BORDER_WIDTH = 1

    SELECTION_BACKGROUND_COLOR = (46, 70, 100, 255)
    HOVER_BACKGROUND_COLOR = (30, 30, 30, 255)

    def __init__(self, parent=None):
        super(NodeTypeItemDelegate, self).__init__(parent=parent)

        self._topBorderPen = QtGui.QPen(QtGui.QColor(*NodeTypeItemDelegate.TOP_BORDER_COLOR), NodeTypeItemDelegate.TOP_BORDER_WIDTH)
        self._selectionBackgroundBrush = QtGui.QBrush(QtGui.QColor(*NodeTypeItemDelegate.SELECTION_BACKGROUND_COLOR))
        self._hoverBackgroundBrush = QtGui.QBrush(QtGui.QColor(*NodeTypeItemDelegate.HOVER_BACKGROUND_COLOR))

    def paint(self, painter, option, index):
        # --- Data ---
        text = index.data(QtCore.Qt.DisplayRole)
        pixmap = index.data(QtCore.Qt.DecorationRole)
        font = index.data(QtCore.Qt.FontRole)
        textPen = index.data(QtCore.Qt.ForegroundRole)
        # isLastVisibleItem = option.widget.indexAt(option.widget.rect().bottomRight()) == index or not index.sibling(index.row() + 1, 0).isValid()

        # --- Static dimensions ---
        leftMargin = NodeTypeItemDelegate.LEFT_MARGIN
        rightMargin = NodeTypeItemDelegate.RIGHT_MARGIN
        spacing = NodeTypeItemDelegate.SPACING
        iconWidth = NodeTypeItemDelegate.HEIGHT

        # --- Dynamic dimensions ---
        width = option.rect.width()
        availableTextWidth = width - leftMargin - rightMargin - spacing - iconWidth
        textWidth = max(NodeTypeItemDelegate.MINIMUM_TEXT_WIDTH, availableTextWidth)
        fontHeight = QtGui.QFontMetrics(font).height()
        verticalTextMargin = (option.rect.height() - fontHeight) / 2.0
        topLeftPos = option.rect.topLeft()
        topRightPos = topLeftPos + QtCore.QPoint(width, 0)

        # --- Painter ---
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setFont(font)
        painter.setPen(textPen)

        # --- Background ---
        # Determine the actual hover state by checking if the `QListView` is itself hovered (Qt 5.6 bug prevents `QStyle.State_MouseOver` update when the mouse leaves)
        if option.state & QtWidgets.QStyle.State_Selected or (option.state & QtWidgets.QStyle.State_MouseOver and option.widget.isHovered):
            brush = self._selectionBackgroundBrush if option.state & QtWidgets.QStyle.State_Selected else self._hoverBackgroundBrush

            path = QtGui.QPainterPath()
            path.addRect(option.rect)
            parentPath = option.widget.painterPath

            painter.setClipPath(parentPath)
            painter.fillPath(path, brush)

        # --- Text ---
        textRect = QtCore.QRectF(option.rect)
        textRect.setWidth(textWidth)
        textRect.moveLeft(leftMargin)
        textRect.moveTop(textRect.top() + verticalTextMargin)
        painter.drawText(textRect, text)

        # --- Pixmap ---
        iconRect = QtCore.QRect(option.rect)
        iconRect.setWidth(NodeTypeItemDelegate.HEIGHT)
        iconRect.moveLeft(leftMargin + textWidth + spacing)
        iconRect.adjust(NodeTypeItemDelegate.ICON_MARGIN, NodeTypeItemDelegate.ICON_MARGIN, -NodeTypeItemDelegate.ICON_MARGIN, -NodeTypeItemDelegate.ICON_MARGIN)
        pixmap = pixmap.scaledToHeight(iconRect.height(), QtCore.Qt.SmoothTransformation)
        painter.drawPixmap(iconRect, pixmap)

        # --- Top border ---
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        painter.setPen(self._topBorderPen)
        painter.drawLine(topLeftPos, topRightPos)
        painter.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(-1, NodeTypeItemDelegate.HEIGHT)


class ListView(QtWidgets.QListView):

    BOTTOM_ROUNDNESS = BackgroundFrame.ROUNDNESS - BackgroundFrame.BORDER_WIDTH / 2.0

    BACKGROUND_COLOR = (255, 255, 255, 10)

    def __init__(self, parent=None):
        super(ListView, self).__init__(parent)

        self._isHovered = False
        self._painterPath = QtGui.QPainterPath()
        self._brush = QtGui.QBrush(QtGui.QColor(*ListView.BACKGROUND_COLOR))

    @property
    def isHovered(self):
        return self._isHovered

    @property
    def painterPath(self):
        return self._painterPath

    def mouseMoveEvent(self, event):
        # NOTE: There is a bug in Qt 5.6 which prevents the `QStyle.State_MouseOver` of a `QAbstractItemDelegate` from updating when the mouse leaves
        # We will force a call to `QAbstractItemDelegate.paint` on leave so the delegate can check if the widget is hovered
        super(ListView, self).mouseMoveEvent(event)

        wasHovered = self._isHovered
        self._isHovered = self.shape().contains(event.pos())

        if self._isHovered != wasHovered:
            self.update()

    def leaveEvent(self, event):
        super(ListView, self).leaveEvent(event)

        self._isHovered = False
        self.update()

    def paintEvent(self, event):
        # `QListView.paintEvent` reimplements `QAbstractScrollArea.paintEvent` (ie. ensure the painter is installed on the viewport)
        painter = QtGui.QPainter(self.viewport())

        # --- Background ---
        rect = QtCore.QRectF(self.geometry())

        if rect.height() < ListView.BOTTOM_ROUNDNESS:
            heightOverflow = ListView.BOTTOM_ROUNDNESS - rect.height()
            rect.setTop(rect.top() - heightOverflow)

        self._painterPath = QT_SHAPE.getRoundedRectPath(rect, roundness=ListView.BOTTOM_ROUNDNESS, roundBottomLeft=True, roundBottomRight=True)
        painter.fillPath(self._painterPath, self._brush)

        # --- Items ---
        super(ListView, self).paintEvent(event)

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def shape(self):
        return QT_SHAPE.getRoundedRectPath(self.geometry(), 20, roundTopLeft=True, roundTopRight=True)


class ScrollBar(QtWidgets.QScrollBar):
    """A `QScrollBar` that adds a limit to the minimum length by making the page step proportional to the document length."""

    MINIMUM_LENGTH_RATIO = 0.2

    def __init__(self, parent):
        super(ScrollBar, self).__init__(parent)

        self._documentLength = 0

    def setDocumentLength(self, length):
        self._documentLength = length

    def sliderChange(self, change):
        pageStep = self.pageStep()
        minPageStep = max(pageStep, int(self._documentLength * ScrollBar.MINIMUM_LENGTH_RATIO))

        if minPageStep != pageStep:
            self.setPageStep(minPageStep)

        super(ScrollBar, self).sliderChange(change)


class ScrollBarContainer(QtWidgets.QWidget):

    def resizeEvent(self, event):
        super(ScrollBarContainer, self).resizeEvent(event)

        rect = self.rect()
        rect.setLeft(rect.width() - CreateNodeToolWindow.SCROLLBAR_WIDTH)
        self.setMask(rect)
