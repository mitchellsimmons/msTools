"""
Utility functions relating to the Maya Node Editor.

----------------------------------------------------------------

Widget Hierarchy
----------------

    The Node Editor has the following simplified widget hierarchy (**verified for Maya 2019**):


    \\- `Window` (:class:`PySide2.QtWidgets.QWidget`)

        \\- `Panel` (:class:`PySide2.QtWidgets.QWidget`)

            \\- `Menu Bar` (:class:`PySide2.QtWidgets.QMenuBar`)

            \\- Container (:class:`PySide2.QtWidgets.QWidget` - placeholder for :func:`cmds.formLayout`)

                \\- Container (:class:`PySide2.QtWidgets.QWidget` - placeholder for :func:`cmds.frameLayout`)

                    \\- Container (:class:`PySide2.QtWidgets.QFrame`)

                        \\- `Icon Bar` (:class:`PySide2.QtWidgets.QWidget` - placeholder for :func:`cmds.flowLayout`)

                \\- Container (:class:`PySide2.QtWidgets.QWidget` - placeholder for :func:`cmds.paneLayout`)

                    \\- Container (:class:`PySide2.QtWidgets.QWidget`)

                        \\- `Editor` (:class:`PySide2.QtWidgets.QTabWidget`)

                            \\- `Tab Bar` (:class:`PySide2.QtWidgets.QTabBar`)

                            \\- `Page Area` (:class:`PySide2.QtWidgets.QStackedWidget`)

                                \\- `Pages` (:class:`PySide2.QtWidgets.QWidget`)

                                    \\- `View` (:class:`PySide2.QtWidgets.QGraphicsView`)

                                        \\- `Viewport` (:class:`PySide2.QtWidgets.QWidget`)

----------------------------------------------------------------

Widget Lifetime
---------------

    The following groups of Node Editor widgets should share the same lifetimes.

    - `window`, `panel`, `menu bar`, `icon bar`.
    - `editor`, `tab bar`, `page area`.
    - `page`, `view`, `viewport`, `scene`.

----------------------------------------------------------------

Note:
    1. A Node Editor `panel` can be created with :func:`cmds.scriptedPanel` using ``type = "nodeEditorPanel"``.
       The initial Node Editor `panel` will contain the primary Node Editor `editor`.
       There can only ever be a single primary Node Editor. The primary `editor` is the only one that has a visible `tab bar`.

Note:
    2. A Node Editor `editor` can be queried and modified with :func:`cmds.nodeEditor`.

Note:
    3. The name of the primary Node Editor `editor` can be retrieved with the MEL command ``getPrimaryNodeEditor``.

.. _note_4:

Note:
    4. A reference to a `page` must be kept in memory in order to access its descendant widgets. The `editor` maintains ownership of all `page` widgets.
       Any reference to a descendant will be automatically invalidated unless a reference to the `page` remains in memory.

.. _note_5:

Note:
    5. When opening a new scene, Maya will delete each `page` for any existing tab in the Node Editor.
       The tab count will sequentially decrement to zero then increment back to one.

Note:
    6. Whilst a tab is being dragged, the :meth:`PySide2.QtWidgets.QTabWidget.count` (`editor`) and :meth:`PySide2.QtWidgets.QTabBar.count` (`tab bar`) will decrement.
       Only the :meth:`PySide2.QtWidgets.QStackedWidget.count` (`page area`) will remain unchanged.

Note:
    7. The :meth:`PySide2.QtWidgets.QTabWidget.count` (`editor`) and :meth:`PySide2.QtWidgets.QTabBar.count` (`tab bar`) are influenced by the 'Add a new tab' button.
       Their value is one greater than the :meth:`PySide2.QtWidgets.QStackedWidget.count` (`page area`), even for non-primary editors whose tab bar is hidden.

Note:
    8. Whilst a tab is being dragged, the :meth:`PySide2.QtWidgets.QTabWidget.currentIndex` (`editor`) and :meth:`PySide2.QtWidgets.QTabBar.currentIndex` (`tab bar`) and
       :meth:`PySide2.QtWidgets.QStackedWidget.currentIndex` (`page area`) will all update dynamically.

Note:
    9. The :meth:`PySide2.QtWidgets.QTabWidget.currentIndex` (`editor`) and :meth:`PySide2.QtWidgets.QTabBar.currentIndex` (`tab bar`) may be influenced by the 'Add a new tab' button.
       It is possible to select this button with `ctrl + tab`, meaning only :meth:`PySide2.QtWidgets.QStackedWidget.currentIndex` (`page area`) is reliable.

Note:
    10. There is a margin of two units between the `viewport` and its parent `view`. Therefore the `viewport` should be used to acquire dimensions.

Warning:
    1. Using :func:`cmds.nodeEditor` to query the `panel` of an `editor` will just remove ``"NodeEditorEd"`` from the name of the `editor`.
       It does not consider the possibility that the `editor` has been unparented and reparented to a different `panel` using :func:`cmds.nodeEditor`.

Warning:
    2. Using the MEL procedure ``getCurrentNodeEditor`` to query the `editor` which has focus will just add ``"NodeEditorEd"`` to the result of ``getCurrentNodeEditorPanel``.
       It does not consider the possibility that the `editor` has been unparented and no longer exists.

Warning:
    3. Do not attempt to access a Node Editor :class:`PySide2.QtWidgets.QGraphicsView` via :meth:`PySide2.QtCore.QObject.findChildren`.

       - A `view` will often show as a :class:`PySide2.QtWidgets.QWidget` within the descendant hierarchy, requiring a cast.
       - When opening a new scene, Maya will create a new `view` as discussed in :ref:`note-5 <note_5>`.
         However previous invalidated `views` may remain temporarily parented to an existing `page` before being removed.
       - When a `view` is created it is initially parented to the `editor`. Only when Maya reaches idle will a `view` be reparented to its associated `page`.
         Operating on a `view` which has not been reparented may cause it to be deleted.

----------------------------------------------------------------
"""
from maya import cmds, mel
from maya.api import OpenMaya as om2

from msTools.vendor.enum import Enum
from msTools.vendor.Qt import QtCompat, QtGui, QtWidgets

from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import om_utils as OM
from msTools.coreUI.maya import exceptions as UI_EXC
from msTools.coreUI.maya import inspect_utils as UI_INSPECT
from msTools.coreUI.qt import widget_utils as QT_WIDGET


# NOTE: The following functions ensure all references are retained since we are dealing with c++ widgets (ie. shiboken2.createdByPython() is False)
# Failing to retain these references would risk invalidating any existing such references within the calling scope of the function

# ----------------------------------------------------------------
# --- Constants ---
# ----------------------------------------------------------------

# NOTE: Data has been verified for Maya 2019.

class NodeEditorGraphicsItem(object):
    """A namespace for Node Editor graphics item type constants.

    These are the unique values returned from :meth:`PySide2.QtWidgets.QGraphicsItem.type`.
    """
    NODE = 65545
    PLUG = 65540
    PATH = 65548
    SIMPLE_TEXT = 65549


class NodeEditorObject(Enum):
    """Node Editor object enumerations."""
    PANEL = 0
    MENU_BAR = 1
    ICON_BAR = 2
    EDITOR = 3
    TAB_BAR = 4
    PAGE_AREA = 5
    PAGE = 6
    VIEW = 7
    VIEWPORT = 8
    SCENE = 9


# Some objects have custom subclass implementations ("Qmaya..." and "Tmaya...")
_NODE_EDITOR_OBJECT_SUBCLASS_NAME_MAPPING = {
    NodeEditorObject.PANEL: "QmayaLayoutWidget",
    NodeEditorObject.MENU_BAR: "QmayaMenuBar",
    NodeEditorObject.ICON_BAR: "QWidget",
    NodeEditorObject.EDITOR: "TmayaNodeGraphEditorViewTabWidget",
    NodeEditorObject.TAB_BAR: "QmayaTabBar",
    NodeEditorObject.PAGE_AREA: "QStackedWidget",
    NodeEditorObject.PAGE: "QWidget",
    NodeEditorObject.VIEW: "TDGNodeGraphEditorView",
    NodeEditorObject.VIEWPORT: "QWidget",
    NodeEditorObject.SCENE: "TnodeGraphEditorScene",
}


_NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING = {
    NodeEditorObject.PANEL: QtWidgets.QWidget,  # Container (menuBarLayout placeholder)
    NodeEditorObject.MENU_BAR: QtWidgets.QMenuBar,
    NodeEditorObject.ICON_BAR: QtWidgets.QWidget,  # Container (flowLayout placeholder)
    NodeEditorObject.EDITOR: QtWidgets.QTabWidget,
    NodeEditorObject.TAB_BAR: QtWidgets.QTabBar,
    NodeEditorObject.PAGE_AREA: QtWidgets.QStackedWidget,  # Container for pages
    NodeEditorObject.PAGE: QtWidgets.QWidget,  # Container for views
    NodeEditorObject.VIEW: QtWidgets.QGraphicsView,
    NodeEditorObject.VIEWPORT: QtWidgets.QWidget,
    NodeEditorObject.SCENE: QtWidgets.QGraphicsScene,
}


# Some layouts have custom subclass implementations ("Qmaya...")
# None indicates the object/widget does not have a layout
_NODE_EDITOR_LAYOUT_SUBCLASS_NAME_MAPPING = {
    NodeEditorObject.PANEL: "QmayaMenuBarLayout",
    NodeEditorObject.MENU_BAR: None,
    NodeEditorObject.ICON_BAR: "QmayaFlowLayout",
    NodeEditorObject.EDITOR: None,
    NodeEditorObject.TAB_BAR: None,
    NodeEditorObject.PAGE_AREA: "QStackedLayout",
    NodeEditorObject.PAGE: "QVBoxLayout",
    NodeEditorObject.VIEW: None,
    NodeEditorObject.VIEWPORT: None,
    NodeEditorObject.SCENE: None,
}


# None indicates the object/widget does not have a layout
_NODE_EDITOR_LAYOUT_QT_BASECLASS_MAPPING = {
    NodeEditorObject.PANEL: QtWidgets.QVBoxLayout,  # scriptedPanel layout
    NodeEditorObject.MENU_BAR: None,
    NodeEditorObject.ICON_BAR: QtWidgets.QLayout,  # flowLayout
    NodeEditorObject.EDITOR: None,
    NodeEditorObject.TAB_BAR: None,
    NodeEditorObject.PAGE_AREA: QtWidgets.QStackedLayout,
    NodeEditorObject.PAGE: QtWidgets.QVBoxLayout,
    NodeEditorObject.VIEW: None,
    NodeEditorObject.VIEWPORT: None,
    NodeEditorObject.SCENE: None,
}


GRAPHICS_SCENE_TO_NODE_EDITOR_TRANSFORM = QtGui.QTransform.fromScale(1.42857142857, -1.42857142857)
""":class:`PySide2.QtGui.QTransform`: Transforms :class:`PySide2.QtWidgets.QGraphicsScene` coordinates into the Node Editor's coordinate space.

Coordinates in this space are used to save the positions of nodes in the Node Editor via ``nodeGraphEditorInfo`` nodes.

Note:
    The transformation inverts the vertical axis. The :class:`PySide2.QtWidgets.QGraphicsScene` adopts y-down coordinates whilst the Node Editor adopts standard y-up coordinates.

Example:
    The following example demonstrates how to determine these contant scaling factors.
    It requires a bookmark to be created in the Node Editor so we can read the ``viewRectLow`` or ``viewRectHigh`` attributes of the ``nodeGraphEditorBookmarkInfo`` node.

    .. code-block:: python

        nodeEditor = getPrimaryNodeEditor()
        graphicsView = getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        viewport = graphicsView.viewport()

        # Use the viewport size since there is a 2px border between it and the graphics view
        viewportSize = viewport.size()

        # Use the QGraphicsView to map viewport coordinates to QGraphicsScene coordinates
        sceneBottomLeftPos = graphicsView.mapToScene(0, viewportSize.height())

        # Use the `viewXL` and `viewYL` attributes from the `nodeGraphEditorBookmarkInfo` node
        sceneToNodeEditorScaleX = viewXL / sceneBottomLeftPos.x()
        sceneToNodeEditorScaleY = viewYL / sceneBottomLeftPos.y()
"""

GRAPHICS_SCENE_TO_GRAPHVIZ_TRANSFORM = QtGui.QTransform.fromScale(0.01, -0.01)
""":class:`PySide2.QtGui.QTransform`: Transforms :class:`PySide2.QtWidgets.QGraphicsScene` coordinates into a Graphviz coordinate space.

Coordinates in this space can be used to position nodes within the Node Editor by passing a minimal graph description to the ``dotFormat`` argument of the :func:`cmds.nodeEditor` command.
The graph description must be provided in the `plain <https://graphviz.org/doc/info/output.html#d:plain>`_ format of the DOT language.

Note:
    The transformation inverts the vertical axis. The :class:`PySide2.QtWidgets.QGraphicsScene` adopts y-down coordinates whilst Graphviz adopts standard y-up coordinates.

Example:
    The following example demonstrates how to position the node named ``"transform1"`` on the cursor.

    .. code-block:: python

        nodeEditor = getPrimaryNodeEditor()
        graphicsView = getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
        viewport = graphicsView.viewport()

        # Determine the cursor position in QGraphicsView viewport coordinates
        cursorPos_viewport = viewport.mapFromGlobal(QtGui.QCursor.pos())
        # The QGraphicsView is used to map viewport coordinates to QGraphicsScene coordinates
        cursorPos_scene = graphicsView.mapToScene(cursorPos_viewport)
        # Offset the position so that the node title is centered on the cursor
        nodePos_scene = QtCore.QPointF(cursorPos_scene.x() - 67.5, cursorPos_scene.y())
        # Determine the node position in Graphviz coordinates
        nodePos_graphviz = nodePos_scene * GRAPHICS_SCENE_TO_GRAPHVIZ_TRANSFORM

        # Generate a plain formatted DOT language graph description
        # The `graphWidth`, `graphHeight`, `nodeWidth` and `nodeHeight` should be ignored in this case
        graph = "graph {graphScale} {graphWidth} {graphHeight}\\nnode {nodeName} {nodeX} {nodeY} {nodeWidth} {nodeHeight}\\nstop".format(
            graphScale=1.0, graphWidth=0.0, graphHeight=0.0,
            nodeName="transform1", nodeX=nodePos_graphviz.x(), nodeY=nodePos_graphviz.y(), nodeWidth=0.0, nodeHeight=0.0)

        cmds.nodeEditor(nodeEditor.objectName(), e=True, dotFormat=graph)
"""

NODE_EDITOR_TO_GRAPHVIZ_TRANSFORM = QtGui.QTransform.fromScale(1.0 / GRAPHICS_SCENE_TO_NODE_EDITOR_TRANSFORM.m11(), 1.0 / GRAPHICS_SCENE_TO_NODE_EDITOR_TRANSFORM.m11())
""":class:`PySide2.QtGui.QTransform`: Transforms Node Editor coordinates into a Graphviz coordinate space.

Coordinates in this space can be used to position nodes within the Node Editor by passing a minimal graph description to the ``dotFormat`` argument of the :func:`cmds.nodeEditor` command.
The graph description must be provided in the `plain <https://graphviz.org/doc/info/output.html#d:plain>`_ format of the DOT language.

Note:
    Both the input and output coordinate spaces adopt standard y-up coordinates.
"""


# ----------------------------------------------------------------
# --- Validate ---
# ----------------------------------------------------------------

def isNodeEditorObject(nodeEditorObject, nodeEditorObjectType):
    """Verify the type of a Node Editor object based on a set of compiled expectations.

    Args:
        nodeEditorObject (T <= :class:`PySide2.QtWidgets.QWidget`): A Node Editor object.
        nodeEditorObjectType (:class:`NodeEditorObject`): An enumeration representing the expected ``nodeEditorObject`` type.

    Returns:
        :class:`bool`: :data:`True` if ``nodeEditorObject`` corresponds to the ``nodeEditorObjectType``, otherwise :data:`False`.
    """
    objectQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[nodeEditorObjectType]
    objectDerivedClassName = _NODE_EDITOR_OBJECT_SUBCLASS_NAME_MAPPING[nodeEditorObjectType]
    layoutQtBaseClass = _NODE_EDITOR_LAYOUT_QT_BASECLASS_MAPPING[nodeEditorObjectType]
    layoutDerivedClassName = _NODE_EDITOR_LAYOUT_SUBCLASS_NAME_MAPPING[nodeEditorObjectType]

    try:
        nodeEditorLayout = nodeEditorObject.layout()
    except AttributeError:
        nodeEditorLayout = None

    # Sometimes layout returns QLayout instead of the derived type (issue occurs for node editor panels)
    if nodeEditorLayout is not None:
        nodeEditorLayout = QT_WIDGET.retainAndReturn(QtCompat.wrapInstance(long(QtCompat.getCppPointer(nodeEditorLayout))))

    # Verify the expected object type
    if type(nodeEditorObject) is objectQtBaseClass:
        # Verify the expected derived object type
        if objectDerivedClassName == nodeEditorObject.metaObject().className():
            # If possible verify the expected object layout type
            if nodeEditorLayout is None:
                if layoutQtBaseClass is None:
                    return True
            elif type(nodeEditorLayout) is layoutQtBaseClass:
                # Verify the expected derived layout type
                if layoutDerivedClassName == nodeEditorLayout.metaObject().className():
                    return True

    return False


# ----------------------------------------------------------------
# --- Retrieve : Panel ---
# ----------------------------------------------------------------

def getNodeEditorPanelFromDescendant(nodeEditorDescendant):
    """Return the Node Editor `panel` for the given Node Editor descendant widget.

    The `panel` contains a `menu bar`, `icon bar` and usually an `editor`.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditorDescendant (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditorDescendant`` does not have an ancestral `panel`.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`: The ancestral `panel` widget for the ``nodeEditorDescendant``.
    """
    # NOTE: It is not sufficient to simply query `cmds.nodeEditor(nodeEditorName, panel=True, q=True)` since it just removes "NodeEditorEd" from the panel name
    nodeEditorPanelNames = cmds.getPanel(scriptType="nodeEditorPanel")

    for nodeEditorPanelName in nodeEditorPanelNames:
        try:
            nodeEditorPanel = QT_WIDGET.retainAndReturn(UI_INSPECT.getWidget(nodeEditorPanelName))
        except UI_EXC.MayaUILookupError:
            continue

        if nodeEditorPanel.isAncestorOf(nodeEditorDescendant):
            if isNodeEditorObject(nodeEditorPanel, NodeEditorObject.PANEL):
                return nodeEditorPanel

    raise UI_EXC.MayaUILookupError("Unable to identify a panel for the given Node Editor editor")


def getNodeEditorMenuBarFromPanel(nodeEditorPanel):
    """Return the Node Editor `menu bar` for the given Node Editor `panel`.

    The `menu bar` contains all menu items (eg. `Edit`, `View`, `Bookmarks`, etc).

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditorPanel (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `panel` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditorPanel`` does not reference a Node Editor `panel`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditorPanel`` does not have a child `menu bar`.

    Returns:
        :class:`PySide2.QtWidgets.QMenuBar`: The child `menu bar` widget for the ``nodeEditorPanel``.
    """
    panelQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.PANEL]

    if cmds.scriptedPanel(nodeEditorPanel.objectName(), type=True, q=True) != "nodeEditorPanel":
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor scripted panel".format(panelQtBaseClass))

    for child in [QT_WIDGET.retainAndReturn(child) for child in nodeEditorPanel.children()]:
        if isNodeEditorObject(child, NodeEditorObject.MENU_BAR):
            return child

    raise UI_EXC.MayaUILookupError("Unable to identify a menu bar for the given Node Editor panel")


def getNodeEditorIconBarFromPanel(nodeEditorPanel):
    """Return the Node Editor `icon bar` for the given Node Editor `panel`.

    The `icon bar` contains all icon elements directly below the `menu bar` (eg. `create node`, `layout`, `search`, etc).
    The `icon bar` widget exists as a placeholder for a :func:`cmds.flowLayout`.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditorPanel (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `panel` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditorPanel`` does not reference a Node Editor `panel`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditorPanel`` does not have a descendant `icon bar`.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`: The descendant `icon bar` widget for the ``nodeEditorPanel``.
    """
    panelQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.PANEL]

    if cmds.scriptedPanel(nodeEditorPanel.objectName(), type=True, q=True) != "nodeEditorPanel":
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor scripted panel".format(panelQtBaseClass))

    iconBarLayoutQtBaseClass = _NODE_EDITOR_LAYOUT_QT_BASECLASS_MAPPING[NodeEditorObject.ICON_BAR]

    for childLayoutWidget in nodeEditorPanel.findChildren(iconBarLayoutQtBaseClass):
        QT_WIDGET.retain(childLayoutWidget)

        # Verify the expected maya layout type
        if childLayoutWidget.objectName() and cmds.flowLayout(childLayoutWidget.objectName(), exists=True):
            childWidget = QT_WIDGET.retainAndReturn(childLayoutWidget.parent())

            if isNodeEditorObject(childWidget, NodeEditorObject.ICON_BAR):
                return childWidget

    raise UI_EXC.MayaUILookupError("Unable to identify an icon bar for the given Node Editor panel")


# ----------------------------------------------------------------
# --- Retrieve : Editor ---
# ----------------------------------------------------------------

def getCurrentNodeEditor():
    """Return the Node Editor `editor` for the `panel` which currently has focus.

    The `editor` manages associations between the :class:`PySide2.QtWidgets.QTabBar` tabs and the :class:`PySide2.QtWidgets.QStackedWidget` `pages`.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Note:
        Only the primary `editor` allows tabs (ie. multiple `views`).
        Non-primary editors are only allowed to display a single `view` (the `tab bar` is hidden).

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If a current Node Editor `editor` could not be identified (ie. there is no `panel` with focus).

    Returns:
        :class:`PySide2.QtWidgets.QTabWidget`: The current Node Editor `editor` widget.
    """
    # NOTE: We avoid "getCurrentNodeEditor" since it just adds "NodeEditorEd" to the result of `getCurrentNodeEditorPanel`
    nodeEditorPanelName = mel.eval("getCurrentNodeEditorPanel")

    if nodeEditorPanelName:
        nodeEditorPanel = QT_WIDGET.retainAndReturn(UI_INSPECT.getWidget(nodeEditorPanelName))
        # If the focused panel does not have an editor this will raise an error
        return getNodeEditorFromPanel(nodeEditorPanel)

    raise UI_EXC.MayaUILookupError("Unable to identify a Node Editor editor which has focus")


def getPrimaryNodeEditor():
    """Return the primary Node Editor `editor`.

    The `editor` manages associations between the :class:`PySide2.QtWidgets.QTabBar` tabs and the :class:`PySide2.QtWidgets.QStackedWidget` `pages`.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Note:
        Only the primary `editor` allows tabs (ie. multiple `views`).
        Non-primary editors are only allowed to display a single `view` (the `tab bar` is hidden).

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If a primary Node Editor `editor` could not be identified.

    Returns:
        :class:`PySide2.QtWidgets.QTabWidget`: The primary Node Editor `editor` widget.
    """
    nodeEditorName = mel.eval("getPrimaryNodeEditor")

    if nodeEditorName:
        nodeEditor = QT_WIDGET.retainAndReturn(UI_INSPECT.getWidget(nodeEditorName))

        if isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
            return nodeEditor

    raise UI_EXC.MayaUILookupError("Unable to identify a primary Node Editor editor")


def getNodeEditorFromPanel(nodeEditorPanel):
    """Return the Node Editor `editor` for the given Node Editor `panel`.

    The `editor` manages associations between the :class:`PySide2.QtWidgets.QTabBar` tabs and the :class:`PySide2.QtWidgets.QStackedWidget` `pages`.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Note:
        It is possible to unparent a Node Editor `editor` from its `panel`.
        Meaning it is not guaranteed a Node Editor `panel` will have an `editor`.

        Only the primary `editor` allows tabs (ie. multiple `views`).
        Non-primary `editors` are only allowed to display a single `view` (the `tab bar` is hidden).

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditorPanel (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `panel` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditorPanel`` does not reference a Node Editor `panel`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditorPanel`` does not have a descendant `editor`.

    Returns:
        :class:`PySide2.QtWidgets.QTabWidget`: The descendant Node Editor `editor` widget for the ``nodeEditorPanel``.
    """
    panelQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.PANEL]

    if cmds.scriptedPanel(nodeEditorPanel.objectName(), type=True, q=True) != "nodeEditorPanel":
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor scripted panel".format(panelQtBaseClass))

    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    for child in nodeEditorPanel.findChildren(editorQtBaseClass):
        QT_WIDGET.retain(child)

        if isNodeEditorObject(child, NodeEditorObject.EDITOR):
            return child

    raise UI_EXC.MayaUILookupError("Unable to identify an editor for the given Node Editor panel")


def getNodeEditorTabBarFromEditor(nodeEditor):
    """Return the Node Editor `tab bar` for the given Node Editor `editor`.

    The `tab bar` provides a user interface for managing the :class:`PySide2.QtWidgets.QStackedWidget` `pages`.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Note:
        The `tab bar` will only be visible in the primary `editor`.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a child `tab bar`.

    Returns:
        :class:`PySide2.QtWidgets.QTabBar`: The child Node Editor `tab bar` widget for the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    for child in [QT_WIDGET.retainAndReturn(child) for child in nodeEditor.children()]:
        if isNodeEditorObject(child, NodeEditorObject.TAB_BAR):
            return child

    raise UI_EXC.MayaUILookupError("Unable to identify a tab bar for the given Node Editor editor")


def getNodeEditorPageAreaFromEditor(nodeEditor):
    """Return the Node Editor `page area` for the given Node Editor `editor`.

    The `page area` provides an area for displaying `pages`. Each `page` contains a `view` for rendering graphics items.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a child `page area`.

    Returns:
        :class:`PySide2.QtWidgets.QStackedWidget`: The child Node Editor `page area` widget for the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    for child in [QT_WIDGET.retainAndReturn(child) for child in nodeEditor.children()]:
        if isNodeEditorObject(child, NodeEditorObject.PAGE_AREA):
            return child

    raise UI_EXC.MayaUILookupError("Unable to identify a page area for the given Node Editor editor")


def getCurrentNodeEditorPageFromEditor(nodeEditor):
    """Return the Node Editor `page` which is visible in the given Node Editor `editor`.

    A `page` is used to display the contents of a `view` for a specific tab.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a current `page`.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`: The current `page` widget shown in the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    # Query the page area in case a tab is being dragged (the editor/tab-bar count is unreliable)
    nodeEditorPageArea = getNodeEditorPageAreaFromEditor(nodeEditor)

    if nodeEditorPageArea.currentIndex() == -1 or not nodeEditorPageArea.count():
        raise UI_EXC.MayaUILookupError("Unable to identify any tabs for the given Node Editor editor")

    return QT_WIDGET.retainAndReturn(nodeEditorPageArea.widget(nodeEditorPageArea.currentIndex()))


def getNodeEditorPagesFromEditor(nodeEditor):
    """Return the Node Editor `pages` for the given Node Editor `editor`.

    A `page` is used to display the contents of a `view` for a specific tab.
    The current tab determines the current `page` shown in the `editor`. The user can show a different `page` by clicking on its associated tab.

    Warning:
        The results of this function are c++ widget references which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have any `pages`.

    Returns:
        :class:`list` [:class:`PySide2.QtWidgets.QWidget`]: The `page` widgets owned by the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    # Query the page area in case a tab is being dragged (the editor/tab-bar count is unreliable)
    nodeEditorPageArea = getNodeEditorPageAreaFromEditor(nodeEditor)

    if nodeEditorPageArea.currentIndex() == -1 or not nodeEditorPageArea.count():
        raise UI_EXC.MayaUILookupError("Unable to identify any tabs for the given Node Editor editor")

    nodeEditorPages = []

    for pageIndex in xrange(nodeEditorPageArea.count()):
        nodeEditorPage = QT_WIDGET.retainAndReturn(nodeEditorPageArea.widget(pageIndex))
        nodeEditorPages.append(nodeEditorPage)

    return nodeEditorPages


def getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor):
    """Return the Node Editor `view` which is visible in the given Node Editor `editor`.

    A `view` is used to visualise the contents of a `scene` by rendering graphics items to a `viewport`. There exists a `view` for each `page`.
    The current tab determines the current `view` shown in the `editor`. The user can show a different `view` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a current `view`.

    Returns:
        :class:`PySide2.QtWidgets.QGraphicsView`: The current `view` widget shown in the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    # Query the page area in case a tab is being dragged (the editor/tab-bar count is unreliable)
    nodeEditorPageArea = getNodeEditorPageAreaFromEditor(nodeEditor)

    if nodeEditorPageArea.currentIndex() == -1 or not nodeEditorPageArea.count():
        raise UI_EXC.MayaUILookupError("Unable to identify any tabs for the given Node Editor editor")

    # NOTE: It is especially important to retain the page reference before accessing a descendant (see note-4 above)
    nodeEditorPage = QT_WIDGET.retainAndReturn(nodeEditorPageArea.widget(nodeEditorPageArea.currentIndex()))

    # NOTE: Do not attempt to access a `QGraphicsView` via `findChildren` - see above warning
    for child in [QT_WIDGET.retainAndReturn(child) for child in nodeEditorPage.children()]:
        # Sometimes the child shows as a QWidget (we need to cast to a QGraphicsView)
        if type(child) is QtWidgets.QWidget:
            ptr = QtCompat.getCppPointer(child)
            child = QtCompat.wrapInstance(long(ptr))

        if isNodeEditorObject(child, NodeEditorObject.VIEW):
            return child

    raise UI_EXC.MayaUILookupError("Unable to identify the current view for the given Node Editor editor")


def getNodeEditorGraphicsViewsFromEditor(nodeEditor):
    """Return the Node Editor `views` for the given Node Editor `editor`.

    A `view` is used to visualise the contents of a `scene` by rendering graphics items to a `viewport`. There exists a `view` for each `page`.
    The current tab determines the current `view` shown in the `editor`. The user can show a different `view` by clicking on its associated tab.

    Warning:
        The results of this function are c++ widget references which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have any `views`.
    ..

    Returns:
        :class:`list` [:class:`PySide2.QtWidgets.QGraphicsView`]: Sequence of `view` widgets for the ``nodeEditor``.
    """
    editorQtBaseClass = _NODE_EDITOR_OBJECT_QT_BASECLASS_MAPPING[NodeEditorObject.EDITOR]

    if not isNodeEditorObject(nodeEditor, NodeEditorObject.EDITOR):
        raise UI_EXC.MayaUITypeError("Expected a {} encapsulation of a Node Editor editor".format(editorQtBaseClass))

    # Query the page area in case a tab is being dragged (the editor/tab-bar count is unreliable)
    nodeEditorPageArea = getNodeEditorPageAreaFromEditor(nodeEditor)

    if nodeEditorPageArea.currentIndex() == -1 or not nodeEditorPageArea.count():
        raise UI_EXC.MayaUILookupError("Unable to identify any tabs for the given Node Editor editor")

    nodeEditorGraphicsViews = []

    for pageIndex in xrange(nodeEditorPageArea.count()):
        nodeEditorPage = QT_WIDGET.retainAndReturn(nodeEditorPageArea.widget(pageIndex))

        for child in [QT_WIDGET.retainAndReturn(child) for child in nodeEditorPage.children()]:
            # Sometimes the child shows as a QWidget (we need to cast to a QGraphicsView)
            if type(child) is QtWidgets.QWidget:
                ptr = QtCompat.getCppPointer(child)
                child = QtCompat.wrapInstance(long(ptr))

            if isNodeEditorObject(child, NodeEditorObject.VIEW):
                nodeEditorGraphicsViews.append(child)
                break
        else:
            raise UI_EXC.MayaUILookupError("Unable to identify a view for a page of the given Node Editor editor")

    return nodeEditorGraphicsViews


def getCurrentNodeEditorGraphicsSceneFromEditor(nodeEditor):
    """Return the Node Editor `scene` for the `view` that is currently visible in the given Node Editor `editor`.

    A `scene` serves as a container for graphics items. A `view` is used to visualise the contents of a `scene` by rendering to a `viewport`.
    The current tab determines the current `scene` visualised within the `editor`. The user can visualise a different `scene` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a current `scene`.

    Returns:
        :class:`PySide2.QtWidgets.QGraphicsScene`: The `scene` for the `view` that is currently visible in the ``nodeEditor``.
    """
    nodeEditorGraphicsView = getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
    return QT_WIDGET.retainAndReturn(nodeEditorGraphicsView.scene())


def getNodeEditorGraphicsScenesFromEditor(nodeEditor):
    """Return the Node Editor `scenes` for the given Node Editor `editor`.

    A `scene` serves as a container for graphics items. A `view` is used to visualise the contents of a `scene` by rendering to a `viewport`.
    The current tab determines the current `scene` visualised within the `editor`. The user can visualise a different `scene` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have any `scenes`.

    Returns:
        :class:`list` [:class:`PySide2.QtWidgets.QGraphicsScene`]: Sequence of `scene` objects for the ``nodeEditor``.
    """
    return [QT_WIDGET.retainAndReturn(nodeEditorGraphicsView.scene()) for nodeEditorGraphicsView in getNodeEditorGraphicsViewsFromEditor(nodeEditor)]


def getCurrentNodeEditorViewportFromEditor(nodeEditor):
    """Return the Node Editor `viewport` that is currently visible in the given Node Editor `editor`.

    A `viewport` provides a scrollable area for visualising a `scene` within a `view`. It allows the user to determine which region of a `scene` is visualised.
    The current tab determines the current `viewport` shown in the `editor`. The user can show a different `viewport` by clicking on its associated tab.

    Warning:
        The results of this function are c++ widget references which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a current `viewport`.

    Returns:
        :class:`PySide2.QtWidgets.QWidget`:  The `viewport` that is currently visible in the ``nodeEditor``
    """
    nodeEditorGraphicsView = getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
    return QT_WIDGET.retainAndReturn(nodeEditorGraphicsView.viewport())


def getCurrentNodeEditorGraphicsItemsFromEditor(nodeEditor, itemType=None):
    """Return the Node Editor graphics items that exist within the `scene` for the `view` that is currently visible in the given Node Editor `editor`.

    Graphics items provide a graphical interface for objects such as nodes, plugs and edges.
    Each item is contained within a `scene`. A `view` is used to visualise the contents of a `scene` by rendering to a `viewport`.
    The current tab determines the current `scene` visualised within the `editor`. The user can visualise a different `scene` by clicking on its associated tab.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.
        itemType (:class:`int`): Specify the type of graphics items to return based on their :meth:`PySide2.QtWidgets.QGraphicsItem.type` constant.
            Possible values include :attr:`NodeEditorGraphicsItem.NODE`, :attr:`NodeEditorGraphicsItem.PLUG`, :attr:`NodeEditorGraphicsItem.PATH` and
            :attr:`NodeEditorGraphicsItem.SIMPLE_TEXT`. Defaults to :data:`None` - all graphics items will be included.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If ``nodeEditor`` does not have a current `scene`.

    Returns:
        :class:`list` [T <= :class:`PySide2.QtWidgets.QGraphicsItem`]: The graphics items that exist within the `scene` for the `view` that is currently visible in the ``nodeEditor``.
    """
    nodeEditorGraphicsScene = getCurrentNodeEditorGraphicsSceneFromEditor(nodeEditor)

    if itemType is None:
        return nodeEditorGraphicsScene.items()
    else:
        return [item for item in nodeEditorGraphicsScene.items() if item.type() == itemType]


def getInterestingNodeEditorWidgetsFromPanel(nodeEditorPanel, allTabs=False):
    """Return interesting objects in the descendant hierarchy of the given Node Editor `panel`.

    Args:
        nodeEditorPanel (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `panel` widget.
        allTabs (:class:`bool`, optional): Whether to return objects for each existing tab.
            If :data:`True`, the :attr:`NodeEditorObject.PAGE`, :attr:`NodeEditorObject.VIEW`, :attr:`NodeEditorObject.VIEWPORT` and :attr:`NodeEditorObject.SCENE`
            keys will each map to a list of objects instead of a single object for the current tab. Defaults to :data:`False`.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditorPanel`` does not reference a Node Editor `panel`.

    Returns:
        :class:`dict` [:class:`NodeEditorObject`, T <= :class:`PySide2.QtWidgets.QObject`]: A dictionary mapping enumerations to objects in the descendant hierarchy of ``nodeEditorPanel``.

        - :attr:`NodeEditorObject.PANEL`: The given ``nodeEditorPanel``.
        - :attr:`NodeEditorObject.MENU_BAR`: The Node Editor `menu bar`.
        - :attr:`NodeEditorObject.ICON_BAR`: The Node Editor `icon bar`.
        - :attr:`NodeEditorObject.EDITOR`: The Node Editor `editor` if one exists, else :data:`None`.
        - :attr:`NodeEditorObject.TAB_BAR`: The Node Editor `tab bar` if an `editor` exists, else :data:`None`.
        - :attr:`NodeEditorObject.PAGE_AREA`: The Node Editor `page area` if an `editor` exists, else :data:`None`.
        - :attr:`NodeEditorObject.PAGE`: The Node Editor `pages` if an `editor` exists, else :data:`None`.
        - :attr:`NodeEditorObject.VIEW`: The Node Editor `views` if an `editor` exists, else :data:`None`.
        - :attr:`NodeEditorObject.VIEWPORT`: The Node Editor `viewports` if an `editor` exists, else :data:`None`.
        - :attr:`NodeEditorObject.SCENE`: The Node Editor `scenes` if an `editor` exists, else :data:`None`.
    """
    interestingObjects = {objectEnum: None for objectEnum in NodeEditorObject}

    interestingObjects[NodeEditorObject.PANEL] = nodeEditorPanel
    interestingObjects[NodeEditorObject.MENU_BAR] = getNodeEditorMenuBarFromPanel(nodeEditorPanel)
    interestingObjects[NodeEditorObject.ICON_BAR] = getNodeEditorIconBarFromPanel(nodeEditorPanel)

    try:
        nodeEditor = getNodeEditorFromPanel(nodeEditorPanel)
    except UI_EXC.MayaUILookupError:
        return interestingObjects

    interestingObjects[NodeEditorObject.EDITOR] = nodeEditor
    interestingObjects[NodeEditorObject.TAB_BAR] = getNodeEditorTabBarFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.PAGE_AREA] = getNodeEditorPageAreaFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.VIEW] = getNodeEditorGraphicsViewsFromEditor(nodeEditor) if allTabs else getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.PAGE] = [view.parent() for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else interestingObjects[NodeEditorObject.VIEW].parent()
    interestingObjects[NodeEditorObject.VIEWPORT] = [QT_WIDGET.retainAndReturn(view.viewport()) for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else QT_WIDGET.retainAndReturn(interestingObjects[NodeEditorObject.VIEW].viewport())
    interestingObjects[NodeEditorObject.SCENE] = [QT_WIDGET.retainAndReturn(view.scene()) for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else QT_WIDGET.retainAndReturn(interestingObjects[NodeEditorObject.VIEW].scene())

    return interestingObjects


def getInterestingNodeEditorWidgetsFromEditor(nodeEditor, allTabs=False):
    """Return interesting objects in the descendant hierarchy of the given Node Editor `editor`.

    Args:
        nodeEditor (:class:`PySide2.QtWidgets.QWidget`): A Node Editor `editor` widget.
        allTabs (:class:`bool`, optional): Whether to return objects for each existing tab.
            If :data:`True`, the :attr:`NodeEditorObject.PAGE`, :attr:`NodeEditorObject.VIEW`, :attr:`NodeEditorObject.VIEWPORT` and :attr:`NodeEditorObject.SCENE`
            keys will each map to a list of objects instead of a single object for the current tab. Defaults to :data:`False`.

    Warning:
        The result of this function is a c++ widget reference which should be discarded at the next idle.

        This function is not guaranteed to remain operable.
        It relies on a specific state of the Maya UI which is subject to change in future versions.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditor`` does not reference a Node Editor `editor`.

    Returns:
        :class:`dict` [:class:`NodeEditorObject`, T <= :class:`PySide2.QtWidgets.QObject`]: A dictionary mapping enumerations to objects in the descendant hierarchy of ``nodeEditor``.

        - :attr:`NodeEditorObject.EDITOR`: The given ``nodeEditor``.
        - :attr:`NodeEditorObject.TAB_BAR`: The Node Editor `tab bar`.
        - :attr:`NodeEditorObject.PAGE_AREA`: The Node Editor `page area`.
        - :attr:`NodeEditorObject.PAGE`: The Node Editor `pages`.
        - :attr:`NodeEditorObject.VIEW`: The Node Editor `views`.
        - :attr:`NodeEditorObject.VIEWPORT`: The Node Editor `viewports`.
        - :attr:`NodeEditorObject.SCENE`: The Node Editor `scenes`.
    """
    interestingObjects = {objectEnum: None for objectEnum in NodeEditorObject if objectEnum.value >= NodeEditorObject.EDITOR.value}

    interestingObjects[NodeEditorObject.EDITOR] = nodeEditor
    interestingObjects[NodeEditorObject.TAB_BAR] = getNodeEditorTabBarFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.PAGE_AREA] = getNodeEditorPageAreaFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.VIEW] = getNodeEditorGraphicsViewsFromEditor(nodeEditor) if allTabs else getCurrentNodeEditorGraphicsViewFromEditor(nodeEditor)
    interestingObjects[NodeEditorObject.PAGE] = [view.parent() for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else interestingObjects[NodeEditorObject.VIEW].parent()
    interestingObjects[NodeEditorObject.VIEWPORT] = [QT_WIDGET.retainAndReturn(view.viewport()) for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else QT_WIDGET.retainAndReturn(interestingObjects[NodeEditorObject.VIEW].viewport())
    interestingObjects[NodeEditorObject.SCENE] = [QT_WIDGET.retainAndReturn(view.scene()) for view in interestingObjects[NodeEditorObject.VIEW]] if allTabs else QT_WIDGET.retainAndReturn(interestingObjects[NodeEditorObject.VIEW].scene())

    return interestingObjects


def getNodeFromGraphicsItem(nodeGraphicsItem):
    """Return a dependency node wrapper for the given Node Editor graphical node item.

    Args:
        nodeGraphicsItem (:class:`PySide2.QtWidgets.QGraphicsItem`): A graphical node item whose type is equivalent to :attr:`NodeEditorGraphicsItem.NODE`.

    Raises:
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If the ``nodeGraphicsItem`` type is not equivalent to :attr:`NodeEditorGraphicsItem.NODE`.
        :exc:`~exceptions.RuntimeError`: If a dependency node could not be identified for the given ``nodeGraphicsItem``.

    Returns:
        :class:`OpenMaya.MObject`: A dependency node wrapper corresponding to the given ``nodeGraphicsItem``.
    """
    if not nodeGraphicsItem.type() == NodeEditorGraphicsItem.NODE:
        raise UI_EXC.MayaUITypeError("Expected a Node Editor node type item")

    with CONTEXT.RestoreSelection():
        om2.MGlobal.setActiveSelectionList(om2.MSelectionList())

        # Even programtically selecting a node graphics item will register on the undo queue
        with CONTEXT.DisableUndoQueue(flush=False):
            nodeGraphicsItem.setSelected(True)

        sel = om2.MGlobal.getActiveSelectionList()

        if sel.length() == 0:
            raise RuntimeError("Unable to identify a dependency node for the given graphics item")

        return sel.getDependNode(0)


def getGraphicsItemFromNode(node, nodeEditorGraphicsScene):
    """Return a `graphics item` for the given dependency node wrapper, if one exists within the given Node Editor `graphics scene`.

    Args:
        node (:class:`OpenMaya.MObject`): A dependency node wrapper.
        nodeEditorGraphicsScene (:class:`PySide2.QtWidgets.QGraphicsScene`): The Node Editor `graphics scene` containing a `graphics item` for the given ``node``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.coreUI.maya.exceptions.MayaUITypeError`: If ``nodeEditorGraphicsScene`` does not reference a Node Editor `graphics scene`.
        :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If a `graphics item` could not be identified for the given ``node``.

    Returns:
        :class:`PySide2.QtWidgets.QGraphicsItem`: A `graphics item` within the given ``nodeEditorGraphicsScene``, corresponding to the given ``node``.
    """
    OM.validateNodeType(node)

    if not isNodeEditorObject(nodeEditorGraphicsScene, NodeEditorObject.SCENE):
        raise UI_EXC.MayaUITypeError("Expected a Node Editor graphics scene")

    with CONTEXT.RestoreSelection():
        selList = om2.MSelectionList().add(node)
        om2.MGlobal.setActiveSelectionList(selList)
        graphicsItems = nodeEditorGraphicsScene.selectedItems()

        # Selected items may include non-node type items
        for graphicsItem in graphicsItems:
            if graphicsItem.type() == NodeEditorGraphicsItem.NODE:
                return graphicsItem

    raise UI_EXC.MayaUILookupError("Unable to identify a graphics item for the given dependency node and graphics scene")
