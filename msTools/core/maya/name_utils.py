"""
Name related operations in Maya.

----------------------------------------------------------------

Terminology
-----------

    The following terminology is adopted by this module and other modules within this package.

    .. list-table::
       :widths: 25 75
       :header-rows: 1

       * - Term
         - Description
       * - `Short Name`
         - The short name of an object represents its minimum internal name. It is not affected by ancestral or namespace information.
       * - `Long Name`
         - The long name of an object represents its maximum internal name. It is not affected by ancestral or namespace information.
       * - `Partial Name`
         - The partial name of an object represents the minimum amount of information necessary to uniquely identify the object.
       * - `Full Name`
         - The full name of an object represents the maximum amount of information that can be provided to identify the object.

----------------------------------------------------------------
"""
import re

from maya.api import OpenMaya as om2

import msTools


# --------------------------------------------------------------
# --- Retrieve : Attribute ---
# --------------------------------------------------------------

def getAttributeName(attribute):
    """Return the name of an attribute.

    Args:
        attribute (:class:`OpenMaya.MObject`): Wrapper of an attribute.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attribute`` does not reference an attribute.

    Returns:
        :class:`str`: Name of ``attribute``.
    """
    msTools.core.maya.om_utils.validateAttributeType(attribute)

    return om2.MFnAttribute(attribute).name


# --------------------------------------------------------------
# --- Retrieve : Node ---
# --------------------------------------------------------------

def getNodeShortName(node):
    """Return the short name of a node.

    The short name of a node has no qualifying path or namespace.
    It is not guaranteed to uniquely identify the node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`str`: The short name of ``node``.
    """
    return getNodePartialName(node).split('|')[-1].split(':')[-1]


def getNodePartialName(node):
    """Return the partial name of a node.

    The partial name of a node is qualified by a path and namespace where applicable or necessary.
    It is guaranteed to uniquely identify the node with the minimum amount of information necessary (partial path for the first occurrence of a DAG node).

    If ``node`` does not reference a DAG node, the partial name is equivalent to its full name.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`str`: The partial name of ``node``.
    """
    msTools.core.maya.om_utils.validateNodeType(node)

    if node.hasFn(om2.MFn.kDagNode):
        return om2.MDagPath.getAPathTo(node).partialPathName()
    else:
        return om2.MFnDependencyNode(node).name()


def getNodeFullName(node):
    """Return the full name of a node.

    The full name of a node is qualified by a path and namespace where applicable.
    It is guaranteed to uniquely identify the node with the maximum amount of information (full path for the first occurrence of a DAG node).

    If ``node`` does not reference a DAG node, the full name is equivalent to its partial name.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Returns:
        :class:`str`: The full name of ``node``.
    """
    msTools.core.maya.om_utils.validateNodeType(node)

    if node.hasFn(om2.MFn.kDagNode):
        return om2.MDagPath.getAPathTo(node).fullPathName()
    else:
        return om2.MFnDependencyNode(node).name()


# --------------------------------------------------------------
# --- Retrieve : Plug ---
# --------------------------------------------------------------

def getPlugPartialName(plug, includeNodeName=True):
    """Return the partial name of a plug with format ``'<plug>'`` or ``'<node>.<plug>'``.

    - ``<node>`` is the partial node name of ``plug`` qualified by a path and namespace where applicable or necessary.
      It is guaranteed to uniquely identify the node with the minimum amount of information necessary (partial path for the first occurrence of a DAG node).
    - ``<plug>`` is guaranteed to uniquely identify ``plug`` with the minimum amount of information necessary (short attribute path, short attribute names).

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        includeNodeName(:class:`bool`): Whether to include the partial node name in the partial plug name. Defaults to :data:`True`.

    Returns:
        :class:`str`: The partial name of ``plug``.
    """
    if includeNodeName:
        nodeName = getNodePartialName(plug.node())
        plugName = plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True)
        return '.'.join([nodeName, plugName])
    else:
        return plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True)


def getPlugFullName(plug, includeNodeName=True):
    """Return the full name of a plug with format ``'<plug>'`` or ``'<node>.<plug>'``.

    - ``<node>`` is the full node name of ``plug`` qualified by a path and namespace where applicable.
      It is guaranteed to uniquely identify the node with the maximum amount of information (full path for the first occurrence of a DAG node).
    - ``<plug>`` is guaranteed to uniquely identify ``plug`` with the maximum amount of information (full attribute path, long attribute names).

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        includeNodeName(:class:`bool`): Whether to include the full node name in the full plug name. Defaults to :data:`True`.

    Returns:
        :class:`str`: The full name of ``plug``.
    """
    if includeNodeName:
        plugName = plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True, useLongNames=True, useFullAttributePath=True)
        nodeName = getNodeFullName(plug.node())
        return '.'.join([nodeName, plugName])
    else:
        return plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True, useLongNames=True, useFullAttributePath=True)


def getPlugStorableName(plug, includeNodeName=True):
    """Return a storable name for a plug with format ``'<plug>'`` or ``'<node>__<plug>'``.

    - ``<node>`` is the short node name of ``plug``.
      It has no qualifying path or namespace and is not guaranteed to uniquely identify the node.
    - ``<plug>`` will represent the short attribute path of ``plug``, with format ``'array_0__child'``.
      A single underscore will be used to seperate an attribute name from its associated logical index if there is an array attribute in the path.
      Two underscores will be used to seperate attributes if there are child attributes in the path.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        includeNodeName(:class:`bool`): Whether to include the short node name in the storable plug name. Defaults to :data:`True`.

    Returns:
        :class:`str`: The storable name of ``plug``.
    """
    plugName = plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True)
    plugNameTokens = plugName.split(".")
    attrNames = [re.findall(r'^\w*', plugNameToken) for plugNameToken in plugNameTokens]
    attrIndices = [re.findall(r'\[(\d+)\]', plugNameToken) for plugNameToken in plugNameTokens]
    plugPath = "__".join(["_".join(attrName + attrIndex) for attrName, attrIndex in zip(attrNames, attrIndices)])

    if includeNodeName:
        nodeName = getNodeShortName(plug.node())
        return "__".join([nodeName, plugPath])
    else:
        return plugPath
