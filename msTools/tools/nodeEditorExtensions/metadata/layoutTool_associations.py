"""
Provides an interface for handling associations between internal `Layout Tool` metadata and the current "MayaNodeEditorSavedTabsInfo" node.

----------------------------------------------------------------

Interface
---------

    The module follows the same principles as Maya's `adsk::Data::Associations` class which handles associations between internal and external data.
    The `layoutTool_accessor` module is responsible for reading initial data into the internal registry and writing it to the "MayaNodeEditorSavedTabsInfo" node upon saving.
    The registry is kept sparse meaning it is the user's responsibility to manage indexing of data.

----------------------------------------------------------------
"""
import copy
import logging
log = logging.getLogger(__name__)

from msTools.vendor import decorator

# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

# Stores a sparse unordered mapping of: tab index -> item uuid -> item member name -> item member value
if "_METADATA_REGISTRY" not in globals():
    log.debug("Initializing global: _METADATA_REGISTRY")
    global _METADATA_REGISTRY
    _METADATA_REGISTRY = {}

# State tracker used by the `layoutTool_accessor` to optimize writing of internal metadata
if "_ARE_ASSOCIATIONS_STALE" not in globals():
    log.debug("Initializing global: _ARE_ASSOCIATIONS_STALE")
    global _ARE_ASSOCIATIONS_STALE
    _ARE_ASSOCIATIONS_STALE = False


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

@decorator.decorator
def _registryModifier(func, *args, **kwargs):
    try:
        ret = func(*args, **kwargs)
    except Exception:
        raise
    else:
        setStaleState(True)

    return ret


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def hasData():
    """Checks if the internal metadata registry has any data."""
    return bool(_METADATA_REGISTRY)


def getData():
    """Returns a copy of the internal metadata registry.

    The registry stores a sparse unordered mapping of: tab index -> item uuid -> item member name -> item member value."""
    return copy.deepcopy(_METADATA_REGISTRY)


def tabCount():
    """Returns a tab count based on the highest tab index within the internal metadata registry.

    This function is designed for validating existing metadata with the scene (ie. the metadata count should not exceed the the physical count).
    """
    allStreamIndices = set([-1])

    for tabIndex, tabData in _METADATA_REGISTRY.iteritems():
        allStreamIndices.add(tabIndex)

    return max(allStreamIndices) + 1


def getStaleState():
    """Returns whether the metadata `adsk::Associations` between the internal data registry and the "MayaNodeEditorSavedTabsInfo" node are stale."""
    return _ARE_ASSOCIATIONS_STALE


def setStaleState(state):
    """Updates the global state tracker used by the `layoutTool_accessor` to optimize writing of internal metadata upon saving the scene.

    Ensures writing of metadata to the "MayaNodeEditorSavedTabsInfo" node only occurs when `adsk::Associations` are stale (ie. when the internal data no longer matches the node data).
    """
    global _ARE_ASSOCIATIONS_STALE
    _ARE_ASSOCIATIONS_STALE = state


@_registryModifier
def registerData(index, qualifier, UUID, **memberData):
    """Registers the given member data in the internal metadata registry under the given index, qualifier and UUID.

    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    """
    if _METADATA_REGISTRY.get(index) is None:
        _METADATA_REGISTRY[index] = {}

    if _METADATA_REGISTRY[index].get(qualifier) is None:
        _METADATA_REGISTRY[index][qualifier] = {}

    _METADATA_REGISTRY[index][qualifier][UUID] = memberData


@_registryModifier
def updateDataMember(index, qualifier, UUID, memberName, memberValue):
    """Updates the value of an existing member within the internal metadata registry under the given `index`, `qualifier` and `UUID`.

    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    Raises a `KeyError` if there is no member registered to the given `index`, `qualifier`, `UUID` and `memberName`.
    """
    try:
        _METADATA_REGISTRY[index][qualifier][UUID][memberName] = memberValue
    except KeyError:
        raise KeyError("Unable to find an existing member to update in the internal metadata registry at the given address : {} -> {} -> {} -> {}".format(
            index, qualifier, UUID, memberName))


@_registryModifier
def reindexTab(oldIndex, newIndex):
    """Change the index under which data is registered in the internal metadata registry.

    Any existing data at the new index will be overwritten and the old index will be removed.
    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    Raises a `KeyError` if the old index is not registered.
    """
    try:
        _METADATA_REGISTRY[newIndex] = _METADATA_REGISTRY.pop(oldIndex)
    except KeyError:
        raise KeyError("There is no data registered in the internal metadata registry under the given index : {}".format(oldIndex))


@_registryModifier
def removeData(index, qualifier, UUID):
    """Removes data which is registered in the internal metadata registry under the given `index`, `qualifier` and `UUID`.

    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    Raises a `KeyError` if there is no data registered at the given `index`, `qualifier` and `UUID`.
    """
    try:
        # Remove stream specific data
        del _METADATA_REGISTRY[index][qualifier][UUID]
    except KeyError:
        raise KeyError("There is no data registered in the internal metadata registry at the given address : {} -> {} -> {}".format(index, qualifier, UUID))

    # Cleanup the parent hierarchy if we have removed the last key under the given qualifier
    if not len(_METADATA_REGISTRY[index][qualifier]):
        del _METADATA_REGISTRY[index][qualifier]

        if not len(_METADATA_REGISTRY[index]):
            del _METADATA_REGISTRY[index]


@_registryModifier
def removeTab(index):
    """Removes data which is registered in the internal metadata registry under the given `index`.

    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    Raises a `KeyError` if there is no data registered at the given `index`.
    """
    try:
        _METADATA_REGISTRY.pop(index)
    except KeyError:
        raise KeyError("There is no data registered in the internal metadata registry under the given index : {}".format(index))


@_registryModifier
def clearData():
    """Resets the internal metadata registry.

    Metadata changes will be written to the "MayaNodeEditorSavedTabsInfo" node after calling the `layoutTool_accessor.write` function.
    """
    global _METADATA_REGISTRY
    _METADATA_REGISTRY = {}
