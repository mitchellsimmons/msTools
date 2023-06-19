"""
Install callbacks in Maya.

----------------------------------------------------------------
"""

import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2


# --------------------------------------------------------------
# --- Callbacks ---
# --------------------------------------------------------------

def getNodesCreatedBy(callable_, *args, **kwargs):
    """Listen for nodes created during the execution of a callable.

    Args:
        callable_ (callable[[\\*args, \\**kwargs], any]): Callable to execute. Must be compatible with ``*args`` and ``**kwargs``.
        *args: Positional arguments used to invoke ``callable_``.
        **kwargs: Keyword arguments used to invoke ``callable_``.

    Other Parameters:
        listenTo (:class:`basestring`, optional): Filter specifying which node types to listen for. Defaults to ``'dependNode'``.
    ..

    Returns:
        (:class:`list` [:class:`OpenMaya.MObject`], any): A two-element :class:`tuple`.

        #. Pointers to the dependency nodes created during the execution of ``callable_``.
        #. Return value of ``callable_``.
    """
    listenTo = kwargs.pop("listenTo", "dependNode")

    newNodeHandles = []

    def nodeAddedCallback(node, clientData):
        newNodeHandles.append(om2.MObjectHandle(node))

    def nodeRemovedCallback(node, clientData):
        removedNodeHandle = om2.MObjectHandle(node)
        if removedNodeHandle in newNodeHandles:
            newNodeHandles.remove(removedNodeHandle)

    # Install listener callbacks
    nodeAddedCallbackId = om2.MDGMessage.addNodeAddedCallback(nodeAddedCallback, listenTo)
    nodeRemovedCallbackId = om2.MDGMessage.addNodeRemovedCallback(nodeRemovedCallback, listenTo)

    try:
        ret = callable_(*args, **kwargs)
    finally:
        # Remove listener callbacks
        om2.MMessage.removeCallback(nodeAddedCallbackId)
        om2.MMessage.removeCallback(nodeRemovedCallbackId)

    newNodes = [handle.object() for handle in newNodeHandles if handle.isAlive() and handle.isValid()]

    return newNodes, ret
