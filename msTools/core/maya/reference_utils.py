"""
Reference operations in Maya.

----------------------------------------------------------------

Basics
------

    A reference node is created for each child scene when it is referenced into a parent scene.
    The reference node is responsible for tracking any changes made to the referenced child nodes within the parent scene.
    When a parent scene is referenced into another parent scene, a multi-level hierarchy of references is created.
    The hierarchy of reference nodes tracks changes made to descendant references and allows them to propogate through to the ancestral scenes.

    .. https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2020/ENU/Maya-ManagingScenes/files/GUID-B17150CB-3EF1-49FD-947D-278582F00C8D-htm.html

----------------------------------------------------------------
"""
from maya import cmds
from maya.api import OpenMaya as om2

from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isReference(node):
    """
    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not references a dependency node.

    Returns:
        :class:`bool`: :data:`True` if ``node`` is a reference node, otherwise :data:`False`.
    """
    OM.validateNodeType(node)
    return node.hasFn(om2.MFn.kReference)


def isReferenced(node):
    """
    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not references a dependency node.

    Returns:
        :class:`bool`: :data:`True` if ``node`` is a referenced node, otherwise :data:`False`.
    """
    OM.validateNodeType(node)
    return om2.MFnDependencyNode(node).isFromReferencedFile


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def getReference(referencedNode):
    """Returns the direct reference node for a referenced dependency node.

    Note:
        If ``referencedNode`` is itself a reference node, the parent reference node will be returned.

    Args:
        referencedNode (:class:`OpenMaya.MObject`): Wrapper of a referenced dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``referencedNode`` is not a referenced dependency node.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper for the direct reference node of ``referencedNode``.
    """
    if not isReferenced(referencedNode):
        raise EXC.MayaTypeError("{}: Is not from a referenced file".format(NAME.getNodeFullName(referencedNode)))

    if isReference(referencedNode):
        # If the node is a reference node, this is the fastest option
        referenceFn = om2.MFnReference(referencedNode)
        return referenceFn.parentReference()
    else:
        partialName = NAME.getNodePartialName(referencedNode)
        return OM.getNodeByName(cmds.referenceQuery(partialName, referenceNode=True))


def getTopReference(referencedNode):
    """Return the top level reference node for a referenced dependency node that may be nested within a multi-level reference hierarchy.

    Args:
        referencedNode (:class:`OpenMaya.MObject`): Wrapper of a referenced dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``referencedNode`` is not a referenced dependency node.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper for the top level reference node of ``referencedNode``.
    """
    return getAllReferences(referencedNode)[0]


def getAllReferences(referencedNode):
    """Return the reference node hierarchy of a referenced node that may be nested within a multi-level reference hierarchy.

    Args:
        referencedNode (:class:`OpenMaya.MObject`): Wrapper of a referenced dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``referencedNode`` is not a referenced dependency node.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the reference node hierarchy of ``referencedNode``.
        Ordered from outer reference node --> inner referenced node.
    """
    # Get direct reference node
    referenceNode = getReference(referencedNode)

    # Check if the reference node is a nested reference
    referenceFn = om2.MFnReference()
    referenceNodes = []
    while not referenceNode.isNull():
        referenceNodes.insert(0, referenceNode)
        referenceFn.setObject(referenceNode)
        referenceNode = referenceFn.parentReference()

    return referenceNodes


def getReferencePath(referenceNode, includeCopyNumber=False):
    """Return the filepath associated with the reference file of a reference dependency node.

    The filepath will be resolved, meaning updated since the reference was loaded.

    Args:
        referenceNode (:class:`OpenMaya.MObject`): Wrapper of a reference node.
        includeCopyNumber (:class:`bool`): Whether to include a copy number in the filepath, used to delineate duplicate references.
            The initial reference is not assigned a copy number.
            Duplicate references are assigned a copy number, starting at ``{1}`` for the first duplicate.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``referenceNode`` is not a reference node.

    Returns:
        :class:`str`: Filepath for the loaded reference file of ``referenceNode``.
    """
    OM.validateNodeType(referenceNode, nodeType=om2.MFn.kReference)
    return om2.MFnReference(referenceNode).fileName(resolvedName=True, includePath=False, includeCopyNumber=includeCopyNumber)


def getReferenced(referenceNode):
    """Return the referenced nodes for a reference node.

    Args:
        referenceNode (:class:`OpenMaya.MObject`): Wrapper of a reference node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``referenceNode`` is not a reference node.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Wrappers for the referenced nodes of ``referenceNode``.
    """
    OM.validateNodeType(referenceNode, nodeType=om2.MFn.kReference)
    return list(om2.MFnReference(referenceNode).nodes())
