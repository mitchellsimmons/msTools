"""
General `OpenMaya`_ API operations.

Operations defined within this module have low level objectives which are designed to be utilised by higher level abstractions of the `OpenMaya`_ API.
Operations include direct retrieval, validation and filtering of `OpenMaya`_ objects.

----------------------------------------------------------------

The following notes/warnings discuss a variety of edge cases or unusual behaviours that are directly associated with the `OpenMaya`_ API.

If a specific behaviour arises from a higher level abstraction of an `OpenMaya`_ operation, that behaviour may be documented in a seperate :doc:`msTools <../index>` utility module.

`M*Array classes`_
------------------

Note:
    1. Maya uses reference semantics for arrays of class type meaning item access will return direct references to elements.
       However Maya does not provide reference counting for these elements.

Warning:
    1. Do not directly assign an `OpenMaya`_ object which enters the current scope via an `OpenMaya`_ array.

.. code-block:: python

    def foo(node):
        # Maya might crash if we operate on `path`
        # The OpenMaya.MDagPath referenced by `path` may already be destroyed if it was never reference counted
        path = OpenMaya.MDagPath.getAllPathsTo(node)[0]

    def bar(node):
        # Even if the OpenMaya.MDagPath assigned to `path` is not reference counted it is still valid whilst `array` is alive
        array = OpenMaya.MDagPath.getAllPathsTo(node)
        path = array[0]

Warning:
    2. Do not return an `OpenMaya`_ object from a local scope if the object entered the scope via an `OpenMaya`_ array.

.. code-block:: python

    def foo(node):
        # The OpenMaya.MDagPath assigned to `path` is valid whilst `array` is alive
        array = OpenMaya.MDagPath.getAllPathsTo(node)
        path = array[0]
        return path

    def bar(node):
        # The OpenMaya.MDagPath assigned to `path` is completely decoupled from the OpenMaya.MDagPathArray
        array = OpenMaya.MDagPath.getAllPathsTo(node)
        path = OpenMaya.MDagPath(array[0])
        return path

    def foobar(node):
        # The OpenMaya.MDagPaths assigned to `paths` are completely decoupled from the OpenMaya.MDagPathArray
        # This is similiar to making a deepcopy of the OpenMaya.MDagPathArray
        # Note, in-place list comprehension is safe since items are copied before the OpenMaya.MDagPathArray is destroyed
        return [OpenMaya.MDagPath(p) for p in OpenMaya.MDagPath.getAllPathsTo(node)]

    # Maya might crash if we operate on `path`
    # The OpenMaya.MDagPath returned from `foo()` may have been destroyed if it was never reference counted
    path = foo(node)

    # The OpenMaya.MDagPath assigned to `path` is valid and reference counted
    path = bar(node)

    # The OpenMaya.MDagPaths assigned to `paths` are valid and reference counted
    paths = foobar(node)


:class:`OpenMaya.MDagPath`
--------------------------

.. _MDagPath_note_1:

Note:
    1. Checking a node for Function Set support produces potentially differing results when using an :class:`OpenMaya.MDagPath` versus an :class:`OpenMaya.MObject`.
       An :class:`OpenMaya.MDagPath` which references a transform will support Function Set types which are compatible with any of its child shape nodes.
       For example a transform which is the parent of a mesh shape will support :attr:`OpenMaya.MFn.kMesh` via :meth:`OpenMaya.MDagPath.hasFn` but not via :meth:`OpenMaya.MObject.hasFn`.

.. _MDagPath_warning_1:

Warning:
    1. The :meth:`~OpenMaya.MDagPath.isValid` state of an :class:`OpenMaya.MDagPath` is not reflective of whether the path references a valid dependency node.
       Rather this value indicates whether the path was `constructed` with a valid reference to a dependency node.

:class:`OpenMaya.MDGModifier`
-----------------------------

Warning:
    1. Always use an :class:`OpenMaya.MDagModifier` to operate on DAG nodes.
       Deleting an instanced DAG node with an :class:`OpenMaya.MDGModifier` can cause Maya's internal state to become invalid.
       Only the first instance will be removed making it impossible to delete others from the GUI.

:class:`OpenMaya.MDagModifier`
------------------------------

Warning:
    1. Never use an :class:`OpenMaya.MDagModifier` to delete an instanced DAG node.
       Deleting an instanced DAG node with an :class:`OpenMaya.MDagModifier` can result in ancestors being deleted.
       Instead it is best to use Maya commands.

:class:`OpenMaya.MItDag`
------------------------

Note:
    1. Setting the root of an :class:`OpenMaya.MItDag` iterator to an :class:`OpenMaya.MObject` that points to an instanced node will not traverse its descendant hierarchy.
       Always use an :class:`OpenMaya.MDagPath` as the root object if traversal of all descendant nodes is required.

:class:`OpenMaya.MItDependencyGraph`
------------------------------------

Note:
    1. The documentation for :meth:`OpenMaya.MItDependencyGraph.resetTo` has an error.
       If an :class:`OpenMaya.MIteratorType` is used, it must be the second argument.

:class:`OpenMaya.MObject`
-------------------------

Note:
    1. An :class:`OpenMaya.MObject` acts as a wrapper for an internal Maya object such as a node or attribute.

.. _MObject_warning_1:

Warning:
    1. The :meth:`~OpenMaya.MObject.isNull` state of an :class:`OpenMaya.MObject` is not reflective of whether an internal Maya object is valid.
       Rather this value indicates whether the wrapper was `constructed` with a valid reference to an internal Maya object.

:class:`OpenMaya.MObjectHandle`
-------------------------------

Warning:
    1. The :meth:`~OpenMaya.MObjectHandle.isValid` state of an :class:`OpenMaya.MObjectHandle` holding an :class:`OpenMaya.MObject` wrapper of a node
       indicates whether the node exists in the dependency graph.

Warning:
    2. The :meth:`~OpenMaya.MObjectHandle.isValid` state of an :class:`OpenMaya.MObjectHandle` holding an :class:`OpenMaya.MObject` wrapper of an attribute will always be :data:`True`.
       Consider that an attribute remains functional even when it is not directly referenced by any dependency node plug.
       For example it can be used to instantiate a plug via :meth:`OpenMaya.MDGModifier.addAttribute`.

:class:`OpenMaya.MPlug`
-----------------------

Note:
    1. In order to explicitly compare two :class:`OpenMaya.MPlug` instances, the logical indices of each ancestor plug need to be compared.
       It is not sufficient to just compare the logical indices of two descendant plugs.
       For example ``ancestor[0].child[0]`` would be considered equivalent to ``ancestor[1].child[0]`` if just the child indices were compared.

Note:
    2. When retrieving the name of a plug via :meth:`OpenMaya.MPlug.partialName`, there are two arguments that should be included to ensure the name is explicit for all cases:

       - ``includeNonMandatoryIndices``: Ensures indices are included in the names of element plugs whose attribute is not marked as indexMatters. See :attr:`OpenMaya.MFnAttribute.indexMatters`.
       - ``includeInstancedIndices``: Ensures indices are included in the names of element plugs whose attribute is marked as world space (eg. ``worldMatrix[0]``). See :attr:`OpenMaya.MFnAttribute.worldSpace`.

.. _MPlug_warning_1:

Warning:
    1. The :attr:`~OpenMaya.MPlug.isNull` state of an :class:`OpenMaya.MPlug` is not reflective of whether the plug references a valid dependency node plug.
       Rather this value indicates whether the plug was `constructed` with valid references to a dependency node and attribute.

.. _MPlug_warning_2:

Warning:
    2. An :class:`OpenMaya.MPlug` will be given placeholder indices if it is initialised with an :class:`OpenMaya.MObject` which is referencing an attribute that is the child of a compound array attribute.
       The :class:`OpenMaya.MPlug` state is valid since each :class:`OpenMaya.MObject` points to a valid internal Maya object.
       However functionally this :class:`OpenMaya.MPlug` is invalid since it does not reference a specific plug in the dependency graph.

.. _MPlug_warning_3:

Warning:
    3. An :class:`OpenMaya.MPlug` can be initialised with :class:`OpenMaya.MObject` instances that reference unrelated internal attribute and node objects.
       The :class:`OpenMaya.MPlug` state is valid since each :class:`OpenMaya.MObject` points to a valid internal Maya object.
       However functionally this :class:`OpenMaya.MPlug` is invalid since it does not reference a specific plug in the dependency graph.

:class:`OpenMaya.MSelectionList`
--------------------------------

Note:
    1. When adding a node via :meth:`OpenMaya.MSelectionList.add`, the ``searchPathsAndNamespaces`` argument defines the behaviour of the search.

       - If :data:`False`, the name must include any identifying path and namespace with format ``'|:namespace:ancestor|:namespace:child'``.
       - If :data:`True`, the name can be a short name with format ``'child'`` or a partial path with format ``'ancestor|child'``.
         The search will be extended to ancestors and namespaces. Selection will preference namespaced nodes.
         For example if there are two nodes with the same short name but only one is namespaced, the namespaced node will be added first.

Note:
    2. When adding a plug or component via :meth:`OpenMaya.MSelectionList.add`, the ``searchPathsAndNamespaces`` argument does not affect the search.

       - A single object will be selected if a node can be uniquely identified within the name.
       - Multiple objects will be selected if a node cannot be not uniquely identified within the name (order of selection is unclear).

Note:
    3. Adding an array plug which references an 'instanced' :attr:`OpenMaya.MFnAttribute.worldSpace` attribute will produce an indexed element plug.
       For example adding ``'transform.worldMatrix'`` will produce a plug corresponding to ``'transform.worldMatrix[0]'`` when accessed via :meth:`OpenMaya.MSelectionList.getPlug`.

----------------------------------------------------------------
"""
import abc
import collections
import logging
import re
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

import msTools
from msTools.core.maya import constants as CONST
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.py import structures as PY_STRUCTURES


# --------------------------------------------------------------
# --- Modifiers ---
# --------------------------------------------------------------

class MDGModifier(object):
    """Composition class for registering an internal :class:`OpenMaya.MDGModifier` with an :class:`OpenMaya.MPxCommand`.

    Upon calling :meth:`doIt` any registered :class:`OpenMaya.MDGModifier` operations are executed
    via an undo/redo capable :class:`OpenMaya.MPxCommand`.

    Refer to :class:`OpenMaya.MDGModifier` for supported operations. Two amendments are made to the public interface:

    - :meth:`doIt`: Reimplements :meth:`OpenMaya.MDGModifier.doIt`.
    - :meth:`undoIt`: Prevents access to :meth:`OpenMaya.MDGModifier.undoIt`.

    Note:
        Once :meth:`doIt` is called, the modifier instance becomes inaccessible.
        Ownership of the internal :class:`OpenMaya.MDGModifier` is transferred to the :class:`OpenMaya.MPxCommand`.

    Example:
        .. code-block:: python

            # Create a network node using the OpenMaya API
            mod = MDGModifier()
            mod.createNode('network')
            mod.doIt()
            # Undo via the Maya command interface
            maya.cmds.undo()
    """

    def __init__(self):
        """Initialize the modifier before registering operations."""
        self._isRegistered = False
        self._dgMod = om2.MDGModifier()
        # Convert the address to a hex string since MPxCommand does not support `long` arguments
        self._memoryAddress = hex(id(self._dgMod))

    def __getattribute__(self, name):
        """Attempts to return the attribute ``name`` from the :class:`MDGModifier` instance.
        If the attribute is not found the search is extended to the internal :class:`OpenMaya.MDGModifier` instance.

        Raises:
            :exc:`~exceptions.AttributeError`: If ``name`` does not exist on the :class:`MDGModifier` instance or the internal :class:`OpenMaya.MDGModifier` instance.
            :exc:`~exceptions.RuntimeError`: If :meth:`MDGModifier.doIt` has been called.

        Returns:
            any: Object bound to ``name``.
        """
        if super(MDGModifier, self).__getattribute__("_isRegistered"):
            raise RuntimeError("Operations have already been executed, modifier is inaccessible.")

        try:
            attr = super(MDGModifier, self).__getattribute__(name)
        except AttributeError:
            attr = getattr(self._dgMod, name)

        return attr

    def doIt(self):
        """Execute any operations which have been applied to the internal :class:`OpenMaya.MDGModifier` and register them with an undoable command.

        Raises:
            :exc:`~exceptions.RuntimeError`: If :meth:`MDGModifier.doIt` has already been called.
        """
        if self._isRegistered:
            raise RuntimeError("Operations have already been executed, modifier is inaccessible.")
        else:
            cmds.polymorphic(self._memoryAddress)
            self._isRegistered = True

    def undoIt(self):
        """Prevents access to :meth:`OpenMaya.MDGModifier.undoIt` which is inherited by the internal :class:`OpenMaya.MDGModifier` instance.

        Raises:
            :exc:`~exceptions.NotImplementedError`: If this method is called.
        """
        raise NotImplementedError("MDGModifier.undoIt() method is not supported.")


class MDagModifier(object):
    """Composition class for registering an internal :class:`OpenMaya.MDagModifier` with an :class:`OpenMaya.MPxCommand`.

    Upon calling :meth:`doIt` any registered :class:`OpenMaya.MDagModifier` operations are executed
    via an undo/redo capable :class:`OpenMaya.MPxCommand`.

    Refer to :class:`OpenMaya.MDagModifier` and its base :class:`OpenMaya.MDGModifier` for supported operations.
    Two amendments are made to the public interface:

    - :meth:`doIt`: Reimplements :meth:`OpenMaya.MDGModifier.doIt`.
    - :meth:`undoIt`: Prevents access to :meth:`OpenMaya.MDGModifier.undoIt`.

    Note:
        Once :meth:`doIt` is called, the modifier instance becomes inaccessible.
        Ownership of the internal :class:`OpenMaya.MDagModifier` is transferred to the :class:`OpenMaya.MPxCommand`.

    Example:
        .. code-block:: python

            # Create a transform node using the OpenMaya API
            mod = MDagModifier()
            mod.createNode('transform')
            mod.doIt()
            # Undo via the Maya command interface
            maya.cmds.undo()
    """

    def __init__(self):
        """Initialize the modifier before registering operations."""
        self._isRegistered = False
        self._dagMod = om2.MDagModifier()
        # Convert the address to a hex string since MPxCommand does not support `long` arguments
        self._memoryAddress = hex(id(self._dagMod))

    def __getattribute__(self, name):
        """Attempts to return the attribute ``name`` from the :class:`MDagModifier` instance.
        If the attribute is not found the search is extended to the internal :class:`OpenMaya.MDagModifier` instance.

        Raises:
            :exc:`~exceptions.AttributeError`: If ``name`` does not exist on the :class:`MDagModifier` instance or the internal :class:`OpenMaya.MDagModifier` instance.
            :exc:`~exceptions.RuntimeError`: If :meth:`MDagModifier.doIt` has been called.

        Returns:
            any: Object bound to ``name``.
        """
        if super(MDagModifier, self).__getattribute__("_isRegistered"):
            raise RuntimeError("Operations have already been executed, modifier is inaccessible.")

        try:
            attr = super(MDagModifier, self).__getattribute__(name)
        except AttributeError:
            attr = getattr(self._dagMod, name)

        return attr

    def doIt(self):
        """Execute any operations which have been applied to the internal :class:`OpenMaya.MDagModifier` and register them with an undoable command.

        Raises:
            :exc:`~exceptions.RuntimeError`: If :meth:`MDagModifier.doIt` has already been called.
        """
        if self._isRegistered:
            raise RuntimeError("Operations have already been executed, modifier is inaccessible.")
        else:
            cmds.polymorphic(self._memoryAddress)
            self._isRegistered = True

    def undoIt(self):
        """Prevents access to :meth:`OpenMaya.MDGModifier.undoIt` which is inherited by the internal :class:`OpenMaya.MDagModifier` instance.

        Raises:
            :exc:`~exceptions.NotImplementedError`: If this method is called.
        """
        raise NotImplementedError("MDagModifier.undoIt() method is not supported.")


class Modifier(object):
    """Abstract baseclass for defining undoable operations in Maya.

    Initializing this baseclass for any subclassed instance will register the interface with an :class:`OpenMaya.MPxCommand`.
    The command makes use of two abstract methods implemented by the subclass:

    - :meth:`doIt`: Modify the state of Maya.
    - :meth:`undoIt`: Undo or reverse the changes made by :meth:`doIt`.

    Example:
        .. code-block:: python

            class LockPlug(Modifier):
                def __init__(self, plug):
                    self._plug = plug
                    super(LockPlug, self).__init__()

                def doIt(self):
                    self._oldLockState = self._plug.isLocked
                    self._plug.isLocked = True

                def undoIt(self):
                    self._plug.isLocked = self._oldLockState

            # Lock `plug` using the OpenMaya API
            LockPlug(plug)
            # Undo via the Maya command interface
            maya.cmds.undo()
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self):
        """Initializes the modifier and registers it with an :class:`OpenMaya.MPxCommand`.
        The command immediately calls :meth:`doIt` upon being registered.
        """
        self._register()

    def _register(self):
        # Convert the address to a hex string since MPxCommand does not support `long` arguments
        memoryAddress = hex(id(self))
        cmds.polymorphic(memoryAddress)

    @abc.abstractmethod
    def doIt(self):
        """Modify the state of Maya.

        Note:
            Abstract method - must be overriden by each subclass.
        """
        pass

    @abc.abstractmethod
    def undoIt(self):
        """Undo or reverse the changes made by :meth:`doIt`.

        Note:
            Abstract method - must be overriden by each subclass.
        """
        pass


# --------------------------------------------------------------
# --- Sets ---
# --------------------------------------------------------------

class MPlugId(collections.namedtuple('_MPlugId', ["plug", "indexPath"])):
    """An :class:`OpenMaya.MPlug` encapsulation which provides an explicit approach to equality comparisons.

    Provided as an alternative to :meth:`OpenMaya.MPlug.__eq__` and :meth:`OpenMaya.MPlug.__ne__` which both complete comparisons via attributes and nodes.
    For instances of this class, comparisons are completed via attributes, nodes and logical indices (including ancestral logical indices).

    Note:
        Instances of this class maintain a unique reference to their encapsulated :class:`OpenMaya.MPlug` to ensure the referenced dependency node plug does not change.
        This enables the logical indices of the :class:`OpenMaya.MPlug` to be cached for efficient comparison.

    Attributes:
        plug (:class:`OpenMaya.MPlug`): Get a copy of the encapsulated dependency node plug.
        indexPath (:class:`list` [:class:`int`]): Get a copy of the logical index cache that plots the ancestral path to the root of ``plug``.

    Example:
        .. code-block:: python

            # Comparison evaluates `True`
            getPlugByName('node.plug[0]') == getPlugByName('node.plug[1]')

            # Comparison evaluates `False`
            MPlugId(getPlugByName('node.plug[0]')) == MPlugId(getPlugByName('node.plug[1]'))
    """

    def __new__(cls, plug):
        """Instantiate an object.

        Args:
            plug (:class:`OpenMaya.MPlug`): Plug to encapsulate.
        """
        return super(MPlugId, cls).__new__(cls, om2.MPlug(plug), cls._getIndexPath(plug))

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Returns:
            :class:`str`: A string representation of the dependency node plug encapsulation.
        """
        return "MPlugId(plug={}, indexPath={})".format(NAME.getPlugFullName(self.plug), self.indexPath)

    def __getattribute__(self, name):
        """``x.__getattribute__(name)`` <==> ``x.name``."""
        attr = super(MPlugId, self).__getattribute__(name)
        if name in MPlugId._fields:
            if name == "plug":
                return om2.MPlug(attr)
            else:
                return list(attr)

    @classmethod
    def _getIndexPath(cls, plug):
        """Returns a list containing the logical indices of a given plug and any of its ancestors. Indices are ordered from descendant to ancestor."""
        indices = []
        ancestorPlug = None

        if plug.isElement:
            indices.append(plug.logicalIndex())
            ancestorPlug = plug.array()
        elif plug.isChild:
            ancestorPlug = plug.parent()

        if ancestorPlug is not None:
            indices.extend(cls._getIndexPath(ancestorPlug))

        return indices


class MObjectSet(PY_STRUCTURES.EqualitySet):
    """Compile an ordered set of unique :class:`OpenMaya.MObject` instances.

    The interface is inherited from :class:`msTools.core.py.structures.EqualitySet` which provides templated functionality based on the :attr:`DATA_TYPE`.
    Designed to mimic a :class:`set` whilst internally data is compiled through equality testing instead of a hash table.
    Expect operations to run in O(n) time compared to their :class:`set` counterparts which are likely to run in O(1) time.

    Example:
        .. code-block:: python

            node0 = getNodeByName('node0')
            node1 = getNodeByName('node1')

            # Initialize a set with `node0`
            mObjSet = MObjectSet([node0])

            # Set already contains `node0`, returns `False`
            assert not mObjSet.add(node0)
            # Add `node1`, returns `True`
            assert mObjSet.add(node1)
            # Set contains `node0` and `node1`
            assert len(mObjSet) == 2
    """

    # Informs the inherited `EqualitySet` interface to expect `MObject` instances as input data
    DATA_TYPE = om2.MObject


class MDagPathSet(PY_STRUCTURES.EqualitySet):
    """Compile an ordered set of unique :class:`OpenMaya.MDagPath` instances.

    The interface is inherited from :class:`msTools.core.py.structures.EqualitySet` which provides templated functionality based on the :attr:`DATA_TYPE`.
    Designed to mimic a :class:`set` whilst internally data is compiled through equality testing instead of a hash table.
    Expect operations to run in O(n) time compared to their :class:`set` counterparts which are likely to run in O(1) time.

    Example:
        .. code-block:: python

            path0 = getPathByName('|node0')
            path1 = getPathByName('|node1')

            # Initialize a set with `path0`
            mPathSet = MDagPathSet([path0])

            # Set already contains `path0`, returns `False`
            assert not mPathSet.add(path0)
            # Add `path1`, returns `True`
            assert mPathSet.add(path1)
            # Set contains `path0` and `path1`
            assert len(mPathSet) == 2
    """

    # Informs the inherited `EqualitySet` interface to expect `MDagPath` instances as input data
    DATA_TYPE = om2.MDagPath


class MPlugSet(PY_STRUCTURES.EqualitySet):
    """Compile an ordered set of unique :class:`OpenMaya.MPlug` instances.

    The interface is inherited from :class:`msTools.core.py.structures.EqualitySet` which provides templated functionality based on the :attr:`DATA_TYPE`.
    Designed to mimic a :class:`set` whilst internally data is compiled through equality testing instead of a hash table.
    Expect operations to run in O(n) time compared to their :class:`set` counterparts which are likely to run in O(1) time.

    Note:
        Internally, each input is encapsulated by an :class:`MPlugId` to ensure equality checks are explicit.

    Example:
        .. code-block:: python

            plug0 = getPlugByName('node.plug[0]')
            plug1 = getPlugByName('node.plug[1]')

            # Initialize a set with `plug0`
            mPlugSet = MPlugSet([plug0])

            # Set already contains `plug0`, returns `False`
            assert not mPlugSet.add(plug0)
            # Add `plug1`, returns `True`
            assert mPlugSet.add(plug1)
            # Set contains `plug0` and `plug1`
            assert len(mPlugSet) == 2
    """

    # Informs the inherited `EqualitySet` interface to expect `MPlug` instances as input data
    DATA_TYPE = om2.MPlug

    def _formatInput(self, arg):
        """Ensures the inherited `EqualitySet` interface stores and operates on non-iterable input data as `MPlugId` instances instead of `MPlug` instances."""
        return MPlugId(arg)

    def _formatIterableInput(self, arg):
        """Ensures the inherited `EqualitySet` interface stores and operates on iterable input data as `MPlugId` instances instead of `MPlug` instances."""
        return [MPlugId(plug) for plug in arg]

    def _formatOutput(self, arg):
        """Ensures the inherited `EqualitySet` interface returns output data as `MPlug` instances instead of `MPlugId` instances."""
        return arg.plug


# --------------------------------------------------------------
# --- Utilities ---
# --------------------------------------------------------------

def inspectTypes(types=None):
    """Split type constants from :class:`OpenMaya.MFn` into negative and non-negative groups.
    Used by operations which check the compatibility of internal Maya objects with object and function-set types.

    Args:
        types (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn` representing object and function-set types.
            Non-negative type constants are ususally used to represent accepted types when checking for compatibility.
            Negative type constants are usually used to represent excluded types when checking for compatibility.
            Defaults to :data:`None`.

    Returns:
        ((:class:`int`, ...), (:class:`int`, ...)): A two-element :class:`tuple`.

        #. A :class:`tuple` containing non-negative type constants from ``types``.
        #. A :class:`tuple` containing negative type constants from ``types``.
    """
    if not types:
        return tuple(), tuple()

    acceptedTypes = []
    excludedTypes = []

    for typeConst in types:
        if typeConst < 0:
            excludedTypes.append(-typeConst)
        else:
            acceptedTypes.append(typeConst)

    return tuple(acceptedTypes), tuple(excludedTypes)


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isValidObjectWrapper(obj):
    """Check if an :class:`OpenMaya.MObject` wrapper of an internal Maya object is functionally valid in terms of its reference.

    Note:
        Functionally valid implies the internal state of the :class:`OpenMaya.MObject` will be disregarded.
        Additional checks will be completed to resolve the above :class:`OpenMaya.MObject` :ref:`warning-1 <MObject_warning_1>`.

    Args:
        obj (:class:`OpenMaya.MObject`): Wrapper of an internal Maya object.

    Returns:
        :class:`bool`: :data:`True` if the reference held by ``obj`` to an internal Maya object is functionally valid, otherwise :data:`False`.
    """
    return not obj.isNull() and isValidObject(om2.MObjectHandle(obj))


def isValidObject(handle, checkAlive=False):
    """Check if an internal Maya object is valid or internally alive.

    Note:
        An internal Maya `node` is considered valid if it exists in the dependency graph.
        An invalid Maya object can still be internally alive if it is registered within the internal scene table.
        For example a Maya `node` which exists in the undo queue will be considered invalid but alive because it exists in the scene table but not the graph.

    Args:
        handle (:class:`OpenMaya.MObjectHandle` [:class:`OpenMaya.MObject`]): Validation wrapper initialised by a wrapper of an internal Maya object.
        checkAlive (:class:`bool`, optional): Whether to check the scene table registry if the internal Maya object is invalid. Defaults to :data:`False`.
    ..

    Returns:
        :class:`bool`: :data:`True` if the following conditions are valid:

        1. The internal Maya object referenced by ``handle`` is valid if ``checkAlive`` is :data:`False`.
        2. The internal Maya object referenced by ``handle`` is alive if ``checkAlive`` is :data:`True`.

        Otherwise :data:`False`.
    """
    return handle.isValid() or (checkAlive and handle.isAlive())


def isValidPath(path):
    """Check if an :class:`OpenMaya.MDagPath` is functionally valid in terms of its :class:`OpenMaya.MObject` reference to a dependency node.

    Note:
        Functionally valid implies the internal state of the :class:`OpenMaya.MDagPath` will be disregarded.
        Additional checks will be completed to resolve the above :class:`OpenMaya.MDagPath` :ref:`warning-1 <MDagPath_warning_1>`.

    Args:
        path (:class:`OpenMaya.MDagPath`): Path encapsulation of a DAG node.

    Returns:
        :class:`bool`: :data:`True` if the DAG node reference held by ``path`` is functionally valid, otherwise :data:`False`.
    """
    return path.isValid() and path.fullPathName()


def isValidPlug(plug):
    """Check if an :class:`OpenMaya.MPlug` is functionally valid in terms of its logical indices and :class:`OpenMaya.MObject` references to a dependency node and attribute.

    Note:
        Functionally valid implies the internal state of the :class:`OpenMaya.MPlug` will be disregarded.
        Additional checks will be completed to resolve the above :class:`OpenMaya.MPlug` :ref:`warning-1 <MPlug_warning_1>`, :ref:`warning-2 <MPlug_warning_2>` and :ref:`warning-3 <MPlug_warning_3>`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

    Returns:
        :class:`bool`: :data:`True` if the following conditions are valid:

        1. The logical indices of ``plug`` are non-negative.
        2. The references held by ``plug`` to an internal node and attribute are both functionally valid.
        3. The references held by ``plug`` to an internal node and attribute are both related.

        Otherwise :data:`False`.
    """
    # Preliminary condition (check if node or attr is null)
    if plug.isNull:
        return False

    # Condition 1 - Logical indices
    if re.search(r'\[-\d+\]', plug.partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True)):
        return False

    # Condition 2 - Functional Maya objects (check if node has been deleted - does not affect MPlug.isNull)
    node = plug.node()
    attr = plug.attribute()
    if not isValidObjectWrapper(node):
        return False

    # Condition 3 - Related Maya objects (check if attribute has been deleted from node + check if attribute/node are unrelated - neither affect MPlug.isNull)
    nodeFn = om2.MFnDependencyNode(node)
    attrFn = om2.MFnAttribute(attr)
    if not nodeFn.hasAttribute(attrFn.name) or nodeFn.attribute(attrFn.name) != attr:
        return False

    return True


def hasCompatibleType(obj, types=None):
    """Check if an object which holds a reference to an internal Maya object is compatible with at least one of the given type constants.

    Note:
        The functionality of :meth:`OpenMaya.MObject.hasFn` differs to :meth:`OpenMaya.MDagPath.hasFn`.
        See the above :class:`OpenMaya.MDagPath` :ref:`note-1 <MDagPath_note_1>`.

    Args:
        obj (:class:`OpenMaya.MObject` | :class:`OpenMaya.MDagPath`): Wrapper of an internal Maya object or path to a DAG node.
        types (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn` representing object and Function Set types used to determine the compatibility of ``obj``.
            Exclusions can be given as negated type constants making it is possible to exclude certain derived Function Set types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`bool`: :data:`True` if ``obj`` is compatible with at least one of the ``types`` or ``types`` is :data:`None`, otherwise :data:`False`.
    """
    if not types:
        return True

    acceptedTypes, excludedTypes = inspectTypes(filterTypes=types)

    for typeConst in excludedTypes:
        if obj.hasFn(typeConst):
            return False

    if not acceptedTypes:
        return True

    for typeConst in acceptedTypes:
        if obj.hasFn(typeConst):
            return True

    return False


def validateNodeType(node, nodeType=om2.MFn.kDependencyNode, nodeTypeId=None):
    """Validate an :class:`OpenMaya.MObject` by checking if it references a certain type of dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.
        nodeType (:class:`int`, optional): Type constant from :class:`OpenMaya.MFn` representing the expected node type of ``node``.
            Defaults to :attr:`OpenMaya.MFn.kDependencyNode` - the base type for all dependency nodes.
        nodeTypeId (:class:`OpenMaya.MTypeId`, optional): Unique node type identifier representing the expected node type of ``node``.
            Defaults to :data:`None` - the :class:`OpenMaya.MTypeId` is not validated.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` is not compatible with ``nodeType``.
        :exc:`~exceptions.ValueError`: If ``nodeTypeId`` is not :data:`None` and does not reference a registered node type.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``nodeTypeId`` is not :data:`None` and ``node`` does not have a corresponding :class:`OpenMaya.MTypeId`.
    """
    if not node.hasFn(nodeType):
        if nodeType == om2.MFn.kDependencyNode:
            raise EXC.MayaTypeError("Expected node, received `OpenMaya.MFn.{}` type object instead".format(node.apiTypeStr))
        else:
            raise EXC.MayaTypeError("Expected node of type `OpenMaya.MFn.{}`, received `OpenMaya.MFn.{}` type object instead".format(CONST.CONSTANT_NAME_MAPPING[nodeType], node.apiTypeStr))

    if nodeTypeId is not None:
        if nodeTypeId.id() == 0:
            raise ValueError("Received invalid {}".format(om2.MTypeId))

        nodeFn = om2.MFnDependencyNode(node)
        if nodeFn.typeId != nodeTypeId:
            raise EXC.MayaTypeError("Expected {} type node, received {} type node instead".format(om2.MNodeClass(nodeTypeId).typeName, nodeFn.typeName))


def validateAttributeType(attribute, attributeType=om2.MFn.kAttribute):
    """Validate an :class:`OpenMaya.MObject` by checking if it references a certain type of attribute.

    Args:
        attribute (:class:`OpenMaya.MObject`): Wrapper of an attribute.
        attributeType (:class:`int`, optional): Type constant from :class:`OpenMaya.MFn` representing the expected attribute type of ``attr``.
            Defaults to :attr:`OpenMaya.MFn.kAttribute` - the base type for all attributes.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``attr`` is not compatible with ``attributeType``.
    """
    if not attribute.hasFn(attributeType):
        if attributeType == om2.MFn.kAttribute:
            raise EXC.MayaTypeError("Expected attribute, received `OpenMaya.MFn.{}` type object instead".format(attribute.apiTypeStr))
        else:
            raise EXC.MayaTypeError("Expected attribute of type `OpenMaya.MFn.{}`, received `OpenMaya.MFn.{}` type object instead".format(CONST.CONSTANT_NAME_MAPPING[attributeType], attribute.apiTypeStr))


def validateComponentType(component, componentType=om2.MFn.kComponent):
    """Validate an :class:`OpenMaya.MObject` by checking if it references a certain type of component.

    Args:
        component (:class:`OpenMaya.MObject`): Wrapper of a component.
        componentType (:class:`int`, optional): Type constant from :class:`OpenMaya.MFn` representing the expected component type of ``component``.
            Defaults to :attr:`OpenMaya.MFn.kComponent` - the base type for all components.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``component`` is not compatible with ``componentType``.
    """
    if not component.hasFn(componentType):
        if componentType == om2.MFn.kComponent:
            raise EXC.MayaTypeError("Expected component, received `OpenMaya.MFn.{}` type object instead".format(component.apiTypeStr))
        else:
            raise EXC.MayaTypeError("Expected component of type `OpenMaya.MFn.{}`, received `OpenMaya.MFn.{}` type object instead".format(CONST.CONSTANT_NAME_MAPPING[componentType], component.apiTypeStr))


def validatePlugType(plug, isArray=None, isCompound=None):
    """Validate an :class:`OpenMaya.MPlug` by checking if it references a certain type of dependency node plug.

    Args:
        plug (:class:`OpenMaya.MObject`): Encapsulation of a dependency node plug.
        isArray (:class:`bool`, optional): Whether ``plug`` is expected to be an array.
            Defaults to :data:`None` - no array expectation.
        isCompound (:class:`bool`, optional): Whether ``plug`` is expected to be a compound.
            Defaults to :data:`None` - no compound expectation.

    Raises:
        :exc:`~exceptions.ValueError`: If ``isCompound`` and ``isArray`` are both :data:`None`.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` does not represent the expectations of ``isCompound`` and ``isArray``.
    """
    if isCompound is None and isArray is None:
        raise ValueError("Must provide at least one expectation for the given plug")

    errorMsg = ""

    if isCompound is not None:
        if isCompound != plug.isCompound:
            errorMsg += " non-compound type" if plug.isCompound else " compound type"

    if isArray is not None:
        if isArray != plug.isArray:
            errorMsg += " non-array" if plug.isArray else " array"

    if errorMsg:
        raise EXC.MayaTypeError("Expected{} plug".format(errorMsg))


# --------------------------------------------------------------
# --- Retrieve : Attribute ---
# --------------------------------------------------------------

def getAttributeByName(nodeAttributeName, searchPathsAndNamespaces=False):
    """Return a wrapper of an attribute identified by name.

    Args:
        nodeAttributeName (:class:`basestring`): Name with format ``'<node>.<attribute>'`` used to identify an attribute.
        searchPathsAndNamespaces (:class:`bool`, optional): Whether to extend the search to ancestors and namespaces of ``<node>``.

            - If :data:`False`, ``<node>`` must include any identifying path and namespace with format ``'|:namespace:ancestor|:namespace:child'``.
            - If :data:`True`, ``<node>`` can be a short name with format ``'child'`` or a partial path with format ``'ancestor|child'``, in which case the first matching node will be used.

            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node attribute could not be identified.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of an attribute.
    """
    try:
        nodeName, attrName = nodeAttributeName.split(".", 1)
    except ValueError:
        raise EXC.MayaLookupError("{}: Attribute does not exist".format(nodeAttributeName))

    node = getNodeByName(nodeName, searchPathsAndNamespaces=searchPathsAndNamespaces)
    nodeFn = om2.MFnDependencyNode(node)
    attr = nodeFn.attribute(attrName)

    if attr.isNull():
        raise EXC.MayaLookupError("{}: Attribute does not exist".format(nodeAttributeName))
    else:
        return attr


def getAttributeFromNodeByName(node, attributeName):
    """Return a wrapper of an attribute identified by a dependency node and name.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.
        attributeName (:class:`basestring`): Name of an attribute on ``node``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If an attribute on ``node`` could not be identified.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of an attribute.
    """
    validateNodeType(node)

    nodeFn = om2.MFnDependencyNode(node)
    attr = nodeFn.attribute(attributeName)

    if attr.isNull():
        raise EXC.MayaLookupError("{}.{}: Attribute does not exist".format(NAME.getNodeFullName(node), attributeName))

    return attr


def iterAttributesFromNode(node):
    """Yield wrappers for the attributes of a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of the attributes on ``node``.
    """
    validateNodeType(node)

    nodeFn = om2.MFnDependencyNode(node)
    attrCount = nodeFn.attributeCount()

    for index in xrange(attrCount):
        yield nodeFn.attribute(index)


def iterAttributesFromNodeByProperties(node, **kwargs):
    """Yield wrappers for the attributes of a dependency node which correspond to the given properties.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.
        **kwargs: Keyword arguments where each argument corresponds to a readable property on :class:`OpenMaya.MFnAttribute` such as
            :attr:`~OpenMaya.MFnAttribute.keyable`, :attr:`~OpenMaya.MFnAttribute.channelBox`, :attr:`~OpenMaya.MFnAttribute.hidden`,
            :attr:`~OpenMaya.MFnAttribute.storable`, :attr:`~OpenMaya.MFnAttribute.readable`, :attr:`~OpenMaya.MFnAttribute.writable`,
            :attr:`~OpenMaya.MFnAttribute.connectable`, :attr:`~OpenMaya.MFnAttribute.array`.
            An attribute will be returned if the value assigned to each keyword argument corresponds to the value of the corresponding attribute property.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of attributes on ``node``.

    Examples:
        .. code-block:: python

            # Iterate over all dynamic attributes that exist on `node` which are also unreadable
            iterAttributesFromNodeByProperties(node, dynamic=True, readable=False)

            # Iterate over all static attributes that exist on `node` which are also keyable
            iterAttributesFromNodeByProperties(node, dynamic=False, keyable=True)
    """
    validateNodeType(node)

    nodeFn = om2.MFnDependencyNode(node)
    attrCount = nodeFn.attributeCount()

    for index in xrange(attrCount):
        attr = nodeFn.attribute(index)
        attrFn = om2.MFnAttribute(attr)

        for prop, value in kwargs.iteritems():
            if getattr(attrFn, prop) != value:
                break
        else:
            yield attr


# --------------------------------------------------------------
# --- Retrieve : Node ---
# --------------------------------------------------------------

def getNodeByName(nodeName, searchPathsAndNamespaces=False):
    """Return a wrapper of a dependency node identified by name.

    Args:
        nodeName (:class:`basestring`): Name or path used to identify a node.
        searchPathsAndNamespaces (:class:`bool`, optional): Whether to extend the search to ancestors and namespaces of ``nodeName``.

            - If :data:`False`, ``nodeName`` must include any identifying path and namespace with format ``'|:namespace:ancestor|:namespace:child'``.
            - If :data:`True`, ``nodeName`` can be a short name with format ``'child'`` or a partial path with format ``'ancestor|child'``, in which case the first matching node will be returned.

            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node could not be identified.

    Returns:
        :class:`OpenMaya.MObject`: Wrapper of a dependency node.
    """
    selection = om2.MSelectionList()

    # Attempt short name or partial path selection first so we can log a message if this fails
    try:
        selection.add(nodeName, False)  # RuntimeError : If node does not exist or is not unique
    except RuntimeError:
        if not searchPathsAndNamespaces:
            raise EXC.MayaLookupError("{}: Node does not exist or is not unique".format(nodeName))

        # Extend the search to ancestor paths and namespaces
        try:
            selection.add(nodeName, searchPathsAndNamespaces)
        except RuntimeError:
            raise EXC.MayaLookupError("{}: Node does not exist".format(nodeName))
        else:
            log.debug("{}: Node name is not unique, returning first match".format(nodeName))

    return selection.getDependNode(0)


def getPathByName(nodeName, searchPathsAndNamespaces=False):
    """Return a path encapsulation of a DAG node identified by name.

    Args:
        nodeName (:class:`basestring`): Name or path used to identify a path to a node.
        searchPathsAndNamespaces (:class:`bool`, optional): Whether to extend the search to ancestors and namespaces of ``nodeName``.

            - If :data:`False`, ``nodeName`` must include any identifying path and namespace with format ``'|:namespace:ancestor|:namespace:child'``.
            - If :data:`True`, ``nodeName`` can be a short name with format ``'child'`` or a partial path with format ``'ancestor|child'``, in which case the first matching path will be returned.

            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a DAG node could not be identified.

    Returns:
        :class:`OpenMaya.MDagPath`: Path encapsulation of a DAG node.
    """
    selection = om2.MSelectionList()

    # Attempt short name or partial path selection first so we can log a message if this fails
    try:
        selection.add(nodeName, False)  # RuntimeError : If node does not exist or is not unique
        path = selection.getDagPath(0)  # TypeError : If selection is not a DAG node
    except (RuntimeError, TypeError):
        if not searchPathsAndNamespaces:
            raise EXC.MayaLookupError("{}: DAG node does not exist or is not unique".format(nodeName))

        # Extend the search to ancestor paths and namespaces
        try:
            selection.add(nodeName, searchPathsAndNamespaces)
            path = selection.getDagPath(0)
        except (RuntimeError, TypeError):
            raise EXC.MayaLookupError("{}: DAG node does not exist".format(nodeName))
        else:
            log.debug("{}: Node name is not unique, returning first match".format(nodeName))
    else:
        # Check if a unique node was identified but not a unique instance
        if path.isInstanced():
            if len(path.partialPathName().split('|')) > len(nodeName.rstrip('|').split("|")):
                log.debug("{}: Node name is not a unique instance, returning first match".format(nodeName))

    return path


def getPathFromNode(node, instanceNumber=0):
    """Return a path encapsulation of a DAG node identified by instance number.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a DAG node.
        instanceNumber (:class:`int`, optional): Instance number used by the path encapsulation of ``node``. Defaults to ``0``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a DAG node.
        :exc:`~exceptions.ValueError`: If there is no instance of ``node`` with corresponding ``instanceNumber``.

    Returns:
        :class:`OpenMaya.MDagPath`: Path encapsulation of ``node`` with corresponding ``instanceNumber``.
    """
    validateNodeType(node, nodeType=om2.MFn.kDagNode)

    if instanceNumber == 0:
        return om2.MDagPath.getAPathTo(node)
    else:
        # Must return a copy, MDagPathArray does not reference count
        pathArray = om2.MDagPath.getAllPathsTo(node)
        try:
            return om2.MDagPath(pathArray[instanceNumber])
        except IndexError:
            raise ValueError("No instance has instance number: {}".format(instanceNumber))


# --------------------------------------------------------------
# --- Retrieve : Plug ---
# --------------------------------------------------------------

def getPlugByName(nodePlugName, searchPathsAndNamespaces=False):
    """Return a plug encapsulation of a dependency node plug identified by name.

    Args:
        nodePlugName (:class:`basestring`): Name with format ``'<node>.<plug>'`` used to identify a plug.
            The ``<plug>`` name should identify a unique plug on ``<node>`` by providing all element indices in the plug path using the format ``'element[0].child'``.
        searchPathsAndNamespaces (:class:`bool`, optional): Whether to extend the search to ancestors and namespaces of ``<node>``.

            - If :data:`False`, ``<node>`` must include any identifying path and namespace with format ``'|:namespace:ancestor|:namespace:child'``.
            - If :data:`True`, ``<node>`` can be a short name with format ``'child'`` or a partial path with format ``'ancestor|child'``, in which case the first matching node will be used.

            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node plug could not be identified.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation of a dependency node plug.
    """
    # Pre-select the node to ensure a single plug will be selected using a unique node name (plug selection behaves differently to node selection)
    try:
        nodeName, plugName = nodePlugName.split(".", 1)
    except ValueError:
        raise EXC.MayaLookupError("{}: Plug does not exist".format(nodePlugName))

    node = getNodeByName(nodeName, searchPathsAndNamespaces=searchPathsAndNamespaces)
    partialNodeName = NAME.getNodePartialName(node)
    partialNodePlugName = ".".join([partialNodeName, plugName])

    # An MSelectionList must be used for element plugs and plug paths containing more than one attribute name but should not be used for 'instanced' array attributes
    if re.search(r'\[\d+\]', plugName) or len(plugName.split('.')) > 1:
        selection = om2.MSelectionList()
        try:
            selection.add(partialNodePlugName)  # RuntimeError : If plug does not exist
            return selection.getPlug(0)  # TypeError : If selection is not a plug
        except (RuntimeError, TypeError):
            raise EXC.MayaLookupError("{}: Plug does not exist".format(partialNodePlugName))
    else:
        nodeFn = om2.MFnDependencyNode(node)
        attr = nodeFn.attribute(plugName)

        if attr.isNull():
            raise EXC.MayaLookupError("{}: Plug does not exist".format(partialNodePlugName))

        # The plug may be invalid if the name of the attribute exists as a child of a compound array
        plug = om2.MPlug(node, attr)
        if plug.isChild:
            attrFn = om2.MFnAttribute(attr)
            while not attrFn.parent.isNull():
                attrFn.setObject(attrFn.parent)
                if attrFn.array:
                    raise EXC.MayaLookupError("{}: Plug does not exist, ensure ancestral array plugs are indexed".format(partialNodePlugName))

        return plug


def getPlugFromNodeByName(node, plugName):
    """Return a plug encapsulation of a dependency node plug identified by a node and an associated plug name.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.
        plugName (:class:`basestring`): Name used to identify a plug on ``node``.
            It should identify a unique plug on ``node`` by providing all element indices in the plug path using the format ``'element[0].child'``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If a dependency node plug could not be identified.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation of a dependency node plug on ``node``.
    """
    validateNodeType(node)

    plugName = plugName.lstrip(".")
    partialNodeName = NAME.getNodePartialName(node)
    partialNodePlugName = ".".join([partialNodeName, plugName])

    # An MSelectionList must be used for element plugs and plug paths containing more than one attribute name but should not be used for 'instanced' array attributes
    if re.search(r'\[\d+\]', plugName) or len(plugName.split('.')) > 1:
        selection = om2.MSelectionList()
        try:
            selection.add(partialNodePlugName)  # RuntimeError : If plug does not exist
            return selection.getPlug(0)  # TypeError : If selection is not a plug
        except (RuntimeError, TypeError):
            raise EXC.MayaLookupError("{}: Plug does not exist".format(partialNodePlugName))
    else:
        nodeFn = om2.MFnDependencyNode(node)
        attr = nodeFn.attribute(plugName)

        if attr.isNull():
            raise EXC.MayaLookupError("{}: Plug does not exist".format(partialNodePlugName))

        # The plug may be invalid if the name of the attribute exists as a child of a compound array
        plug = om2.MPlug(node, attr)
        if plug.isChild:
            attrFn = om2.MFnAttribute(attr)
            while not attrFn.parent.isNull():
                attrFn.setObject(attrFn.parent)
                if attrFn.array:
                    raise EXC.MayaLookupError("{}: Plug does not exist, ensure ancestral array plugs are indexed".format(partialNodePlugName))

        return plug


def iterPlugsFromNode(node, forceInitialElements=False):
    """Yield plug encapsulations for the attributes of a dependency node.

    Args:
        node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.
        forceInitialElements (:class:`bool`, optional): Whether to traverse the zeroth indexed element of each array plug if no elements have been assigned.
            If :data:`False`, traversal of a plug's descendant hierarchy will terminate upon reaching an array plug that has no in-use elements.
            If :data:`True`, it is guaranteed that the full descendant hierarchy of each plug will be traversed. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of dependency node plugs on ``node``.
    """
    for attr in iterAttributesFromNode(node):
        attrFn = om2.MFnAttribute(attr)

        if attrFn.parent.isNull():
            plug = om2.MPlug(node, attr)
            yield plug

            try:
                for descendantPlug in msTools.core.maya.plug_utils.iterDescendants(plug, forceInitialElements=forceInitialElements):
                    yield descendantPlug
            except EXC.MayaTypeError:
                pass


# --------------------------------------------------------------
# --- Filter ---
# --------------------------------------------------------------

def filterObjectWrappersByType(objs, filterTypes=None):
    """Filter :class:`OpenMaya.MObject` wrappers of internal Maya objects based on their compatibility with type constants from :class:`OpenMaya.MFn`.

    Args:
        objs (iterable [:class:`OpenMaya.MObject`]): Wrappers of internal Maya objects.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`list` [:class:`OpenMaya.MObject`]: Filtered ``objs``.

    Example:
        .. code-block:: python

            # Returns object wrappers that reference non-mesh shape nodes
            filterObjectWrappersByType(objs, filterTypes=(OpenMaya.MFn.kShape, -OpenMaya.MFn.kMesh))
    """
    filteredObjs = []
    for obj in objs:
        if hasCompatibleType(obj, types=filterTypes):
            filteredObjs.append(obj)

    return filteredObjs


def filterPathsByType(paths, filterTypes=None):
    """Filter :class:`OpenMaya.MDagPath` objects based on their compatibility with type constants from :class:`OpenMaya.MFn`.

    Args:
        paths (iterable [:class:`OpenMaya.MDagPath`]): Path encapsulations of DAG nodes.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`list` [:class:`OpenMaya.MDagPath`]: Filtered ``paths``.

    Example:
        .. code-block:: python

            # Returns paths which reference non-mesh shape nodes or transforms with child non-mesh shape nodes
            filterPathsByType(paths, filterTypes=(OpenMaya.MFn.kShape, -OpenMaya.MFn.kMesh))
    """
    filteredPaths = []
    for path in paths:
        if hasCompatibleType(path, types=filterTypes):
            filteredPaths.append(path)

    return filteredPaths


def filterPathsByNodeType(paths, filterTypes=None):
    """Filter :class:`OpenMaya.MDagPath` objects based on their internal :class:`OpenMaya.MObject` compatibility with type constants from :class:`OpenMaya.MFn`.

    Args:
        paths (iterable [:class:`OpenMaya.MDagPath`]): Path encapsulations of DAG nodes.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`list` [:class:`OpenMaya.MDagPath`]: Filtered ``paths``.

    Example:
        .. code-block:: python

            # Returns paths which reference non-mesh shape nodes
            filterPathsByNodeType(paths, filterTypes=(OpenMaya.MFn.kShape, -OpenMaya.MFn.kMesh))
    """
    filteredPaths = []
    for path in paths:
        if hasCompatibleType(path.node(), types=filterTypes):
            filteredPaths.append(path)

    return filteredPaths


def filterPlugsByNodeType(plugs, filterTypes=None):
    """Filter :class:`OpenMaya.MPlug` objects based on their internal :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.

    Args:
        plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`list` [:class:`OpenMaya.MPlug`]: Filtered ``plugs``.

    Example:
        .. code-block:: python

            # Returns plugs which reference non-mesh shape nodes
            filterPlugsByNodeType(paths, filterTypes=(OpenMaya.MFn.kShape, -OpenMaya.MFn.kMesh))
    """
    filteredPlugs = []
    for plug in plugs:
        node = plug.node()
        if hasCompatibleType(node, types=filterTypes):
            filteredPlugs.append(plug)

    return filteredPlugs


def filterPlugsByAttributeType(plugs, filterTypes=None):
    """Filter :class:`OpenMaya.MPlug` objects based on their internal :class:`OpenMaya.MObject` attribute compatibility with type constants from :class:`OpenMaya.MFn`.

    Args:
        plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn`.
            Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kCompoundAttribute`.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`list` [:class:`OpenMaya.MPlug`]: Filtered ``plugs``.

    Example:
        .. code-block:: python

            # Returns plugs which reference non-compound attributes
            filterPlugsByNodeType(paths, filterTypes=(-OpenMaya.MFn.kCompoundAttribute,))
    """
    filteredPlugs = []
    for plug in plugs:
        attr = plug.attribute()
        if hasCompatibleType(attr, types=filterTypes):
            filteredPlugs.append(plug)

    return filteredPlugs


def createIteratorTypeFilter(objectType=om2.MIteratorType.kMObject, filterTypes=None):
    """Instantiate an :class:`OpenMaya.MIteratorType` object for use with either :class:`OpenMaya.MItDag`, :class:`OpenMaya.MItDependencyGraph` or :class:`OpenMaya.MItDependencyNodes`.

    Args:
        objectType (:class:`int`, optional): Type constant from :class:`OpenMaya.MIteratorType` corresponding to the type of root object that will be used by the iterator.
            Valid values are :attr:`~OpenMaya.MIteratorType.kMObject`, :attr:`~OpenMaya.MIteratorType.kMDagPathObject`, :attr:`~OpenMaya.MIteratorType.kMPlug`.
            Defaults to :attr:`~OpenMaya.MIteratorType.kMObject`.
        filterTypes (iterable [:class:`int`], optional): Type constants from :class:`OpenMaya.MFn` used to filter the type of objects generated by the iterator.
            Defaults to :data:`None` - no type filtering will occur.

    Returns:
        :class:`OpenMaya.MIteratorType`: Object used to filter the type of objects generated by the iterator.
    """
    iterType = om2.MIteratorType()
    iterType.objectType = objectType
    if filterTypes:
        iterType.filterList = filterTypes

    return iterType
