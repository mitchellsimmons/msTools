"""
UUID related operations in Maya.

----------------------------------------------------------------

Each dependency node in Maya is assigned a UUID.
This value is designed to provide a unique immutable identity for the dependency node.

When a duplicate reference is created multiple dependency nodes will share the same UUID.
It is possible to resolve the uniqueness of a referenced node by inspecting its reference node hierarchy.
However once duplicate references are imported, the ability to resolve uniqueness is lost since the reference node hierarchies are removed.
The problem is produced by the following differences in import behaviours:

- When a `non-referenced` file is imported, each node from the source file is recreated and assigned a new UUID.
- When a `referenced` file is imported, the child scene is effectively baked from a pre-loaded state into the parent scene.
  Each node from the child scene will retain its original UUID in the parent scene.

----------------------------------------------------------------

Note:
    1. In order to use dependency node UUIDs reliably the issue of duplicate references needs to be addressed.
       One such solution is provided by :mod:`msTools.tools.uuid_manager`.

----------------------------------------------------------------
"""
from maya.api import OpenMaya as om2

from msTools.core.maya import exceptions as EXC
from msTools.core.maya import om_utils as OM


# ----------------------------------------------------------------------------
# --- Validation ---
# ----------------------------------------------------------------------------

def isValidUuid(UUID):
    """Return whether a UUID identifies a unique dependency node.

    Args:
        UUID (:class:`basestring`): Universally unique identifier.

    Returns:
        :class:`bool`: :data:`True` if ``UUID`` identifies a dependency node, otherwise :data:`False`.
    """
    try:
        getNodeFromUuid(UUID)
    except EXC.MayaLookupError:
        return False
    else:
        return True


# ----------------------------------------------------------------------------
# --- Retrieve ---
# ----------------------------------------------------------------------------

def getUuidFromNode(node):
    """Return the UUID assigned to a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`str`: UUID assigned to ``node``.
    """
    OM.validateNodeType(node)

    nodeDepFn = om2.MFnDependencyNode(node)
    return nodeDepFn.uuid().asString()


def getNodeFromUuid(UUID):
    """Return the dependency node identified by a UUID.

    Args:
        UUID (:class:`basestring`): Universally unique identifier.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``UUID`` does not identify exactly one dependency node.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of the dependency node identified by ``UUID``.
    """
    selection = om2.MSelectionList()

    try:
        selection.add(om2.MUuid(UUID))
    except RuntimeError:
        raise EXC.MayaLookupError("{} : UUID does not correspond to an existing node".format(UUID))

    # If there are duplicate references there will be duplicate UUIDs
    if selection.length() == 1:
        return selection.getDependNode(0)
    else:
        raise EXC.MayaLookupError("{} : UUID is assigned to multiple nodes".format(UUID))
