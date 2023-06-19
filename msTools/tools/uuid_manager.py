"""
Install callbacks to ensure unique UUIDs are assigned to referenced nodes.

----------------------------------------------------------------

Problem
-------

    Referenced nodes which are loaded from duplicate file references will have clashing UUIDs.

----------------------------------------------------------------

Details
-------

    Every dependency node in Maya has a unique UUID at the time of creation.

    **Importing**

    - When Maya imports a file, it recreates nodes/edges from the source file serialisation.
    - UUIDs are reassigned to each 'imported' node since the nodes are newly created.

    **Referencing**

    - When Maya references a child scene into a parent scene, nodes from the child scene are loaded not created.
    - UUIDs of referenced child scene nodes therefore do not change when the child scene is referenced into a parent scene meaning duplicate child scene references will create clashing UUIDs.

----------------------------------------------------------------

Solution
--------

    Every time we load a reference we can update the UUIDs of each referenced node from the child scene.
    Because the UUID attribute of referenced nodes is read-only we must use the technique described in the below link.

    - The command ``rename -uuid <node> <uuid>`` will fail.
    - Using :meth:`OpenMaya.MFnDependencyNode.setUuid` will force the update.
    - From what I can tell this has no effect on how a referenced node is tracked in the parent scene.

    This tool ensures only the UUIDs of referenced nodes loaded in by a referenced file will be updated.
    Updating all UUIDs upon loading a reference would break any tools which relies upon the UUIDs of existing nodes.

    **Sources**

    - http://www.csa3d.com/code/universally-unique-identifiers-are-not-necessarily-unique.html

----------------------------------------------------------------

Implications
------------

    Updating the UUIDs of referenced nodes upon loading a reference means the UUIDs of any referenced node within a parent scene are constant only for the duration of the session.

    - As soon as we reopen a saved parent scene, each child scene reference will be reloaded and each referenced node will have its UUID reassigned by the callback.
    - This will break any tool which relies upon cached UUIDs between sessions.
    - This seems like a reasonable trade-off for ensuring a node can be reliably identified.

.. -------------------------------------------------------------

    Alternatives
    ------------

    There is an alternative if the user requires referenced nodes to have constant UUIDs between sessions however they will need to adopt a specific contract accross all of their tools.
    Instead of updating UUIDs upon loading a reference we could rely on 'UUID paths' for all referenced nodes.

    **UUID paths**

    - When a reference is loaded each child scene is loaded with a reference node that tracks changes to referenced nodes within the parent scene.
    - It is therefore possible to create a 'UUID path' which uniquely identifies a referenced node using the UUIDs of each reference node in the referenced node's reference hierarchy.
    - The top reference node is guaranteed to have a unique UUID as it represents the root of a reference hierarchy.

    **Importing References**

    - However when we import a referenced child scene into the parent scene (Reference Editor |xrarr| File |xrarr| Import Objects from Reference), the reference nodes for that child scene are removed.
    - This essentially bakes any changes to referenced nodes that were being tracked by the associated reference nodes.
    - The referenced nodes are not recreated upon importing a reference meaning the UUIDs of each referenced node remain constant.
    - We now have a situation where upon importing duplicate references we will have multiple nodes which share the same UUIDs and have the same 'UUID path'.

    **Solution**

    - Once the reference is imported (see :attr:`OpenMaya.MSceneMessage.kBeforeImportReference`, :attr:`OpenMayaMSceneMessage.kAfterImportReference`) we could update the UUIDs.
    - The trade-off for this solution would mean the user would have to implement UUID paths accross all of their tools making this a highly specialised solution.
    - I have therefore chosen to implement a more generalised solution which results in less overhead for the majority of users.

----------------------------------------------------------------
"""

import functools
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.tools import callback_manager as CBM


# --------------------------------------------------------------
# --- Installation ---
# --------------------------------------------------------------

def isInstalled():
    """
    Returns:
        :class:`bool`: True if the `UUID Manager` is installed, False otherwise.
    """
    return CBM.isCallableRegistered(CBM.SceneEvent.BeforeLoadReference, _beforeLoadReference) \
        and CBM.isCallableRegistered(CBM.SceneEvent.AfterLoadReference, _afterLoadReference)


def install():
    """Install the `UUID Manager`.

    Note:
        Two callables will be registered to the following message events.
        Callbacks for these events will be installed by the :mod:`msTools.tools.callback_manager` if they do not yet exist.

        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kBeforeLoadReference` message.
        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kAfterLoadReference` message.
    """
    log.debug("Installing : {}".format(__name__))

    CBM.registerCallable(CBM.SceneEvent.BeforeLoadReference, _beforeLoadReference)
    CBM.registerCallable(CBM.SceneEvent.AfterLoadReference, _afterLoadReference)


def uninstall():
    """Uninstall the `UUID Manager`.

    Note:
        Two callables will be deregistered from the following message events.
        Callbacks for these events will be uninstalled by the :mod:`msTools.tools.callback_manager` if no other callables are registered.

        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kBeforeLoadReference` message.
        - One corresponding to the :attr:`OpenMaya.MSceneMessage.kAfterLoadReference` message.
    """
    log.debug("Uninstalling : {}".format(__name__))

    CBM.deregisterCallable(CBM.SceneEvent.BeforeLoadReference, _beforeLoadReference)
    CBM.deregisterCallable(CBM.SceneEvent.AfterLoadReference, _afterLoadReference)


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

def _beforeLoadReference():
    _createNodeAddedCallback()


def _afterLoadReference():
    _removeNodeAddedCallback()


def _nodeAddedCallback(node):
    def _deferUuidUpdate(nodeHandle):
        if nodeHandle.isValid() and nodeHandle.isAlive():
            node = nodeHandle.object()
            uuid = om2.MUuid().generate()
            om2.MFnDependencyNode(node).setUuid(uuid)

    nodeHandle = om2.MObjectHandle(node)
    cmds.evalDeferred(functools.partial(_deferUuidUpdate, nodeHandle))


def _createNodeAddedCallback():
    CBM.registerCallable(CBM.DGEvent.NodeAdded, _nodeAddedCallback, receivesCallbackArgs=True)


def _removeNodeAddedCallback():
    CBM.deregisterCallable(CBM.DGEvent.NodeAdded, _nodeAddedCallback)
