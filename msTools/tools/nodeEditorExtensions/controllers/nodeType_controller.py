import logging
log = logging.getLogger(__name__)

from maya import cmds

from msTools.tools import callback_manager
from msTools.tools.nodeEditorExtensions.models import nodeType_model

# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

log.debug('Initializing global: _NODE_TYPE_CONTROLLER')
_NODE_TYPE_CONTROLLER = None


# ----------------------------------------------------------------------------
# --- Setup ---
# ----------------------------------------------------------------------------

def getGlobalNodeTypeController():
    """Access a global instance of the :class:`NodeTypeController`.

    Note:
        The controller is instantiated with the result of :meth:`~msTools.tools.nodeEditorExtensions.models.nodeType_model.getGlobalNodeTypeModel`.
        It ensures changes made to the internal Maya node type registry are reflected within the model.
    """
    global _NODE_TYPE_CONTROLLER
    if _NODE_TYPE_CONTROLLER is None:
        _NODE_TYPE_CONTROLLER = NodeTypeController(nodeType_model.getGlobalNodeTypeModel())

    return _NODE_TYPE_CONTROLLER


# ----------------------------------------------------------------------------
# --- Controller ---
# ----------------------------------------------------------------------------

class NodeTypeController(object):

    def __init__(self, model):
        super(NodeTypeController, self).__init__()

        self._model = model
        self._scheduledNodeTypes = []

        self._installCallbacks()

    def _installCallbacks(self):
        callback_manager.registerCallable(callback_manager.SceneEvent.AfterPluginLoad, self._afterLoad, receivesCallbackArgs=True)
        callback_manager.registerCallable(callback_manager.SceneEvent.BeforePluginUnload, self._beforeUnload, receivesCallbackArgs=True)

    def _deferInsert(self):
        if self._scheduledNodeTypes:
            self._model.addNodeTypes(self._scheduledNodeTypes)
            self._scheduledNodeTypes = []

    def _afterLoad(self, pluginData):
        def deferQuery():
            pluginName = pluginData[1]
            nodeTypes = cmds.pluginInfo(pluginName, q=True, dependNode=True)

            if nodeTypes:
                # Defer updating the model in case multiple plugins are loaded within the same call stack
                # The model queries internal Maya resources (an expensive operation) everytime new node types are inserted
                cmds.evalDeferred(self._deferInsert)
                self._scheduledNodeTypes.extend(nodeTypes)

        # Defer querying plugins until they have finished loading
        cmds.evalDeferred(deferQuery)

    def _beforeUnload(self, pluginData):
        pluginName = pluginData[0]
        nodeTypes = cmds.pluginInfo(pluginName, q=True, dependNode=True)

        if nodeTypes:
            self._model.removeNodeTypes(nodeTypes)
