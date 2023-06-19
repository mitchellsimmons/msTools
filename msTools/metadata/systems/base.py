"""
A base level metadata system providing the framework for higher level interfaces.

----------------------------------------------------------------

Interfaces
----------

    There are two base level dependency node interfaces provided by this module:

    - :class:`Meta`: Associates low level operations with an encapsulated dependency node. Implements a registration system for persistent identification of metadata.
    - :class:`MetaDag`: Associates low level operations with an encapsulated DAG node. Inherits from :class:`Meta`.

    There are three base level dependency node plug interfaces provided by this module:

    - :class:`MetaAttribute`: Associates low level operations with an encapsulated dependency node plug. Designed to interface with the above dependency node encapsulations.
    - :class:`MetaArrayAttribute`: Associates low level operations with an encapsulated dependency node array plug. Inherits from :class:`MetaAttribute`.
    - :class:`MetaCompoundAttribute`: Associates low level operations with an encapsulated dependency node non-array compound plug. Inherits from :class:`MetaAttribute`.

----------------------------------------------------------------

Terminology
-----------

    The following terminology is adopted by this module and other modules within this package.

    .. list-table::
       :widths: 25 75
       :header-rows: 1

       * - Term
         - Description
       * - `nodeId`
         - The UUID that is assigned to a dependency node upon creation.
       * - `mNode`
         - An instantiated (non-strict) subclass of :class:`Meta`. Provides a metadata encapsulation of a dependency node.
       * - `mType`
         - A (non-strict) subclass of :class:`Meta`.
       * - `mTypeId`
         - The name of a (non-strict) subclass of :class:`Meta`.
           Used with an `mSystemId` to register an `mNode` or identify the `mType` of a tagged dependency node.
       * - `mSystem`
         - A system of related `mTypes` that can be used to build a network or hierarchy of tagged dependency nodes.
           Provides the ability to register metadata within a persistent framework that associates a programatic interface with a contractual system of dependency nodes.
       * - `mSystemId`
         - The name of an `mSystem`, assigned to each `mType` via its :attr:`~Meta.SYSTEM_ID` attribute.
           Used with an `mTypeId` to register an `mNode` or identify the `mType` of a tagged dependency node.
       * - `mSystemRoot`
         - A property assigned to each `mType` via its :attr:`~Meta.SYSTEM_ROOT` attribute.
           Defines whether an `mType` is the root of an `mSystem`, used for identifying tagged dependency nodes.
       * - `mAttr`
         - An instantiated (non-strict) subclass of :class:`MetaAttribute`.
           Provides an encapsulation of a dependency node plug which has been designed to interface with `mNodes`.

----------------------------------------------------------------

Registration
------------

    The :class:`Meta` :ref:`registration <Meta_registration>` system allows for the persistent association of an `mType` with a dependency node,
    enabling `mNode` retrieval for tagged dependency nodes.

----------------------------------------------------------------

.. _systems:

Systems
-------

    Higher level `mSystems` such as :mod:`msTools.metadata.systems.mrs` should be used to build a network or hierarchy of tagged dependency nodes.
    This should provide the ability to register metadata within a persistent framework that associates a programatic interface with a contractual system of dependency nodes.
    The contracts which were used to create the system of dependency nodes should allow the `mSystem` to generalize accross different setups.
    For example a modular rigging system should define certain contracts which would allow an `mSystem` to register metadata for different setups.

----------------------------------------------------------------
"""
import collections
import inspect
import itertools
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.vendor import decorator

from msTools.core.maya import exceptions as EXC
from msTools.core.maya import attribute_utils as ATTR
from msTools.core.maya import component_utils as COMPONENT
from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import dag_utils as DAG
from msTools.core.maya import dg_utils as DG
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM
from msTools.core.maya import plug_utils as PLUG
from msTools.core.maya import reference_utils as REF
from msTools.core.maya import uuid_utils as UUID

from msTools.core.py import metaclasses as PY_META
from msTools.core.py import class_utils as PY_CLASS

from msTools.tools import uuid_manager


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

# Resets on any module reload (not import), file open, file new callback : _resetMNodeRegistryCallback()
if "_META_NODE_REGISTRY" in globals():
    log.debug("Clearing mNode registry")
else:
    log.debug("Initializing global: _META_NODE_REGISTRY")

_META_NODE_REGISTRY = {}

# Prevents reset on reload
if "_META_CALLBACKS" not in globals():
    log.debug("Initializing global: _META_CALLBACKS")
    _META_CALLBACKS = {}
    _META_CALLBACKS['Open'] = None
    _META_CALLBACKS['New'] = None


# ----------------------------------------------------------------------------
# --- Exceptions ---
# ----------------------------------------------------------------------------

class MTypeError(Exception):
    """Raised for operations which involve an invalid or incompatible `mType`."""


class MSystemError(Exception):
    """Raised for operations which involve an invalid or incompatible `mSystem`."""


# ----------------------------------------------------------------------------
# --- Decorators ---
# ----------------------------------------------------------------------------

@decorator.decorator
def unlockMeta(func, *args, **kwargs):
    """Decorator used to unlock the dependency node of an `mNode` or `mAttr`.

    Registered `mNodes` are locked to account for the following deletion issues:

    - Deleting connected network nodes will delete the entire network.
    - Calling :func:`cmds.cutKey` on a keyframed attribute of a network node will delete the node if it has no other connections.
    """
    self = args[0]
    isLocked = self.nodeFn.isLocked

    if isLocked:
        DG.unlockNode(self.node)

    try:
        return func(*args, **kwargs)
    except StandardError:
        raise
    finally:
        if isLocked:
            DG.lockNode(self.node)


# ----------------------------------------------------------------------------
# --- mType (Meta Type) ---
# ----------------------------------------------------------------------------

def getMSystemRegistry():
    """Returns a registry that maps registered `mTypes` to their corresponding `mSystemId` and `mTypeId`.
    Provides centralised access to all registered :class:`Meta` subclasses.

    Returns:
        :class:`collections.namedtuple`: Where each field is an `mSystemId` that maps to another :class:`collections.namedtuple`,
        where each field is an `mTypeId` that maps to a registered `mType`.

    Example:
        .. code-block:: python

            # Access mTypes for the all mSystems
            mSystems = getMSystemRegistry()
            # Access an mType via an mSystem
            assert mSystems.base.Meta is Meta
            # Access the mType registry for an mSystem
            assert mSystems.base == getMTypeRegistry('base')
            # Retrieve tagged dependency nodes for each mSystem
            for mSystemId, mTypes in mSystems.__dict__.iteritems():
                assert list(iterMetaNodes(mSystemIds=(mSystemId,))) == list(iterMetaNodes(mTypes=mTypes))
    """
    mSystemMapping = collections.defaultdict(dict)

    for cls in PY_CLASS.iterSubclasses(Meta, strict=False):
        mSystemMapping[cls.SYSTEM_ID][cls.__name__] = cls

    for mSystemId, mTypeMapping in mSystemMapping.iteritems():
        MTypeRegistry = collections.namedtuple('MTypeRegistry', mTypeMapping.keys())
        mSystemMapping[mSystemId] = MTypeRegistry(**mTypeMapping)

    MSystemRegistry = collections.namedtuple('MSystemRegistry', mSystemMapping.keys())
    return MSystemRegistry(**mSystemMapping)


def getMTypeRegistry(mSystemId):
    """Returns a registry that maps registered `mTypes` to their corresponding `mTypeId` for a given `mSystemId`.
    Provides centralised access to all registered :class:`Meta` subclasses for an `mSystem`.

    Raises:
        :exc:`MSystemError`: If ``mSystemId`` does not correspond to a registered `mSystem`. Meaning there are no registered mTypes for that ``mSystemId``.

    Returns:
        :class:`collections.namedtuple`: Where each field is an `mTypeId` that maps to a registered `mType`.

    Example:
        .. code-block:: python

            # Access mTypes for the 'base' mSystem
            mTypes = getMTypeRegistry('base')
            # Access an mType from the 'base' mSystem
            assert mTypes.Meta is Meta
            # Retrieve tagged dependency nodes for the 'base' mSystem
            assert list(iterMetaNodes(mSystemIds=('base',))) == list(iterMetaNodes(mTypes=mTypes))
    """
    try:
        return getattr(getMSystemRegistry(), mSystemId)
    except AttributeError:
        raise MSystemError("{}: Is not a registered mSystem".format(mSystemId))


def getMTypeInheritance(mType):
    """Returns a :class:`collections.namedtuple` object where each field maps to a registered `mType` that inherits from the given ``mType``.

    Args:
        mType (:class:`type`): A (non-strict) subclass of :class:`Meta`.

    Returns:
        :class:`collections.namedtuple`: Where each field is an `mType` name that maps to a registered subclass of ``mType``.
    """
    mapping = {}

    for cls in PY_CLASS.iterSubclasses(mType):
        mapping[cls.__name__] = cls

    MTypeRegistry = collections.namedtuple('MTypeRegistry', mapping.keys())
    return MTypeRegistry(**mapping)


def getMTypeFromIds(mSystemId, mTypeId):
    """Return the `mType` identified by an `mTypeId` and `mSystemId`.

    Args:
        mSystemId (:class:`basestring`): Identifier for a registered `mSystem`.
        mTypeId (:class:`basestring`): Identifier for a registered `mType`.

    Raises:
        :exc:`MSystemError`: If `mSystemId` does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If `mTypeId` does not correspond to a registered `mType` for its `mSystem`.

    Returns:
        :class:`type`: A (non-strict) subclass of :class:`Meta` corresponding to a registered `mType`.
    """
    try:
        return getattr(getMTypeRegistry(mSystemId), mTypeId)
    except AttributeError:
        raise MTypeError("{}: Is not a registered mType of the mSystem: {}".format(mTypeId, mSystemId))


def getMTypeFromNode(node):
    """Return the `mType` of a tagged dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node that has an `mSystemId` and `mTypeId` attribute.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``node`` is not tagged with `mSystemId` and `mTypeId` attributes.
        :exc:`MSystemError`: If the `mSystemId` of ``node`` does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If the `mTypeId` of ``node`` does not correspond to a registered `mType` for its `mSystem`.

    Returns:
        :class:`type`: A (non-strict) subclass of :class:`Meta` corresponding to the `mType` of ``node``.
    """
    mSystemIdPlug = OM.getPlugFromNodeByName(node, "mSystemId")
    mTypeIdPlug = OM.getPlugFromNodeByName(node, "mTypeId")
    mSystemId = PLUG.getValue(mSystemIdPlug)
    mTypeId = PLUG.getValue(mTypeIdPlug)
    return getMTypeFromIds(mSystemId, mTypeId)


# ----------------------------------------------------------------------------
# --- nType (Node Type) ---
# ----------------------------------------------------------------------------

def getNodeTypeConstants(mTypes=None):
    """Return the node type constants used to filter searches for tagged and registered `mNodes`.

    Args:
        mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, from which to retrieve node type constants.
            Defaults to :data:`None` - retrieve constants from all registered `mTypes`.

    Returns:
        list [:class:`int`]: Node type constants for the given ``mTypes`` or for each registered `mType` if ``mTypes`` is :data:`None`.
    """
    nodeTypeConstants = set()

    for mType in mTypes or itertools.chain.from_iterable(list(getMSystemRegistry())):
        nodeTypeConstants.add(mType.NODE_TYPE_CONSTANT)

    return list(nodeTypeConstants)


# ----------------------------------------------------------------------------
# --- _META_NODE_REGISTRY ---
# ----------------------------------------------------------------------------

def getMNodeFromRegistry(node):
    """Returns the registered `mNode` encapsulation of a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`~exceptions.KeyError`: If there is no `mNode` registered to the UUID of ``node``.

    Returns:
        T <= :class:`Meta`: The registered `mNode` encapsulation of ``node``.
    """
    uuid = UUID.getUuidFromNode(node)

    try:
        mNode = _META_NODE_REGISTRY[uuid]
    except KeyError:
        raise KeyError("{}: Dependency node does not have a registered mNode".format(NAME.getNodeFullName(node)))
    else:
        if mNode.isValid:
            if mNode.node == node:
                log.debug("{!r}: Returning registered mNode".format(mNode))
                return mNode
            else:
                log.warning("{!r}: Found mNode registered to a different nodeId, cleaning the registry".format(mNode))
                # The mNode will be removed since this behaviour is unexpected (even if a mNode's UUID changes, it should never be registered to the UUID of another node)
                cleanMNodeRegistry()
        else:
            log.debug("{!r}: Found invalid mNode, cleaning the registry".format(mNode))
            # The mNode will be revalidated since the node is valid
            cleanMNodeRegistry()

        try:
            mNode = _META_NODE_REGISTRY[uuid]
        except KeyError:
            raise KeyError("{}: Dependency node does not have a registered mNode".format(NAME.getNodeFullName(node)))
        else:
            log.debug("{!r}: Returning registered mNode from cleaned registry".format(mNode))
            return mNode


def cleanMNodeRegistry():
    """Remove invalid items from the internal `mNode` registry.

    Attempts to revalidate any invalid `mNode` using its cached `nodeId`.
    Ensures the each registered `mNode` is registered under its cached `nodeId`.
    Ensures the tag of each registered `mNode` is valid.
    """
    global _META_NODE_REGISTRY

    # Iterate once using the items method instead of iteritems as keys may be altered
    # - Any invalid mNode will be removed from the registry (ie. nodeId invalid or not unique)
    # - Any mNode whose dependency node has had its UUID changed will be re-registered under its new nodeId
    for nodeId, mNode in _META_NODE_REGISTRY.items():
        try:
            mNode.nodeId
        except EXC.MayaObjectError:
            pass

    # Iterate once more to verify the registry interface has been respected
    # - Remove or replace any mNode that has been manually registered under an invalid key
    # - Remove any mNode whose dependency node is tagged with an invalid mTypeId
    for nodeId, mNode in _META_NODE_REGISTRY.items():
        if nodeId != mNode._nodeId:
            del _META_NODE_REGISTRY[nodeId]

            try:
                mNode.nodeId
            except EXC.MayaObjectError:
                log.warning("{!r}: Deregistered invalid mNode from invalid nodeId: {}".format(mNode, nodeId))
            else:
                log.warning("{!r}: Deregistered valid mNode from invalid nodeId: {}".format(mNode, nodeId))

                if mNode.hasValidTag:
                    mNode.register()

        elif not mNode.hasValidTag():
            del _META_NODE_REGISTRY[nodeId]
            log.warning("{!r}: Deregistered mNode for dependency node with invalid mTypeId".format(mNode))


def _resetMNodeRegistryCallback(*clientData):
    """Resets the internal `mNode` registry. Called after `MSceneMessage` Open/New (_META_CALLBACKS)."""
    log.debug("Clearing mNode registry due to 'File -> Open' or 'File -> New'")
    global _META_NODE_REGISTRY
    _META_NODE_REGISTRY = {}


def resetMNodeRegistry():
    """Reset the internal `mNode` registry."""
    log.debug("Clearing mNode registry")
    global _META_NODE_REGISTRY
    _META_NODE_REGISTRY = {}


def inspectMNodeRegistry():
    """Log each registered mapping of `nodeId` -> `mNode`."""
    cleanMNodeRegistry()
    for nodeId, mNode in _META_NODE_REGISTRY.items():
        log.info("{}: {!r}".format(nodeId, mNode))


# ----------------------------------------------------------------------------
# --- Meta Node (mNode) ---
# ----------------------------------------------------------------------------

def getMNode(node):
    """Return an `mNode` encapsulation of a dependency node.

    The `mType` of the `mNode` will be determined as follows:

    - If ``node`` is tagged, its `mTypeId` and `mSystemId` will be used to determine the `mType`.
    - If ``node`` is untagged, its node type will be used to determine a default `mType` that provides an appropriate level of functionality for the node.
      :class:`Meta` provides functionality to non-DAG nodes whilst :class:`MetaDag` provides functionality to DAG nodes.

    Note:
        An `mNode` will be returned from the internal registry if ``node`` is tagged and registered.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`MSystemError`: If ``node`` is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If ``node`` is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

    Returns:
        T <= :class:`Meta`: An `mNode` encapsulation of ``node`` for a (non-strict) subclass of :class:`Meta`.
    """
    try:
        mType = getMTypeFromNode(node)
    except EXC.MayaLookupError:
        mType = MetaDag if node.hasFn(om2.MFn.kDagNode) else Meta

    # The mType constructor will check the registry for an mNode of this mType
    return mType(node)


def getMNodeFromPath(path):
    """Return an `mNode` encapsulation of a DAG node for a specific ancestral path.

    The `mType` of the `mNode` will be determined as follows:

    - If the DAG node referenced by ``path`` is tagged, its `mTypeId` and `mSystemId` will be used to determine the `mType`.
    - If the DAG node referenced by ``path`` is untagged, :class:`MetaDag` will be used as a default `mType`.

    Note:
        An `mNode` will be returned from the internal registry if the DAG node referenced by ``path`` is tagged and registered.

    Args:
        path (:class:`OpenMaya.MDagPath`): Path to a DAG node.

    Raises:
        :exc:`MSystemError`: If the DAG node referenced by ``path`` is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If the DAG node referenced by ``path`` is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

    Returns:
        T <= :class:`MetaDag`: An `mNode` encapsulation of ``path`` for a (non-strict) subclass of :class:`MetaDag`.
    """
    node = path.node()

    try:
        mType = getMTypeFromNode(node)
    except EXC.MayaLookupError:
        mType = MetaDag

    return mType(path)


def iterMetaNodes(nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
    """Yield tagged dependency nodes in the scene. Filter based on the given properties.

    Args:
        nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
            Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
            Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
        mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
            Only consider dependency nodes which are tagged with an `mTypeId` and `mSystemId` corresponding to one of the given `mTypes`.
            Defaults to :data:`None` - no `mType` filtering will occur.
        mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
            Only consider dependency nodes which are tagged with an `mTypeId` and `mSystemId` corresponding to an `mType` that inherits from one of the given `mTypes`.
            Defaults to :data:`None` - no `mType` inheritance filtering will occur.
        mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
            Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
            Defaults to :data:`None` - no `mSystemId` filtering will occur.
        mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
            Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
        asMeta (:class:`bool`, optional): Whether to yield each tagged dependency node as an `mNode` of its tagged `mType`. Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

    Raises:
        :exc:`MSystemError`: If the `mSystemId` of a tagged dependency node does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If the `mTypeId` of a tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

    Yields:
        :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrappers or `mNode` encapsulations for tagged dependency nodes. Type is determined by ``asMeta``.
    """
    nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)

    for node in DG.iterNodes(nTypes):
        try:
            mType = getMTypeFromNode(node)
        except EXC.MayaLookupError:
            continue

        if mTypes is not None:
            if mType not in mTypes:
                continue

        if mTypeBases is not None:
            for mTypeBase in mTypeBases:
                if mTypeBase != mType and issubclass(mType, mTypeBase):
                    break
            else:
                continue

        if mSystemIds is not None:
            if mType.SYSTEM_ID not in mSystemIds:
                continue

        if mSystemRoots:
            if not mType.SYSTEM_ROOT:
                continue

        yield mType(node) if asMeta else node


# ----------------------------------------------------------------------------
# --- Meta Attribute (mAttr) ---
# ----------------------------------------------------------------------------

def getMAttr(plug):
    """Return an `mAttr` encapsulation of a dependency node plug. The encapsulation is designed to provide an appropriate level of functionality for the plug.

    The type of the `mAttr` will be determined as follows:

    - :class:`MetaArrayAttribute` if ``plug`` references an array attribute of any type.
    - :class:`MetaCompoundAttribute` if ``plug`` references a non-array compound type attribute.
    - :class:`MetaAttribute` for any other ``plug``.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

    Returns:
        T <= :class:`MetaAttribute`: An `mAttr` encapsulation of ``plug`` for a (non-strict) subclass of :class:`MetaAttribute`.
    """
    if plug.isArray:
        return MetaArrayAttribute(plug)
    elif plug.isCompound:
        return MetaCompoundAttribute(plug)

    return MetaAttribute(plug)


# ----------------------------------------------------------------------------
# --- _MetaClass ---
# ----------------------------------------------------------------------------

class _MetaClass(
        PY_META.MetaAccessWrapperFactory(
            wrapFunctions=True,
            wrapPropertyGetters=True,
            wrapPropertySetters=True,
            wrapPropertyDeleters=True,
            wrapExclusions=("__init__", "__repr__", "__setattr__", "_createNode", "_validate", "isValid")
        )):
    """The metaclass used exclusively by (non-strict) subclasses of :class:`Meta`."""

    def __new__(metaCls, mTypeId, bases, namespace):
        """Metaclass constructor for instantiating `mType` classes.

        - Completes basic validation of the `mType` interface.
        - Adds an `ALL_EXCLUSIVE` attribute to the namespace of the `mType` to store the names of exclusive attributes from all (non-strict) subclasses.
        - Wraps instance methods and data descriptor methods in a pre and post access wrapper.
        """
        log.debug("_MetaClass.__new__(metaCls={}, mTypeId={}, bases={}, namespace={})".format(metaCls, mTypeId, bases, namespace))

        if mTypeId != "Meta" and Meta not in itertools.chain(*[base.__mro__ for base in bases]):
            raise TypeError("{}: metaclass is designed for (non-strict) subclasses of {}".format(metaCls, Meta))

        nTypeId = namespace.get("NODE_TYPE_ID")
        if nTypeId is not None and nTypeId.id() == 0:
            raise ValueError("{}: {}.NODE_TYPE_ID does not correspond to a valid {}".format(nTypeId, mTypeId, om2.MTypeId))

        if namespace.get("__init__"):
            initialiserArgs = inspect.getargspec(namespace["__init__"])[0]
            if len(initialiserArgs) < 2 or initialiserArgs[1] != "node":
                raise RuntimeError("{}: mType initialiser must define signature with 'node' as its first user argument".format(mTypeId))

        exclusive = namespace.get("EXCLUSIVE")
        if exclusive is not None:
            if "mTypeId" in exclusive:
                raise ValueError("'mTypeId' attribute is reserved for dependency nodes and must not be included in the {}.EXCLUSIVE set of attributes".format(mTypeId))
            if "mSystemId" in exclusive:
                raise ValueError("'mSystemId' attribute is reserved for dependency nodes and must not be included in the {}.EXCLUSIVE set of attributes".format(mTypeId))

        allExclusive = set(exclusive or [])
        if bases[0] is not PY_META.AbstractAccessWrapper:
            allExclusive.update(bases[0].ALL_EXCLUSIVE)

        namespace["ALL_EXCLUSIVE"] = allExclusive

        mType = super(_MetaClass, metaCls).__new__(metaCls, mTypeId, bases, namespace)

        return mType

    def __call__(cls, *args, **kwargs):
        """Handles instantiation and initialisation of `mNodes`.

        - If a registered `mNode` is returned from the constructor, its initialiser will be bypassed.
        """
        mNode, isRegistered = cls.__new__(cls, *args, **kwargs)

        if isinstance(mNode, cls):
            if not isRegistered:
                mNode.__init__(*args, **kwargs)

        return mNode


# ----------------------------------------------------------------------------
# --- Meta ---
# ----------------------------------------------------------------------------

class Meta(PY_META.AbstractAccessWrapper):
    """A dependency node encapsulation designed to provide base level metadata functionality to higher level `mSystem` abstractions.

    **Interface:**

        The encapsulation associates a low level interface with the node, similiar to that of an `OpenMaya`_ function set.
        The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

        Typically higher level `mSystems` may define specific relationships between their `mTypes`.
        These relationships can be registered within the dependency graph for type specific identification of metadata.

    .. _Meta_registration:

    **Registration:**

        A persistent tagging system enables an `mType` to be associated with a dependency node:

        - When an `mNode` is registered, its `mType` and `mSystem` are used to tag the encapsulated dependency node with `mTypeId` and `mSystemId` attributes.
          The `mNode` is added to an internal registry for optimised retrieval within the current session.
          If the user attempts to instantiate the same `mType` with the same dependency node, the registered `mNode` will be returned.
        - When an `mNode` is deregistered, its `mType` is disassociated from its encapsulated dependency node by removing the `mTypeId` and `mSystemId` attributes.
          The `mNode` is removed from the internal registry.

        An `mNode` can only be registered if :attr:`isRegisterable` returns :data:`True`.

    .. _Meta_attributes:

    **Attributes:**

        The ability to modify the namespace of an `mNode` is restricted in order to preserve the following behaviours:

        - When retrieving attributes, the encapsulated dependency node will only be queried if there is no class/instance attribute.
        - When setting attributes, the encapsulated dependency node will be accessed if the attribute is not registered as exclusive to the `mNode`.

    .. _Meta_validation:

    **Validation:**

        The interface provides the option to track the state of the encapsulated dependency node.
        When tracking is enabled, an :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.

    .. _Meta_subclassing:

    **Subclassing:**

        Derived `mTypes` should be implemented as part of a :ref:`system <systems>`.

        The following attributes can be overridden to define the `mSystem` properties of an `mType`:

        - :attr:`SYSTEM_ID`: Define the `mSystem` of an `mType`.
        - :attr:`SYSTEM_ROOT`: Define whether the `mType` is an `mSystemRoot`.

        The following attributes can be overridden to define which node types are compatible with the interface of an `mType`:

        - :attr:`NODE_TYPE_CONSTANT`: Define which :class:`OpenMaya.MFn` node type constants are compatible with the interface.
          The node type compatibility of derived `mTypes` must be limited by baseclass compatibility. Do not widen the compatibility of a derived `mType`.
        - :attr:`NODE_TYPE_ID`: Define a single node type which is compatible with the interface.
          If :data:`None`, the :attr:`NODE_TYPE_CONSTANT` is used instead.

        The :attr:`NODE_TYPE_CONSTANT` is also used to optimise the search for tagged dependency nodes.
        It must be implemented even if the :attr:`NODE_TYPE_ID` is assigned.

        The :attr:`EXCLUSIVE` attribute must be overridden by any subclass which implements its own exclusive data.
        The override only needs to include the names of property setters and instance attributes which are defined within the subclass implementation.

        Derived `mTypes` which implement their own initialiser must:

        - Invoke the baseclass initialiser.
        - Enforce an initial ``node`` argument within the signature, used to identify a dependency node via an :class:`OpenMaya.MObject` wrapper.
          The argument must be defined positionally within the signature in order to be accessible from :meth:`__new__`.
    """
    __metaclass__ = _MetaClass

    SYSTEM_ID = "base"
    """:class:`basestring`: Defines the `mSystemId` of this `mType`, used as a property for registering `mNodes` and identifying tagged dependency nodes.

    :access: R
    """

    SYSTEM_ROOT = False
    """:class:`bool`: Defines whether this `mType` is the root of an `mSystem`, used as a property for identifying tagged dependency nodes.

    :access: R
    """

    NODE_TYPE_CONSTANT = om2.MFn.kDependencyNode
    """:class:`int`: Defines which :class:`OpenMaya.MFn` dependency node types are compatible with this `mType`.

    Type compatibility is determined by calling :meth:`~OpenMaya.MObject.hasFn` on an :class:`OpenMaya.MObject` wrapper of the dependency node.

    :access: R
    """

    NODE_TYPE_ID = None
    """:class:`OpenMaya.MTypeId` | :data:`None`: Allows subclasses to define a single dependency node type that is compatible with their `mType`.

    Designed for node types which are not associated with a specific :class:`OpenMaya.MFn` type constant such as those derived from :class:`OpenMaya.MPxNode`.

    :access: R
    """

    EXCLUSIVE = set(["_node", "_nodeHandle", "_nodeFn", "_nodeId", "_partialName", "_stateTracking", "stateTracking", "notes"])
    """:class:`set` [:class:`str`]: Defines exclusive instance attributes which can be set using the default :meth:`object.__setattr__` behaviour.

    - Includes the names of property setters defined by this `mType`.
    - Includes the names of instance attributes which are assigned to an `mNode` via :meth:`__init__`.

    Invoking :meth:`__setattr__` with a non-exclusive attribute will attempt to access the attribute via the encapsulated dependency node.

    :access: R
    """

    # --- Instantiation ----------------------------------------------------------------------------

    def __new__(cls, *args, **kwargs):
        """Base constructor for any `mType` that is not a (non-strict) subclass of :class:`MetaDag`.

        If a dependency node is received, the internal registry will be checked for an `mNode` with the same encapsulated dependency node and derived `mType`.
        A new `mNode` will be constructed for the dependency node if the registry does not contain a matching `mNode`.

        If no dependency node is given, an empty `mNode` will be constructed and assigned a new dependency node.
        """
        # The metaclass ensures that if an mType is called with positional args, the first argument will always be the node
        node = kwargs.get("node", args[0] if args else None)

        if node is not None:
            OM.validateNodeType(node, nodeType=cls.NODE_TYPE_CONSTANT, nodeTypeId=cls.NODE_TYPE_ID)

            try:
                mNode = getMNodeFromRegistry(node)
            except KeyError:
                pass
            else:
                if type(mNode) is cls:
                    # The second value indicates whether the metaclass should bypass the initialiser
                    return mNode, True

        mNode = object.__new__(cls, *args, **kwargs)

        if node:
            object.__setattr__(mNode, "_node", node)

        return mNode, False

    def __init__(self, node=None, name=None, nType="network", register=False, stateTracking=True):
        """Base initialiser for all `mNodes`.

        Args:
            node (:class:`OpenMaya.MObject`, optional): Wrapper of a dependency node to encapsulate.
                Defaults to :data:`None` - A new dependency node will be created using the ``nType``.
            name (:class:`basestring`, optional): Name for the new dependency node if ``node`` is :data:`None`.
                Defaults to :data:`None` - The `mTypeId` will be used.
            nType (:class:`basestring`, optional): Node type identifier used to create a dependency node if ``node`` is :data:`None`.
                If the node type derives from a shape, its transform will be encapsulated. Defaults to ``'network'``.
            register (:class:`bool`, optional): Whether to register this `mNode` internally,
                tagging the encapsulated dependency node with the `mTypeId` and `mSystemId` of the derived `mType`. Defaults to :data:`False`.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated dependency node.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``nType`` is an invalid node type identifier or is incompatible with the accepted node types of the derived `mType`.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` references a dependency node whose type is incompatible with the accepted node types of the derived `mType`.
            :exc:`MTypeError`: If an attempt is made to register a DAG node to an `mType` that is not a (non-strict) subclass of :class:`MetaDag`.
        """
        log.debug("Meta.__init__(node={}, name={}, nType={}, register={}, stateTracking={})".format(node, name, nType, register, stateTracking))

        # Create a node if one has not been provided by the caller, including by potential subclass callers
        try:
            object.__getattribute__(self, "_node")
        except AttributeError:
            object.__setattr__(self, "_node", self._createNode(nType, name))

        # Bind exclusive data
        self._nodeHandle = om2.MObjectHandle(self._node)
        self._nodeFn = om2.MFnDependencyNode(node)
        self._nodeId = UUID.getUuidFromNode(self._node)
        self._partialName = om2.MDagPath.getAPathTo(self._node).partialPathName() if self._node.hasFn(om2.MFn.kDagNode) else self._nodeFn.name()
        self._stateTracking = stateTracking

        if not stateTracking:
            log.debug(("{!r}: State tracking of the encapsulated dependency node is disabled").format(self))

        # Register if the user is explicit or the dependency node is already tagged
        if register:
            log.debug("Attempting explicit registration of mNode: {!r}".format(self))
            self.register()
        elif self.hasValidTag:
            log.debug("Attempting registration of tagged mNode: {!r}".format(self))
            self.register()
        else:
            log.debug("Returning unregistered mNode wrapper: {!r}".format(self))

    def _createNode(self, nType, name):
        """Creates a dependency node for encapsulation.

        To be called exclusively by :meth:`__init__` when the ``node`` argument is set to :data:`None`.
        Designed to be overridden by derived `mTypes` which may want to implement specialised rules for creating dependency nodes.

        Raises:
            :exc:`~exceptions.ValueError`: If ``nType`` is an invalid node type identifier or is incompatible with the accepted node types of the derived `mType`.

        Returns:
            :class:`OpenMaya.MObject`: Wrapper of the new dependency node.
        """
        try:
            node = DG.createNode(nType)
        except ValueError:
            node = DAG.createNode(nType)

        try:
            OM.validateNodeType(node, nodeType=type(self).NODE_TYPE_CONSTANT, nodeTypeId=type(self).NODE_TYPE_ID)
        except EXC.MayaTypeError:
            DAG.deleteNode(node) if node.hasFn(om2.MFn.kDagNode) else DG.deleteNode(node)
            raise ValueError("{}: Node type is incompatible with {} mNodes".format(nType, type(self)))

        DG.renameNode(node, name or type(self).__name__)

        return node

    # --- Abstract ----------------------------------------------------------------------------

    def _preAccess(self):
        """Abstract override which validates this `mNode` before providing access to an instance method, otherwise raises a `MayaObjectError`."""
        self._validate(verifyNodeId=False)

    def _postAccess(self):
        """Abstract override - null op."""
        pass

    # --- Special ----------------------------------------------------------------------------

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Note:
            This method is not subject to :attr:`stateTracking` and is therefore accessible even if the encapsulated dependency node is invalid.
            In this case cached data is used.

        Returns:
            :class:`str`: A string representation of the `mNode`.
        """
        isValid = self.isValid
        partialName = self.partialName if isValid else self._partialName
        state = "valid" if isValid else "invalid"
        return "{}('{}') <{}>".format(type(self).__name__, partialName, state)

    def __eq__(self, other):
        """``x.__eq__(y)`` <==> ``x == y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: If ``other`` has an equivalent type, return whether its contents (dependency node) are equivalent.
            Otherwise swap the operands and return the result, unless the operands have already been swapped in which case the result is :data:`False`.
        """
        if type(self) is type(other):
            return self.node == other.node

        return NotImplemented

    def __ne__(self, other):
        """``x.__ne__(y)`` <==> ``x != y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: The negation of :meth:`__eq__`.
        """
        return not self == other

    def __getattribute__(self, attr):
        """``x.__getattribute__(attr)`` <==> ``getattr(x, attr)``.

        Access the value referenced by an attribute of this instance or attempt to retrieve a plug from the encapsulated dependency node via :meth:`getPlug`.

        Note:
            Instance access precedes dependency node access.
            Invocation via the instance access operator limits access to root level plugs, while :func:`getattr` allows for direct retrieval of descendant plugs.

        Args:
            attr (:class:`basestring`): Name of an instance attribute or dependency node plug.

        Raises:
            :exc:`~exceptions.AttributeError`: If an instance attribute or dependency node plug could not be identified for the given ``attr`` name.

        Returns:
            any | T <= :class:`MetaAttribute`: Data referenced by the instance attribute or `mAttr` encapsulation of a dependency node plug corresponding to ``attr``.
        """
        try:
            return super(Meta, self).__getattribute__(attr)
        except AttributeError:
            log.debug("{}: mNode attribute does not exist, expanding search to dependency node".format(attr))

        try:
            return self.getPlug(attr, asMeta=True)
        except EXC.MayaLookupError:
            raise AttributeError("{}.{}: Dependency node plug does not exist".format(self.partialName, attr))

    def __setattr__(self, attr, value):
        """``x.__setattr__(attr)`` <==> ``setattr(x, attr, value)``.

        Set the value of an exclusive instance attribute or retrieve a plug from the encapsulated dependency node and set its value via :meth:`MetaAttribute.set`.

        Note:
            Instance access precedes dependency node access.
            Invocation via the instance access operator limits access to root level plugs, while :func:`setattr` allows for direct retrieval of descendant plugs.

        Args:
            attr (:class:`basestring`): Name of an exclusive instance attribute or dependency node plug.
            value (any): Used to set the value referenced by the instance attribute or held by a dependency node plug corresponding to ``attr``.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node plug could not be identified for the given ``attr`` name.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a dependency node plug array.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a dependency node compound plug with a child array or compound.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a dependency node plug that references a typed attribute which holds
                :attr:`OpenMaya.MFnData.kComponentList` type data and the :class:`OpenMaya.MObject` ``value`` does not reference :attr:`OpenMaya.MFn.kComponent` type data.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a dependency node plug that references an unsupported attribute type.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a dependency node plug that references a numeric or typed attribute with an unsupported data type.
            :exc:`~exceptions.TypeError`: If ``attr`` identifies a dependency node plug for which the ``value`` type is not supported.
            :exc:`~exceptions.ValueError`: If ``attr`` identifies a dependency node plug which requires a sequence of values with a different length to the ``value`` sequence.
            :exc:`~exceptions.RuntimeError`: If ``attr`` identifies a dependency node plug which has an input connection.
        """
        # Restrict mNode access
        if attr in type(self).ALL_EXCLUSIVE:
            return super(Meta, self).__setattr__(attr, value)
        else:
            log.debug("{}: Exclusive mNode attribute does not exist, expanding search to dependency node".format(attr))

            # mAttr will handle mNode deregistration when setting the mTypeId
            mAttr = self.getPlug(attr, asMeta=True)
            mAttr.set(value, forceLocked=True)

    def __delattr__(self, attr):
        """``x.__delattr__(attr)`` <==> ``delattr(x, attr)``.

        Delete an attribute directly from the encapsulated dependency node.

        Args:
            attr (:class:`basestring`): Name of a dynamic, non-child attribute on the encapsulated dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attr`` does not identify an attribute on the encapsulated dependency node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a static attribute.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child attribute.
            :exc:`~exceptions.RuntimeError`: If the plug corresponding to ``attr`` is locked or has a locked and connected descendant plug.
        """
        # mAttr will handle mNode deregistration when deleting the mTypeId
        mAttr = self.getPlug(attr, asMeta=True)
        mAttr.delete()

    def __rshift__(self, other):
        """``x.__rshift__(other)`` <==> ``x >> other`` <==> ``other.cacheNode(x.node)``.

        Cache the encapsulated dependency node on that of another `mNode` via :meth:`cacheNode`.

        Args:
            other (T <= :class:`Meta`): `mNode` to receive the cache.
        """
        other.cacheNode(self._node)

    def __floordiv__(self, other):
        """``x.__floordiv__(other)`` <==> ``x // other`` <==> ``other.uncacheNode(x.node, forceLocked=True)``.

        Uncache the encapsulated dependency node from that of another `mNode` via :meth:`uncacheNode`.

        Args:
            other (T <= :class:`Meta`): `mNode` from which to remove the cache.
        """
        other.uncacheNode(self._node, forceLocked=True)

    # --- Protected -----------------------------------------------------------------------------

    def _validate(self, verifyNodeId=False):
        """Verify the encapsulated dependency node is valid.

        Args:
            verifyNodeId (:class:`bool`, optional): Whether to check if the cached `nodeId` is valid.
                If :data:`True`, the cached `nodeId` will be updated if the encapsulated dependency node UUID has changed. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaObjectError`: If the encapsulated dependency node is invalid or is not uniquely identified by the cached `nodeId`.
        """
        global _META_NODE_REGISTRY

        if not self._stateTracking:
            return

        if self.isValid:
            if verifyNodeId:
                cachedUUID = self._nodeId
                currentUUID = UUID.getUuidFromNode(self._node)

                if currentUUID != cachedUUID:
                    log.info("{!r}: Updating mNode with the current nodeId of the encapsulated dependency node".format(self))

                    try:
                        # Deregister before updating the UUID path
                        self.deregister()
                    except KeyError:
                        self._nodeId = currentUUID
                    except MTypeError:
                        _META_NODE_REGISTRY[self._nodeId].nodeId
                        self._nodeId = currentUUID
                    else:
                        self._nodeId = currentUUID
                        self.register()
        else:
            # Attempt to retrieve a valid dependency node wrapper using the cached UUID
            # Careful not to cause a recursive loop via the _preAccess validation wrapper
            try:
                self._node = UUID.getNodeFromUuid(self._nodeId)
            except EXC.MayaLookupError:  # If the node is not found or is not unique
                try:
                    del _META_NODE_REGISTRY[self._nodeId]
                    log.warning("{!r}: Deregistered invalid mNode from invalid nodeId: {}".format(self, self._nodeId))
                except KeyError:
                    pass

                raise EXC.MayaObjectError("{!r}: Failed to validate mNode, last valid nodeId was: {}".format(self, self._nodeId))
            else:
                self._updateExclusiveData()
                log.info("{!r}: Revalidated mNode using nodeId: {}".format(self, self._nodeId))

    def _updateExclusiveData(self):
        """Update internally cached dependency node data. Designed to be overloaded by subclasses.
        Called exclusively by :meth:`_validate` if :attr:`isValid` was :data:`False` but the :class:`OpenMaya.MObject` wrapper of the encapsulated dependency node has been revalidated.
        """
        self._nodeHandle = om2.MObjectHandle(self._node)
        self._nodeFn = om2.MFnDependencyNode(self._node)
        self._partialName = om2.MDagPath.getAPathTo(self._node).partialPathName() if self._node.hasFn(om2.MFn.kDagNode) else self._nodeFn.name()

    # --- Public : Properties ----------------------------------------------------------------------------

    @property
    def isValid(self):
        """:class:`bool`: :data:`True` if the internal :class:`OpenMaya.MObject` wrapper references a valid dependency node, otherwise :data:`False`.

        Note:
            This property is not subject to :attr:`stateTracking` and is therefore accessible even if the encapsulated dependency node is deleted.

        :access: R
        """
        return self._nodeHandle.isValid()

    @property
    def isLocked(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node is locked, otherwise :data:`False`.

        :access: R
        """
        return self._nodeFn.isLocked

    @property
    def isReferenced(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node is from a referenced file, otherwise :data:`False`.

        :access: R
        """
        return self._nodeFn.isFromReferencedFile

    @property
    def isRegisterable(self):
        """:class:`bool`: :data:`True` if this `mNode` can be registered, otherwise :data:`False`.

        A DAG node can only be registered to an `mType` which is a (non-strict) subclass of :class:`MetaDag`.
        This ensures the :class:`MetaDag` interface can always produce outputs with an appropriate upper bound `mType`.

        :access: R
        """
        return not self._node.hasFn(om2.MFn.kDagNode) or issubclass(type(self), MetaDag)

    @property
    def isTagged(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node is tagged with `mSystemId` and `mTypeId` attributes, otherwise :data:`False`.

        :access: R
        """
        return self.hasPlug("mSystemId") and self.hasPlug("mTypeId")

    @property
    def hasValidTag(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node is tagged with an `mTypeId` attribute that corresponds to the derived `mType` of this `mNode`
        as well as a `mSystemId` that corresponds to the :attr:`SYSTEM_ID`, otherwise :data:`False`.

        :access: R
        """
        try:
            return type(self).__name__ == self.getPlug("mTypeId", asMeta=True).get() and type(self).SYSTEM_ID == self.getPlug("mSystemId", asMeta=True).get()
        except StandardError:
            return False

    @property
    def node(self):
        """:class:`OpenMaya.MObject`: Wrapper of the encapsulated dependency node.

        :access: R
        """
        return self._node

    @property
    def nodeFn(self):
        """:class:`OpenMaya.MFnDependencyNode`: Function set encapsulation of the encapsulated dependency node.

        :access: R
        """
        return om2.MFnDependencyNode(self._node)

    @property
    def nodeId(self):
        """:class:`str`: UUID of the encapsulated dependency node.

        :access: R
        """
        self._validate(verifyNodeId=True)
        return self._nodeId

    @property
    def stateTracking(self):
        """:class:`bool`: Whether to track the state of the encapsulated dependency node in order to restrict access to the public interface if invalid.

        Restriction involves raising an :exc:`msTools.core.maya.exceptions.MayaObjectError` upon attempting to access a bound instance attribute from the public interface.
        The following bindings are excluded: :meth:`__repr__`, :attr:`isValid`.

        :access: RW
        """
        return self._stateTracking

    @stateTracking.setter
    def stateTracking(self, state):
        self._stateTracking = state
        if not state:
            log.debug(("{!r}: State tracking of the encapsulated dependency node is disabled").format(self))

    @property
    def shortName(self):
        """:class:`str`: Short name of the encapsulated dependency node.

        The short name has no qualifying path or namespace.
        It is not guaranteed to uniquely identify the node.

        :access: R
        """
        return self.partialName.split('|')[-1].split(':')[-1]

    @property
    def partialName(self):
        """:class:`str`: Partial name of the encapsulated dependency node.

        The partial name is qualified by a path and namespace where applicable or necessary.
        It is guaranteed to uniquely identify the node with the minimum amount of information necessary (partial path for the first occurrence of a DAG node).

        If the encapsulated dependency node is a not a DAG node, the partial name is equivalent to its full name.

        :access: R
        """
        if self._node.hasFn(om2.MFn.kDagNode):
            self._partialName = om2.MDagPath.getAPathTo(self._node).partialPathName()
        else:
            self._partialName = self._nodeFn.name()

        return self._partialName

    @property
    def fullName(self):
        """:class:`str`: Full name of the encapsulated dependency node.

        The full name is qualified by a path and namespace where applicable.
        It is guaranteed to uniquely identify the node with the maximum amount of information (full path for the first occurrence of a DAG node).

        If the encapsulated dependency node is a not a DAG node, the full name is equivalent to its partial name.
        """
        if self._node.hasFn(om2.MFn.kDagNode):
            return om2.MDagPath.getAPathTo(self._node).fullPathName()
        else:
            return self._nodeFn.name()

    @property
    def absoluteNamespace(self):
        """:class:`str`: Absolute namespace of the encapsulated dependency node. Includes all parent namespaces and a ``:`` delineating the root.

        :access: R
        """
        return ":" + self._nodeFn.namespace

    @property
    def baseNamespace(self):
        """:class:`str`: Leaf level namespace of the encapsulated dependency node. Does not include parent namespaces of the leaf.
        The leaf namespace of the root will be an empty string.

        :access: R
        """
        return self.namespace.split(":")[-1]

    @property
    def notes(self):
        """:class:`str`: Information stored with the ``'notes'`` attribute of the encapsulated dependency node.

        :access: RW
        """
        try:
            return self.getPlug("notes", asMeta=True).get()
        except EXC.MayaLookupError:
            return ""

    @notes.setter
    def notes(self, text):
        try:
            self.getPlug("notes", asMeta=True).set(text)
        except EXC.MayaLookupError:
            self.addTypedAttribute(shortName="nts", longName="notes", dataType=om2.MFnData.kString, value=text)

    # --- Public : Registration ----------------------------------------------------------------------------------------

    def register(self):
        """Register this `mNode` internally and within the scene.

        The encapsulated dependency node will be locked and tagged with an `mTypeId` and `mSystemId` for the derived `mType`.

        The `mTypeId` and `mSystemId` tag of the encapsulated dependency node will be overridden if it was previously registered to a different `mType`.
        If an `mNode` corresponding to the previous `mType` is registered internally, it will be replaced with this `mNode`.

        Note:
            This `mNode` can only be registered if :attr:`isRegisterable` returns :data:`True`.

        Raises:
            :exc:`MTypeError`: If an attempt is made to register a DAG node to an `mType` that is not a (non-strict) subclass of :class:`MetaDag`.
        """
        global _META_NODE_REGISTRY

        nodeId = self.nodeId

        if not self.isRegisterable:
            raise MTypeError("{!r}: mNode cannot be registered, DAG nodes are restricted to (non-strict) subclasses of {}".format(self, MetaDag))

        if not self.hasValidTag:
            try:
                deregisteredMNode = _META_NODE_REGISTRY.pop(self.nodeId)
                log.debug("{!r}: mNode with previous mType has been deregistered".format(deregisteredMNode))
            except KeyError:
                pass

            try:
                self.getPlug("mTypeId", asMeta=True).set(type(self).__name__)
            except EXC.MayaLookupError:
                self.addTypedAttribute(longName='mTypeId', dataType=om2.MFnData.kString, value=type(self).__name__)

            try:
                self.getPlug("mSystemId", asMeta=True).set(type(self).SYSTEM_ID)
            except EXC.MayaLookupError:
                self.addTypedAttribute(longName='mSystemId', dataType=om2.MFnData.kString, value=type(self).SYSTEM_ID)

        self.lock()

        _META_NODE_REGISTRY[nodeId] = self
        log.debug("{!r}: mNode registered".format(self))

    def deregister(self):
        """Deregister this `mNode` internally and from the scene.

        The encapsulated dependency node will be unlocked and its `mTypeId` and `mSystemId` tag will be removed.

        Raises:
            :exc:`~exceptions.KeyError`: If this `mNode` is not registered to its last valid `nodeId`.
            :exc:`MTypeError`: If the `mType` of this `mNode` does not match the `mType` of the registered `mNode`.
        """
        global _META_NODE_REGISTRY

        try:
            registeredMNode = _META_NODE_REGISTRY[self._nodeId]
        except KeyError:
            raise KeyError("{!r}: mNode is not registered under its last valid nodeId: {}".format(self, self._nodeId))

        if type(registeredMNode) is type(self):
            del _META_NODE_REGISTRY[self._nodeId]
            log.debug("{!r}: mNode has been deregistered".format(self))

            del self.mTypeId
            del self.mSystemId

            self.unlock()
        else:
            raise MTypeError("{!r}: mNode has different mType to registered mNode: {!r}".format(self, registeredMNode))

    # --- Public : Utility -----------------------------------------------------------------------------

    def lock(self):
        """Lock the encapsulated dependency node.

        Returns:
            :class:`bool`: :data:`True` if the lock state of the encapsulated dependency node has changed, otherwise :data:`False`.
        """
        return DG.lockNode(self._node)

    def unlock(self):
        """Unlock the encapsulated dependency node.

        Returns:
            :class:`bool`: :data:`True` if the lock state of the encapsulated dependency node has changed, otherwise :data:`False`.
        """
        return DG.unlockNode(self._node)

    def select(self, addFirst=False, add=False):
        """Select the encapsulated dependency node, adding to or replacing the active selection list.

        Args:
            addFirst (:class:`bool`, optional): Whether to add the encapsulated dependency node to the head of the active selection list.
                Defaults to :data:`False`.
            add (:class:`bool`, optional): Whether to add the encapsulated dependency node to the tail of the active selection list.
                Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``addFirst`` and ``add`` are both :data:`True`.
        """
        if addFirst and add:
            raise ValueError("Choose either to add node to head or tail of the active selection")

        if addFirst:
            cmds.select(self.partialName, addFirst=addFirst)
        elif add:
            cmds.select(self.partialName, add=add)
        else:
            cmds.select(self.partialName)

    def deselect(self):
        """Remove the encapsulated dependency node from the active selection list."""
        cmds.select(self.partialName, deselect=True)

    @unlockMeta
    def rename(self, name):
        """Rename the encapsulated dependency node.

        Args:
            name (:class:`basestring`): New name for the node.
        """
        DG.renameNode(self._node, name)

    def delete(self):
        """Delete the encapsulated dependency node. If the node is a DAG node this will include all of its children.

        Note:
            The current `mNode` will become invalid.
        """
        self.unlock()

        try:
            self.deregister()
        except (KeyError, MTypeError):
            pass

        if self._node.hasFn(om2.MFn.kDagNode):
            DAG.deleteNode(self._node)
        else:
            DG.deleteNode(self._node)

    # --- Public : Reference -----------------------------------------------------------------------------

    def getReference(self, asMeta=False):
        """Returns the direct reference node for the encapsulated dependency node.

        Note:
            If the encapsulated dependency node is itself a reference node, the parent reference node will be returned.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the reference node as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node is not a referenced node.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the reference node is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the reference node is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrapper or `mNode` encapsulation for the reference node.
            Type is determined by ``asMeta``.
        """
        referenceNode = REF.getReference(self._node)
        return getMNode(referenceNode) if asMeta else referenceNode

    # --- Public : Attributes -----------------------------------------------------------------------------------

    def hasPlug(self, plugName):
        """Return whether a plug on the encapsulated dependency node can be identified by name.

        Args:
            plugName (:class:`basestring`): Name used in attempting to identify a plug on the encapsulated dependency node.
                It should provide all element indices in the plug path using the format ``'element[0].child'``.

        Returns:
            :class:`bool`: Whether a dependency node plug could be identified.
        """
        try:
            OM.getPlugFromNodeByName(self._node, plugName)
            return True
        except EXC.MayaLookupError:
            return False

    def getPlug(self, plugName, asMeta=False):
        """Return a dependency node plug identified on the encapsulated dependency node by name.

        Args:
            plugName (:class:`basestring`): Name used to identify a plug on the encapsulated dependency node.
                It should identify a unique plug on the encapsulated dependency node by providing all element indices in the plug path using the format ``'element[0].child'``.
            asMeta (:class:`bool`, optional): Whether to return the plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node plug could not be identified.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the dependency node plug. Type is determined by ``asMeta``.
        """
        plug = OM.getPlugFromNodeByName(self._node, plugName)
        return getMAttr(plug) if asMeta else plug

    @unlockMeta
    def addCompoundAttribute(self, childAttributes, shortName=None, longName=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic compound attribute to the encapsulated dependency node, useful for storing a related set of data.

        Note:
            Dynamic attributes should be married to a single dependency node.
            Callers are responsible for ensuring the ``childAttributes`` have not already been added to a dependency node.
            Failing to do so may produce undefined behaviour.

        Args:
            childAttributes (iterable [:class:`OpenMaya.MObject`]): Wrappers of attributes to add as children of the compound attribute.
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If any of the ``childAttributes`` do not reference an attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``
                or the same name as any of the ``childAttributes``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        compAttr = ATTR.createCompoundAttribute(shortName=shortName, longName=longName, **kwargs)

        for childAttr in childAttributes:
            OM.validateAttributeType(childAttr)
            ATTR.addToCompound(compAttr, childAttr)

        ATTR.addToNode(self._node, compAttr)
        plug = om2.MPlug(self._node, compAttr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addNumericAttribute(self, shortName=None, longName=None, dataType=om2.MFnNumericData.kFloat, point=False, color=False, value=None, min_=None, max_=None, softMin=None, softMax=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic numeric attribute to the encapsulated dependency node based on a data type constant from :class:`OpenMaya.MFnNumericData`.

        Args:
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnNumericData` representing the default data type.
                Valid values are :attr:`~OpenMaya.MFnNumericData.kFloat`, :attr:`~OpenMaya.MFnNumericData.kAddr`, :attr:`~OpenMaya.MFnNumericData.kChar`,
                :attr:`~OpenMaya.MFnNumericData.kByte`, :attr:`~OpenMaya.MFnNumericData.kShort`, :attr:`~OpenMaya.MFnNumericData.kInt`,
                :attr:`~OpenMaya.MFnNumericData.kInt64`, :attr:`~OpenMaya.MFnNumericData.kDouble`, :attr:`~OpenMaya.MFnNumericData.kBoolean`,
                :attr:`~OpenMaya.MFnNumericData.k2Short`, :attr:`~OpenMaya.MFnNumericData.k2Int`, :attr:`~OpenMaya.MFnNumericData.k2Float`,
                :attr:`~OpenMaya.MFnNumericData.k2Double`, :attr:`~OpenMaya.MFnNumericData.k3Short`, :attr:`~OpenMaya.MFnNumericData.k3Int`,
                :attr:`~OpenMaya.MFnNumericData.k3Float`, :attr:`~OpenMaya.MFnNumericData.k3Double`, :attr:`~OpenMaya.MFnNumericData.k4Double`.
                Multi data point types such as :attr:`~OpenMaya.MFnNumericData.k2Float` will create a compound attribute of type :attr:`OpenMaya.MFn.kAttribute2Float`.
                In this case, child attribute names would be suffixed with an index and would be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data.
                Defaults to :attr:`~OpenMaya.MFnNumericData.kFloat`.
            point (:class:`bool`, optional): If :data:`True`, the ``dataType`` will be ignored and an attribute of type :attr:`OpenMaya.MFn.kAttribute3Float` will be created, storing :attr:`~OpenMaya.MFnNumericData.k3Float` data.
                If ``value`` is given, it must be a three-element :class:`tuple`.
                Child attribute names will be suffixed with ``'X'``, ``'Y'``, ``'Z'`` respectively and will be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data. Defaults to :data:`False`.
            color (:class:`bool`, optional): If :data:`True` and ``point`` is :data:`False`, the ``dataType`` will be ignored and an attribute of type :attr:`OpenMaya.MFn.kAttribute3Float` will be created, storing :attr:`~OpenMaya.MFnNumericData.k3Float` data.
                If ``value`` is given, it must be a three-element :class:`tuple`.
                Child attribute names will be suffixed with ``'R'``, ``'G'``, ``'B'`` respectively and will be of type :attr:`OpenMaya.MFn.kNumericAttribute`, storing :attr:`~OpenMaya.MFnNumericData.kFloat` data. Defaults to :data:`False`.
            value (numeric-type, optional): Default value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            min_ (:class:`float` | :class:`int`, optional): Min value for the attribute. Defaults to :data:`None`.
            max_ (:class:`float` | :class:`int`, optional): Max value for the attribute. Defaults to :data:`None`.
            softMin (:class:`float` | :class:`int`, optional): Soft min value for the attribute. Defaults to :data:`None`.
            softMax (:class:`float` | :class:`int`, optional): Soft max value for the attribute. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`~exceptions.ValueError`: If a compound attribute type is passed a ``value`` with an incompatible number of elements.
            :exc:`~exceptions.TypeError`: If the ``value`` type is incompatible with the ``dataType``.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createNumericAttribute(shortName=shortName, longName=longName, dataType=dataType, point=point, color=color, value=value, min_=min_, max_=max_, softMin=softMin, softMax=softMax, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addUnitAttribute(self, shortName=None, longName=None, dataType=om2.MFnUnitAttribute.kDistance, value=None, min_=None, max_=None, softMin=None, softMax=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic unit attribute to the encapsulated dependency node based on a data type constant from :class:`OpenMaya.MFnUnitAttribute`.

        Args:
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnUnitAttribute` representing the default data type.
                Valid values are :attr:`~OpenMaya.MFnUnitAttribute.kAngle`, :attr:`~OpenMaya.MFnUnitAttribute.kDistance`, :attr:`~OpenMaya.MFnUnitAttribute.kTime`.
                Defaults to :attr:`~OpenMaya.MFnUnitAttribute.kDistance`.
            value (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
                Default value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            min_ (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
                Min value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            max_ (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
                Max value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            softMin (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
                Soft min value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            softMax (:class:`float` | :class:`int` | :class:`OpenMaya.MAngle` | :class:`OpenMaya.MDistance` | :class:`OpenMaya.MTime`, optional):
                Soft max value for the attribute, must be compatible with the ``dataType`` constant. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`~exceptions.TypeError`: If the ``value``, ``min``, ``max``, ``softMin`` or ``softMax`` type is incompatible with the ``dataType``.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createUnitAttribute(shortName=shortName, longName=longName, dataType=dataType, value=value, min_=min_, max_=max_, softMin=softMin, softMax=softMax, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addEnumAttribute(self, fields, shortName=None, longName=None, default=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic enum attribute to the encapsulated dependency node based on a mapping of field names to integer values.

        Args:
            fields (:class:`dict` [ :class:`basestring`, :class:`int` ]): Mapping of field names to unique values.
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            default (:class:`basestring`, optional): Default field, must correspond to a key in the ``fields`` mapping.
                If :data:`None`, the field with the smallest value will be used. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`~exceptions.ValueError`: If the ``fields`` mapping is empty or the set of values contained within the ``fields`` mapping is not unique.
            :exc:`~exceptions.KeyError`: If the ``default`` field does not exist within the ``fields`` mapping.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createEnumAttr(fields, shortName=shortName, longName=longName, default=default, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addMatrixAttribute(self, shortName=None, longName=None, dataType=om2.MFnMatrixAttribute.kDouble, matrix=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic matrix attribute to the encapsulated dependency node based on a data type constant from :class:`OpenMaya.MFnMatrixAttribute`.

        Args:
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnMatrixAttribute` representing the default data type.
                Either single precision (:attr:`~OpenMaya.MFnMatrixAttribute.kFloat`) or double precision (:attr:`~OpenMaya.MFnMatrixAttribute.kDouble`).
                Defaults to :attr:`~OpenMaya.MFnMatrixAttribute.kDouble`.
            matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`, optional): Default value for the attribute.
                If :data:`None`, an identity matrix of the given ``dataType`` will be used. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createMatrixAttribute(shortName=shortName, longName=longName, dataType=dataType, matrix=matrix, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addTypedAttribute(self, shortName=None, longName=None, dataType=om2.MFnData.kString, value=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic typed attribute to the encapsulated dependency node based on a data type constant from :class:`OpenMaya.MFnData`.

        Args:
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            dataType (:class:`int`, optional): Type constant present on :class:`OpenMaya.MFnData` representing the default data type.
                Supported constants are: :attr:`~OpenMaya.MFnData.kComponentList`, :attr:`~OpenMaya.MFnData.kDoubleArray`, :attr:`~OpenMaya.MFnData.kIntArray`,
                :attr:`~OpenMaya.MFnData.kMatrix`, :attr:`~OpenMaya.MFnData.kMesh`, :attr:`~OpenMaya.MFnData.kNurbsCurve`, :attr:`~OpenMaya.MFnData.kNurbsSurface`,
                :attr:`~OpenMaya.MFnData.kPlugin`, :attr:`~OpenMaya.MFnData.kPointArray`, :attr:`~OpenMaya.MFnData.kString`, :attr:`~OpenMaya.MFnData.kStringArray`,
                :attr:`~OpenMaya.MFnData.kVectorArray`. Defaults to :attr:`~OpenMaya.MFnData.kString`.
            value (any, optional): Default value for the attribute. The following values are compatible with each ``dataType`` constant:

                - :attr:`~OpenMaya.MFnData.kComponentList`: An :class:`OpenMaya.MObject` referencing derived :attr:`OpenMaya.MFn.kComponent` type data.
                - :attr:`~OpenMaya.MFnData.kMatrix`: An :class:`OpenMaya.MMatrix` or :class:`OpenMaya.MTransformationMatrix`.
                - :attr:`~OpenMaya.MFnData.kDoubleArray`, :attr:`~OpenMaya.MFnData.kIntArray`: An iterable of numeric data.
                - :attr:`~OpenMaya.MFnData.kVectorArray`: An iterable of :class:`OpenMaya.MVector` data.
                - :attr:`~OpenMaya.MFnData.kPointArray`: An iterable of :class:`OpenMaya.MPoint` data.
                - :attr:`~OpenMaya.MFnData.kStringArray`: An iterable of :class:`basestring` or :mod:`json` serializable data.
                - :attr:`~OpenMaya.MFnData.kString`: A :class:`basestring` or :mod:`json` serializable data.
                - :attr:`~OpenMaya.MFnData.kPlugin`: An :class:`OpenMaya.MTypeId` specifying a user defined data type.
                - :attr:`~OpenMaya.MFnData.kMesh`, :attr:`~OpenMaya.MFnData.kNurbsCurve`, :attr:`~OpenMaya.MFnData.kNurbsSurface`: :data:`None`.

                Defaults to :data:`None`.

            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.
            :exc:`~exceptions.ValueError`: If the ``dataType`` is unsupported (eg. :attr:`~OpenMaya.MFnData.kNumeric`, :attr:`~OpenMaya.MFnData.kFloatArray`, etc).
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the ``dataType`` is :attr:`~OpenMaya.MFnData.kComponentList` and the :class:`OpenMaya.MObject` ``value`` does not reference component data.
            :exc:`~exceptions.TypeError`: If the ``value`` type is incompatible with the ``dataType``.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createTypedAttribute(shortName=shortName, longName=longName, dataType=dataType, value=value, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    @unlockMeta
    def addMessageAttribute(self, shortName=None, longName=None, resultAsMeta=False, **kwargs):
        """Add a new dynamic message attribute to the encapsulated dependency node.

        Args:
            shortName (:class:`basestring`, optional): Short name for the attribute. ``longName`` used if :data:`None`. Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the attribute. ``shortName`` used if :data:`None`. Defaults to :data:`None`.
            resultAsMeta (:class:`bool`, optional): Whether to return the new plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MPlug` encapsulation.
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MFnAttribute` such as
                :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
                :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
                :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``shortName`` and ``longName`` are :data:`None`.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the new dependency node plug. Type is determined by ``resultAsMeta``.
        """
        attr = ATTR.createMessageAttribute(shortName=shortName, longName=longName, **kwargs)
        ATTR.addToNode(self._node, attr)
        plug = om2.MPlug(self._node, attr)

        return getMAttr(plug) if resultAsMeta else plug

    # --- Public : Connection ----------------------------------------------------------------------------

    @unlockMeta
    def disconnectDependencies(self, upstream=False, downstream=False, walk=False, filterTypes=None, forceLocked=False):
        """Disconnect pairs of source and destination plugs for the dependencies of the encapsulated dependency node.

        Args:
            upstream (:class:`bool`, optional): Whether to disconnect upstream dependencies of the encapsulated dependency node. Defaults to :data:`False`.
            downstream (:class:`bool`, optional): Whether to disconnect downstream dependencies of the encapsulated dependency node. Defaults to :data:`False`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
                Each connected plug on the encapsulated dependency node acts as the root of a path. Defaults to :data:`True`.
            filterTypes (iterable [:class:`int`], optional): Filter dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            forceLocked (:class:`bool`, optional): Whether to force disconnect a dependency that is connected via a locked destination plug. Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.RuntimeError`: If any of the dependencies are connected via a locked destination plug and ``forceLocked`` is :data:`False`.

        Example:
            .. code-block:: python

                # Remove direct connections to any constraints downstream of the encapsulated dependency node
                disconnectDependencies(downstream=True, filterTypes=(OpenMaya.MFn.kConstraint,))
        """
        DG.disconnectDependencies(self._node, upstream=upstream, downstream=downstream, walk=walk, filterTypes=filterTypes, forceLocked=forceLocked)

    def hasCachedNode(self, node):
        """Return whether a dependency node is cached on the encapsulated dependency node.

        Args:
            node (:class:`OpenMaya.MObject`): Wrapper of a dependency node to check.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

        Returns:
            :class:`bool`: :data:`True` if ``node`` is connected from its static ``'message'`` attribute to a message type attribute on the encapsulated dependency node, otherwise :data:`False`.
        """
        for sourcePlug, destPlug in DG.iterDependenciesByEdge(self._node, directionType=om2.MItDependencyGraph.kUpstream):
            if destPlug.attribute().apiType() == om2.MFn.kMessageAttribute and sourcePlug.node() == node:
                return True

        return False

    def cacheNode(self, sourceNode, shortName=None, longName=None):
        """Cache a dependency node on the encapsulated dependency node.

        A connection will be made from the static ``'message'`` attribute of the souce node to a message type attribute on the encapsulated dependency node.

        Args:
            sourceNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node to cache on the encapsulated dependency node.
            shortName (:class:`basestring`, optional): Short name for the new message type attribute used to cache the ``sourceNode``.
                If :data:`None`, the ``longName`` will be used. If the ``longName`` is also :data:`None`, the ``sourceNode`` short name will be used.
                Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the new message type attribute used to cache the ``sourceNode``.
                If :data:`None`, the ``shortName`` will be used. If the ``shortName`` is also :data:`None`, the ``sourceNode`` short name will be used.
                Defaults to :data:`None`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``sourceNode`` does not reference a dependency node.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.
        """
        if not shortName and not longName:
            longName = NAME.getNodeShortName(sourceNode)

        sourcePlug = OM.getPlugFromNodeByName(sourceNode, "message")
        destPlug = self.addMessageAttribute(shortName=shortName, longName=longName, readable=False)
        PLUG.connect(sourcePlug, destPlug)

    @unlockMeta
    def uncacheNode(self, sourceNode, forceLocked=False):
        """Uncache a dependency node from the encapsulated dependency node.

        Any message type attribute on the encapsulated dependency node which is connected from the static ``'message'`` attribute of the souce node will be removed if permitted.
        Otherwise if the destination plug is a descendant, it will be disconnected but not removed.

        Args:
            sourceNode (:class:`OpenMaya.MObject`): Wrapper of a dependency node to uncache from the encapsulated dependency node.
            forceLocked (:class:`bool`, optional): Whether to force remove an attribute if the corresponding plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``sourceNode`` does not reference a dependency node.
            :exc:`~exceptions.RuntimeError`: If any of the connected message type attributes on the encapsulated dependency node correspond to a locked plug and ``forceLocked`` is :data:`False`.
        """
        for sourcePlug, destPlug in list(DG.iterDependenciesByEdge(self._node, directionType=om2.MItDependencyGraph.kUpstream)):
            if destPlug.attribute().apiType() == om2.MFn.kMessageAttribute and sourcePlug.node() == sourceNode:
                if destPlug.isElement or destPlug.isChild:
                    log.info("{}: Cached node is connected via a descendant plug: {}. Unable to remove attribute".format(NAME.getNodeFullName(sourceNode), NAME.getPlugFullName(destPlug)))
                    PLUG.disconnect(sourcePlug, destPlug, forceLocked=forceLocked)
                else:
                    ATTR.removeFromNode(self._node, destPlug.attribute())

    def hasCachedPlug(self, plug):
        """Return whether a dependency node plug is cached on the encapsulated dependency node.

        Args:
            plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug to check.

        Returns:
            :class:`bool`: :data:`True` if ``plug`` is connected to a message type attribute on the encapsulated dependency node, otherwise :data:`False`.
        """
        plugId = OM.MPlugId(plug)

        for sourcePlug, destPlug in DG.iterDependenciesByEdge(self._node, directionType=om2.MItDependencyGraph.kUpstream):
            if destPlug.attribute().apiType() == om2.MFn.kMessageAttribute and OM.MPlugId(sourcePlug) == plugId:
                return True

        return False

    def cachePlug(self, sourcePlug, shortName=None, longName=None):
        """Cache a dependency node plug on the encapsulated dependency node.

        A connection will be made from the source plug to a message type attribute on the encapsulated dependency node.

        Args:
            sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug to cache on the encapsulated dependency node.
            shortName (:class:`basestring`, optional): Short name for the new message type attribute used to cache the ``sourcePlug``. If :data:`None`, the ``longName`` will be used.
                If the ``longName`` is also :data:`None`, :meth:`msTools.core.maya.name_utils.getPlugStorableName` will be used to determine a name for the ``sourcePlug``.
                Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the new message type attribute used to cache the ``sourcePlug``. If :data:`None`, the ``shortName`` will be used.
                If the ``shortName`` is also :data:`None`, :meth:`msTools.core.maya.name_utils.getPlugStorableName` will be used to determine a name for the ``sourcePlug``.
                Defaults to :data:`None`.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.
        """
        if not shortName and not longName:
            longName = NAME.getPlugStorableName(sourcePlug)

        destPlug = self.addMessageAttribute(shortName=shortName, longName=longName, readable=False)
        PLUG.connect(sourcePlug, destPlug)

    @unlockMeta
    def uncachePlug(self, sourcePlug, forceLocked=False):
        """Uncache a dependency node plug from the encapsulated dependency node.

        Any message type attribute on the encapsulated dependency node which is connected from the souce plug will be removed if permitted.
        Otherwise if the destination plug is a descendant, it will be disconnected but not removed.

        Args:
            sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug to uncache from the encapsulated dependency node.
            forceLocked (:class:`bool`, optional): Whether to force remove an attribute if the corresponding plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.RuntimeError`: If any of the connected message type attributes on the encapsulated dependency node correspond to a locked plug and ``forceLocked`` is :data:`False`.
        """
        sourcePlugId = OM.MPlugId(sourcePlug)

        for connectedSourcePlug, connectedDestPlug in list(DG.iterDependenciesByEdge(self._node, directionType=om2.MItDependencyGraph.kUpstream)):
            if connectedDestPlug.attribute().apiType() == om2.MFn.kMessageAttribute and om2.MPlugId(connectedSourcePlug) == sourcePlugId:
                if connectedDestPlug.isElement or connectedDestPlug.isChild:
                    log.info("{}: Cached plug is connected via a descendant plug: {}. Unable to remove attribute".format(NAME.getPlugFullName(connectedSourcePlug), NAME.getPlugFullName(connectedDestPlug)))
                    PLUG.disconnect(connectedSourcePlug, connectedDestPlug, forceLocked=forceLocked)
                else:
                    ATTR.removeFromNode(self._node, connectedDestPlug.attribute())

    def hasCachedComponent(self, component):
        """Return whether dependency node components are cached on the encapsulated dependency node.

        Args:
            component ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` representing component data to check on the encapsulated dependency node.

                #. Path encapsulation of a shape node.
                #. Wrapper holding :attr:`OpenMaya.MFn.kComponent` type date corresponding to components on the shape node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the first element of ``component`` does not reference a shape node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the second element of ``component`` does not reference component data.
        ..

        Returns:
            :class:`bool`: :data:`True` if the following two conditions are valid:

            - The shape node referenced by ``component`` is connected from its static ``'message'`` attribute to a typed attribute on the encapsulated dependency node.
            - The typed attribute holds :attr:`OpenMaya.MFnData.kComponentList` type data which is equivalent to the component data referenced by ``component``.

            Otherwise :data:`False`.
        """
        OM.validateNode(component[0].node(), om2.MFn.kShape)
        OM.validateComponent(component[1])

        for sourcPlug, destPlug in self.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream):
            if destPlug.attribute().apiType() == om2.MFn.kTypedAttribute and sourcPlug.node() == component[0].node():
                try:
                    destValue = PLUG.getValue(destPlug)
                except EXC.MayaTypeError:
                    continue

                if isinstance(destValue, om2.MObject) and destValue.hasFn(om2.MFn.kComponent):
                    if COMPONENT.areEqual(destValue, component[1]):
                        return True

        return False

    def cacheComponent(self, sourceComponent, shortName=None, longName=None):
        """Cache shape node components on the encapsulated dependency node.

        A connection will be made from the static ``'message'`` attribute of the souce node to a typed attribute on the encapsulated dependency node.
        The typed attribute will hold the component data from the source node.

        Args:
            sourceComponent ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` representing component data to cache on the encapsulated dependency node.

                #. Path encapsulation of a shape node.
                #. Wrapper holding :attr:`OpenMaya.MFn.kComponent` type date corresponding to components on the shape node.

            shortName (:class:`basestring`, optional): Short name for the new typed attribute used to cache the component data. If :data:`None`, the ``longName`` will be used.
                If the ``longName`` is also :data:`None`, the short name of the node referenced by ``sourceComponent`` will be suffixed by ``'__components'``.
                Defaults to :data:`None`.
            longName (:class:`basestring`, optional): Long name for the new typed attribute used to cache the component data. If :data:`None`, the ``shortName`` will be used.
                If the ``shortName`` is also :data:`None`, the short name of the node referenced by ``sourceComponent`` will be suffixed by ``'__components'``.
                Defaults to :data:`None`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the first element of ``sourceComponent`` does not reference a shape node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the second element of ``sourceComponent`` does not reference component data.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node already has an attribute with the same ``shortName`` or ``longName``.
        """
        sourceNode = sourceComponent[0].node()
        OM.validateNode(sourceNode, om2.MFn.kShape)

        if not shortName and not longName:
            longName = "__".join([NAME.getNodeShortName(sourceNode), "components"])

        sourcePlug = OM.getPlugFromNodeByName(sourceNode, "message")
        destPlug = self.createTypedAttribute(shortName=shortName, longName=longName, dataType=om2.MFnData.kComponentList, value=sourceComponent[1], readable=False)
        PLUG.connect(sourcePlug, destPlug)

    @unlockMeta
    def uncacheComponent(self, sourceComponent, forceLocked=False):
        """Uncache shape node components from the encapsulated dependency node.

        Any typed attribute on the encapsulated dependency node which holds the source component data and is connected from the static ``'message'`` attribute of the souce node will be removed if permitted.
        Otherwise if the destination plug is a descendant, it will be disconnected but not removed.

        Args:
            sourceComponent ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` representing component data to uncache from the encapsulated dependency node.

                #. Path encapsulation of a shape node.
                #. Wrapper holding :attr:`OpenMaya.MFn.kComponent` type date corresponding to components on the shape node.

            forceLocked (:class:`bool`, optional): Whether to force remove an attribute if the corresponding plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the first element of ``sourceComponent`` does not reference a shape node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the second element of ``sourceComponent`` does not reference component data.
            :exc:`~exceptions.RuntimeError`: If any of the connected typed attributes on the encapsulated dependency node correspond to a locked plug and ``forceLocked`` is :data:`False`.
        """
        OM.validateNode(sourceComponent[0].node(), om2.MFn.kShape)
        OM.validateComponent(sourceComponent[1])

        for sourcePlug, destPlug in list(self.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream)):
            if destPlug.attribute().apiType() == om2.MFn.kTypedAttribute and sourcePlug.node() == sourceComponent[0].node():
                try:
                    destValue = PLUG.getValue(destPlug)
                except EXC.MayaTypeError:
                    continue

                if isinstance(destValue, om2.MObject) and destValue.hasFn(om2.MFn.kComponent):
                    if COMPONENT.areEqual(destValue, sourceComponent[1]):
                        if destPlug.isElement or destPlug.isChild:
                            PLUG.disconnect(sourcePlug, destPlug, forceLocked=forceLocked)
                            log.info("Cached component is connected via a descendant plug: {}. Unable to remove attribute".format(NAME.getNodeFullName(destPlug)))
                        else:
                            ATTR.removeFromNode(self._node, destPlug.attribute())

    # --- Public : Traversal ----------------------------------------------------------------------------

    def iterDependenciesByNode(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield the node dependencies of the encapsulated dependency node.

        Each connected plug on the encapsulated dependency node will be traversed. A node is yielded if it has not been visited.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
                Each connected plug on the encapsulated dependency node acts as the root of a path. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter node dependencies based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each node dependency as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a node dependency is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a node dependency is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrappers or `mNode` encapsulations for node dependencies of the encapsulated dependency node.
            Type is determined by ``asMeta``.
        """
        nodeGen = DG.iterDependenciesByNode(self._node, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for node in nodeGen:
            yield getMNode(node) if asMeta else node

    def iterDependenciesByPlug(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield the plug dependencies of the encapsulated dependency node.

        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kDownstream`, dependencies will correspond to destination plug connections.
        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kUpstream`, dependencies will correspond to source plug connections.

        Each connected plug on the encapsulated dependency node will be traversed. A plug is yielded if it has not been visited.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
                Each connected plug on the encapsulated dependency node acts as the root of a path. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each plug dependency as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for plug dependencies of the encapsulated node. Type is determined by ``asMeta``.
        """
        plugGen = DG.iterDependenciesByPlug(self._node, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for plug in plugGen:
            yield getMAttr(plug) if asMeta else plug

    def iterDependenciesByEdge(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield dependencies of the encapsulated dependency node as edges represented by a pair of connected source and destination plugs.

        Each pair will correspond to a connection from a source plug to a destination plug regardless of the ``directionType``.

        Each connected plug on the encapsulated dependency node will be traversed.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed.
                Each connected plug on the encapsulated dependency node acts as the root of a path. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each pair of connected plug dependencies as `mAttrs` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as pairs of :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            (:class:`OpenMaya.MPlug`, :class:`OpenMaya.MPlug`) | (T <= :class:`MetaAttribute`, T <= :class:`MetaAttribute`): A two-element :class:`tuple` of connected plug dependencies.

            #. A source plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.
            #. A corresponding destination plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.

            Together each pair represents a connected edge in the graph.
        """
        edgeGen = DG.iterDependenciesByEdge(self._node, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for edge in edgeGen:
            yield getMAttr(edge[0]), getMAttr(edge[1]) if asMeta else edge

    def iterMetaDependenciesByNode(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=False,
                                   nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield the tagged node dependencies of the encapsulated dependency node. Filter based on the given properties.

        Each connected plug on the encapsulated dependency node will be traversed. A tagged node will be yielded if it has not been visited.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each node dependency as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the `mSystemId` of any tagged dependency does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the `mTypeId` of any tagged dependency does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrappers or `mNode` encapsulations for tagged node dependencies of the encapsulated dependency node.
            Type is determined by ``asMeta``.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)

        for connectedNode in DG.iterDependenciesByNode(self._node, directionType=directionType, traversalType=traversalType, walk=walk, filterTypes=nTypes):
            try:
                mType = getMTypeFromNode(connectedNode)
            except EXC.MayaLookupError:
                continue

            if mTypes is not None:
                if mType not in mTypes:
                    continue

            if mTypeBases is not None:
                for mTypeBase in mTypeBases:
                    if mTypeBase != mType and issubclass(mType, mTypeBase):
                        break
                else:
                    continue

            if mSystemIds is not None:
                if mType.SYSTEM_ID not in mSystemIds:
                    continue

            if mSystemRoots:
                if not mType.SYSTEM_ROOT:
                    continue

            yield mType(connectedNode) if asMeta else connectedNode

    def iterMetaDependenciesByPlug(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=False,
                                   nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield plugs which form a dependency between a tagged node and the encapsulated dependency node. Filter nodes based on the given properties.

        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kDownstream`, dependencies will correspond to destination plug connections.
        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kUpstream`, dependencies will correspond to source plug connections.

        Each connected plug on the encapsulated dependency node will be traversed. A plug on a tagged node will be yielded if it has not been visited.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each plug dependency as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`MSystemError`: If the `mSystemId` of a tagged dependency node does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If the `mTypeId` of a tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for plugs which form a dependency between a tagged node and the encapsulated dependency node.
            Type is determined by ``asMeta``.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)

        for connectedPlug in DG.iterDependenciesByPlug(self._node, directionType=directionType, traversalType=traversalType, walk=walk, filterTypes=nTypes):
            try:
                mType = getMTypeFromNode(connectedPlug.node())
            except EXC.MayaLookupError:
                continue

            if mTypes is not None:
                if mType not in mTypes:
                    continue

            if mTypeBases is not None:
                for mTypeBase in mTypeBases:
                    if mTypeBase != mType and issubclass(mType, mTypeBase):
                        break
                else:
                    continue

            if mSystemIds is not None:
                if mType.SYSTEM_ID not in mSystemIds:
                    continue

            if mSystemRoots:
                if not mType.SYSTEM_ROOT:
                    continue

            yield getMAttr(connectedPlug) if asMeta else connectedPlug

    def iterMetaDependenciesByEdge(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=False,
                                   nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield pairs of connected source and destination plugs which form a dependency between a tagged node and the encapsulated dependency node. Filter nodes based on the given properties.

        Each connected plug on the encapsulated dependency node will be traversed.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each pair of connected plug dependencies as `mAttrs` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as pairs of :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`MSystemError`: If the `mSystemId` of a tagged dependency node does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If the `mTypeId` of a tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            (:class:`OpenMaya.MPlug`, :class:`OpenMaya.MPlug`) | (T <= :class:`MetaAttribute`, T <= :class:`MetaAttribute`): A two-element :class:`tuple` of connected plugs which form a dependency between a tagged node and the encapsulated dependency node.

            #. A source plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.
            #. A corresponding destination plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.

            Together each pair represents a connected edge in the graph.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)

        for sourcePlug, destPlug in DG.iterDependenciesByEdge(self._node, directionType=directionType, traversalType=traversalType, walk=walk, filterTypes=nTypes):
            connectedNode = destPlug.node() if directionType == om2.MItDependencyGraph.kDownstream else sourcePlug.node()

            try:
                mType = getMTypeFromNode(connectedNode)
            except EXC.MayaLookupError:
                continue

            if mTypes is not None:
                if mType not in mTypes:
                    continue

            if mTypeBases is not None:
                for mTypeBase in mTypeBases:
                    if mTypeBase != mType and issubclass(mType, mTypeBase):
                        break
                else:
                    continue

            if mSystemIds is not None:
                if mType.SYSTEM_ID not in mSystemIds:
                    continue

            if mSystemRoots:
                if not mType.SYSTEM_ROOT:
                    continue

            yield getMAttr(sourcePlug), getMAttr(destPlug) if asMeta else sourcePlug, destPlug

    def iterMetaNetworkByNode(self, directionType=om2.MItDependencyGraph.kDownstream, stepOver=True,
                              nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield tagged dependency nodes which are connected contiguously within the meta network of the encapsulated dependency node. Filter based on the given properties.

        Each connected plug on the encapsulated dependency node will be traversed. All adjacent dependency paths are traversed for each connected node.
        A connected node will be yielded if it has not been visited.

        Note:
            Traversal is pruned when:

            #. The source side of a connection is not a message type attribute.
            #. A connected node is not tagged with an `mTypeId`.
            #. ``stepOver`` is :data:`False` and a connected node does not meet the given filter requirements of ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``.

        Args:
            directionType (:class:`int`, optional): The direction of traversal through the meta network of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            stepOver (:class:`bool`, optional): Whether to continue traversing connections if a node does not meet the given filter requirements of
                ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each dependency node as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If the `mSystemId` of any tagged dependency node does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If the `mTypeId` of any tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrappers or `mNode` encapsulations for contiguous tagged dependency nodes within the meta network of the encapsulated dependency node.
            Type is determined by ``asMeta``.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)
        seenNodeSet = OM.MObjectSet([self._node])
        nodeQueue = collections.deque([self._node])

        while nodeQueue:
            currentNode = nodeQueue.popleft()

            # Walking must be disabled to ensure only direct connections are traversed
            # Node type filtering must be delayed so that we can step over invalid node types
            for sourcePlug, destPlug in DG.iterDependenciesByEdge(currentNode, directionType=directionType, walk=False):
                connectedNode = destPlug.node() if directionType == om2.MItDependencyGraph.kDownstream else sourcePlug.node()

                # Prune if non-mNode or non-message source
                try:
                    mType = getMTypeFromNode(connectedNode)
                except EXC.MayaLookupError:
                    continue

                if not sourcePlug.attribute().hasFn(om2.MFn.kMessageAttribute):
                    continue

                # Prune if seen (must come after attribute type pruning in case an mNode is connected via multiple attributes)
                if not seenNodeSet.add(connectedNode):
                    continue

                # Filter
                if not OM.hasCompatibleType(connectedNode, types=nTypes):
                    if stepOver:
                        nodeQueue.append(connectedNode)
                    continue

                if mTypes is not None:
                    if mType not in mTypes:
                        if stepOver:
                            nodeQueue.append(connectedNode)
                        continue

                if mTypeBases is not None:
                    for mTypeBase in mTypeBases:
                        if mTypeBase != mType and issubclass(mType, mTypeBase):
                            break
                    else:
                        if stepOver:
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemIds is not None:
                    if mType.SYSTEM_ID not in mSystemIds:
                        if stepOver:
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemRoots:
                    if not mType.SYSTEM_ROOT:
                        if stepOver:
                            nodeQueue.append(connectedNode)
                        continue

                yield mType(connectedNode) if asMeta else connectedNode

                nodeQueue.append(connectedNode)

    def iterMetaNetworkByPlug(self, directionType=om2.MItDependencyGraph.kDownstream, stepOver=True,
                              nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield plugs which form connections between contiguous tagged dependency nodes within the meta network of the encapsulated dependency node. Filter based on the given properties.

        Each connected plug on the encapsulated dependency node will be traversed. All adjacent dependency paths are traversed for each connected node.
        A connected plug will be yielded if it has not been visited.

        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kDownstream`, connections will correspond to destination plugs.
        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kUpstream`, connections will correspond to source plugs.

        Note:
            Traversal is pruned when:

            #. The source side of a connection is not a message type attribute.
            #. A connected node is not tagged with an `mTypeId`.
            #. ``stepOver`` is :data:`False` and a connected node does not meet the given filter requirements of ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``.

        Args:
            directionType (:class:`int`, optional): The direction of traversal through the meta network of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            stepOver (:class:`bool`, optional): Whether to continue traversing connections if a node does not meet the given filter requirements of
                ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`MSystemError`: If the `mSystemId` of a tagged dependency node does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If the `mTypeId` of a tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for plugs which form connections between contiguous tagged dependency nodes within the meta network of the encapsulated dependency node.
            Type is determined by ``asMeta``.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)
        seenNodeSet = OM.MObjectSet([self._node])
        nodeQueue = collections.deque([self._node])

        while nodeQueue:
            currentNode = nodeQueue.popleft()

            # Walking must be disabled to ensure only direct connections are traversed
            # Node type filtering must be delayed so that we can step over invalid node types
            for sourcePlug, destPlug in DG.iterDependenciesByEdge(currentNode, directionType=directionType, walk=False):
                connectedPlug = destPlug if directionType == om2.MItDependencyGraph.kDownstream else sourcePlug
                connectedNode = connectedPlug.node()

                # Prune if non-mNode or non-message source
                try:
                    mType = getMTypeFromNode(connectedNode)
                except EXC.MayaLookupError:
                    continue

                if not sourcePlug.attribute().hasFn(om2.MFn.kMessageAttribute):
                    continue

                # Filter
                if not OM.hasCompatibleType(connectedNode, types=nTypes):
                    if stepOver and seenNodeSet.add(connectedNode):
                        nodeQueue.append(connectedNode)
                    continue

                if mTypes is not None:
                    if mType not in mTypes:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mTypeBases is not None:
                    for mTypeBase in mTypeBases:
                        if mTypeBase != mType and issubclass(mType, mTypeBase):
                            break
                    else:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemIds is not None:
                    if mType.SYSTEM_ID not in mSystemIds:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemRoots:
                    if not mType.SYSTEM_ROOT:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                yield getMAttr(connectedPlug) if asMeta else connectedPlug

                if seenNodeSet.add(connectedNode):
                    nodeQueue.append(connectedNode)

    def iterMetaNetworkByEdge(self, directionType=om2.MItDependencyGraph.kDownstream, stepOver=True,
                              nTypes=None, mTypes=None, mTypeBases=None, mSystemIds=None, mSystemRoots=False, asMeta=False):
        """Yield pairs of source and destination plugs which form connections between contiguous tagged dependency nodes within the meta network of the encapsulated dependency node. Filter based on the given properties.

        Each connected plug on the encapsulated dependency node will be traversed. All adjacent dependency paths are traversed for each connected node.

        Note:
            Traversal is pruned when:

            #. The source side of a connection is not a message type attribute.
            #. A connected node is not tagged with an `mTypeId`.
            #. ``stepOver`` is :data:`False` and a connected node does not meet the given filter requirements of ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``.

        Args:
            directionType (:class:`int`, optional): The direction of traversal through the meta network of the encapsulated dependency node.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream traversal of the encapsulated dependency node. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            stepOver (:class:`bool`, optional): Whether to continue traversing connections if a node does not meet the given filter requirements of
                ``nTypes``, ``mTypes``, ``mTypeBases``, ``mSystemIds``, ``mSystemRoots``. Defaults to :data:`True`.
            nTypes (iterable [:class:`int`], optional): Sequence of type constants from :class:`OpenMaya.MFn` used to filter tagged dependency nodes based on node type.
                Only consider dependency nodes if a corresponding :class:`OpenMaya.MObject` is compatible with one of the given type constants.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types.
                Defaults to :data:`None` - the node type constants used for filtering will be determined by calling :func:`getNodeTypeConstants` with ``mTypes``.
            mTypes (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their `mType`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` filtering will occur.
            mTypeBases (iterable [:class:`type`], optional): Sequence of class types which are (non-strict) subclasses of :class:`Meta`, used to filter tagged dependency nodes based on their inherited `mTypes`.
                Only consider dependency nodes which are tagged with an `mTypeId` corresponding to an `mType` that inherits from one of the given `mTypes`.
                Defaults to :data:`None` - no `mType` inheritance filtering will occur.
            mSystemIds (iterable [:class:`basestring`], optional): Sequence of `mSystem` identifiers, used to filter tagged dependency nodes based on their `mSystemId`.
                Only consider dependency nodes which are tagged with an `mSystemId` corresponding to one of the given identifiers.
                Defaults to :data:`None` - no `mSystemId` filtering will occur.
            mSystemRoots (:class:`bool`, optional): Whether to only consider dependency nodes which are tagged as an `mSystemRoot`.
                Defaults to :data:`False` - no `mSystemRoot` filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each pair of connected plugs as `mAttrs` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as pairs of :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`MSystemError`: If the `mSystemId` of a tagged dependency node does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If the `mTypeId` of a tagged dependency node does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            (:class:`OpenMaya.MPlug`, :class:`OpenMaya.MPlug`) | (T <= :class:`MetaAttribute`, T <= :class:`MetaAttribute`): A two-element :class:`tuple` of plugs representing a connection between contiguous tagged dependency nodes within the meta network of the encapsulated dependency node.

            #. A source plug for a connection between contiguous tagged dependency nodes. Type is determined by ``asMeta``.
            #. A corresponding destination plug for a connection between contiguous tagged dependency nodes. Type is determined by ``asMeta``.

            Together each pair represents a connected edge in the graph.
        """
        nTypes = nTypes or getNodeTypeConstants(mTypes=mTypes or mTypeBases)
        seenNodeSet = OM.MObjectSet([self._node])
        nodeQueue = collections.deque([self._node])

        while nodeQueue:
            currentNode = nodeQueue.popleft()

            # Walking must be disabled to ensure only direct connections are traversed
            # Node type filtering must be delayed so that we can step over invalid node types
            for sourcePlug, destPlug in DG.iterDependenciesByEdge(currentNode, directionType=directionType, walk=False):
                connectedNode = destPlug.node() if directionType == om2.MItDependencyGraph.kDownstream else sourcePlug.node()

                # Prune if non-mNode or non-message source
                try:
                    mType = getMTypeFromNode(connectedNode)
                except EXC.MayaLookupError:
                    continue

                if not sourcePlug.attribute().hasFn(om2.MFn.kMessageAttribute):
                    continue

                # Filter
                if not OM.hasCompatibleType(connectedNode, types=nTypes):
                    if stepOver and seenNodeSet.add(connectedNode):
                        nodeQueue.append(connectedNode)
                    continue

                if mTypes is not None:
                    if mType not in mTypes:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mTypeBases is not None:
                    for mTypeBase in mTypeBases:
                        if mTypeBase != mType and issubclass(mType, mTypeBase):
                            break
                    else:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemIds is not None:
                    if mType.SYSTEM_ID not in mSystemIds:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                if mSystemRoots:
                    if not mType.SYSTEM_ROOT:
                        if stepOver and seenNodeSet.add(connectedNode):
                            nodeQueue.append(connectedNode)
                        continue

                yield getMAttr(sourcePlug), getMAttr(destPlug) if asMeta else sourcePlug, destPlug

                if seenNodeSet.add(connectedNode):
                    nodeQueue.append(connectedNode)


# ----------------------------------------------------------------------------
# --- MetaDag (DAG Nodes) ---
# ----------------------------------------------------------------------------

class MetaDag(Meta):
    """A DAG node encapsulation designed to provide base level metadata functionality to higher level `mSystem` abstractions.

    **Interface:**

        The encapsulation associates a low level interface with the node, similiar to that of an `OpenMaya`_ function set.
        The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

        The encapsulation stores a :attr:`path` to the node for operations which require a distinct ancestral description.

        Typically higher level `mSystems` may define specific relationships between their `mTypes`.
        These relationships can be registered within the dependency graph for type specific identification of metadata.

    **Inherited:**

        See :class:`Meta` for information relating to :ref:`registration <Meta_registration>`, :ref:`attributes <Meta_attributes>`, :ref:`validation <Meta_validation>`
        and :ref:`subclassing <Meta_subclassing>`.

        The following amendments are made to the subclassing contract:

        - Subclass initialisers may also accept an :class:`OpenMaya.MDagPath` instance for the ``node`` argument.
        - The :attr:`NODE_TYPE_CONSTANT` and :attr:`~Meta.NODE_TYPE_ID` must be assigned DAG node types.
    """

    NODE_TYPE_CONSTANT = om2.MFn.kDagNode
    """:class:`int`: Defines which :class:`OpenMaya.MFn` dependency node types are compatible with this `mType`.

    Type compatibility is determined by calling :meth:`~OpenMaya.MObject.hasFn` on an :class:`OpenMaya.MObject` wrapper of the dependency node.

    :access: R
    """

    EXCLUSIVE = set(["instanceNumber"])
    """:class:`set` [:class:`str`]: Defines exclusive instance attributes which can be set using the default :meth:`object.__setattr__` behaviour.

    - Includes the names of property setters defined by this `mType`.

    Invoking :meth:`Meta.__setattr__` with a non-exclusive attribute will attempt to access the attribute via the encapsulated dependency node.

    :access: R
    """

    # --- Instantiation ----------------------------------------------------------------------------

    def __new__(cls, *args, **kwargs):
        """Base constructor for any `mType` that is a (non-strict) subclass of :class:`MetaDag`.

        If a DAG node is received, the internal registry will be checked for an `mNode` with the same encapsulated DAG node, instance number and derived `mType`.
        A new `mNode` will be constructed for the DAG node if the registry does not contain a matching `mNode`.

        If no DAG node is given, an empty `mNode` will be constructed and assigned a new DAG node.
        """
        node = kwargs.get("node", args[0] if args else None)

        if node is not None:
            if isinstance(node, om2.MDagPath):
                nodePath = node
                nodeWrapper = nodePath.node()
                OM.validateNodeType(nodeWrapper, nodeType=cls.NODE_TYPE_CONSTANT, nodeTypeId=cls.NODE_TYPE_ID)
            else:
                nodeWrapper = node
                OM.validateNodeType(nodeWrapper, nodeType=cls.NODE_TYPE_CONSTANT, nodeTypeId=cls.NODE_TYPE_ID)
                nodePath = om2.MDagPath.getAPathTo(nodeWrapper)

            try:
                mNode = getMNodeFromRegistry(nodeWrapper)
            except KeyError:
                pass
            else:
                if type(mNode) is cls and mNode.instanceNumber == nodePath.instanceNumber():
                    # The second value indicates whether the metaclass should bypass the initialiser
                    return mNode, True

        # Bypass the Meta constructor
        mNode = object.__new__(cls, *args, **kwargs)

        if node:
            object.__setattr__(mNode, "_node", nodeWrapper)
            object.__setattr__(mNode, "_path", nodePath)

        return mNode, False

    def __init__(self, node=None, name=None, nType="transform", register=False, stateTracking=True):
        """Initialiser for :class:`MetaDag` `mNodes`.

        Args:
            node (:class:`OpenMaya.MObject` | :class:`OpenMaya.MDagPath`, optional): Wrapper or path of a DAG node to encapsulate.
                Defaults to :data:`None` - A new DAG node will be created using the ``nType``.
            name (:class:`basestring`, optional): Name for the new DAG node if ``node`` is :data:`None`.
                Defaults to :data:`None` - The `mTypeId` will be used.
            nType (:class:`basestring`, optional): Node type identifier used to create a DAG node if ``node`` is :data:`None`.
                If the node type derives from a shape, its transform will be encapsulated. Defaults to ``'transform'``.
            register (:class:`bool`, optional): Whether to register this `mNode` internally,
                tagging the encapsulated DAG node with the `mTypeId` and `mSystemId` of the derived `mType`. Defaults to :data:`False`.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated DAG node.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``nType`` is an invalid node type identifier or is incompatible with the accepted node types of the derived `mType`.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` is an :class:`OpenMaya.MObject` that does not reference a DAG node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` references a DAG node whose type is incompatible with the accepted node types of the derived `mType`.
        """
        log.debug("MetaDag.__init__(node={}, name={}, nType={}, register={}, stateTracking={})".format(node, name, nType, register, stateTracking))

        # Create a node if one has not been provided by the caller, including by potential subclass callers
        try:
            object.__getattribute__(self, "_node")
        except AttributeError:
            node = self._createNode(nType, name)
            path = om2.MDagPath.getAPathTo(node)
            object.__setattr__(self, "_node", node)
            object.__setattr__(self, "_path", path)

        super(MetaDag, self).__init__(node=node, name=name, nType=nType, register=register, stateTracking=stateTracking)

        # Override exclusive data
        self._nodeFn = om2.MFnDagNode(self._path)
        self._partialName = self._path.partialPathName()

    def _createNode(self, nType, name):
        """Creates a DAG node for encapsulation.

        To be called exclusively by :meth:`__init__` when the ``node`` argument is set to :data:`None`.
        Designed to be overridden by derived `mTypes` which may want to implement specialised rules for creating DAG nodes.

        Raises:
            :exc:`~exceptions.ValueError`: If ``nType`` is an invalid node type identifier or is incompatible with the accepted node types of the derived `mType`.

        Returns:
            :class:`OpenMaya.MObject`: Wrapper of the new DAG node.
        """
        node = DAG.createNode(nType)

        try:
            OM.validateNodeType(node, nodeType=type(self).NODE_TYPE_CONSTANT, nodeTypeId=type(self).NODE_TYPE_ID)
        except EXC.MayaTypeError:
            DAG.deleteNode(node)
            raise ValueError("{}: Node type is incompatible with {} mNodes".format(nType, type(self)))

        DG.renameNode(node, name or type(self).__name__)

        return node

    # --- Public : Properties (baseclass overrides) ----------------------------------------------------

    @property
    def isValid(self):
        """:class:`bool`: :data:`True` if the internal :class:`OpenMaya.MObject` and :class:`OpenMaya.MDagPath` reference a valid DAG node, otherwise :data:`False`.

        Note:
            This property is not subject to :attr:`Meta.stateTracking` and is therefore accessible even if the encapsulated DAG node is deleted.

        :access: R
        """
        return self._nodeHandle.isValid() and self._path.isValid() and self._path.fullPathName()

    @property
    def nodeFn(self):
        """:class:`OpenMaya.MFnDagNode`: Function set encapsulation of the internal :attr:`path` to the encapsulated DAG node.

        :access: R
        """
        return om2.MFnDagNode(self._path)

    @property
    def shortName(self):
        """:class:`str`: Short name of the encapsulated DAG node.

        The short name has no qualifying path or namespace.
        It is not guaranteed to uniquely identify the node.

        :access: R
        """
        return self.partialName.split('|')[-1].split(':')[-1]

    @property
    def partialName(self):
        """:class:`str`: Partial name of the encapsulated DAG node for the current :attr:`path`.

        The partial name is qualified by a path and namespace where necessary.
        It is guaranteed to uniquely identify the node with the minimum amount of information necessary.

        :access: R
        """
        self._partialName = self._path.partialPathName()
        return self._partialName

    @property
    def fullName(self):
        """:class:`str`: Full name of the encapsulated DAG node for the current :attr:`path`.

        The full name is qualified by a path and namespace.
        It is guaranteed to uniquely identify the node with the maximum amount of information.

        :access: R
        """
        return self._path.fullPathName()

    # --- Public : Properties ----------------------------------------------------------------------------

    @property
    def isInstanced(self):
        """:class:`bool`: :data:`True` if the encapsulated DAG node is instanced, otherwise :data:`False`.

        :access: R
        """
        return self._path.isInstanced()

    @property
    def isIndirectInstance(self):
        """:class:`bool`: :data:`True` if the encapsulated DAG node is indirectly instanced, otherwise :data:`False`.

        :access: R
        """
        return DAG.isIndirectInstance(self._path)

    @property
    def path(self):
        """:class:`OpenMaya.MDagPath`: The internally referenced path to the encapsulated DAG node, used by operations which require a distinct ancestral description.

        The path can be updated by setting the :attr:`instanceNumber`.

        :access: R
        """
        return om2.MDagPath(self._path)

    @property
    def paths(self):
        """:class:`list` [:class:`OpenMaya.MDagPath`]: Paths to the encapsulated DAG node for all instances.

        :access: R
        """
        return [om2.MDagPath(path) for path in om2.MDagPath.getAllPathsTo(self._node)]

    @property
    def instanceNumber(self):
        """:class:`int`: The instance number for the internal :attr:`path` to the encapsulated DAG node.

        The internal :attr:`path` can be changed by setting this value.

        :access: RW
        """
        return self._path.instanceNumber()

    @instanceNumber.setter
    def instanceNumber(self, value):
        try:
            self._path = self.paths[value]
            self._nodeFn.setObject(self._path)
        except IndexError:
            raise ValueError("{!r}: Has no instance with instance number: {}".format(self, value))

    @property
    def instanceCount(self):
        """:class:`int`: The number of instances for the encapsulated DAG node.

        :access: R
        """
        return self._nodeFn.instanceCount(True)

    @property
    def childCount(self):
        """:class:`int`: The number of child nodes for the encapsulated DAG node.

        :access: R
        """
        return self._nodeFn.childCount()

    @property
    def parentCount(self):
        """:class:`int`: The number of parent nodes for the encapsulated DAG node.

        :access: R
        """
        return self._nodeFn.parentCount()

    # --- Protected ----------------------------------------------------------------------------

    def _updateExclusiveData(self):
        """Update internally cached DAG node data. Designed to be overloaded by subclasses.
        Called exclusively by :meth:`Meta._validate` if :attr:`isValid` was :data:`False` but the :class:`OpenMaya.MObject` wrapper of the encapsulated dependency node has been revalidated.
        """
        super(MetaDag, self)._updateExclusiveData()

        self._path = om2.MDagPath.getAPathTo(self._node)
        self._nodeFn = om2.MFnDagNode(self._path)

        if self._path.isInstanced():
            log.info(("{!r}: Revalidated mNode references an instanced DAG node. Set the `instanceNumber` property to update the internal DAG path.".format(self)))

    # --- Public : Retrieve ------------------------------------------------------------------------------

    def inspectVisibility(self):
        """Inspect the visibility of the encapsulated DAG node.

        The global visibility state of a node is given by :meth:`OpenMaya.MDagPath.isVisible`.
        If any of the return values are :data:`False`, the :attr:`path` visibility state will also be :data:`False`.

        Returns:
            (:class:`bool`, :class:`bool`, :class:`bool`, :class:`bool`): A four-element :class:`tuple`.

            #. Value of the ``'visibility'`` attribute for the encapsulated DAG node.
            #. Value of the ``'lodVisibility'`` attribute for the encapsulated DAG node.
            #. Visibility state of draw-overrides for the encapsulated DAG node.
               If :data:`False`, the ``'overrideEnabled'`` attribute is on and the ``'overrideVisibility'`` attribute is off.
            #. Visibility state for ancestors of encapsulated DAG node. If :data:`False`, the node is hidden because of an ancestor.
        """
        return DAG.inspectVisibility(self._path)

    def hasShapes(self):
        """Return whether the encapsulated DAG node has intermediate child shapes.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.

        Returns:
            :class:`bool`: :data:`True` the encapsulated DAG node has child shapes, :data:`False` otherwise.
        """
        return DAG.hasShapes(self._node)

    def hasIntermediateShapes(self):
        """Return whether the encapsulated DAG node has child shapes.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.

        Returns:
            :class:`bool`: :data:`True` if the encapsulated DAG node has intermediate child shapes, :data:`False` otherwise.
        """
        return DAG.hasIntermediateShapes(self._node)

    def hasChild(self, node):
        """Return whether the encapsulated transform has a given child.

        Args:
            node (:class:`OpenMaya.MObject`): Wrapper of a DAG node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a DAG node.

        Returns:
            :class:`bool`: :data:`True` if the encapsulated transform has ``node`` as a child, otherwise :data:`False`.
        """
        OM.validateNodeType(self._node, nodeType=om2.MFn.kTransform)
        OM.validateNodeType(node, nodeType=om2.MFn.kDagNode)

        return self._nodeFn.hasChild(node)

    def hasChildWithName(self, nodeShortName):
        """Return whether the encapsulated transform has a child with a given short name.

        Args:
            nodeShortName (:class:`basestring`): Short name of a DAG node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.

        Returns:
            :class:`bool`: :data:`True` if the encapsulated transform has a child with name ``nodeShortName``, otherwise :data:`False`.
        """
        OM.validateNodeType(self._node, nodeType=om2.MFn.kTransform)

        for child in self.iterChildren():
            if NAME.getNodeShortName(child) == nodeShortName:
                return True

        return False

    def hasParent(self, node):
        """Return whether the encapsulated transform has a given parent.

        Note:
            This operation queries each parent of :attr:`node` instead of the distinct parent referenced by :attr:`path`.

        Args:
            node (:class:`OpenMaya.MObject`): Wrapper of a transform.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a transform.

        Returns:
            :class:`bool`: :data:`True` if the encapsulated transform has ``node`` as one of its parents, otherwise :data:`False`.
        """
        OM.validateNodeType(node, nodeType=om2.MFn.kTransform)

        return self._nodeFn.hasParent(node)

    def hasParentWithName(self, nodeShortName):
        """Return whether the encapsulated transform has a parent with a given short name.

        Note:
            This operation queries each parent of :attr:`node` instead of the distinct parent referenced by :attr:`path`.

        Args:
            nodeShortName (:class:`basestring`): Short name of a DAG node.

        Returns:
            :class:`bool`: :data:`True` if the encapsulated DAG node has a parent with name ``nodeShortName``, otherwise :data:`False`.
        """
        for parent in self.iterParents():
            if NAME.getNodeShortName(parent) == nodeShortName:
                return True

        return False

    def getComponents(self, componentType=om2.MFn.kMeshVertComponent):
        """Return the components of the encapsulated shape for a specific component type.

        The result can be used to select the components of the encapsulated shape via an :class:`OpenMaya.MSelectionList`.

        Args:
            componentType (:class:`int`, optional): Component type constant from :class:`OpenMaya.MFn`, compatible with the encapsulated shape.
                See :data:`msTools.core.maya.constants.SHAPE_CONSTANT_COMPONENT_CONSTANTS_MAPPING` for a mapping of valid shape types to valid component type constants.
                Defaults to :attr:`OpenMaya.MFn.kMeshVertComponent`.

        Raises:
            :exc:`~exceptions.ValueError`: If the ``componentType`` is not compatible with the encapsulated shape.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated shape is neither a mesh, surface nor curve.

        Returns:
            :class:`OpenMaya.MObject`: Wrapper of the component indices and ``componentType``.
        """
        return COMPONENT.getComponentsFromShape(self._node, componentType=componentType)

    def getChildByName(self, childShortName, asMeta=False):
        """Return a child of the encapsulated transform.

        Args:
            childShortName (:class:`basestring`): Short name of a child node parented under the encapsulated transform.
            asMeta (:class:`bool`, optional): Whether to return the child as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If the encapsulated DAG node does not have a child with name ``childShortName``.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the child is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the child is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrapper or `mNode` encapsulation for the relative child node with name ``childShortName``.
            Type is determined by ``asMeta``.
        """
        child = DAG.getChildByName(self._node, childShortName)
        return getMNode(child) if asMeta else child

    def getChildPathByName(self, childShortName, asMeta=False):
        """Return a path to the child of the encapsulated transform, relative to :attr:`path`.

        Args:
            childShortName (:class:`basestring`): Short name of a child node parented under the encapsulated transform.
            asMeta (:class:`bool`, optional): Whether to return the child path as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MDagPath` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If the encapsulated DAG node does not have a child with name ``childShortName``.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the child is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the child is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: Path or `mNode` encapsulation for the relative child node with name ``childShortName``.
            Type is determined by ``asMeta``.
        """
        childPath = DAG.getChildPathByName(self._path, childShortName)
        return getMNodeFromPath(childPath) if asMeta else childPath

    def getParent(self, asMeta=False):
        """Return the parent transform of the encapsulated DAG node, relative to :attr:`path`.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the parent as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node does not have a parent transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the parent is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the parent is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrapper or `mNode` encapsulation for the relative parent node.
            Type is determined by ``asMeta``.
        """
        parent = DAG.getParent(self._path)
        return getMNode(parent) if asMeta else parent

    def getParentPath(self, asMeta=False):
        """Return a path to the parent transform of the encapsulated DAG node, relative to :attr:`path`.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the parent path as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MDagPath` encapsulation.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node does not have a parent transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and the parent is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and the parent is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: Path or `mNode` encapsulation for the relative parent node.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Returns the parent transform relative to the internal `mNode` path
                MetaDag.getParentPath(mNode)
                # Similiar to returning a path via the following Maya command
                maya.cmds.listRelatives(childPartialName, parent=True, path=True)
        """
        parentPath = DAG.getParentPath(self._path)
        return getMNodeFromPath(parentPath) if asMeta else parentPath

    def iterShapes(self, nonIntermediates=True, intermediates=True, filterTypes=None, asMeta=False):
        """Yield shapes parented under the encapsulated transform.

        Note:
            At least one of ``nonIntermediates`` or ``intermediates`` must be :data:`True`.

        Args:
            nonIntermediates (:class:`bool`, optional): Whether to yield non-intermediate shapes. Defaults to :data:`True`.
            intermediates (:class:`bool`, optional): Whether to yield intermediate shapes. Defaults to :data:`True`.
            filterTypes (iterable [:class:`int`], optional): Filter child shapes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kCamera`, :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each child shape as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`~exceptions.ValueError`: If neither ``nonIntermediates`` nor ``intermediates`` is :data:`True`.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a child shape is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a child shape is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative child shape nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields child mesh shapes directly under the encapsulated `mNode` transform
                MetaDag.iterShapes(mNode, filterTypes=(OpenMaya.MFn.kMesh,))
                # Yields child non-mesh shapes directly under the encapsulated `mNode` transform
                MetaDag.iterShapes(mNode, filterTypes=(-OpenMaya.MFn.kMesh,))
        """
        for shape in DAG.iterShapes(self._node, nonIntermediates=nonIntermediates, intermediates=intermediates, filterTypes=filterTypes):
            yield getMNode(shape) if asMeta else shape

    def iterShapesByPath(self, nonIntermediates=True, intermediates=True, filterTypes=None, asMeta=False):
        """Yield paths to shapes parented under the encapsulated transform, relative to :attr:`path`.

        Note:
            At least one of ``nonIntermediates`` or ``intermediates`` must be :data:`True`.

        Args:
            nonIntermediates (:class:`bool`, optional): Whether to yield non-intermediate shapes. Defaults to :data:`True`.
            intermediates (:class:`bool`, optional): Whether to yield intermediate shapes. Defaults to :data:`True`.
            filterTypes (iterable [:class:`int`], optional): Filter child shapes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kCamera`, :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield paths to each child shape as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`~exceptions.ValueError`: If neither ``nonIntermediates`` nor ``intermediates`` is :data:`True`.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a child shape is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a child shape is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: Paths or `mNode` encapsulations for the relative child shape nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields child mesh shapes relative to the internal `mNode` path
                MetaDag.iterShapesByPath(mNode, filterTypes=(OpenMaya.MFn.kMesh,))
                # Yields child non-mesh shape relative to the internal `mNode` path
                MetaDag.iterShapesByPath(mNode, filterTypes=(-OpenMaya.MFn.kMesh,))
                # Called without filtering is similiar to returning paths via the following Maya command
                maya.cmds.listRelatives(parentPartialName, shapes=True, path=True)
        """
        for shapePath in DAG.iterShapesByPath(self._path, nonIntermediates=nonIntermediates, intermediates=intermediates, filterTypes=filterTypes):
            yield getMNodeFromPath(shapePath) if asMeta else shapePath

    def iterChildren(self, filterTypes=None, asMeta=False):
        """Yield children parented under the encapsulated transform.

        Args:
            filterTypes (iterable [:class:`int`], optional): Filter children based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
                :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each child as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a child is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a child is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative child nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields child transforms directly under the encapsulated `mNode` transform
                MetaDag.iterChildren(mNode, filterTypes=(OpenMaya.MFn.kTransform,))
                # Yields child transforms directly under the encapsulated `mNode` transform, excluding constraints
                MetaDag.iterChildren(mNode, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
        """
        for child in DAG.iterChildren(self._node, filterTypes=filterTypes):
            yield getMNode(child) if asMeta else child

    def iterChildrenByPath(self, filterTypes=None, asMeta=False):
        """Yield paths to children parented under the encapsulated transform, relative to :attr:`path`.

        Args:
            filterTypes (iterable [:class:`int`], optional): Filter children based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
                :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield paths to each child as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a child is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a child is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: Paths or `mNode` encapsulations for the relative child nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields child transforms relative to the internal `mNode` path
                MetaDag.iterChildren(mNode, filterTypes=(OpenMaya.MFn.kTransform,))
                # Yields child transforms relative to the internal `mNode` path, excluding constraints
                MetaDag.iterChildren(mNode, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
                # Called without filtering is similiar to returning paths via the following Maya command
                maya.cmds.listRelatives(parentPartialName, children=True, path=True)
        """
        for childPath in DAG.iterChildrenByPath(self._path, filterTypes=filterTypes):
            yield getMNodeFromPath(childPath) if asMeta else childPath

    def iterDescendants(self, depthLimit=-1, breadth=False, filterTypes=None, asMeta=False):
        """Yield descendants of the encapsulated transform.

        Args:
            depthLimit (:class:`int`, optional): Limit the depth of iteration down descendant branches. Defaults to ``-1``.

                - ``<0`` : Full traversal of descendants.
                - ``=0`` : No traversal.
                - ``>0`` : Traverse until the given depth.

            breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
                If :data:`True`, exhaust an entire level of descendants before proceeding to the next level.
                If :data:`False`, exhaust an entire branch of descendants before proceeding to the next closest branch using depth first traversal.
            filterTypes (iterable [:class:`int`], optional): Filter descendants based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
                :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each descendant as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a descendant is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a descendant is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative descendant nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields descendant transforms relative to the encapsulated `mNode` transform
                MetaDag.iterDescendants(mNode, filterTypes=(OpenMaya.MFn.kTransform,))
                # Yields descendant transforms relative to the encapsulated `mNode` transform, excluding constraints
                MetaDag.iterDescendants(mNode, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
        """
        for descendant in DAG.iterDescendants(root=self._node, depthLimit=depthLimit, breadth=breadth, filterTypes=filterTypes):
            yield getMNode(descendant) if asMeta else descendant

    def iterDescendantsByPath(self, allPaths=False, depthLimit=-1, breadth=False, filterTypes=None, asMeta=False):
        """Yield paths to descendants of the encapsulated transform, relative to :attr:`path`.

        Args:
            allPaths (:class:`bool`): Whether to yield a path for every instance in the descendant hierarchy of :attr:`path`.
                If :data:`False`, only yield a single path to instanced nodes in the descendant hierarchy of :attr:`path`.
                Defaults to :data:`False`.
            depthLimit (:class:`int`, optional): Limit the depth of iteration down descendant branches. Defaults to ``-1``.

                - ``<0`` : Full traversal of descendants.
                - ``=0`` : No traversal.
                - ``>0`` : Traverse until the given depth.

            breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
                If :data:`True`, exhaust an entire level of descendants before proceeding to the next level.
                If :data:`False`, exhaust an entire branch of descendants before proceeding to the next closest branch using depth first traversal.
            filterTypes (iterable [:class:`int`], optional): Filter descendants based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
                :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield paths to each descendant as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a descendant is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a descendant is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: Paths or `mNode` encapsulations for the relative descendant nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields descendant transforms relative to the internal `mNode` path
                MetaDag.iterDescendantsByPath(mNode, filterTypes=(OpenMaya.MFn.kTransform,))
                # Yields descendant transforms relative to the internal `mNode` path, excluding constraints
                MetaDag.iterDescendantsByPath(mNode, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
                # Called without filtering is similiar to returning paths via the following Maya command
                maya.cmds.listRelatives(rootPartialName, allDescendants=True, path=True)
        """
        for descendantPath in DAG.iterDescendantsByPath(rootPath=self._path, allPaths=allPaths, depthLimit=depthLimit, breadth=breadth, filterTypes=filterTypes):
            yield getMNodeFromPath(descendantPath) if asMeta else descendantPath

    def iterParents(self, filterTypes=None, asMeta=False):
        """Yield parents of the encapsulated DAG node.

        Note:
            By default the world object will be yielded if the encapsulated DAG node is parented to the world.
            The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this parent if necessary.

        Args:
            filterTypes (iterable [:class:`int`], optional): Filter parents based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kConstraint`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kConstraint`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each parent as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a parent is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a parent is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative parent nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields parents relative to the encapsulated `mNode` DAG node
                MetaDag.iterParents(mNode)
                # Yields parent transforms relative to the encapsulated `mNode` DAG node, excluding constraints
                MetaDag.iterParents(mNode, filterTypes=(-OpenMaya.MFn.kConstraint,))
                # Yields parent transforms relative to the encapsulated `mNode` DAG node
                MetaDag.iterParents(mNode, filterTypes=(-OpenMaya.MFn.kWorld,))
        """
        for parent in DAG.iterParents(self._node):
            yield getMNode(parent) if asMeta else parent

    def iterAncestors(self, depthLimit=-1, breadth=False, filterTypes=None, asMeta=False):
        """Yield ancestors of the encapsulated DAG node.

        Note:
            By default the world :class:`OpenMaya.MObject` will be yielded since it is the root ancestor of all children.
            The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this ancestor if necessary.

        Args:
            depthLimit (:class:`int`, optional): Limit the depth of iteration up ancestral branches. Defaults to ``-1``.

                - ``<0`` : Full traversal of ancestors.
                - ``=0`` : No traversal.
                - ``>0`` : Traverse until the given depth.

            breadth (:class:`bool`, optional): Whether to use breadth first traversal. Defaults to :data:`False`.
                If :data:`True`, exhaust an entire level of ancestors before proceeding to the next level.
                If :data:`False`, exhaust an entire branch of ancestors before proceeding to the next closest branch using depth first traversal.
            filterTypes (iterable [:class:`int`], optional): Filter ancestors based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kConstraint`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kConstraint`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each ancestor as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and an ancestor is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and an ancestor is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative ancestor nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields ancestors relative to the encapsulated `mNode` DAG node
                MetaDag.iterAncestors(mNode)
                # Yields ancestors relative to the encapsulated `mNode` DAG node, excluding constraints
                MetaDag.iterAncestors(mNode, filterTypes=(-OpenMaya.MFn.kConstraint,))
                # Yields ancestor transforms relative to the encapsulated `mNode` DAG node
                MetaDag.iterAncestors(mNode, filterTypes=(-OpenMaya.MFn.kWorld,))
        """
        for ancestor in DAG.iterAncestors(self._node, depthLimit=depthLimit, breadth=breadth, filterTypes=filterTypes):
            yield getMNode(ancestor) if asMeta else ancestor

    def iterRelatives(self, shapes=False, children=False, descendants=False, parents=False, ancestors=False, filterTypes=None, asMeta=False):
        """Yield relatives of the encapsulated DAG node.

        Note:
            By default if ``parents`` is :data:`True`, the world object will be yielded if the encapsulated DAG node is parented to the world.
            By default if ``ancestors`` is :data:`True`, the world object will be yielded since it is the root ancestor of all children.
            The :attr:`~OpenMaya.MFn.kWorld` type constant can be used to exclude this ancestor if necessary.

        Args:
            shapes (:class:`bool`, optional): Whether to yield child shapes. Defaults to :data:`False`.
            children (:class:`bool`, optional): Whether to yield all children. Overrides the ``shapes`` argument. Defaults to :data:`False`.
            descendants (:class:`bool`, optional): Whether to yield all descendants. Traversal will be depth first.
                Overrides the ``shapes`` and ``children`` arguments. Defaults to :data:`False`.
            parents (:class:`bool`, optional): Whether to yield parent transforms. If the encapsulated DAG node is instanced, the parent of each instance will be yielded.
                Defaults to :data:`False`.
            ancestors (:class:`bool`, optional): Whether to yield ancestor transforms. If the encapsulated DAG node is instanced, the ancestors of each instance will be yielded.
                Traversal will be depth first. Overrides the ``parents`` argument. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter relative nodes based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh` or :attr:`~OpenMaya.MFn.kConstraint`.
                Applicable values include :attr:`~OpenMaya.MFn.kTransform`, :attr:`~OpenMaya.MFn.kShape`, :attr:`~OpenMaya.MFn.kCamera`,
                :attr:`~OpenMaya.MFn.kMesh`, :attr:`~OpenMaya.MFn.kNurbsCurve`, :attr:`~OpenMaya.MFn.kNurbsSurface`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each relative as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If either ``shapes``, ``children`` or ``descendants`` is :data:`True` and the encapsulated DAG node does not reference a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If either ``parents`` or ``ancestors`` is :data:`True` and the encapsulated DAG node does not reference a DAG node.
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a relative is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a relative is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`MetaDag`: Wrappers or `mNode` encapsulations for the relative nodes.
            Type is determined by ``asMeta``.

        Example:
            .. code-block:: python

                # Yields child transforms relative to the encapsulated `mNode` transform
                MetaDag.iterRelatives(mNode, children=True, filterTypes=(OpenMaya.MFn.kTransform,))
                # Yields child transforms relative to the encapsulated `mNode` transform, excluding constraints
                MetaDag.iterRelatives(mNode, children=True, filterTypes=(OpenMaya.MFn.kTransform, -OpenMaya.MFn.kConstraint))
                # Yields ancestor transforms relative to the encapsulated `mNode` DAG node
                MetaDag.iterRelatives(mNode, ancestors=True, filterTypes=(-OpenMaya.MFn.kWorld,))
        """
        for relative in DAG.iterRelatives(self._node, shapes=shapes, children=children, descendants=descendants, parents=parents, ancestors=ancestors, filterTypes=filterTypes):
            yield getMNode(relative) if asMeta else relative

    # --- Public : Modify -------------------------------------------------------------------------------

    def renameShapes(self):
        """Rename all child shape nodes under the encapsulated transform.

        Names for non-instanced shapes will follow the format ``'<parentShortName>_shape<##>'``.

        Names for instanced shapes will follow the format ``'<parentShortName>_instance_shape<##>'``.

        - ``'<parentShortName>'`` will correspond to the parent of the zeroth indexed shape instance.
        - The addition of the ``'instance'`` token aims to prevent confusion for instances whose parent does not correspond to ``'<parentShortName>'``.

        A recursive call will be made for the parents of every instanced shape in order to avoid name clashes with their own child shapes.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
        """
        DAG.renameShapes(self._node)

    def addChildAsInstance(self, child, resultAsMeta=False):
        """Instance a node under the encapsulated transform.

        Note:
            The ``child`` instance will always be added relative to the encapsulated transform since all instances must share the same transforms.

        Args:
            child (:class:`OpenMaya.MObject`): Wrapper of a DAG node to instance.
            resultAsMeta (:class:`bool`, optional): Whether to return the path to the instanced node as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MDagPath` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``child`` does not reference a DAG node.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`~exceptions.RuntimeError`: If ``child`` is already a child of the encapsulated transform.

        Returns:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: A path or `mNode` encapsulation of ``child`` for the first instance of the encapsulated transform.
        """
        childPath = DAG.instance(child, self._node)
        return getMNodeFromPath(childPath) if resultAsMeta else childPath

    def addChild(self, childPath, relative=False, renameShapes=True, resultAsMeta=False):
        """Reparent a DAG node under the encapsulated transform.

        Args:
            childPath (:class:`OpenMaya.MDagPath`): Path to a DAG node to reparent.
            relative (:class:`bool`): Whether to preserve the current relative transforms of the child DAG node under its new parent.

                If :data:`True`:

                - If ``childPath`` is uninstanced, it will be reparented directly under the encapsulated transform.
                - If ``childPath`` is instanced, it will be reinstanced directly under the encapsulated transform.
                - If ``childPath`` is indirectly instanced, other instances with the same parent will be reinstanced under their own intermediary transform,
                  inserted between the encapsulated transform and the instance.

                If :data:`False`, absolute reparenting of ``childPath`` will be relative to the world space transforms of :attr:`path`:

                - If ``childPath`` is an uninstanced shape, it will be reparented under a new intermediary transform, inserted between encapsulated transform and the shape.
                - If ``childPath`` is an uninstanced transform, its local matrix will inherit the relative transform from the old parent to the encapsulated transform.
                - If ``childPath`` is directly instanced, it will be reinstanced under a new intermediary transform, inserted between encapsulated transform and the instance.
                - If ``childPath`` is indirectly instanced, other instances with the same parent will be parented under a new intermediary transform,
                  inserted between encapsulated transform and the instance.

                Defaults to :data:`False`.

            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the new and old parents if ``childPath`` is a shape.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return paths to the reparented node as `mNodes` each resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is not a transform.
            :exc:`~exceptions.RuntimeError`: If ``childPath`` is already a child of the encapsulated transform.

        Returns:
            :class:`list` [:class:`OpenMaya.MDagPath`] | :class:`list` [T <= :class:`MetaDag`]: A path or `mNode` encapsulation to the reparented node for the first instance of each new parent.
            If ``childPath`` is an indirect instance there will be multiple paths. Type is determined by ``resultAsMeta``.
        """
        if relative:
            reparentedPaths = DAG.relativeReparent(childPath, parent=self._node, renameShapes=renameShapes)
        else:
            reparentedPaths = DAG.absoluteReparent(childPath, parent=self._path, renameShapes=renameShapes)

        return [getMNodeFromPath(path) for path in reparentedPaths] if resultAsMeta else reparentedPaths

    def addParent(self, parent, resultAsMeta=False):
        """Instance the encapsulated DAG node under a transform.

        Note:
            The encapsulated DAG node instance will always be added relative to ``parent`` since all instances must share the same transforms.

        Args:
            parent (:class:`OpenMaya.MObject`): Wrapper of a transform.
            resultAsMeta (:class:`bool`, optional): Whether to return the path to the instanced node as an `mNode` resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MDagPath` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` does not reference a transform.
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node is already a child of ``parent``.

        Returns:
            :class:`OpenMaya.MDagPath` | T <= :class:`MetaDag`: A path or `mNode` encapsulation of the encapsulated DAG node for the first instance of the new ``parent``.
        """
        childPath = DAG.instance(self._node, parent)
        return getMNodeFromPath(childPath) if resultAsMeta else childPath

    def absoluteReparent(self, parentPath=None, renameShapes=True, resultAsMeta=False):
        """Reparent the encapsulated DAG node under a transform or the world whilst preserving its current world space transforms.

        Note:
            - If the encapsulated DAG node is an uninstanced shape, it will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.
            - If the encapsulated DAG node is an uninstanced transform, its local matrix will inherit the relative transform from the old parent to ``parentPath``.
            - If the encapsulated DAG node is directly instanced, it will be reinstanced under a new intermediary transform, inserted between ``parentPath`` and the instance.
            - If the encapsulated DAG node is indirectly instanced, other instances with the same parent will be parented under a new intermediary transform, inserted between ``parentPath`` and the instance.

        Args:
            parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the new and old parents if the encapsulated DAG node is a shape.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return paths to the reparented node as `mNodes` each resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is a shape and ``parentPath`` is :data:`None`.
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node is already a child of ``parentPath``.

        Returns:
            :class:`list` [:class:`OpenMaya.MDagPath`] | :class:`list` [T <= :class:`MetaDag`]: A path or `mNode` encapsulation to the reparented node for the first instance of each new parent.
            If :attr:`path` references an indirect instance there will be multiple paths. Type is determined by ``resultAsMeta``.
        """
        reparentedPaths = DAG.absoluteReparent(self._path, parentPath=parentPath, renameShapes=renameShapes)

        self._path = reparentedPaths[0]
        self._nodeFn.setObject(self._path)

        if len(reparentedPaths) > 1:
            log.info("Reparented indirect instance under multiple transforms. Cached the first instance: {!r}".format(self))

        return [getMNodeFromPath(path) for path in reparentedPaths] if resultAsMeta else reparentedPaths

    def relativeReparent(self, parent=None, renameShapes=True, resultAsMeta=False):
        """Reparent the encapsulated DAG node under a transform or the world whilst preserving its current local space transforms.

        Note:
            - If :attr:`path` is uninstanced, it will be reparented directly under ``parent``.
            - If :attr:`path` is instanced, it will be reinstanced directly under ``parent``.
            - If :attr:`path` is indirectly instanced, other instances with the same parent will be reinstanced under their own intermediary transform,
              inserted between ``parent`` and the instance.

        Args:
            parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the new and old parents if the encapsulated DAG node is a shape.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return paths to the reparented node as `mNodes` each resulting from :meth:`getMNodeFromPath`.
                Defaults to :data:`False` - return :class:`OpenMaya.MDagPath` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is a shape and ``parent`` is :data:`None`.
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node is already a child of ``parent``.

        Returns:
            :class:`list` [:class:`OpenMaya.MDagPath`] | :class:`list` [T <= :class:`MetaDag`]: A path or `mNode` encapsulation to the reparented node for the first instance of each new parent.
            If :attr:`path` references an indirect instance there will be multiple paths. Type is determined by ``resultAsMeta``.
        """
        reparentedPaths = DAG.relativeReparent(self._path, parent=parent, renameShapes=renameShapes)

        self._path = reparentedPaths[0]
        self._nodeFn.setObject(self._path)

        if len(reparentedPaths) > 1:
            log.info("Reparented indirect instance under multiple transforms. Cached the first instance: {!r}".format(self))

        return [getMNodeFromPath(path) for path in reparentedPaths] if resultAsMeta else reparentedPaths

    def duplicate(self, renameShapes=True, resultAsMeta=False, **kwargs):
        """Duplicate the hierarchy of the encapsulated DAG node :attr:`path`.

        Note:
            If the encapsulated DAG node is a shape, its parent transform will be duplicated.

        Args:
            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return duplicate nodes as `mNodes` each resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return :class:`OpenMaya.MObject` wrappers.
            **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

        Returns:
            :class:`list` [:class:`OpenMaya.MObject`] | :class:`list` [T <= :class:`MetaDag`]: Wrappers or `mNode` encapsulations of the duplicate nodes, including any descendants.
            The first element is always the root transform of the duplicate hierarchy. If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
            If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned. Type is determined by ``resultAsMeta``.
        """
        duplicates = DAG.duplicate(self._path, renameShapes=renameShapes, **kwargs)
        return [getMNode(duplicate) for duplicate in duplicates] if resultAsMeta else duplicates

    def absoluteDuplicateTo(self, parentPath=None, renameShapes=True, resultAsMeta=False, **kwargs):
        """Duplicate the encapsulated DAG node and parent it under a transform or the world whilst preserving its current world space transforms.

        Provides a safe way to duplicate and reparent any DAG node including indirect instances and shapes.

        If :attr:`path` is an indirect instance, a single duplicate will be created for that specific indirect instance.

        Note:
            - If the encapsulated DAG node is a transform, the duplicate's local matrix will inherit the relative transform from the old parent to ``parentPath``.
            - If the encapsulated DAG node is a shape, the duplicate will be reparented under a new intermediary transform, inserted between ``parentPath`` and the shape.

        Args:
            parentPath (:class:`OpenMaya.MDagPath`, optional): Path to a transform. Defaults to :data:`None` - world is used as the parent.
            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return duplicate nodes as `mNodes` each resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return :class:`OpenMaya.MObject` wrappers.
            **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parentPath`` is given but does not reference a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is a shape and ``parentPath`` is :data:`None`.

        Returns:
            :class:`list` [:class:`OpenMaya.MObject`] | :class:`list` [T <= :class:`MetaDag`]: Wrappers or `mNode` encapsulations of the duplicate nodes, including any descendants.
            The first element is always the root transform of the duplicate hierarchy. If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
            If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned. Type is determined by ``resultAsMeta``.
        """
        duplicates = DAG.absoluteDuplicateTo(self._path, parentPath=parentPath, renameShapes=renameShapes, **kwargs)
        return [getMNode(duplicate) for duplicate in duplicates] if resultAsMeta else duplicates

    def relativeDuplicateTo(self, parent=None, renameShapes=True, resultAsMeta=False, **kwargs):
        """Duplicate the encapsulated DAG node and parent it under a transform or the world whilst preserving its current local space transforms.

        Provides a safe way to duplicate and reparent any DAG node including indirect instances and shapes.

        Args:
            parent (:class:`OpenMaya.MObject`, optional): Wrapper of a transform. Defaults to :data:`None` - world is used as the parent.
            renameShapes (:class:`bool`, optional): Whether to rename shape nodes under the duplicate.
                If the encapsulated DAG node is a shape, renaming will occur for all shapes under ``parent``.
                Renaming is completed via :func:`msTools.core.maya.dag_utils.renameShapes`. Defaults to :data:`True`.
            resultAsMeta (:class:`bool`, optional): Whether to return duplicate nodes as `mNodes` each resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return :class:`OpenMaya.MObject` wrappers.
            **kwargs: Keyword arguments corresponding to those from :func:`cmds.duplicate`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``parent`` is given but does not reference a transform.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated DAG node is a shape and ``parent`` is :data:`None`.

        Returns:
            :class:`list` [:class:`OpenMaya.MObject`] | :class:`list` [T <= :class:`MetaDag`]: Wrappers or `mNode` encapsulations of the duplicate nodes, including any descendants.
            The first element is always the root transform of the duplicate hierarchy. If ``upstreamNodes`` is :data:`True`, any duplicate upstream nodes will be included.
            If ``returnRootsOnly`` is :data:`True`, a single element :class:`list` will be returned. Type is determined by ``resultAsMeta``.
        """
        duplicates = DAG.absoluteDuplicateTo(self._node, parent=parent, renameShapes=renameShapes, **kwargs)
        return [getMNode(duplicate) for duplicate in duplicates] if resultAsMeta else duplicates

    def removeInstances(self):
        """Removes all other instances of the node referenced :attr:`path`.

        Note:
            If :attr:`path` references an indirect instance, it will remain indirectly instanced under its current parent.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated DAG node does not reference an instanced node.
        """
        DAG.removeInstances(self._path)

    def remove(self):
        """Remove the encapsulated DAG node from the parent referenced in the current :attr:`path`.

        Note:
            The current `mNode` will be invalidated.

        Example:
            .. code-block:: python

                # This function is equivalent to the following Maya command
                maya.cmds.parent(nodePartialName, removeObject=True)
        """
        if self.parentCount > 1:
            # No need to unlock when removing
            DAG.removeNode(self._path)
        else:
            # Ensure the node is deregistered
            self.delete()


# ----------------------------------------------------------------------------
# --- _MetaClassAttribute ---
# ----------------------------------------------------------------------------

class _MetaClassAttribute(
        PY_META.MetaAccessWrapperFactory(
            wrapFunctions=True,
            wrapPropertyGetters=True,
            wrapPropertySetters=True,
            wrapPropertyDeleters=True,
            wrapExclusions=("__init__", "__repr__", "__setattr__", "isValid")
        )):
    """The metaclass used exclusively by (non-strict) subclasses of :class:MetaAttribute`."""

    def __new__(metaCls, clsName, bases, namespace):
        """Metaclass constructor for instantiating (non-strict) subclasses of :class:MetaAttribute`.

        - Completes basic validation of the class interface.
        - Adds an `ALL_EXCLUSIVE` attribute to the namespace of the class to store the names of exclusive attributes from all (non-strict) subclasses.
        - Wraps instance methods and data descriptor methods in a pre and post access wrapper.
        """
        log.debug("_MetaClassAttribute.__new__(metaCls={}, clsName={}, bases={}, namespace={})".format(metaCls, clsName, bases, namespace))

        if clsName != "MetaAttribute" and MetaAttribute not in itertools.chain(*[base.__mro__ for base in bases]):
            raise TypeError("{}: metaclass is designed for (non-strict) subclasses of {}".format(metaCls, MetaAttribute))

        if namespace.get("__init__"):
            initialiserArgs = inspect.getargspec(namespace["__init__"])[0]
            if len(initialiserArgs) < 2 or initialiserArgs[1] != "plug":
                raise RuntimeError("{}: Class initialiser must define signature with 'plug' as its first user argument".format(clsName))

        allExclusive = set(namespace.get("EXCLUSIVE", []))
        if bases[0] is not PY_META.AbstractAccessWrapper:
            allExclusive.update(bases[0].ALL_EXCLUSIVE)

        namespace["ALL_EXCLUSIVE"] = allExclusive

        cls = super(_MetaClassAttribute, metaCls).__new__(metaCls, clsName, bases, namespace)

        return cls


# ----------------------------------------------------------------------------
# --- MetaAttribute ---
# ----------------------------------------------------------------------------

class MetaAttribute(PY_META.AbstractAccessWrapper):
    """A dependency node plug encapsulation designed to interface with `mNodes`.

    The encapsulation associates a low level interface with the plug, similiar to that of an `OpenMaya`_ function set.
    The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

    Instantiation occurs implicitly upon accessing an attribute from an `mNode` via :meth:`Meta.__getattribute__`.

    **Validation:**

        The interface provides the option to track the functional state of the internal :class:`OpenMaya.MPlug`.
        When tracking is enabled, an :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.
    """

    __metaclass__ = _MetaClassAttribute

    EXCLUSIVE = set(["_plug", "_plugId", "_attr", "_attrFn", "_node", "_nodeHandle", "_nodeFn", "_partialName", "_stateTracking", "stateTracking"])
    """:class:`set` [:class:`str`]: Defines exclusive instance attributes which can be set using the default :meth:`object.__setattr__` behaviour.

    - Includes the names of property setters defined by this class.
    - Includes the names of instance attributes which are assigned to an `mAttr` via :meth:`__init__`.

    :access: R
    """

    # --- Instantiation ----------------------------------------------------------------------------

    def __init__(self, plug, stateTracking=True):
        """Initialiser for :class:`MetaAttribute` `mAttrs`.

        Args:
            plug (:class:`OpenMaya.MPlug`): Plug to encapsulate.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated dependency node plug.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.
        """
        log.debug("MetaAttribute.__init__(plug={!r}, stateTracking={})".format(plug, stateTracking))

        attr = plug.attribute()
        node = plug.node()

        self._plug = om2.MPlug(plug)
        self._plugId = OM.MPlugId(plug)
        self._attr = attr
        self._attrFn = om2.MFnAttribute(attr)
        self._node = node
        self._nodeHandle = om2.MObjectHandle(node)
        self._nodeFn = om2.MFnDependencyNode(node)
        self._partialName = NAME.getPlugPartialName(plug)
        self._stateTracking = stateTracking

        if not stateTracking:
            log.debug(("{!r}: State tracking of the encapsulated plug is disabled").format(self))

    # --- Abstract ----------------------------------------------------------------------------

    def _preAccess(self):
        """Abstract override which validates this `mAttr` before providing access to an instance method, otherwise raises a `MayaObjectError`."""
        if not self._stateTracking:
            return

        if not self.isValid:
            raise EXC.MayaObjectError("{!r}: Plug is no longer valid, attribute or node may have been removed".format(self))

    def _postAccess(self):
        """Abstract override - null op."""

    # --- Special ----------------------------------------------------------------------------

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Note:
            This method is not subject to :attr:`stateTracking` and is therefore accessible even if the encapsulated dependency node plug is invalid.
            In this case cached data is used.

        Returns:
            :class:`str`: A string representation of the `mAttr`.
        """
        isValid = self.isValid
        partialName = self.partialName if isValid else self._partialName
        state = "valid" if isValid else "invalid"
        return "{}('{}') <{}>".format(type(self).__name__, partialName, state)

    def __eq__(self, other):
        """``x.__eq__(y)`` <==> ``x == y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: If ``other`` has an equivalent type, return whether its contents (dependency node plug) are equivalent.
            Otherwise swap the operands and return the result, unless the operands have already been swapped in which case the result is :data:`False`.
        """
        if type(self) is type(other):
            return self.plugId == other.plugId

        return NotImplemented

    def __ne__(self, other):
        """``x.__ne__(y)`` <==> ``x != y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: The negation of :meth:`__eq__`.
        """
        return not self == other

    def __setattr__(self, attr, value):
        """``x.__setattr__(attr)`` <==> ``setattr(x, attr, value)``.

        Set the value of an exclusive instance attribute.

        Args:
            attr (:class:`basestring`): Name of an exclusive instance attribute.
            value (any): Used to set the value of the instance attribute corresponding to ``attr``.

        Raises:
            :exc:`~exceptions.AttributeError`: If an instance attribute corresponding to ``attr`` could not be identified.
        """
        if attr in type(self).ALL_EXCLUSIVE:
            return super(MetaAttribute, self).__setattr__(attr, value)
        else:
            raise AttributeError("{}: Exclusive mNode attribute does not exist".format(attr))

    def __delattr__(self, attr):
        """Prevents the deletion of instance attributes.

        Raises:
            :exc:`~exceptions.RuntimeError`: If invoked.
        """
        raise RuntimeError("Instance attribute cannot be deleted")

    def __rshift__(self, other):
        """``x.__rshift__(other)`` <==> ``x >> other`` <==> ``x.connectOut(other.plug)``.

        Connect the encapsulated dependency node plug to a destination via :meth:`connectOut`.

        Args:
            other (T <= :class:`MetaAttribute`): `mAttr` to which the encapsulated dependency node plug will connect.
        """
        self.connectOut(other.plug, forceConnected=True, forceLocked=True)

    def __floordiv__(self, other):
        """``x.__floordiv__(other)`` <==> ``x // other`` <==> ``x.disconnectOut(other.plug, forceLocked=True)``.

        Disconnect the encapsulated dependency node plug from a destination via :meth:`disconnectOut`.

        Args:
            other (T <= :class:`MetaAttribute`): `mAttr` from which to disconnect the encapsulated dependency node plug.
        """
        self.disconnectOut(other.plug, forceLocked=True)

    # --- Public : Properties --------------------------------------------------------------

    @property
    def isValid(self):
        """:class:`bool`: :data:`True` if the internal :class:`OpenMaya.MPlug` references a valid dependency node plug, otherwise :data:`False`.

        Note:
            This method is not subject to :attr:`stateTracking` and is therefore accessible even if the encapsulated dependency node plug is removed.

        :access: R
        """
        if self._plug.isNull:
            return False

        if not self._nodeHandle.isValid():
            return False

        if not self._nodeFn.hasAttribute(self._attrFn.name) or self._nodeFn.attribute(self._attrFn.name) != self._attr:
            return False

        return True

    @property
    def isLocked(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node plug is globally locked, otherwise :data:`False`.

        Note:
            The global lock state of a plug is influenced by the lock state of each ancestor.
            A plug can be globally locked whilst also being internally unlocked.

            This method is designed as an alternative to :attr:`OpenMaya.MPlug.isLocked` which is not always reliable.
            Locking an ancestor plug will not have an immediate affect on the lock state of any descendant element plug which is not yet considered in-use.

        :access: R
        """
        return PLUG.isLocked(self._plug)

    @property
    def isInternallyLocked(self):
        """:class:`bool`: :data:`True` if the encapsulated dependency node plug is internally locked, otherwise :data:`False`.

        Note:
            The internal lock state of a plug is not influenced by the lock state of ancestors.
            A plug can be globally locked whilst also being internally unlocked.

        :access: R
        """
        return PLUG.isLocked(self._plug, checkInternalState=True)

    @property
    def plug(self):
        """:class:`OpenMaya.MPlug`: A copy of the internal plug object.

        :access: R
        """
        return om2.MPlug(self._plug)

    @property
    def plugId(self):
        """:class:`msTools.core.maya.om_utils.MPlugId`: Identifier for the internal :class:`OpenMaya.MPlug`.

        :access: R
        """
        return self._plugId

    @property
    def node(self):
        """:class:`OpenMaya.MObject`: Wrapper of the dependency node referenced by the encapsulated dependency node plug.

        :access: R
        """
        return self._node

    @property
    def nodeFn(self):
        """:class:`OpenMaya.MFnDependencyNode`: Function set encapsulation of the dependency node referenced by the encapsulated dependency node plug.

        :access: R
        """
        return om2.MFnDependencyNode(self._node)

    @property
    def attribute(self):
        """:class:`OpenMaya.MObject`: Wrapper of the attribute referenced by the encapsulated dependency node plug.

        :access: R
        """
        return self._attr

    @property
    def attributeFn(self):
        """:class:`OpenMaya.MFnAttribute`: Function set encapsulation of the attribute referenced by the encapsulated dependency node plug.

        :access: R
        """
        return om2.MFnAttribute(self._attrFn)

    @property
    def stateTracking(self):
        """:class:`bool`: Whether to track the state of the internal :class:`OpenMaya.MPlug` in order to restrict access to the public interface if invalid.

        Restriction involves raising an :exc:`msTools.core.maya.exceptions.MayaObjectError` upon attempting to access a bound instance attribute from the public interface.
        The following bindings are excluded: :meth:`__repr__`, :attr:`isValid`.

        :access: RW
        """
        return self._stateTracking

    @stateTracking.setter
    def stateTracking(self, state):
        self._stateTracking = state
        if not state:
            log.debug(("{!r}: State tracking of the encapsulated plug is disabled").format(self))

    @property
    def partialName(self):
        """:class:`str`: The partial name of the encapsulated dependency node plug with format ``'<node>.<plug>'``.

        - ``<node>`` will be a partial node name qualified by a path and namespace where applicable or necessary.
          It is guaranteed to uniquely identify the plug's node with the minimum amount of information necessary (partial path for the first occurrence of a DAG node).
        - ``<plug>`` is guaranteed to uniquely identify the plug with the minimum amount of information necessary (short attribute path, short attribute names).

        :access: R
        """
        self._partialName = NAME.getPlugPartialName(self._plug)
        return self._partialName

    @property
    def fullName(self):
        """:class:`str`: Full name of the encapsulated dependency node plug with format ``'<node>.<plug>'``.

        - ``<node>`` will be a partial node name qualified by a path and namespace where applicable or necessary.
          It is guaranteed to uniquely identify the plug's node with the maximum amount of information necessary (full path for the first occurrence of a DAG node).
        - ``<plug>`` is guaranteed to uniquely identify the plug with the maximum amount of information necessary (full attribute path, long attribute names).

        :access: R
        """
        return NAME.getPlugFullName(self._plug)

    @property
    def partialNameWithoutNode(self):
        """:class:`str`: The partial name of the encapsulated dependency node plug, not including its node.

        It is guaranteed to uniquely identify the plug relative to its node with the minimum amount of information necessary (short attribute path, short attribute names).

        :access: R
        """
        return NAME.getPlugPartialName(self._plug, includeNodeName=False)

    @property
    def fullNameWithoutNode(self):
        """:class:`str`: The full name of the encapsulated dependency node plug, not including its node.

        It is guaranteed to uniquely identify the plug relative to its node with the maximum amount of information necessary (full attribute path, long attribute names).

        :access: R
        """
        return NAME.getPlugFullName(self._plug, includeNodeName=False)

    @property
    def attrShortName(self):
        """:class:`str`: Short name of the attribute referenced by the encapsulated dependency node plug.

        :access: R
        """
        return self._attrFn.shortName

    @property
    def attrLongName(self):
        """:class:`str`: Long name of the attribute referenced by the encapsulated dependency node plug.

        :access: R
        """
        return self._attrFn.name

    @property
    def nodePartialName(self):
        """:class:`str`: Partial name of the node referenced by the encapsulated dependency node plug.

        The partial name is qualified by a path and namespace where applicable or necessary.
        It is guaranteed to uniquely identify the node with the minimum amount of information necessary (partial path for the first occurrence of a DAG node).

        If the encapsulated dependency node plug does not reference a DAG node, the partial node name is equivalent to its full node name.

        :access: R
        """
        return NAME.getNodePartialName(self._node)

    @property
    def nodeFullName(self):
        """:class:`str`: Full name of the encapsulated dependency node.

        The full name is qualified by a path and namespace where applicable.
        It is guaranteed to uniquely identify the node with the maximum amount of information (full path for the first occurrence of a DAG node).

        If the encapsulated dependency node plug does not reference a DAG node, the full node name is equivalent to its partial node name.
        """
        return NAME.getNodeFullName(self._node)

    # --- Public : Utilities ----------------------------------------------------------------------------------

    @unlockMeta
    def rename(self, newShortName=None, newLongName=None):
        """Rename the attribute referenced by the encapsulated dependency node plug.

        Args:
            newShortName (:class:`basestring`): New short name for attribute. Must not clash with an existing attribute on the node.
                ``newLongName`` used if :data:`None`. Defaults to :data:`None`.
            newLongName (:class:`basestring`): New long name for attribute. Must not clash with an existing attribute on the node.
                ``newShortName`` used if :data:`None`. Defaults to :data:`None`.

        Raises:
            :exc:`~exceptions.ValueError`: If both ``newShortName`` and ``newLongName`` are :data:`None`.
            :exc:`~exceptions.ValueError`: If either of the ``newShortName`` or ``newLongName`` already exists on the node referenced by the encapsulated dependency node plug.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the attribute referenced by the encapsulated dependency node plug is static.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is locked.
        """
        global _META_NODE_REGISTRY

        oldPartialNameWithoutNode = self.partialNameWithoutNode
        ATTR.renameOnNode(self._node, self._attr, newShortName, newLongName)
        newPartialNameWithoutNode = self.partialNameWithoutNode

        if oldPartialNameWithoutNode == "mTypeId" != newPartialNameWithoutNode or oldPartialNameWithoutNode == "mSystemId" != newPartialNameWithoutNode:
            nodeId = UUID.getUuidFromNode(self._node)

            try:
                deregisteredMNode = _META_NODE_REGISTRY.pop(nodeId)
                log.debug("{}: mNode deregistered after renaming the mTypeId or mSystemId attribute of its encapsulated dependency node".format(deregisteredMNode))
            except KeyError:
                pass

    def unlockGlobal(self, resultAsMeta=False):
        """Globally unlock the encapsulated dependency node plug by ensuring any locked ancestor is also unlocked.

        Note:
            The global lock state of a plug is influenced by the lock state of each ancestor.
            A plug can be globally locked whilst also being internally unlocked.

        Args:
            resultAsMeta (:class:`bool`, optional): Whether to return unlocked ancestor plugs as `mAttrs` each resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return :class:`OpenMaya.MPlug` encapsulations.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`] | :class:`list` [T <= :class:`MetaAttribute`]: Encapsulations of dependency node plugs that have been unlocked,
            ordered from the furthest ancestor of the encapsulated dependency node plug.
        """
        unlockedAncestors = PLUG.unlockGlobal(self._plug)
        return [getMAttr(unlockedAncestor) for unlockedAncestor in unlockedAncestors] if resultAsMeta else unlockedAncestors

    def unlockRelatives(self, resultAsMeta=False):
        """Unlock all ancestors and descendants of the encapsulated dependency node plug.

        Designed for use before removing an attribute.
        Any descendant plug which is locked and connected must be unlocked in order to remove an attribute.

        Args:
            resultAsMeta (:class:`bool`, optional): Whether to return unlocked relative plugs as `mAttrs` each resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return :class:`OpenMaya.MPlug` encapsulations.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`] | :class:`list` [T <= :class:`MetaAttribute`]: Encapsulations of dependency node plugs that have been unlocked,
            ordered from furthest ancestor to furthest descendant of the encapsulated dependency node plug.
        """
        unlockedRelatives = PLUG.unlockRelatives(self._plug)
        return [getMAttr(unlockedRelative) for unlockedRelative in unlockedRelatives] if resultAsMeta else unlockedRelatives

    # --- Public : Retrieve ----------------------------------------------------------------------------------

    def get(self):
        """Get the value held by the encapsulated dependency node plug.

        Supported `attribute types` are: :attr:`OpenMaya.MFn.kNumericAttribute`, :attr:`OpenMaya.MFn.kAttribute2Double`, :attr:`OpenMaya.MFn.kAttribute2Float`,
        :attr:`OpenMaya.MFn.kAttribute2Int`, :attr:`OpenMaya.MFn.kAttribute2Short`, :attr:`OpenMaya.MFn.kAttribute3Double`, :attr:`OpenMaya.MFn.kAttribute3Float`,
        :attr:`OpenMaya.MFn.kAttribute3Int`, :attr:`OpenMaya.MFn.kAttribute3Short`, :attr:`OpenMaya.MFn.kAttribute4Double`, :attr:`OpenMaya.MFn.kDoubleLinearAttribute`,
        :attr:`OpenMaya.MFn.kFloatLinearAttribute`, :attr:`OpenMaya.MFn.kDoubleAngleAttribute`, :attr:`OpenMaya.MFn.kFloatAngleAttribute`, :attr:`OpenMaya.MFn.kTimeAttribute`,
        :attr:`OpenMaya.MFn.kMatrixAttribute`, :attr:`OpenMaya.MFn.kFloatMatrixAttribute`, :attr:`OpenMaya.MFn.kTypedAttribute`.
        Type :attr:`OpenMaya.MFn.kCompoundAttribute` is also supported if each child attribute corresponds to one of the afformentioned types.

        Supported `data types` for :attr:`OpenMaya.MFn.kNumericAttribute` are: :attr:`OpenMaya.MFnNumericData.kBoolean`, :attr:`OpenMaya.MFnNumericData.kChar`,
        :attr:`OpenMaya.MFnNumericData.kByte`, :attr:`OpenMaya.MFnNumericData.kShort`, :attr:`OpenMaya.MFnNumericData.kInt`, :attr:`OpenMaya.MFnNumericData.kLong`,
        :attr:`OpenMaya.MFnNumericData.kAddr`, :attr:`OpenMaya.MFnNumericData.kInt64`, :attr:`OpenMaya.MFnNumericData.kFloat`, :attr:`OpenMaya.MFnNumericData.kDouble`.

        Supported `data types` for :attr:`OpenMaya.MFn.kTypedAttribute` are: :attr:`OpenMaya.MFnData.kInvalid`, :attr:`OpenMaya.MFnData.kMatrix`, :attr:`OpenMaya.MFnData.kNumeric`,
        :attr:`OpenMaya.MFnData.kString`, :attr:`OpenMaya.MFnData.kStringArray`, :attr:`OpenMaya.MFnData.kDoubleArray`, :attr:`OpenMaya.MFnData.kIntArray`, :attr:`OpenMaya.MFnData.kPointArray`,
        :attr:`OpenMaya.MFnData.kVectorArray`, :attr:`OpenMaya.MFnData.kComponentList`.

        Note:
            If the encapsulated dependency node plug references a typed attribute with :attr:`OpenMaya.MFnData.kString` or :attr:`OpenMaya.MFnData.kStringArray` data type,
            an attempt will be made to :mod:`json` deserialize the data held by the plug.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is an array.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is a compound with a child array or compound.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references an unsupported attribute type.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references a numeric or typed attribute with an unsupported data type.

        Returns:
            any: Data held by the encapsulated dependency node plug.
        """
        return PLUG.getValue(self._plug)

    def getCachedNode(self, asMeta=False):
        """Retrieve the cached dependency node from the encapsulated dependency node plug. Designed for use with :meth:`Meta.cacheNode`.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the cached node as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MObject` wrapper.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug does not reference a message type attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug does not have an an input connection.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrapper or `mNode` encapsulation of the cached dependency node.
            Type is determined by ``asMeta``.
        """
        cachedNode = DG.getCachedNode(self._plug)
        return getMNode(cachedNode) if asMeta else cachedNode

    def getCachedPlug(self, asMeta=False):
        """Retrieve the cached dependency node plug from the encapsulated dependency node plug. Designed for use with :meth:`Meta.cachePlug`.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the cached plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug does not reference a message type attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug does not have an an input connection.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the cached dependency node plug.
            Type is determined by ``asMeta``.
        """
        cachedPlug = DG.getCachedPlug(self._plug)
        return getMAttr(cachedPlug) if asMeta else cachedPlug

    def getCachedComponent(self, instanceNumber=0):
        """Retrieve cached component data from the encapsulated dependency node plug. Designed for use with :meth:`Meta.cacheComponent`.

        Args:
            instanceNumber (:class:`int`, optional): Instance number to be used by the path encapsulation of the cached node. Defaults to ``0``.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug does not reference a typed attribute which holds :attr:`OpenMaya.MFnData.kComponentList` type data.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is not connected to an input shape node.
            :exc:`~exceptions.ValueError`: If there is no instance of the cached shape node with corresponding ``instanceNumber``.
        ..

        Returns:
            (:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`): A two-element :class:`tuple` containing the cached component data.

            #. Path encapsulation of the cached shape node with ``instanceNumber``.
            #. Wrapper of the cached :attr:`OpenMaya.MFn.kComponent` type data.
        """
        return DG.getCachedComponent(self._plug, instanceNumber=instanceNumber)

    def getMNode(self):
        """
        Returns:
            :class:`T <= Meta`: `mNode` encapsulation of the dependency node referenced by the encapsulated dependency node plug.
        """
        return getMNode(self._node)

    def getAncestor(self, asMeta=False):
        """Return the ancestor of the encapsulated dependency node plug.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the ancestor plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is neither an element nor a child.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation of the ancestor dependency node plug.
            Type is determined by ``asMeta``.
        """
        ancestorPlug = PLUG.getAncestor(self._plug)
        return getMAttr(ancestorPlug) if asMeta else ancestorPlug

    def iterAncestors(self, asMeta=False):
        """Yield ancestors of the encapsulated dependency node plug.

        Args:
            asMeta (:class:`bool`, optional): Whether to yield each ancestor plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is neither an element nor a child.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations of the ancestor dependency node plugs.
            Type is determined by ``asMeta``.
        """
        for ancestorPlug in PLUG.iterAncestors(self._plug):
            yield getMAttr(ancestorPlug) if asMeta else ancestorPlug

    # --- Public : Set ------------------------------------------------------------------------------------

    def set(self, value, forceLocked=False):
        """Set the value held by the encapsulated dependency node plug.

        Supported `attribute types` are: :attr:`OpenMaya.MFn.kNumericAttribute`, :attr:`OpenMaya.MFn.kAttribute2Double`, :attr:`OpenMaya.MFn.kAttribute2Float`,
        :attr:`OpenMaya.MFn.kAttribute2Int`, :attr:`OpenMaya.MFn.kAttribute2Short`, :attr:`OpenMaya.MFn.kAttribute3Double`, :attr:`OpenMaya.MFn.kAttribute3Float`,
        :attr:`OpenMaya.MFn.kAttribute3Int`, :attr:`OpenMaya.MFn.kAttribute3Short`, :attr:`OpenMaya.MFn.kAttribute4Double`, :attr:`OpenMaya.MFn.kDoubleLinearAttribute`,
        :attr:`OpenMaya.MFn.kFloatLinearAttribute`, :attr:`OpenMaya.MFn.kDoubleAngleAttribute`, :attr:`OpenMaya.MFn.kFloatAngleAttribute`, :attr:`OpenMaya.MFn.kTimeAttribute`,
        :attr:`OpenMaya.MFn.kMatrixAttribute`, :attr:`OpenMaya.MFn.kFloatMatrixAttribute`, :attr:`OpenMaya.MFn.kTypedAttribute`.
        Type :attr:`OpenMaya.MFn.kCompoundAttribute` is also supported if each child attribute corresponds to one of the afformentioned types.

        Supported `data types` for :attr:`OpenMaya.MFn.kNumericAttribute` are: :attr:`OpenMaya.MFnNumericData.kBoolean`, :attr:`OpenMaya.MFnNumericData.kChar`,
        :attr:`OpenMaya.MFnNumericData.kByte`, :attr:`OpenMaya.MFnNumericData.kShort`, :attr:`OpenMaya.MFnNumericData.kInt`, :attr:`OpenMaya.MFnNumericData.kLong`,
        :attr:`OpenMaya.MFnNumericData.kAddr`, :attr:`OpenMaya.MFnNumericData.kInt64`, :attr:`OpenMaya.MFnNumericData.kFloat`, :attr:`OpenMaya.MFnNumericData.kDouble`.

        Supported `data types` for :attr:`OpenMaya.MFn.kTypedAttribute` are: :attr:`OpenMaya.MFnData.kInvalid`, :attr:`OpenMaya.MFnData.kMatrix`, :attr:`OpenMaya.MFnData.kString`,
        :attr:`OpenMaya.MFnData.kStringArray`, :attr:`OpenMaya.MFnData.kDoubleArray`, :attr:`OpenMaya.MFnData.kIntArray`, :attr:`OpenMaya.MFnData.kPointArray`,
        :attr:`OpenMaya.MFnData.kVectorArray`, :attr:`OpenMaya.MFnData.kComponentList`.

        Note:
            If the encapsulated dependency node plug references a typed attribute with :attr:`OpenMaya.MFnData.kString` or :attr:`OpenMaya.MFnData.kStringArray` data type,
            an attempt will be made to :mod:`json` serialize the ``value`` if it does not reference :class:`str` castable data.

        Args:
            value (any): Data used to update the value held by the encapsulated dependency node plug. The type must be compatible with the data type of the attribute referenced by the plug.
            forceLocked (:class:`bool`, optional): Whether to force set the value if the encapsulated dependency node plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is an array.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is a compound with a child array or compound.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references a typed attribute which holds :attr:`OpenMaya.MFnData.kComponentList` type data
                and the :class:`OpenMaya.MObject` ``value`` does not reference :attr:`OpenMaya.MFn.kComponent` type data.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references an unsupported attribute type.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references a numeric or typed attribute with an unsupported data type.
            :exc:`~exceptions.TypeError`: If the ``value`` type is not supported by the encapsulated dependency node plug.
            :exc:`~exceptions.ValueError`: If the encapsulated dependency node plug requires a sequence of values which has a different length to the ``value`` sequence.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug has an input connection.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is locked and ``forceLocked`` is :data:`False`.
        """
        PLUG.setValue(self._plug, value, forceLocked=forceLocked)

        partialNameWithoutNode = self.partialNameWithoutNode

        if partialNameWithoutNode == "mTypeId" or partialNameWithoutNode == "mSystemId":
            global _META_NODE_REGISTRY
            nodeId = UUID.getUuidFromNode(self._node)

            try:
                registeredMNode = _META_NODE_REGISTRY[nodeId]
            except KeyError:
                pass
            else:
                if type(registeredMNode).__name__ != value:
                    del _META_NODE_REGISTRY[nodeId]
                    log.debug("{}: mNode has been deregistered after updating the mTypeId or mSystemId of its encapsulated dependency node".format(registeredMNode))

    def setProperties(self, **kwargs):
        """Set properties corresponding to any writable property on :class:`OpenMaya.MPlug` for the encapsulated dependency node plug. Changes are placed on the undo queue.

        Note:
            Plugs cannot have both :attr:`OpenMaya.MPlug.isKeyable` and :attr:`OpenMaya.MPlug.isChannelBox` properties :data:`True`.
            Setting one :data:`True` will set the other :data:`False`.

        Args:
            **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MPlug` such as
                :attr:`OpenMaya.MPlug.isCaching`, :attr:`OpenMaya.MPlug.isChannelBox`, :attr:`OpenMaya.MPlug.isKeyable`, :attr:`OpenMaya.MPlug.isLocked`.

        Examples:
            .. code-block:: python

                # Unlock the encapsulated `mAttr` plug and set keyable
                MetaAttribute.setProperties(mAttr, isKeyable=True, isLocked=False)
        """
        PLUG.setProperties(self._plug, **kwargs)

    # --- Public : Traverse ---------------------------------------------------------------------------------

    def walkUp(self, asMeta=False):
        """Return the source plug which is connected to the encapsulated dependency node plug.

        Designed with :meth:`walkDown` to provide a convenient interface for traversing direct connections.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the source plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is not the destination of a connection.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for the source of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        if self._plug.isDestination:
            sourcePlug = self._plug.sourceWithConversion()
            return getMAttr(sourcePlug) if asMeta else sourcePlug

        raise RuntimeError("{!r}: Could not walk upstream of plug since there is no input connection".format(self))

    def walkDown(self, asMeta=False):
        """Return the singular destination plug which is connected to the encapsulated dependency node plug.

        Designed with :meth:`walkUp` to provide a convenient interface for traversing direct connections.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the destination plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is not the source of a connection or is connected to more than one destination.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for the destination of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        if self._plug.isSource:
            destinationPlugs = self._plug.destinationsWithConversions()

            if len(destinationPlugs) > 1:
                raise RuntimeError("{!r}: Could not walk downstream of plug since there is more than one output connection".format(self))

            return getMAttr(destinationPlugs[0]) if asMeta else destinationPlugs[0]

        raise RuntimeError("{!r}: Could not walk downstream of plug since there is no output connection".format(self))

    def iterDependenciesByNode(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield the node dependencies of the encapsulated dependency node plug.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node plug.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node plug.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node plug. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter node dependencies based on :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each node dependency as an `mNode` resulting from :meth:`getMNode`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

        Raises:
            :exc:`MSystemError`: If ``asMeta`` is :data:`True` and a node dependency is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`MTypeError`: If ``asMeta`` is :data:`True` and a node dependency is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`Meta`: Wrappers or `mNode` encapsulations for node dependencies of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        nodeGen = DG.iterDependenciesByNode(self._plug, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for node in nodeGen:
            yield getMNode(node) if asMeta else node

    def iterDependenciesByPlug(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield the plug dependencies of the encapsulated dependency node plug.

        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kDownstream`, dependencies will correspond to destination plug connections.
        If the ``directionType`` is :attr:`OpenMaya.MItDependencyGraph.kUpstream`, dependencies will correspond to source plug connections.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node plug.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node plug.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node plug. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each plug dependency as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for plug dependencies of the encapsulated node. Type is determined by ``asMeta``.
        """
        plugGen = DG.iterDependenciesByPlug(self._plug, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for plug in plugGen:
            yield getMAttr(plug) if asMeta else plug

    def iterDependenciesByEdge(self, directionType=om2.MItDependencyGraph.kDownstream, traversalType=om2.MItDependencyGraph.kDepthFirst, walk=True, pruneMessage=False, filterTypes=None, asMeta=False):
        """Yield dependencies of the encapsulated dependency node plug as edges represented by a pair of connected source and destination plugs.

        Each pair will correspond to a connection from a source plug to a destination plug regardless of the ``directionType``.

        Note:
            Cyclic dependency paths may terminate back on the encapsulated dependency node plug.

        Args:
            directionType (:class:`int`, optional): The direction of traversal for dependencies of the encapsulated dependency node plug.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDownstream` or :attr:`OpenMaya.MItDependencyGraph.kUpstream`.
                Values correspond to either downstream or upstream dependency traversal of the encapsulated dependency node plug. Defaults to :attr:`OpenMaya.MItDependencyGraph.kDownstream`.
            traversalType (:class:`int`, optional): The type of dependency traversal.
                Valid values are either :attr:`OpenMaya.MItDependencyGraph.kDepthFirst` or :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`.
                If :attr:`OpenMaya.MItDependencyGraph.kBreadthFirst`, exhaust an entire level of dependencies before proceeding to the next level using breadth first traversal.
                If :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`, exhaust an entire dependency path before proceeding to the next path using depth first traversal.
                Defaults to :attr:`OpenMaya.MItDependencyGraph.kDepthFirst`.
            walk (:class:`bool`, optional): Whether to traverse entire dependency paths. If :data:`False`, only direct dependencies are traversed. Defaults to :data:`True`.
            pruneMessage (:class:`bool`, optional): Whether to prune traversal when a connection originates from a message type attribute. Defaults to :data:`False`.
            filterTypes (iterable [:class:`int`], optional): Filter plug dependencies based on their :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
                Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
                Defaults to :data:`None` - no type filtering will occur.
            asMeta (:class:`bool`, optional): Whether to yield each pair of connected plug dependencies as `mAttrs` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as pairs of :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            (:class:`OpenMaya.MPlug`, :class:`OpenMaya.MPlug`) | (T <= :class:`MetaAttribute`, T <= :class:`MetaAttribute`): A two-element :class:`tuple` of connected plug dependencies.

            #. A source plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.
            #. A corresponding destination plug connection for a dependency of the encapsulated node. Type is determined by ``asMeta``.

            Together each pair represents a connected edge in the graph.
        """
        edgeGen = DG.iterDependenciesByEdge(self._plug, directionType=directionType, traversalType=traversalType, walk=walk, pruneMessage=pruneMessage, filterTypes=filterTypes)

        for edge in edgeGen:
            yield getMAttr(edge[0]), getMAttr(edge[1]) if asMeta else edge

    # --- Public : Connect ---------------------------------------------------------------------------------

    def connectIn(self, sourcePlug, forceConnected=False, forceLocked=False):
        """Connect a plug to the destination side of the encapsulated dependency node plug.

        Args:
            sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug used as the source of the connection.
            forceConnected (:class:`bool`, optional): Whether to force the connection if the encapsulated dependency node plug is already connected. Defaults to :data:`False`.
            forceLocked (:class:`bool`, optional): Whether to force the connection if the encapsulated dependency node plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the data types of the plug attributes are incompatible.
            :exc:`~exceptions.RuntimeError`: If either plug references an unconnectable attribute.
            :exc:`~exceptions.RuntimeError`: If ``sourcePlug`` references an unreadable attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug references an unwritable attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is globally locked and ``forceLocked`` is :data:`False`.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is connected and ``forceConnected`` is :data:`False`.
        """
        PLUG.connect(sourcePlug, self._plug, forceConnected=forceConnected, forceLocked=forceLocked)

    def connectOut(self, destPlug, forceConnected=False, forceLocked=False):
        """Connect a plug to the source side the encapsulated dependency node plug.

        Args:
            destPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug used as the destination of the connection.
            forceConnected (:class:`bool`, optional): Whether to force the connection if ``destPlug`` is already connected. Defaults to :data:`False`.
            forceLocked (:class:`bool`, optional): Whether to force the connection if ``destPlug`` is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the data types of the plug attributes are incompatible.
            :exc:`~exceptions.RuntimeError`: If either plug references an unconnectable attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug references an unreadable attribute.
            :exc:`~exceptions.RuntimeError`: If the ``destPlug`` references an unwritable attribute.
            :exc:`~exceptions.RuntimeError`: If the ``destPlug`` is globally locked and ``forceLocked`` is :data:`False`.
            :exc:`~exceptions.RuntimeError`: If the ``destPlug`` is connected and ``forceConnected`` is :data:`False`.
        """
        PLUG.connect(self._plug, destPlug, forceConnected=forceConnected, forceLocked=forceLocked)

    def disconnectIn(self, sourcePlug, forceLocked=False):
        """Disconnect a plug from the destination side of the encapsulated dependency node plug.

        Args:
            sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug representing the source of the connection.
            forceLocked (:class:`bool`, optional): Whether to force the disconnection if the encapsulated dependency node plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.RuntimeError`: If ``sourcePlug`` and the encapsulated dependency node plug are not connected.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is globally locked and ``forceLocked`` is :data:`False`.
        """
        PLUG.disconnect(sourcePlug, self._plug, forceLocked=forceLocked)

    def disconnectOut(self, destPlug, forceLocked=False):
        """Disconnect a plug from the source side of the encapsulated dependency node plug.

        Args:
            destPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug representing the destination of the connection.
            forceLocked (:class:`bool`, optional): Whether to force the disconnection if ``destPlug`` is locked. Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug and ``destPlug`` are not connected.
            :exc:`~exceptions.RuntimeError`: If ``destPlug`` is globally locked and ``forceLocked`` is :data:`False`.
        """
        PLUG.disconnect(self._plug, destPlug, forceLocked=forceLocked)

    # --- Public : Delete ---------------------------------------------------------------------------------

    def remove(self, forceConnected=False, forceLocked=False):
        """Remove the encapsulated dependency node element plug.

        Note:
            This `mAttr` will be invalidated.

        Args:
            forceConnected (:class:`bool`, optional): Whether to force the removal if the encapsulated dependency node plug or one of its descendants is connected. Defaults to :data:`False`.
            forceLocked (:class:`bool`, optional): Whether to force the removal if the encapsulated dependency node plug is locked. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug is not an element plug.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is locked and ``forceLocked`` is :data:`False`.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug or one of its descendants is connected and ``forceConnected`` is :data:`False`.
        """
        # Locked node does not produce an error
        PLUG.removeElement(self._plug, forceConnected=forceConnected, forceLocked=forceLocked)

    def delete(self):
        """Delete the dynamic, non-child attribute referenced by the encapsulated dependency node plug.

        Note:
            This `mAttr` will be invalidated.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references a static attribute.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node plug references a child attribute.
            :exc:`~exceptions.RuntimeError`: If the encapsulated dependency node plug is locked or has a locked and connected descendant plug.
        """
        global _META_NODE_REGISTRY

        partialNameWithoutNode = self.partialNameWithoutNode

        # The unlockMeta decorator will not work since the post-function call logic will invoke the _preAccess validation wrapper for the MPlug
        with CONTEXT.UnlockNode(self._node):
            ATTR.removeFromNode(self._node, self._attr)

        if partialNameWithoutNode == "mTypeId" or partialNameWithoutNode == "mSystemId":
            nodeId = UUID.getUuidFromNode(self._node)

            try:
                deregisteredMNode = _META_NODE_REGISTRY.pop(nodeId)
                log.debug("{}: mNode has been deregistered after removing the mTypeId or mSystemId attribute from its encapsulated dependency node".format(deregisteredMNode))
            except KeyError:
                pass


# ----------------------------------------------------------------------------
# --- MetaCompoundAttribute ---
# ----------------------------------------------------------------------------

class MetaCompoundAttribute(MetaAttribute):
    """A dependency node non-array compound plug encapsulation designed to interface with `mNodes`.

    The encapsulation associates a low level interface with the plug, similiar to that of an `OpenMaya`_ function set.
    The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

    Instantiation occurs implicitly upon accessing a compound type attribute from an `mNode` via :meth:`Meta.__getattribute__`.

    **Validation:**

        The interface provides the option to track the functional state of the internal :class:`OpenMaya.MPlug`.
        When tracking is enabled, an :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.
    """

    def __init__(self, plug, stateTracking=True):
        """Initialiser for :class:`MetaCompoundAttribute` `mAttrs`.

        Args:
            plug (:class:`OpenMaya.MPlug`): Compound plug to encapsulate.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated dependency node plug.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not reference a dependency node compound plug.
        """
        log.debug("MetaCompoundAttribute.__init__(plug={!r}, stateTracking={})".format(plug, stateTracking))

        OM.validatePlugType(isArray=False, isCompound=True)

        super(MetaCompoundAttribute, self).__init__(plug, stateTracking=stateTracking)

    # --- Special ----------------------------------------------------------------------------------

    def __getattribute__(self, attr):
        """``x.__getattribute__(attr)`` <==> ``getattr(x, attr)``.

        Access the value referenced by an attribute of this instance or attempt to retrieve a child of the encapsulated dependency node plug via :meth:`getChildByName`.

        Note:
            Instance access precedes dependency node plug access.

        Args:
            attr (:class:`basestring`): Name of an instance attribute or child of the encapsulated dependency node plug.

        Raises:
            :exc:`~exceptions.AttributeError`: If an instance attribute or child dependency node plug could not be identified for the given ``attr`` name.

        Returns:
            any | T <= :class:`MetaAttribute`: Data referenced by the instance attribute or `mAttr` encapsulation of a child dependency node plug corresponding to ``attr``.
        """
        try:
            return super(Meta, self).__getattribute__(attr)
        except AttributeError:
            log.debug("{}: mAttr attribute does not exist, expanding search to dependency node plug".format(attr))

        try:
            return self.getChildByName(attr, asMeta=True)
        except EXC.MayaLookupError:
            raise AttributeError("{}.{}: Child dependency node plug does not exist".format(self.partialName, attr))

    def __setattr__(self, attr, value):
        """``x.__setattr__(attr)`` <==> ``setattr(x, attr, value)``.

        Set the value of an exclusive instance attribute or retrieve a child of the encapsulated dependency node plug and set its value via :meth:`MetaAttribute.set`.

        Note:
            Instance access precedes dependency node access.

        Args:
            attr (:class:`basestring`): Name of an exclusive instance attribute or child of the encapsulated dependency node plug.
            value (any): Used to set the value referenced by the instance attribute or held by the child dependency node plug corresponding to ``attr``.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a child dependency node plug could not be identified for the given ``attr`` name.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child dependency node plug array.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child dependency node compound plug with a child array or compound.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child dependency node plug that references a typed attribute which holds
                :attr:`OpenMaya.MFnData.kComponentList` type data and the :class:`OpenMaya.MObject` ``value`` does not reference :attr:`OpenMaya.MFn.kComponent` type data.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child dependency node plug that references an unsupported attribute type.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` identifies a child dependency node plug that references a numeric or typed attribute with an unsupported data type.
            :exc:`~exceptions.TypeError`: If ``attr`` identifies a child dependency node plug for which the ``value`` type is not supported.
            :exc:`~exceptions.ValueError`: If ``attr`` identifies a child dependency node plug which requires a sequence of values with a different length to the ``value`` sequence.
            :exc:`~exceptions.RuntimeError`: If ``attr`` identifies a child dependency node plug which has an input connection.
        """
        # Restrict mNode access
        if attr in type(self).ALL_EXCLUSIVE:
            return super(Meta, self).__setattr__(attr, value)
        else:
            log.debug("{}: Exclusive mAttr attribute does not exist, expanding search to dependency node plug".format(attr))

            # mAttr will handle mNode deregistration when setting the mTypeId
            mAttr = self.getChildByName(attr, asMeta=True)
            mAttr.set(value, forceLocked=True)

    def __delattr__(self, attr):
        """Prevents the deletion of instance attributes and child attributes.

        Raises:
            :exc:`~exceptions.RuntimeError`: If invoked.
        """
        raise RuntimeError("Instance attribute or child attribute cannot be deleted")

    # --- Public : Retrieve ----------------------------------------------------------------------------------

    def getChildByName(self, attributeName, asMeta=False):
        """Return a child of the encapsulated dependency node plug.

        Args:
            attributeName (:class:`basestring`): Name of an attribute that is a child of the encapsulated dependency node plug.
            asMeta (:class:`bool`, optional): Whether to return the child plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attributeName`` does not correspond to a child of the encapsulated dependency node plug.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for a child of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        childPlug = PLUG.getChildByName(self._plug, attributeName)
        return getMAttr(childPlug) if asMeta else childPlug

    def iterChildren(self, asMeta=False):
        """Yield the children of the encapsulated dependency node plug.

        Args:
            asMeta (:class:`bool`, optional): Whether to yield each child plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for children of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        for childPlug in PLUG.iterChildren(self._plug):
            yield getMAttr(childPlug) if asMeta else childPlug

    def iterDescendants(self, forceInitialElements=True, asMeta=False):
        """Yield descendants of the encapsulated dependency node plug.

        Args:
            forceInitialElements (:class:`bool`, optional): Whether to return the zeroth indexed element of each array plug if there are no existing elements.
                If :data:`False`, traversal of the descendant hierarchy will terminate upon reaching an array plug that has no in-use elements.
                If :data:`True`, it is guaranteed that the full descendant hierarchy of the encapsulated dependency node plug will be traversed. Defaults to :data:`True`.
            asMeta (:class:`bool`, optional): Whether to return each descendant plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for descendants of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        for descendantPlug in PLUG.iterDescendants(self._plug, forceInitialElements=forceInitialElements):
            yield getMAttr(descendantPlug) if asMeta else descendantPlug


# ----------------------------------------------------------------------------
# --- MetaArrayAttribute ---
# ----------------------------------------------------------------------------

class MetaArrayAttribute(MetaAttribute):
    """A dependency node array plug encapsulation designed to interface with `mNodes`.

    The encapsulation associates a low level interface with the plug, similiar to that of an `OpenMaya`_ function set.
    The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

    Instantiation occurs implicitly upon accessing an array attribute from an `mNode` via :meth:`Meta.__getattribute__`.

    **Validation:**

        The interface provides the option to track the functional state of the internal :class:`OpenMaya.MPlug`.
        When tracking is enabled, an :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.
    """

    def __init__(self, plug, stateTracking=True):
        """Initialiser for :class:`MetaArrayAttribute` `mAttrs`.

        Args:
            plug (:class:`OpenMaya.MPlug`): Array plug to encapsulate.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated dependency node plug.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not reference a dependency node array plug.
        """
        log.debug("MetaArrayAttribute.__init__(plug={!r}, stateTracking={})".format(plug, stateTracking))

        OM.validatePlugType(isArray=True)

        super(MetaArrayAttribute, self).__init__(plug, stateTracking=stateTracking)

    # --- Special ----------------------------------------------------------------------------------

    def __iter__(self):
        """``x.__iter__()`` <==> ``iter(x)``.

        Yield elements of the encapsulated dependency node plug for existing logical indices.

        Yields:
            T <= :class:`MetaAttribute`: `mAttr` encapsulations for elements of the encapsulated dependency node plug.
        """
        for elementPlug in PLUG.iterElements(self._plug):
            yield getMAttr(elementPlug)

    def __len__(self):
        """``x.__len__()`` <==> ``len(x)``

        Returns:
            :class:`int`: The number of elements for the encapsulated dependency node plug. Equivalent to calling :meth:`OpenMaya.MPlug.evaluateNumElements`.
        """
        return self._plug.evaluateNumElements()

    def __getitem__(self, index):
        """``x.__getitem__(index)`` <==> ``x[index]``.

        Return an element of the encapsulated dependency node plug corresponding to a given logical index.

        Args:
            index (:class:`int`): Logical index of the element plug. Must be non-negative.

        Raises:
            :exc:`~exceptions.ValueError`: If ``index`` is negative.

        Returns:
            T <= :class:`MetaAttribute`: `mAttr` encapsulation for an element of the encapsulated dependency node plug corresponding to ``index``.
        """
        if index < 0:
            raise ValueError("Expected non-negative logical index")

        elementPlug = self._plug.elementByLogicalIndex(index)
        return getMAttr(elementPlug)

    def __setitem__(self, index, value):
        """``x.__setitem__(index)`` <==> ``x[index] = value``.

        Set the value held by an element of the encapsulated dependency node plug corresponding to a given logical index.

        Args:
            index (:class:`int`): Logical index of the element plug. Must be non-negative.
            value (any): For the element plug corresponding to ``attr``.

        Raises:
            :exc:`~exceptions.ValueError`: If ``index`` is negative.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the element plug with a child array or compound.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the element plug references a typed attribute which holds
                :attr:`OpenMaya.MFnData.kComponentList` type data and the :class:`OpenMaya.MObject` ``value`` does not reference :attr:`OpenMaya.MFn.kComponent` type data.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the element plug references an unsupported attribute type.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the element plug references a numeric or typed attribute with an unsupported data type.
            :exc:`~exceptions.TypeError`: If the ``value`` type is not supported by the element plug.
            :exc:`~exceptions.ValueError`: If the element plug requires a sequence of values with a different length to the ``value`` sequence.
            :exc:`~exceptions.RuntimeError`: If the element plug which has an input connection.
        """
        mAttr_element = self.getElement(index, asMeta=True)
        mAttr_element.set(value, forceLocked=True)

    def __delitem__(self, index):
        """``x.__delitem__(index)`` <==> ``del x[index]``.

        Remove an element of the encapsulated dependency node plug corresponding to a given logical index.

        Args:
            index (:class:`int`): Logical index of the element plug. Must be non-negative.

        Raises:
            :exc:`~exceptions.ValueError`: If ``index`` is negative.
        """
        self.removeElement(index, forceConnected=True, forceLocked=True)

    # --- Public : Properties ----------------------------------------------------------------------------

    @property
    def numElements(self):
        """:class:`int`: The number of elements for the encapsulated dependency node plug. Equivalent to calling :meth:`OpenMaya.MPlug.evaluateNumElements`.

        :access: R
        """
        return len(self)

    # --- Public : Retrieve ----------------------------------------------------------------------------

    def getPacked(self, allowMultiples=False):
        """Removes sparcity from the encapsulated dependency node array plug by removing any disconnected elements.

        Args:
            allowMultiples (:class:`bool`, optional): Whether multiple elements can be connected to a single input plug.
                Defaults to :data:`False` - Any existing duplicates will be removed from the tail end of the array.

        Returns:
            :class:`msTools.core.maya.plug_utils.PackArray`: An interface for managing input connections to the elements of the encapsulated dependency node array plug.
        """
        return PLUG.PackArray(self._plug, allowMultiples=allowMultiples)

    def getPackedCompound(self, allowMultiples=False):
        """Removes sparcity from the encapsulated dependency node compound array plug by removing any elements that contain a disconnected child group.

        A disconnected child group occurs when an element plug has no child plug connections.

        Args:
            allowMultiples (:class:`bool`, optional): Whether multiple child groups can be connected to a single group of input plugs.
                Defaults to :data:`False` - Any existing duplicates will be removed from the tail end of the array.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the encapsulated dependency node array plug is not also a compound.

        Returns:
            :class:`msTools.core.maya.plug_utils.PackCompoundArray`: An interface for managing input connections to the elemental children of the encapsulated dependency node array plug.
        """
        return PLUG.PackCompoundArray(self._plug, allowMultiples=allowMultiples)

    def getUnusedLogicalIndex(self):
        """Returns the logical index for the next available unused element plug of the encapsulated dependency node plug.

        Note:
            If the array is sparse, the smallest sparse index will be returned.
            If no element plugs are considered in-use, the zeroth index will be returned.

        Returns:
            :class:`int`: Logical index for the next available unused element of the encapsulated dependency node plug.
        """
        return PLUG.getUnusedLogicalIndex(self._plug)

    def getUnusedElement(self, asMeta=False):
        """Return the next available unused element plug of the encapsulated dependency node plug.

        Note:
            If the array is sparse, the element will correspond to the smallest sparse logical index.
            If no element plugs are considered in-use, the element will correspond to the zeroth logical index.

        Args:
            asMeta (:class:`bool`, optional): Whether to return the element plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for the next available unused element plug of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        elementPlug = PLUG.getUnusedElement(self._plug)
        return getMAttr(elementPlug) if asMeta else elementPlug

    def getUnconnectedLogicalIndex(self, checkSource=True, checkDestination=True):
        """Returns the logical index for the first unconnected element plug of the encapsulated dependency node plug.

        Note:
            If the array is sparse and other elements are connected, the smallest sparse index will be returned.
            If no element plugs are considered in-use, the zeroth index will be returned.

        Args:
            checkSource (:class:`bool`, optional): Whether to check the source side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.
            checkDestination (:class:`bool`, optional): Whether to check the destination side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.

        Returns:
            :class:`int`: Logical index for the first unconnected element plug of the encapsulated dependency node plug.
        """
        return PLUG.getUnconnectedLogicalIndex(self._plug, checkSource=checkSource, checkDestination=checkDestination)

    def getUnconnectedElement(self, checkSource=True, checkDestination=True, asMeta=False):
        """Returns the first unconnected element plug of the encapsulated dependency node plug.

        Note:
            If the array is sparse and other elements are connected, the element will correspond to the smallest sparse logical index.
            If no element plugs are considered in-use, the element will correspond to the zeroth logical index.

        Args:
            checkSource (:class:`bool`, optional): Whether to check the source side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.
            checkDestination (:class:`bool`, optional): Whether to check the destination side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.
            asMeta (:class:`bool`, optional): Whether to return the element plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for the first unconnected element plug of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        elementPlug = PLUG.getUnconnectedLogicalIndex(self._plug, checkSource=checkSource, checkDestination=checkDestination)
        return getMAttr(elementPlug) if asMeta else elementPlug

    def getElement(self, index, asMeta=False):
        """Return an element of the encapsulated dependency node plug corresponding to a given logical index.

        Args:
            index (:class:`int`): Logical index of the element plug. Must be non-negative.
            asMeta (:class:`bool`, optional): Whether to return the element plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as an :class:`OpenMaya.MPlug` encapsulation.

        Raises:
            :exc:`~exceptions.ValueError`: If ``index`` is negative.

        Returns:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulation for an element of the encapsulated dependency node plug corresponding to ``index``.
            Type is determined by ``asMeta``.
        """
        if index < 0:
            raise ValueError("Expected non-negative logical index")

        elementPlug = self._plug.elementByLogicalIndex(index)
        return getMAttr(elementPlug) if asMeta else elementPlug

    def iterElements(self, forceInitialElement=False, asMeta=False):
        """Yield the existing elements of the encapsulated dependency node plug.

        Args:
            forceInitialElement (:class:`bool`, optional): Whether to return the zeroth indexed element of the encapsulated dependency node plug if there are no existing elements.
                Defaults to :data:`False`.
            asMeta (:class:`bool`, optional): Whether to yield each element plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for elements of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        for elementPlug in PLUG.iterElements(self._plug, forceInitialElement=forceInitialElement):
            yield getMAttr(elementPlug) if asMeta else elementPlug

    def iterConnectedElements(self, checkSource=True, checkDestination=True, asMeta=False):
        """Yield the connected elements of the encapsulated dependency node plug.

        Args:
            checkSource (:class:`bool`, optional): Whether to check the source side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.
            checkDestination (:class:`bool`, optional): Whether to check the destination side of the encapsulated dependency node plug for connections. Defaults to :data:`True`.
            asMeta (:class:`bool`, optional): Whether to yield each connected element plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - yield as :class:`OpenMaya.MPlug` encapsulations.

        Raises:
            :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for connected elements of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        for elementPlug in PLUG.iterConnectedElements(self._plug, checkSource=checkSource, checkDestination=checkDestination):
            yield getMAttr(elementPlug) if asMeta else elementPlug

    def iterDescendants(self, forceInitialElements=True, asMeta=False):
        """Yield descendants of the encapsulated dependency node plug.

        Args:
            forceInitialElements (:class:`bool`, optional): Whether to return the zeroth indexed element of each array plug if there are no existing elements.
                If :data:`False`, traversal of the descendant hierarchy will terminate upon reaching an array plug that has no in-use elements.
                If :data:`True`, it is guaranteed that the full descendant hierarchy of the encapsulated dependency node plug will be traversed. Defaults to :data:`True`.
            asMeta (:class:`bool`, optional): Whether to return each descendant plug as an `mAttr` resulting from :meth:`getMAttr`.
                Defaults to :data:`False` - return as :class:`OpenMaya.MPlug` encapsulations.

        Yields:
            :class:`OpenMaya.MPlug` | T <= :class:`MetaAttribute`: Encapsulations for descendants of the encapsulated dependency node plug.
            Type is determined by ``asMeta``.
        """
        for descendantPlug in PLUG.iterDescendants(self._plug, forceInitialElements=forceInitialElements):
            yield getMAttr(descendantPlug) if asMeta else descendantPlug

    # --- Public : Delete ---------------------------------------------------------------------------------

    @unlockMeta
    def removeElement(self, index, forceConnected=False, forceLocked=False):
        """Remove an element of the encapsulated dependency node plug corresponding to a given logical index.

        Args:
            index (:class:`int`): Logical index of the element plug. Must be non-negative.
            forceConnected (:class:`bool`, optional): Whether to force the removal if ``elementPlug`` or one of its descendants is connected. Defaults to :data:`False`.
            forceLocked (:class:`bool`, optional): Whether to force the removal if ``elementPlug`` is locked. Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``index`` is negative.
            :exc:`~exceptions.RuntimeError`: If the element plug is locked and ``forceLocked`` is :data:`False`.
            :exc:`~exceptions.RuntimeError`: If the element plug or one of its descendants is connected and ``forceConnected`` is :data:`False`.
        """
        elementPlug = self.getElement(index)
        PLUG.removeElement(elementPlug)


# ----------------------------------------------------------------------------
# --- Setup ---
# ----------------------------------------------------------------------------

if not uuid_manager.isInstalled():
    log.warning("The metadata registration system relies on dependency node UUIDs. It is recommended the `uuid_manager` is installed to ensure each UUID is actually unique")

# Callbacks are registered once per Maya session, global attribute is unaffected by reloads of meta
if not _META_CALLBACKS['Open']:
    _META_CALLBACKS['Open'] = om2.MSceneMessage.addCallback(om2.MSceneMessage.kBeforeOpen, _resetMNodeRegistryCallback)
if not _META_CALLBACKS['New']:
    _META_CALLBACKS['New'] = om2.MSceneMessage.addCallback(om2.MSceneMessage.kBeforeNew, _resetMNodeRegistryCallback)
