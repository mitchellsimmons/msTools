"""
Dependency node plug operations in Maya.

----------------------------------------------------------------

Creation
--------

    A dependency node plug uses an attribute like a template.
    The attribute defines the data type, name and default value for the plug.
    When an attribute is added to a node, a plug object is instantiated from the attribute.

    - A static attribute can act as the template for a plug on multiple dependency nodes.
    - A dynamic attribute can act as the template for a plug on a single dependency node.

----------------------------------------------------------------

Connections
-----------

    Plugs enable the flow of data through the dependency graph.
    A pair of connected plugs forms an edge or a dependency in the graph over which data can flow.

----------------------------------------------------------------

Access
------

    A dependency node plug can be accessed via an :class:`OpenMaya.MPlug` encapsulation.
    Each plug is defined in terms of a dependency node, an attribute and an array of attribute indices that plot a path from the root of the plug.

----------------------------------------------------------------

.. _note_1:

Note:
    1. Plugs cannot have both :attr:`OpenMaya.MPlug.isKeyable` and :attr:`OpenMaya.MPlug.isChannelBox` properties :data:`True`.
       Setting one :data:`True` will set the other :data:`False`.

Note:
    2. Elements of an array plug are stored sparsely meaning there is no guarantee that elements will have contiguous logical indices.

Note:
    3. An element plug is only considered in-use if it exists in the dataBlock of its associated dependency node.
       An element can be placed into the dataBlock by forcing an evaluate of the plug.

Note:
    4. If a plug holds complex data, it can usually be accessed via :meth:`OpenMaya.MPlug.asMObject`.
       The result can then be manipulated using a subclass of :class:`OpenMaya.MFnData` that is compatible with the specific :class:`OpenMaya.MObject` type.

.. _note_5:

Note:
    5. Locking an ancestor plug has a global affect on the lock state of each descendant plug.
       A descendant plug can therefore be locked even if it is not internally locked.
       The :attr:`OpenMaya.MPlug.isLocked` property can be used to get the global lock state of a plug or set the internal lock state of a plug.

.. _warning_1:

Warning:
    1. Locking an ancestor plug will not have an immediate affect on the lock state of any descendant element plug which is not yet considered in-use.
       This has the potential to cause an invalid state if a connection is made to one of the elements.
       Upon making a connection the lock state of the element will be updated as it is now considered in-use.
       Attempting to undo the connection will cause Maya to crash.

----------------------------------------------------------------
"""
import json
import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2

from msTools.core.maya import constants as CONST
from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import decorator_utils as DECORATOR
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM
from msTools.core.py import context_utils as PY_CONTEXT
from msTools.core.py import metaclasses as PY_META


# --------------------------------------------------------------
# --- Classes : Array Encapsulation ---
# --------------------------------------------------------------

class PackArray(PY_META.AbstractAccessWrapper):
    """An interface for managing input connections to the elements of a dependency node array plug.

    **Inputs:**

        When making a connection via the interface, each input must be given as an :class:`OpenMaya.MPlug` encapsulation of a dependency node plug.

    **Cleaning:**

        The interface enforces a cleaning routine that is run as a preliminary step before querying or modifying existing connections.
        Cleaning of the array is implemented as :meth:`clean`.

    **Validation:**

        The interface provides the option to track the functional state of the internal :class:`OpenMaya.MPlug`.
        When tracking is enabled, a :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.

    Note:
        Instances of this class maintain a unique reference to their internal :class:`OpenMaya.MPlug` to ensure the referenced dependency node plug does not change.
        This enables the logical indices of the :class:`OpenMaya.MPlug` to be cached for efficient comparison.
    """

    __metaclass__ = PY_META.MetaAccessWrapperFactory(
        wrapFunctions=True,
        wrapPropertyGetters=True,
        wrapPropertySetters=True,
        wrapPropertyDeleters=True,
        wrapExclusions=("__init__", "__repr__", "isValid")
    )

    # --- Abstract --------------------------------------------------------------

    def _preAccess(self):
        """Abstract override which checks the internal `MPlug` is functionally valid before providing access to an instance method, otherwise raises a `MayaObjectError`."""
        if not self._stateTracking:
            return

        if not self.isValid:
            raise EXC.MayaObjectError("{!r}: Plug is no longer valid, attribute or node may have been removed".format(self))

    def _postAccess(self):
        """Abstract override - null op."""
        pass

    # --- Special --------------------------------------------------------------

    def __init__(self, arrayPlug, inputPlugs=None, allowMultiples=False, stateTracking=True):
        """Initialize an encapsulation for a dependency node array plug.

        Args:
            arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.
            inputPlugs (iterable [:class:`OpenMaya.MPlug`], optional): Encapsulations of dependency node plugs.
                Each input is connected to the next available ``arrayPlug`` element. Defaults to :data:`None`.
            allowMultiples (:class:`bool`, optional): Whether multiple ``arrayPlug`` elements can be connected to a single input plug.
                Defaults to :data:`False` - Any existing duplicates will be removed from the tail end of the array.
            stateTracking (:class:`bool`, optional): Whether to track the functional state of the ``arrayPlug``.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` does not reference a dependency node array plug.
        """
        log.debug("PackArray.__init__(arrayPlug={!r}, inputPlugs={}, allowMultiples={}, stateTracking={})".format(
            arrayPlug, inputPlugs, allowMultiples, stateTracking))

        if not arrayPlug.isArray:
            raise EXC.MayaTypeError("{}: Plug is not an array".format(NAME.getPlugFullName(arrayPlug)))

        attr = arrayPlug.attribute()
        node = arrayPlug.node()

        # Use the superclass __setattr__ since the override will try to validate the array before the necessary attributes have been set
        super(PackArray, self).__setattr__("_plug", om2.MPlug(arrayPlug))
        super(PackArray, self).__setattr__("_plugId", OM.MPlugId(arrayPlug))
        super(PackArray, self).__setattr__("_attr", attr)
        super(PackArray, self).__setattr__("_attrFn", om2.MFnAttribute(attr))
        super(PackArray, self).__setattr__("_node", node)
        super(PackArray, self).__setattr__("_nodeHandle", om2.MObjectHandle(node))
        super(PackArray, self).__setattr__("_nodeFn", om2.MFnDependencyNode(node))
        super(PackArray, self).__setattr__("_partialName", NAME.getPlugPartialName(arrayPlug))
        super(PackArray, self).__setattr__("_allowMultiples", allowMultiples)
        super(PackArray, self).__setattr__("_stateTracking", stateTracking)

        # Append additional input plugs to the array or clean the connections
        if inputPlugs:
            self.extend(inputPlugs)
        else:
            self.clean()

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Note:
            This method is not subject to :attr:`stateTracking` and is therefore accessible even if the internal :class:`OpenMaya.MPlug` is functionally invalid.
            In this case cached data is used.

        Returns:
            :class:`str`: A string representation of the dependency node plug encapsulation.
        """
        isValid = self.isValid
        partialName = self.partialName if isValid else self._partialName
        state = "valid" if isValid else "invalid"
        return "PackArray('{}') <{}>".format(partialName, state)

    def __eq__(self, other):
        """``x.__eq__(y)`` <==> ``x == y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: If ``other`` has an equivalent type, return whether its contents (dependency node plug) are equivalent.
            Otherwise swap the operands and return the result, unless the operands have already been swapped in which case the result is :data:`False`.
        """
        if type(self) is type(other):
            return self._plugId == other.plugId

        return NotImplemented

    def __ne__(self, other):
        """``x.__ne__(y)`` <==> ``x != y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: The negation of :meth:`__eq__`.
        """
        return not self == other

    def __len__(self):
        """``x.__len__()`` <==> ``len(x)``.

        Returns:
            :class:`int`: The number of destination connections to the encapsulated plug.
        """
        return len(self.clean()[0])

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
    def isConnected(self):
        """:class:`bool`: :data:`True` if at least one element of the encapsulated plug has a destination connection, otherwise :data:`False`.

        :access: R
        """
        return bool(len(self))

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
    def allowMultiples(self):
        """:class:`bool`: Whether multiple elements of the encapsulated plug can be connected to a single input plug.

        :access: RW
        """
        return self._allowMultiples

    @allowMultiples.setter
    def allowMultiples(self, state):
        self._allowMultiples = state
        if not state:
            self.clean()

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
        """:class:`str`: The partial name of the encapsulated plug with format ``'<node>.<plug>'``.

        - ``<node>`` will be a partial node name qualified by a path and namespace where applicable or necessary.
          It is guaranteed to uniquely identify the plug's node with the minimum amount of information necessary (partial path of a DAG node).
        - ``<plug>`` is guaranteed to uniquely identify the plug with the minimum amount of information necessary (short attribute path, short attribute names).

        :access: R
        """
        self._partialName = NAME.getPlugPartialName(self.plug)
        return self._partialName

    # --- Public : Query --------------------------------------------------------------

    def hasInputNode(self, node):
        """Check if a dependency node is connected as an input to an element of the encapsulated plug.

        Args:
            node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.

        Returns:
            :class:`bool`: :data:`True` if ``node`` is connected as an input to an element of the encapsulated plug, otherwise :data:`False`.
        """
        OM.validateNodeType(node)
        return node in self.getInputNodes()

    def hasInputPlug(self, plug):
        """Check if a dependency node plug is connected as an input to an element of the encapsulated plug.

        Args:
            plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

        Returns:
            :class:`bool`: :data:`True` if ``plug`` is connected as an input to an element of the encapsulated plug, otherwise :data:`False`.
        """
        plugId = OM.MPlugId(plug)
        sourcePlugIDs, _ = self.clean()
        return plugId in sourcePlugIDs

    def getInputNodes(self):
        """Return nodes connected to each element of the encapsulated plug.

        Returns:
            :class:`list` [:class:`OpenMaya.MObject`]: Wrappers of dependency nodes connected as inputs to elements of the encapsulated plug.
        """
        sourcePlugIDs, _ = self.clean()
        return [sourcePlugID.plug.node() for sourcePlugID in sourcePlugIDs]

    def getInputPlugs(self):
        """Return plugs connected to each element of the encapsulated plug.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs connected as inputs to elements of the encapsulated plug.
        """
        sourcePlugIDs, _ = self.clean()
        return [sourcePlugID.plug for sourcePlugID in sourcePlugIDs]

    def getExistingElementPlugs(self):
        """Return existing element plugs for the encapsulated plug without cleaning.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs for the existing elements of the encapsulated plug.
        """
        existingElementPlugs = []

        for logicalIndex in self._plug.getExistingArrayAttributeIndices():
            elementPlug = self._plug.elementByLogicalIndex(logicalIndex)
            existingElementPlugs.append(elementPlug)

        return existingElementPlugs

    def getElementPlugs(self):
        """Return the connected element plugs for the encapsulated plug after cleaning.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs for the connected elements of the encapsulated plug after cleaning.
        """
        _, destPlugIDs = self.clean()
        return [destPlugID.plug for destPlugID in destPlugIDs]

    # --- Public : Modify --------------------------------------------------------------

    @DECORATOR.undoOnError(StandardError)
    def clean(self):
        """Removes sparcity from the encapsulated plug by removing any disconnected elements.
        Removes any duplicate input connections from the tail end of the array if :attr:`allowMultiples` is :data:`False`.

        Note:
            This method acts as the basis for all query and modify operations provided by the :class:`PackArray` interface.

        Returns:
            (:class:`list` [:class:`msTools.core.maya.om_utils.MPlugId`], :class:`list` [:class:`msTools.core.maya.om_utils.MPlugId`]): A two-element :class:`tuple`.

            #. A sequence of dependency node plug encapsulations representing the input plugs for elements of the encapsulated plug.
            #. A sequence of dependency node plug encapsulations representing the element plugs of the encapsulated plug.
        """
        log.debug("{!r}: Cleaning".format(self))

        existingElementPlugs = self.getExistingElementPlugs()
        cleanSourcePlugIDs = []
        cleanDestPlugIDs = []

        for existingElementPlug in existingElementPlugs:
            logicalIndex = existingElementPlug.logicalIndex()

            if existingElementPlug.isDestination:
                sourcePlugID = OM.MPlugId(existingElementPlug.sourceWithConversion())

                if not self.allowMultiples and sourcePlugID in cleanSourcePlugIDs:
                    log.info("{!r}: Contains duplicate connection, `allowMultiples=False`, removing index: {}".format(self, logicalIndex))
                    self._remove(logicalIndex)
                else:
                    nextAvailableLogicalIndex = self._getUnconnectedLogicalIndex()
                    if nextAvailableLogicalIndex < logicalIndex:
                        self._reconnect(fromIndex=logicalIndex, toIndex=nextAvailableLogicalIndex)
                        logicalIndex = nextAvailableLogicalIndex

                    # Cache clean plugs so we can check duplicate connections for existing elements
                    elementPlug = self._plug.elementByLogicalIndex(logicalIndex)
                    cleanDestPlugIDs.append(OM.MPlugId(elementPlug))
                    cleanSourcePlugIDs.append(sourcePlugID)
            else:
                log.info("{!r}: Contains disconnected element, removing index: {}".format(self, logicalIndex))
                self._remove(logicalIndex)

        return cleanSourcePlugIDs, cleanDestPlugIDs

    @DECORATOR.undoOnError(StandardError)
    def append(self, inputPlug):
        """Connect an input plug to the next available element of the encapsulated plug after cleaning.

        Args:
            inputPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding element plug. See :func:`connect`.
        """
        inputPlugID = OM.MPlugId(inputPlug)
        sourcePlugIDs, _ = self.clean()

        if not self._isInputAllowed(inputPlugID, sourcePlugIDs):
            return

        elementPlug = self._plug.elementByLogicalIndex(len(sourcePlugIDs))
        connect(inputPlug, elementPlug)

    @DECORATOR.undoOnError(StandardError)
    def extend(self, inputPlugs):
        """Connect input plugs to the next available elements of the encapsulated plug after cleaning.

        Args:
            inputPlugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding element plug. See :func:`connect`.
        """
        inputPlugIDs = [OM.MPlugId(inputPlug) for inputPlug in inputPlugs]
        sourcePlugIDs, _ = self.clean()
        elementCount = len(sourcePlugIDs)
        inputCount = len(inputPlugs)

        for inputIndex in xrange(inputCount):
            if not self._isInputAllowed(inputPlugIDs[inputIndex], sourcePlugIDs) or not self._isInputAllowed(inputPlugIDs[inputIndex], inputPlugIDs[:inputIndex]):
                continue

            elementPlug = self._plug.elementByLogicalIndex(elementCount)
            inputPlug = inputPlugs[inputIndex]
            connect(inputPlug, elementPlug)

            elementCount += 1

    @DECORATOR.undoOnError(StandardError)
    def insert(self, index, inputPlug):
        """Connect an input plug to an element of the encapsulated plug corrresponding to a specific index after cleaning.

        Note:
            Any packed element with a logical index greater or equal to the insertion index will be reconnected at an incremented index.

        Args:
            index (:class:`int`): The index at which to insert the ``inputPlug`` connection after cleaning the encapsulated plug.
            inputPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding element plug. See :func:`connect`.
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
        """
        inputPlugID = OM.MPlugId(inputPlug)
        sourcePlugIDs, _ = self.clean()
        index = self._convertToPositiveIndex(index, len(sourcePlugIDs))
        elementCount = len(sourcePlugIDs)

        if not self._isInputAllowed(inputPlugID, sourcePlugIDs):
            return

        # Increment the index of any existing connections with an index equal to or greater than the one given
        for indexToIncrement in xrange(elementCount - 1, index - 1, -1):
            self._reconnect(fromIndex=indexToIncrement, toIndex=indexToIncrement + 1)

        # Make the insertion
        elementPlug = self._plug.elementByLogicalIndex(index)
        connect(inputPlug, elementPlug)

    @DECORATOR.undoOnError(StandardError)
    def remove(self, index):
        """Disconnect an input plug from an element of the encapsulated plug at a specific index after cleaning.

        Note:
            Any packed element with a logical index greater than the removal index will be reconnected at a decremented index.

        Args:
            index (:class:`int`): The index at which to remove an input connection after cleaning the encapsulated plug.

        Raises:
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
        """
        elementCount = len(self)
        index = self._convertToPositiveIndex(index, elementCount)

        self._remove(index)

        # Decrement the index of any existing connections with an index greater than the one given
        for indexToDecrement in xrange(index + 1, elementCount):
            self._reconnect(fromIndex=indexToDecrement, toIndex=indexToDecrement - 1)

    @DECORATOR.undoOnError(StandardError)
    def clear(self):
        """Removes all input connections to elements of the encapsulated plug"""
        for logicalIndex in self._plug.getExistingArrayAttributeIndices():
            self._remove(logicalIndex)

    @DECORATOR.undoOnError(StandardError)
    def copy(self, inputPlugs):
        """Replace all input connections to elements of the encapsulated plug with a new sequence.

        Args:
            inputPlugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding element plug. See :func:`connect`.
        """
        inputPlugIDs = [OM.MPlugId(inputPlug) for inputPlug in inputPlugs]
        inputCount = len(inputPlugs)
        elementCount = 0

        self.clear()

        for inputIndex in xrange(inputCount):
            if not self._isInputAllowed(inputPlugIDs[inputIndex], inputPlugIDs[:inputIndex]):
                continue

            # Connect valid inputs
            elementPlug = self._plug.elementByLogicalIndex(elementCount)
            inputPlug = inputPlugs[inputIndex]
            connect(inputPlug, elementPlug)

            elementCount += 1

    @DECORATOR.undoOnError(StandardError)
    def replace(self, index, inputPlug):
        """Replace an input connection to an element of the encapsulated plug corrresponding to a specific index after cleaning.

        Args:
            index (:class:`int`): The index at which to replace the existing connection after cleaning the encapsulated plug.
            inputPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding element plug. See :func:`connect`.
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
        """
        inputPlugID = OM.MPlugId(inputPlug)
        sourcePlugIDs, _ = self.clean()
        index = self._convertToPositiveIndex(index, len(sourcePlugIDs))

        # Check if the input is already connected
        if not self._isInputAllowed(inputPlugID, sourcePlugIDs):
            return

        self._remove(index)

        elementPlug = self._plug.elementByLogicalIndex(index)
        connect(inputPlug, elementPlug)

    # --- Private : Utilities --------------------------------------------------------------

    def _convertToPositiveIndex(self, index, arrayLength):
        """Handle negative indices for inserting into the array"""
        result = index
        if result < 0:
            result = index + arrayLength
        if result < 0 or result >= arrayLength:
            raise IndexError("{!r}: Index {} is out of range".format(self, index))
        return result

    def _getUnconnectedLogicalIndex(self):
        """Simplified versions of `getUnconnectedLogicalIndex`, returns the logical index of the first unconnected element plug for the encapsulated plug."""
        availableIndex = getUnusedLogicalIndex(self._plug)

        for i in xrange(availableIndex):
            elementPlug = self._plug.elementByLogicalIndex(i)
            if elementPlug.isDestination:
                continue
            return i

        return availableIndex

    def _isInputAllowed(self, inputPlugID, sourcePlugIDs):
        """Returns whether a plug is allowed to be connected as an input to the encapsulated plug."""
        if not self._allowMultiples and inputPlugID in sourcePlugIDs:
            log.info("{!r}: Input plug is already connected to array, set property `allowMultiples=True` if required".format(self))
            return False

        return True

    # --- Private : Modify --------------------------------------------------------------

    def _remove(self, index):
        """Removes an unclean element corresponding to a non-negative index."""
        dgMod = OM.MDGModifier()
        elementPlug = self._plug.elementByLogicalIndex(index)
        dgMod.removeMultiInstance(elementPlug, True)
        dgMod.doIt()

    def _reconnect(self, fromIndex, toIndex):
        """Moves an existing input connection from one unclean element to another unclean element, removing the previous element."""
        # Move connections
        sourcePlug = self._plug.elementByLogicalIndex(fromIndex).sourceWithConversion()
        elementPlug = self._plug.elementByLogicalIndex(toIndex)
        connect(sourcePlug, elementPlug)

        # Remove old index
        self._remove(fromIndex)


class PackCompoundArray(PY_META.AbstractAccessWrapper):
    """An interface for managing input connections to the elemental children of a dependency node compound array plug.

    **Inputs:**

        When making a connection via the interface, each input must be given as a sequence containing :class:`OpenMaya.MPlug` encapsulations of dependency node plugs.
        Each sequence is referred to as an input group for which each element will be connected as an input to a corresponding child of the next available element plug.
        The group of child plugs to which an input group connects is referred to as a child group.

        - Each input group must contain an equivalent number of values as there are children such that each input can be paired to a single child group plug.
        - Each input group can contain :data:`None` values such that the corresponding child group plug will not receive a connection.
        - Each input group must contain at least one non-:data:`None` value such that at least one child group plug receives a connection.

    **Cleaning:**

        The interface enforces a cleaning routine that is run as a preliminary step before querying or modifying existing connections.
        Cleaning of the array is implemented as :meth:`clean`.

    **Validation:**

        The interface provides the option to track the functional state of the internal :class:`OpenMaya.MPlug`.
        When tracking is enabled, an :exc:`msTools.core.maya.exceptions.MayaObjectError` will be raised when attempting to access the interface of an invalid encapsulation.
        The :attr:`isValid` property and :meth:`__repr__` method will remain accessible regardless of whether the functional state is invalid.

    Note:
        Instances of this class maintain a unique reference to their internal :class:`OpenMaya.MPlug` to ensure the referenced dependency node plug does not change.
        This enables the logical indices of the :class:`OpenMaya.MPlug` to be cached for efficient comparison.
    """

    __metaclass__ = PY_META.MetaAccessWrapperFactory(
        wrapFunctions=True,
        wrapPropertyGetters=True,
        wrapPropertySetters=True,
        wrapPropertyDeleters=True,
        wrapExclusions=("__init__", "__repr__", "isValid")
    )

    # --- Abstract --------------------------------------------------------------

    def _preAccess(self):
        """Abstract override which checks the internal `MPlug` is functionally valid before providing access to an instance method, otherwise raises a `MayaObjectError`."""
        if not self._stateTracking:
            return

        if not self.isValid:
            raise EXC.MayaObjectError("{!r}: Plug is no longer valid, attribute or node may have been removed".format(self))

    def _postAccess(self):
        """Abstract override - null op."""
        pass

    # --- Special --------------------------------------------------------------

    def __init__(self, compoundArrayPlug, inputPlugGroups=None, allowMultiples=False, stateTracking=True):
        """Initialize an encapsulation for a dependency node compound array plug.

        Args:
            compoundArrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node compound array plug.
            inputPlugGroups (iterable [iterable [:class:`OpenMaya.MPlug`]], optional): Sequences containing encapsulations of dependency node plugs.
                Each group of inputs is connected to the children of the next available ``compoundArrayPlug`` element. Defaults to :data:`None`.
            allowMultiples (:class:`bool`, optional): Whether multiple ``compoundArrayPlug`` child groups can be connected to a single group of input plugs.
                Defaults to :data:`False` - Any existing duplicates will be removed from the tail end of the array.
            stateTracking (:class:`bool`, optional): Whether to track the functional state of the ``compoundArrayPlug``.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundArrayPlug`` does not reference a dependency node compound array plug.
        """
        log.debug("PackArray.__init__(compoundArrayPlug={!r}, inputPlugs={}, allowMultiples={}, stateTracking={})".format(
            compoundArrayPlug, inputPlugGroups, allowMultiples, stateTracking))

        if not compoundArrayPlug.isCompound or not compoundArrayPlug.isArray:
            raise EXC.MayaTypeError("{}: Plug is not a compound array".format(NAME.getPlugFullName(compoundArrayPlug)))

        attr = compoundArrayPlug.attribute()
        node = compoundArrayPlug.node()

        # Use the superclass __setattr__ since the override will try to validate the array before the necessary attributes have been set
        super(PackCompoundArray, self).__setattr__("_plug", om2.MPlug(compoundArrayPlug))
        super(PackCompoundArray, self).__setattr__("_plugId", OM.MPlugId(compoundArrayPlug))
        super(PackCompoundArray, self).__setattr__("_attr", attr)
        super(PackCompoundArray, self).__setattr__("_attrFn", om2.MFnAttribute(attr))
        super(PackCompoundArray, self).__setattr__("_node", node)
        super(PackCompoundArray, self).__setattr__("_nodeHandle", om2.MObjectHandle(node))
        super(PackCompoundArray, self).__setattr__("_nodeFn", om2.MFnDependencyNode(node))
        super(PackCompoundArray, self).__setattr__("_partialName", NAME.getPlugPartialName(compoundArrayPlug))
        super(PackCompoundArray, self).__setattr__("_allowMultiples", allowMultiples)
        super(PackCompoundArray, self).__setattr__("_stateTracking", stateTracking)

        # Append additional input plugs to the array or clean the connections
        if inputPlugGroups:
            self.extend(inputPlugGroups)
        else:
            self.clean()

    def __repr__(self):
        """``x.__repr__()`` <==> ``repr(x)``.

        Note:
            This method is not subject to :attr:`stateTracking` and is therefore accessible even if the internal :class:`OpenMaya.MPlug` is functionally invalid.
            In this case cached data is used.

        Returns:
            :class:`str`: A string representation of the dependency node plug encapsulation.
        """
        isValid = self.isValid
        partialName = self.partialName if isValid else self._partialName
        state = "valid" if isValid else "invalid"
        return "PackCompoundArray('{}') <{}>".format(partialName, state)

    def __eq__(self, other):
        """``x.__eq__(y)`` <==> ``x == y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: If ``other`` has an equivalent type, return whether its contents (dependency node plug) are equivalent.
            Otherwise swap the operands and return the result, unless the operands have already been swapped in which case the result is :data:`False`.
        """
        if type(self) is type(other):
            return self._plugId == other.plugId

        return NotImplemented

    def __ne__(self, other):
        """``x.__ne__(y)`` <==> ``x != y``.

        Args:
            other (any): Any object.

        Returns:
            :class:`bool`: The negation of :meth:`__eq__`.
        """
        return not self == other

    def __len__(self):
        """``x.__len__()`` <==> ``len(x)``.

        Returns:
            :class:`int`: The number of destination connections to the encapsulated plug.
        """
        return len(self.clean()[0])

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
    def isConnected(self):
        """:class:`bool`: :data:`True` if at least one element of the encapsulated plug has a destination connection, otherwise :data:`False`.

        :access: R
        """
        return bool(len(self))

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
    def allowMultiples(self):
        """:class:`bool`: Whether multiple elements of the encapsulated plug can be connected to a single input plug.

        :access: RW
        """
        return self._allowMultiples

    @allowMultiples.setter
    def allowMultiples(self, state):
        self._allowMultiples = state
        if not state:
            self.clean()

    @property
    def stateTracking(self):
        """:class:`bool`: Whether to track the state of the internal :class:`OpenMaya.MPlug` in order to restrict access to the public interface if invalid.

        Restriction involves raising a :exc:`msTools.core.maya.exceptions.MayaObjectError` upon attempting to access a bound instance attribute from the public interface.
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
        """:class:`str`: The partial name of the encapsulated plug with format ``'<node>.<plug>'``.

        - ``<node>`` will be a partial node name qualified by a path and namespace where applicable or necessary.
          It is guaranteed to uniquely identify the plug's node with the minimum amount of information necessary (partial path of a DAG node).
        - ``<plug>`` is guaranteed to uniquely identify the plug with the minimum amount of information necessary (short attribute path, short attribute names).

        :access: R
        """
        self._partialName = NAME.getPlugPartialName(self.plug)
        return self._partialName

    # --- Public : Query --------------------------------------------------------------

    def hasInputNodeGroup(self, nodeGroup):
        """Check if a group of dependency nodes are connected sequentially as inputs to a child plug group of the encapsulated plug.

        Args:
            nodeGroup (iterable [:class:`OpenMaya.MObject`, :data:`None`]): Sequence of dependency node wrappers.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If any of the ``nodeGroup`` wrappers do not reference dependency nodes.

        Returns:
            :class:`bool`: :data:`True` if the ``nodeGroup`` is representative of a sequence of input connections to a child plug group of the encapsulated plug, otherwise :data:`False`.
        """
        for node in nodeGroup:
            if node:
                OM.validateNodeType(node)

        return list(nodeGroup) in self.getInputNodeGroups()

    def hasInputPlugGroup(self, plugGroup):
        """Check if a group of dependency node plugs are connected sequentially as inputs to a child plug group of the encapsulated plug.

        Args:
            plugGroup (iterable [:class:`OpenMaya.MPlug`, :data:`None`]): Sequence of dependency node plug encapsulations.

        Returns:
            :class:`bool`: :data:`True` if the ``plugGroup`` is representative of a sequence of input connections to a child plug group of the encapsulated plug, otherwise :data:`False`.
        """
        plugIdGroup = [OM.MPlugId(plug) for plug in plugGroup]
        sourcePlugIDGroups, _ = self.clean()
        return plugIdGroup in sourcePlugIDGroups

    def getInputNodeGroups(self):
        """Return node sequences representing the input group connections to each child group of the encapsulated plug.

        Returns:
            :class:`list` [:class:`list` [:class:`OpenMaya.MObject`, :data:`None`]]: Sequences of dependency node wrappers representing the input group connections to each child group of the encapsulated plug.
        """
        sourcePlugIDGroups, _ = self.clean()
        return [[sourcePlugID.plug.node() if sourcePlugID else None for sourcePlugID in sourcePlugIDGroup] for sourcePlugIDGroup in sourcePlugIDGroups]

    def getInputPlugGroups(self):
        """Return plug sequences representing the input group connections to each child group of the encapsulated plug.

        Returns:
            :class:`list` [:class:`list` [:class:`OpenMaya.MPlug`, :data:`None`]]: Sequences of dependency node plug encapsulations representing the input group connections to each child group of the encapsulated plug.
        """
        sourcePlugIDGroups, _ = self.clean()
        return [[sourcePlugID.plug if sourcePlugID else None for sourcePlugID in sourcePlugIDGroup] for sourcePlugIDGroup in sourcePlugIDGroups]

    def getExistingElementPlugs(self):
        """Return existing element plugs for the encapsulated plug without cleaning.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs for the existing elements of the encapsulated plug.
        """
        existingElementPlugs = []

        for logicalIndex in self._plug.getExistingArrayAttributeIndices():
            elementPlug = self._plug.elementByLogicalIndex(logicalIndex)
            existingElementPlugs.append(elementPlug)

        return existingElementPlugs

    def getElementPlugs(self):
        """Return the connected element plugs for the encapsulated plug after cleaning.

        Returns:
            :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs for the connected elements of the encapsulated plug after cleaning.
        """
        _, destPlugIDGroups = self.clean()
        return [destPlugIDGroup[0].plug.parent() for destPlugIDGroup in destPlugIDGroups]

    def getExistingChildPlugGroups(self):
        """Return plug sequences representing the existing child groups of the encapsulated plug without cleaning.

        Returns:
            :class:`list` [:class:`list` [:class:`OpenMaya.MPlug`]]: Sequences of dependency node plug encapsulations representing the child group plugs for each existing element of the encapsulated plug.
        """
        existingElementPlugs = self.getExistingElementPlugs()
        childCount = self._plug.numChildren()
        return [[existingElementPlug.child(childIndex) for childIndex in xrange(childCount)] for existingElementPlug in existingElementPlugs]

    def getChildPlugGroups(self):
        """Return plug sequences representing the child groups of the encapsulated plug after cleaning.

        Returns:
            :class:`list` [:class:`list` [:class:`OpenMaya.MPlug`]]: Sequences of dependency node plug encapsulations representing the child group plugs for each element of the encapsulated plug after cleaning.
        """
        elementPlugs = self.getElementPlugs()
        childCount = self._plug.numChildren()
        return [[elementPlug.child(childIndex) for childIndex in xrange(childCount)] for elementPlug in elementPlugs]

    # --- Public : Modify --------------------------------------------------------------

    @DECORATOR.undoOnError(StandardError)
    def clean(self):
        """Removes sparcity from the encapsulated plug by removing any elements that contain a disconnected child group.
        Removes any duplicate input group connections from the tail end of the array if :attr:`allowMultiples` is :data:`False`.

        Note:
            This method acts as the basis for all query and modify operations provided by the :class:`PackCompoundArray` interface.

        Returns:
            (:class:`list` [:class:`list` [:class:`msTools.core.maya.om_utils.MPlugId`, :data:`None`]], :class:`list` [:class:`list` [:class:`msTools.core.maya.om_utils.MPlugId`]]): A two-element :class:`tuple`.

            #. Sequences of dependency node plug encapsulations representing the input group plugs for each element of the encapsulated plug.
            #. Sequences of dependency node plug encapsulations representing the child group plugs for each element of the encapsulated plug.
        """
        log.debug("{!r}: Cleaning".format(self))

        childCount = self._plug.numChildren()
        existingElementPlugs = self.getExistingElementPlugs()
        existingChildPlugGroups = [[existingElementPlug.child(childIndex) for childIndex in xrange(childCount)] for existingElementPlug in existingElementPlugs]
        sourcePlugIDGroups = []
        destPlugIDGroups = []

        for existingElementPlug, existingChildPlugGroup in zip(existingElementPlugs, existingChildPlugGroups):
            logicalIndex = existingElementPlug.logicalIndex()
            sourcePlugIDGroup = [OM.MPlugId(existingChildPlug.sourceWithConversion()) if existingChildPlug.isDestination else None for existingChildPlug in existingChildPlugGroup]

            if any(sourcePlugIDGroup):
                if not self.allowMultiples and sourcePlugIDGroup in sourcePlugIDGroups:
                    log.info("{!r}: Contains duplicate input group connections, `allowMultiples=False`, removing index : {}".format(self, logicalIndex))
                    self._remove(logicalIndex)
                else:
                    nextAvailableLogicalIndex = self._getUnconnectedLogicalIndex()
                    if nextAvailableLogicalIndex < logicalIndex:
                        self._reconnect(fromIndex=logicalIndex, toIndex=nextAvailableLogicalIndex)
                        logicalIndex = nextAvailableLogicalIndex

                    # Cache clean plugs so we can check duplicate connections for existing elements
                    destPlugIDGroup = [OM.MPlugId(self._plug.elementByLogicalIndex(logicalIndex).child(childIndex)) for childIndex in xrange(childCount)]
                    destPlugIDGroups.append(destPlugIDGroup)
                    sourcePlugIDGroups.append(sourcePlugIDGroup)
            else:
                log.info("{!r}: Contains disconnected child plug group, removing index : {}".format(self, logicalIndex))
                self._remove(logicalIndex)

        return sourcePlugIDGroups, destPlugIDGroups

    @DECORATOR.undoOnError(StandardError)
    def append(self, inputPlugGroup):
        """Connect a group of input plugs to the next available group of child plugs for an element of the encapsulated plug after cleaning.

        Args:
            inputPlugGroup (iterable [:class:`OpenMaya.MPlug`]): Sequence of dependency node plug encapsulations.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding child plug. See :func:`connect`.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains all :data:`None` values.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains the wrong number of inputs.
        """
        self._validateInput(inputPlugGroup)

        inputPlugIDGroup = [OM.MPlugId(inputPlug) if inputPlug else None for inputPlug in inputPlugGroup]
        sourcePlugIDGroups, _ = self.clean()
        elementCount = len(sourcePlugIDGroups)

        if not self._isInputAllowed(inputPlugIDGroup, sourcePlugIDGroups):
            return

        self._connect(elementCount, inputPlugGroup)

    @DECORATOR.undoOnError(StandardError)
    def extend(self, inputPlugGroups):
        """Connect groups of input plugs to the next available groups of child plugs for elements of the encapsulated plug after cleaning.

        Args:
            inputPlugGroups (iterable [iterable [:class:`OpenMaya.MPlug`]]): Sequences of dependency node plug encapsulations.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding child plug. See :func:`connect`.
            :exc:`~exceptions.ValueError`: If any of the ``inputPlugGroups`` contain all :data:`None` values.
            :exc:`~exceptions.ValueError`: If any of the ``inputPlugGroups`` contain the wrong number of inputs.
        """
        for inputPlugGroup in inputPlugGroups:
            self._validateInput(inputPlugGroup)

        inputPlugIDGroups = [[OM.MPlugId(inputPlug) if inputPlug else None for inputPlug in inputPlugGroup] for inputPlugGroup in inputPlugGroups]
        sourcePlugIDGroups, _ = self.clean()
        elementCount = len(sourcePlugIDGroups)
        inputGroupCount = len(inputPlugGroups)

        for inputGroupIndex in xrange(inputGroupCount):
            inputPlugGroup = inputPlugGroups[inputGroupIndex]
            inputPlugIDGroup = inputPlugIDGroups[inputGroupIndex]

            if not self._isInputAllowed(inputPlugIDGroup, sourcePlugIDGroups) or not self._isInputAllowed(inputPlugIDGroup, inputPlugIDGroups[:inputGroupIndex]):
                continue

            self._connect(elementCount, inputPlugGroup)
            elementCount += 1

    @DECORATOR.undoOnError(StandardError)
    def insert(self, index, inputPlugGroup):
        """Connect a group of input plugs to a group of child plugs for an element of the encapsulated plug corrresponding to a specific index after cleaning.

        Note:
            Any packed element with a logical index greater or equal to the insertion index will be reconnected at an incremented index.

        Args:
            index (:class:`int`): The index at which to insert the ``inputPlugGroup`` connections after cleaning the encapsulated plug.
            inputPlugGroup (iterable [:class:`OpenMaya.MPlug`]): Sequence of dependency node plug encapsulations.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding child plug. See :func:`connect`.
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains all :data:`None` values.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains the wrong number of inputs.
        """
        self._validateInput(inputPlugGroup)

        inputPlugIDGroup = [OM.MPlugId(inputPlug) if inputPlug else None for inputPlug in inputPlugGroup]
        sourcePlugIDGroups, _ = self.clean()
        elementCount = len(sourcePlugIDGroups)
        index = self._convertToPositiveIndex(index, elementCount)

        if not self._isInputAllowed(inputPlugIDGroup, sourcePlugIDGroups):
            return

        # Increment the index of any existing connections with an index equal to or greater than the one given
        for indexToIncrement in xrange(elementCount - 1, index - 1, -1):
            self._reconnect(fromIndex=indexToIncrement, toIndex=indexToIncrement + 1)

        # Make the insertion
        self._connect(index, inputPlugGroup)

    @DECORATOR.undoOnError(StandardError)
    def remove(self, index):
        """Disconnect a group of input plugs from a group of child plugs for an element of the encapsulated plug at a specific index after cleaning.

        Note:
            Any packed element with a logical index greater than the removal index will be reconnected at a decremented index.

        Args:
            index (:class:`int`): The index at which to remove a group of input connections after cleaning the encapsulated plug.

        Raises:
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
        """
        # Implicit cleaning is invoked here
        elementCount = len(self)
        index = self._convertToPositiveIndex(index, elementCount)

        self._remove(index)

        # Decrement the index of any existing connections with an index greater than the one given
        for indexToDecrement in xrange(index + 1, elementCount):
            self._reconnect(fromIndex=indexToDecrement, toIndex=indexToDecrement - 1)

    @DECORATOR.undoOnError(StandardError)
    def clear(self):
        """Removes all input connections to elements of the encapsulated plug"""
        for logicalIndex in self._plug.getExistingArrayAttributeIndices():
            self._remove(logicalIndex)

    @DECORATOR.undoOnError(StandardError)
    def copy(self, inputPlugGroups):
        """Replace all input group connections to child groups of the encapsulated plug with a new sequence of input groups.

        Args:
            inputPlugGroups (iterable [iterable [:class:`OpenMaya.MPlug`]]): Sequences of dependency node plug encapsulations.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding child plug. See :func:`connect`.
            :exc:`~exceptions.ValueError`: If any of the ``inputPlugGroups`` contain all :data:`None` values.
            :exc:`~exceptions.ValueError`: If any of the ``inputPlugGroups`` contain the wrong number of inputs.
        """
        for inputPlugGroup in inputPlugGroups:
            self._validateInput(inputPlugGroup)

        inputPlugIDGroups = [[OM.MPlugId(inputPlug) if inputPlug else None for inputPlug in inputPlugGroup] for inputPlugGroup in inputPlugGroups]
        inputGroupCount = len(inputPlugGroups)

        self.clear()
        elementCount = 0

        for inputGroupIndex in xrange(inputGroupCount):
            inputPlugGroup = inputPlugGroups[inputGroupIndex]
            inputPlugIDGroup = inputPlugIDGroups[inputGroupIndex]

            if not self._isInputAllowed(inputPlugIDGroup, inputPlugIDGroups[:inputGroupIndex]):
                continue

            # Connect valid inputs
            self._connect(elementCount, inputPlugGroup)
            elementCount += 1

    @DECORATOR.undoOnError(StandardError)
    def replace(self, index, inputPlugGroup):
        """Replace the input group connections for an element of the encapsulated plug corrresponding to a specific index after cleaning.

        Args:
            index (:class:`int`): The index at which to replace the existing connections after cleaning the encapsulated plug.
            inputPlugGroup (iterable [:class:`OpenMaya.MPlug`]): Sequence of dependency node plug encapsulations.

        Raises:
            :exc:`~exceptions.RuntimeError`: If there are any connection issues between an input and a corresponding child plug. See :func:`connect`.
            :exc:`~exceptions.IndexError`: If ``index`` is out of range after the encapsulated plug has been cleaned.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains all :data:`None` values.
            :exc:`~exceptions.ValueError`: If ``inputPlugGroup`` contains the wrong number of inputs.
        """
        self._validateInput(inputPlugGroup)

        inputPlugIDGroup = [OM.MPlugId(inputPlug) if inputPlug else None for inputPlug in inputPlugGroup]
        sourcePlugIDGroups, _ = self.clean()
        elementCount = len(sourcePlugIDGroups)
        index = self._convertToPositiveIndex(index, elementCount)

        # Check if the input is already connected
        if not self._isInputAllowed(inputPlugIDGroup, sourcePlugIDGroups):
            return

        self._remove(index)
        self._connect(index, inputPlugGroup)

    # --- Private : Utilities --------------------------------------------------------------

    def _validateInput(self, inputPlugGroup):
        """Ensures an input group has at least one plug to connect and has a value corresponding to each child plug."""
        inputCount = len(inputPlugGroup)
        childCount = self._plug.numChildren()

        if not any(inputPlugGroup):
            raise ValueError("{!r}: Input plug group is empty".format(self))

        if inputCount != childCount:
            raise ValueError("{!r}: Input plug group has the wrong number of inputs".format(self))

    def _convertToPositiveIndex(self, index, arrayLength):
        """Handle negative indices for inserting into the array"""
        result = index
        if result < 0:
            result = index + arrayLength
        if result < 0 or result >= arrayLength:
            raise IndexError("{!r}: Index {} is out of range".format(self, index))
        return result

    def _getUnconnectedLogicalIndex(self):
        """Specialised version of `getUnconnectedLogicalIndex`, returns the logical index of the first element with no connected children for the encapsulated plug."""
        childCount = self._plug.numChildren()
        availableIndex = getUnusedLogicalIndex(self._plug)

        for i in xrange(availableIndex):
            elementPlug = self._plug.elementByLogicalIndex(i)
            if any([elementPlug.child(childIndex).isDestination for childIndex in xrange(childCount)]):
                continue

            return i

        return availableIndex

    def _isInputAllowed(self, inputPlugIDGroup, sourcePlugIDGroups):
        """Returns whether an input group is allowed to be connected as an input to the encapsulated plug."""
        if not self._allowMultiples and inputPlugIDGroup in sourcePlugIDGroups:
            log.info("{!r}: Input plug group is already connected to array, set property `allowMultiples=True` if required".format(self))
            return False

        return True

    # --- Private : Modify --------------------------------------------------------------

    def _connect(self, index, inputPlugGroup):
        """Connects an input plug group to a child plug group for a specific element of the encapsulated plug. Assumes the child plug group is disconnected."""
        childCount = self._plug.numChildren()
        elementPlug = self._plug.elementByLogicalIndex(index)

        for childIndex in xrange(childCount):
            inputPlug = inputPlugGroup[childIndex]
            if inputPlug is not None:
                childPlug = elementPlug.child(childIndex)
                connect(inputPlug, childPlug)

    def _remove(self, index):
        """Removes an unclean element corresponding to a non-negative index."""
        dgMod = OM.MDGModifier()
        elementPlug = self._plug.elementByLogicalIndex(index)
        dgMod.removeMultiInstance(elementPlug, True)
        dgMod.doIt()

    def _reconnect(self, fromIndex, toIndex):
        """Moves an existing input connection from one unclean element to another unclean element, removing the previous element."""
        # Move connections
        childCount = self._plug.numChildren()
        elementPlug = self._plug.elementByLogicalIndex(fromIndex)
        childPlugGroup = [elementPlug.child(childIndex) for childIndex in xrange(childCount)]
        inputPlugGroup = [childPlug.sourceWithConversion() if childPlug.isDestination else None for childPlug in childPlugGroup]
        self._connect(toIndex, inputPlugGroup)

        # Remove old index
        self._remove(fromIndex)


# --------------------------------------------------------------
# --- Classes : Modifiers ---
# --------------------------------------------------------------

class _PropertyModifier(OM.Modifier):
    """Modify properties of a dependency node plug via an :class:`OpenMaya.MPlug` encapsulation.
    Modifications will be placed on the Maya undo queue.
    """

    def __init__(self, plug, **properties):
        if properties.get("isKeyable") and properties.get("isChannelBox"):
            log.info("Cannot set `isKeyable=True` and `isChannelBox=True`. Ignoring `isChannelBox`, only one property can be enabled")
            del properties["isChannelBox"]

        self._plug = plug
        self._doItValues = properties
        self._undoItValues = {}

        super(_PropertyModifier, self).__init__()

    def doIt(self):
        for prop, newValue in self._doItValues.iteritems():
            # Either isKeyable or isChannelBox can be True, not both
            # Must record both previous values before setting either since each affects the other
            if prop == "isChannelBox" or prop == "isKeyable":
                if self._undoItValues.get("isKeyable") is None:
                    self._undoItValues["isKeyable"] = getattr(self._plug, "isKeyable")
                    self._undoItValues["isChannelBox"] = getattr(self._plug, "isChannelBox")
            else:
                self._undoItValues[prop] = getattr(self._plug, prop)

            setattr(self._plug, prop, newValue)

    def undoIt(self):
        for prop, oldValue in self._undoItValues.iteritems():
            setattr(self._plug, prop, oldValue)


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isLocked(plug, checkInternalState=False):
    """Return whether a dependency node plug is internally or globally locked.

    Note:
        The global lock state of a plug is influenced by the lock state of each ancestor.
        A plug can be globally locked whilst also being internally unlocked. See :ref:`note-5 <note_5>`.

        This method is designed as an alternative to :attr:`OpenMaya.MPlug.isLocked` which is not always reliable. See :ref:`warning-1 <warning_1>`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        checkInternalState (:class:`bool`, optional): Whether to check if ``plug`` is internally locked. Defaults to :data:`False`.

    Returns:
        :class:`bool`: The lock state of ``plug``.
    """
    if not checkInternalState:
        if plug.isLocked:
            return True

        # Check the ancestor hierarchy (the lock state of an unconnected descendant does not automatically update when an ancestor is locked)
        try:
            for ancestor in iterAncestors(plug):
                if ancestor.isLocked:
                    return True
        except EXC.MayaTypeError:
            return False

        return False

    isInternallyLocked = False
    unlockedPlugHierarchy = unlockGlobal(plug)
    unlockedPlugHierarchySet = OM.MPlugSet(unlockedPlugHierarchy)
    if plug in unlockedPlugHierarchySet:
        isInternallyLocked = True

    for unlockedPlug in unlockedPlugHierarchy:
        setProperties(unlockedPlug, isLocked=True)

    return isInternallyLocked


# --------------------------------------------------------------
# --- Connect ---
# --------------------------------------------------------------

def connect(sourcePlug, destPlug, forceConnected=False, forceLocked=False):
    """Connect two dependency node plugs.

    Args:
        sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug used as the source of the connection.
        destPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug used as the destination of the connection.
        forceConnected (:class:`bool`, optional): Whether to force the connection if ``destPlug`` is already connected. Defaults to :data:`False`.
        forceLocked (:class:`bool`, optional): Whether to force the connection if ``destPlug`` is locked. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If the data types of the plug attributes are incompatible.
        :exc:`~exceptions.RuntimeError`: If either plug references an unconnectable attribute.
        :exc:`~exceptions.RuntimeError`: If ``sourcePlug`` references an unreadable attribute.
        :exc:`~exceptions.RuntimeError`: If ``destPlug`` references an unwritable attribute.
        :exc:`~exceptions.RuntimeError`: If ``destPlug`` is globally locked and ``forceLocked`` is :data:`False`.
        :exc:`~exceptions.RuntimeError`: If ``destPlug`` is connected and ``forceConnected`` is :data:`False`.
    """
    attrFnSource = om2.MFnAttribute(sourcePlug.attribute())
    attrFnDest = om2.MFnAttribute(destPlug.attribute())

    # Implement a descriptive error for incompatible types (kFailure is default)
    if not attrFnDest.acceptsAttribute(attrFnSource):
        raise EXC.MayaTypeError("Connection not made: '{}' -> '{}'.  Attributes do not have compatible types".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))

    # Implement descriptive errors for unreadable source or unwritable destination (kFailure is default). Unconnectable produces a descriptive error.
    if not om2.MFnAttribute(sourcePlug.attribute()).readable:
        raise RuntimeError("Connection not made: '{}' -> '{}'.  Source is not readable".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))
    if not om2.MFnAttribute(destPlug.attribute()).writable:
        raise RuntimeError("Connection not made: '{}' -> '{}'.  Destination is not writable".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))

    # Checks the ancestor hierarchy (the lock state of an unconnected descendant does not automatically update when an ancestor is locked)
    isLocked_ = isLocked(destPlug)
    if isLocked_ and not forceLocked:
        raise RuntimeError("Connection not made: '{}' -> '{}'.  Destination is locked, use `forceLocked=True`".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))

    context = CONTEXT.UnlockPlug(destPlug) if isLocked_ else PY_CONTEXT.Null()
    with context:
        if destPlug.isDestination:
            connectedSourcePlug = destPlug.sourceWithConversion()

            if forceConnected:
                disconnect(connectedSourcePlug, destPlug)
            else:
                raise RuntimeError("Connection not made: '{}' -> '{}'.  Destination is connected, use `forceConnected=True`".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))

        dgMod = OM.MDGModifier()
        dgMod.connect(sourcePlug, destPlug)
        dgMod.doIt()


def disconnect(sourcePlug, destPlug, forceLocked=False):
    """Disconnect two dependency node plugs.

    Args:
        sourcePlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug representing the source of the connection.
        destPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug representing the destination of the connection.
        forceLocked (:class:`bool`, optional): Whether to force the disconnection if ``destPlug`` is locked. Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.RuntimeError`: If ``sourcePlug`` and ``destPlug`` are not connected.
        :exc:`~exceptions.RuntimeError`: If ``destPlug`` is globally locked and ``forceLocked`` is :data:`False`.
    """
    # Lock state of connected descendant should be valid
    if destPlug.isLocked and not forceLocked:
        raise RuntimeError("Connection not removed: '{}' -> '{}'.  Destination is locked, use `forceLocked=True`".format(NAME.getPlugFullName(sourcePlug), NAME.getPlugFullName(destPlug)))

    context = CONTEXT.UnlockPlug(destPlug) if destPlug.isLocked else PY_CONTEXT.Null()
    with context:
        dgMod = OM.MDGModifier()
        dgMod.disconnect(sourcePlug, destPlug)
        dgMod.doIt()


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def getUnusedLogicalIndex(arrayPlug):
    """Returns the logical index for the next available unused element plug of an array plug.

    Note:
        If the array is sparse, the smallest sparse index will be returned.
        If no element plugs are considered in-use, the zeroth index will be returned.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Returns:
        :class:`int`: Logical index for the next available unused element of ``arrayPlug``.
    """
    OM.validatePlugType(arrayPlug, isArray=True)

    plugArrayIndices = arrayPlug.getExistingArrayAttributeIndices()
    availableIndex = None

    for index, plugArrayIndex in enumerate(plugArrayIndices):
        if index != plugArrayIndex:
            availableIndex = index
            break
    else:
        # If the loop exits without finding an index, the next available is after the last index
        # Or if the loop was never entered then we know that there are no element plugs currently in use so we can return the zeroth index
        availableIndex = len(plugArrayIndices)

    return availableIndex


def getUnusedElement(arrayPlug):
    """Return the next available unused element plug of an array plug.

    Note:
        If the array is sparse, the element will correspond to the smallest sparse logical index.
        If no element plugs are considered in-use, the element will correspond to the zeroth logical index.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation for the next available unused element plug of ``arrayPlug``.
    """
    availableIndex = getUnusedLogicalIndex(arrayPlug)
    return arrayPlug.elementByLogicalIndex(availableIndex)


def getUnconnectedLogicalIndex(arrayPlug, checkSource=True, checkDestination=True):
    """Returns the logical index for the first unconnected element plug of an array plug.

    Note:
        If the array is sparse and other elements are connected, the smallest sparse index will be returned.
        If no element plugs are considered in-use, the zeroth index will be returned.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.
        checkSource (:class:`bool`, optional): Whether to check the source side of the ``arrayPlug`` for connections. Defaults to :data:`True`.
        checkDestination (:class:`bool`, optional): Whether to check the destination side of the ``arrayPlug`` for connections. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Returns:
        :class:`int`: Logical index for the first unconnected element plug of ``arrayPlug``.
    """
    if not checkSource and not checkDestination:
        raise ValueError("Must check at least one side of the plug for connections")

    availableIndex = getUnusedLogicalIndex(arrayPlug)

    for i in xrange(availableIndex):
        elementPlug = arrayPlug.elementByLogicalIndex(i)
        if checkSource and elementPlug.isSource:
            continue
        if checkDestination and elementPlug.isDestination:
            continue
        return i

    return availableIndex


def getUnconnectedElement(arrayPlug, checkSource=True, checkDestination=True):
    """Returns the first unconnected element plug of an array plug.

    Note:
        If the array is sparse and other elements are connected, the element will correspond to the smallest sparse logical index.
        If no element plugs are considered in-use, the element will correspond to the zeroth logical index.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.
        checkSource (:class:`bool`, optional): Whether to check the source side of the ``arrayPlug`` for connections. Defaults to :data:`True`.
        checkDestination (:class:`bool`, optional): Whether to check the destination side of the ``arrayPlug`` for connections. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation for the first unconnected element plug of ``arrayPlug``.
    """
    availableIndex = getUnconnectedLogicalIndex(arrayPlug, checkSource=checkSource, checkDestination=checkDestination)
    return arrayPlug.elementByLogicalIndex(availableIndex)


def iterConnectedElements(arrayPlug, checkSource=True, checkDestination=True):
    """Yield the connected elements of an array plug.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.
        checkSource (:class:`bool`, optional): Whether to check the source side of the ``arrayPlug`` for connections. Defaults to :data:`True`.
        checkDestination (:class:`bool`, optional): Whether to check the destination side of the ``arrayPlug`` for connections. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If ``checkSource`` and ``checkDestination`` are both :data:`False`.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of the connected dependency node element plugs for the ``arrayPlug``.
    """
    if not checkSource and not checkDestination:
        raise ValueError("Must check at least one side of the plug for connections")

    elementPlugGen = iterElements(arrayPlug, forceInitialElement=False)

    if checkSource and checkDestination:
        for elementPlug in elementPlugGen:
            if elementPlug.isConnected:
                yield elementPlug
    elif checkSource:
        for elementPlug in elementPlugGen:
            if elementPlug.isSource:
                yield elementPlug
    else:
        for elementPlug in elementPlugGen:
            if elementPlug.isDestination:
                yield elementPlug


def iterElements(arrayPlug, forceInitialElement=False):
    """Yield the existing elements of an array plug.

    Args:
        arrayPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array plug.
        forceInitialElement (:class:`bool`, optional): Whether to return the zeroth indexed element of the ``arrayPlug`` if there are no existing elements.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``arrayPlug`` is not an array.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of the dependency node element plugs for the ``arrayPlug``.
    """
    OM.validatePlugType(arrayPlug, isArray=True)

    # Can also use `arrayPlug.evaluateNumElements()` with `arrayPlug.elementByPhysicalIndex`
    indices = arrayPlug.getExistingArrayAttributeIndices()

    for index in indices:
        yield arrayPlug.elementByLogicalIndex(index)

    if forceInitialElement and not indices:
        yield arrayPlug.elementByLogicalIndex(0)


def getChildByName(compoundPlug, attributeName):
    """Return a child of a non-array compound plug.

    Args:
        compoundPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node compound plug.
        attributeName (:class:`basestring`): Name of an attribute that is a child of ``compoundPlug``.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundPlug`` is not a compound.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundPlug`` is an array.
        :exc:`msTools.core.maya.exceptions.MayaLookupError`: If ``attributeName`` does not correspond to a child of ``compoundPlug``.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation of a dependency node plug for a child of ``arrayPlug`` corresponding to ``attributeName``.
    """
    OM.validatePlugType(compoundPlug, isArray=False, isCompound=True)

    nodeFn = om2.MFnDependencyNode(compoundPlug.node())
    attr = nodeFn.attribute(attributeName)

    if attr.isNull():
        raise EXC.MayaLookupError("{}.{}: Child plug does not exist".format(NAME.getPlugFullName(compoundPlug), attributeName))

    childPlug = compoundPlug.child(attr)
    # If the user has given the name of an existing attribute which is not a direct child of the compound, the compound plug will itself be returned
    if childPlug == compoundPlug:
        raise EXC.MayaLookupError("{}.{}: Child plug does not exist".format(NAME.getPlugFullName(compoundPlug), attributeName))

    return childPlug


def iterChildren(compoundPlug):
    """Yield the children of a non-array compound plug.

    Args:
        compoundPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node compound plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundPlug`` is not a compound.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``compoundPlug`` is an array.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of dependency node plugs for the children of ``arrayPlug``.
    """
    OM.validatePlugType(compoundPlug, isArray=False, isCompound=True)

    for index in xrange(compoundPlug.numChildren()):
        yield compoundPlug.child(index)


def iterDescendants(plug, forceInitialElements=True):
    """Yield descendants of an array or compound plug.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node array or compound plug.
        forceInitialElements (:class:`bool`, optional): Whether to return the zeroth indexed element of each array plug if there are no existing elements.
            If :data:`False`, traversal of the descendant hierarchy will terminate upon reaching an array plug that has no in-use elements.
            If :data:`True`, it is guaranteed that the full descendant hierarchy of ``plug`` will be traversed. Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is neither an array nor a compound.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of dependency node plugs for the descendants of ``plug``.
    """
    if not plug.isArray and not plug.isCompound:
        raise EXC.MayaTypeError("{}: Plug is neither an array nor a compound".format(NAME.getPlugFullName(plug)))

    nonArrayPlugs = []

    # 1. Search arrays for elements
    if plug.isArray:
        try:
            for elementPlug in iterElements(plug, forceInitialElement=forceInitialElements):
                yield elementPlug
                nonArrayPlugs.append(elementPlug)
        except EXC.MayaTypeError:
            pass
    else:
        nonArrayPlugs.append(plug)

    # 2. Search compounds for children
    for nonArrayPlug in nonArrayPlugs:
        if nonArrayPlug.isCompound:
            for childPlug in iterChildren(nonArrayPlug):
                yield childPlug

                # 3. Recurse 1 and 2 for each child
                try:
                    for descendantPlug in iterDescendants(childPlug, forceInitialElements=forceInitialElements):
                        yield descendantPlug
                except EXC.MayaTypeError:
                    pass


def getAncestor(plug):
    """Return the ancestor of an element or child plug.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node element or child plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is neither an element nor a child.

    Returns:
        :class:`OpenMaya.MPlug`: Encapsulation of a dependency node plug for the ancestor of ``plug``.
    """
    if plug.isElement():
        ancestorPlug = plug.array()
    elif plug.isChild():
        ancestorPlug = plug.parent()
    else:
        raise EXC.MayaTypeError("{}: Plug is neither an element nor a child".format(NAME.getPlugFullName(plug)))

    return ancestorPlug


def iterAncestors(plug):
    """Yield ancestors of an element or child plug.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node element or child plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is neither an element nor a child.

    Yields:
        :class:`OpenMaya.MPlug`: Encapsulations of dependency node plugs for the ancestors of ``plug``.
    """
    if plug.isElement:
        ancestorPlug = plug.array()
    elif plug.isChild:
        ancestorPlug = plug.parent()
    else:
        raise EXC.MayaTypeError("{}: Plug is neither an element nor a child".format(NAME.getPlugFullName(plug)))

    yield ancestorPlug

    try:
        for ancestorPlug in iterAncestors(ancestorPlug):
            yield ancestorPlug
    except EXC.MayaTypeError:
        pass


def getValue(plug):
    """Get the value held by a plug.

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
        If ``plug`` references a typed attribute with :attr:`OpenMaya.MFnData.kString` or :attr:`OpenMaya.MFnData.kStringArray` data type,
        an attempt will be made to :mod:`json` deserialize the data held by the plug.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is an array.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is a compound with a child array or compound.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` references an unsupported attribute type.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` references a numeric or typed attribute with an unsupported data type.

    Returns:
        any: ``plug`` data.
    """
    if plug.isArray:
        raise EXC.MayaTypeError("{}: Array plugs are not supported".format(NAME.getPlugFullName(plug)))

    # Check the attribute type then if necessary check the default data type held by the attribute (some attribute types can handle multiple data types)
    attr = plug.attribute()
    attrType = attr.apiType()

    # NUMBERS
    if attrType == om2.MFn.kNumericAttribute:
        attrFn = om2.MFnNumericAttribute(attr)
        attrDataType = attrFn.numericType()

        if attrDataType == om2.MFnNumericData.kBoolean:
            return plug.asBool()
        elif attrDataType in [om2.MFnNumericData.kChar, om2.MFnNumericData.kByte, om2.MFnNumericData.kShort, om2.MFnNumericData.kInt, om2.MFnNumericData.kLong, om2.MFnNumericData.kAddr, om2.MFnNumericData.kInt64]:
            return plug.asInt()
        elif attrDataType in [om2.MFnNumericData.kFloat, om2.MFnNumericData.kDouble]:
            return plug.asDouble()
        else:
            raise EXC.MayaTypeError("{}: Plug references numeric attribute with unsupported data type: OpenMaya.MFnNumericData.{}".format(NAME.getPlugFullName(plug), CONST.NUMERIC_DATA_CONSTANT_NAME_MAPPING[attrDataType]))

    # GROUP data (kAttribute<numChildren><numericType>) eg. Translate, Rotate, Scale
    elif attrType in [om2.MFn.kAttribute2Double, om2.MFn.kAttribute2Float, om2.MFn.kAttribute2Int, om2.MFn.kAttribute2Short,
                      om2.MFn.kAttribute3Double, om2.MFn.kAttribute3Float, om2.MFn.kAttribute3Int, om2.MFn.kAttribute3Short,
                      om2.MFn.kAttribute4Double]:
        childData = []

        for i in xrange(plug.numChildren()):
            childData.append(getValue(plug.child(i)))

        return childData

    # COMPOUNDS
    elif attrType == om2.MFn.kCompoundAttribute:
        childData = []

        for i in xrange(plug.numChildren()):
            childPlug = plug.child(i)
            if childPlug.isArray:
                raise EXC.MayaTypeError("{}: Compound plugs with child arrays are not supported".format(NAME.getPlugFullName(plug)))
            elif childPlug.isCompound:
                raise EXC.MayaTypeError("{}: Compound plugs with child compounds are not supported".format(NAME.getPlugFullName(plug)))
            else:
                childData.append(getValue(childPlug))

        return childData

    # DISTANCE
    elif attrType in [om2.MFn.kDoubleLinearAttribute, om2.MFn.kFloatLinearAttribute]:
        # return plug.asMDistance().asUnits(om2.MDistance.uiUnit())
        return plug.asMDistance()

    # ANGLE
    elif attrType in [om2.MFn.kDoubleAngleAttribute, om2.MFn.kFloatAngleAttribute]:
        return plug.asMAngle()

    # TIME
    elif attrType == om2.MFn.kTimeAttribute:
        return plug.asMTime()

    # MATRIX
    elif attrType in [om2.MFn.kMatrixAttribute, om2.MFn.kFloatMatrixAttribute]:
        return om2.MFnMatrixData(plug.asMObject()).matrix()

    # ENUM
    elif attrType == om2.MFn.kEnumAttribute:
        return plug.asInt()

    # TYPED
    elif attrType == om2.MFn.kTypedAttribute:
        attrFn = om2.MFnTypedAttribute(attr)
        attrDataType = attrFn.attrType()

        # INVALID
        if attrDataType == om2.MFnData.kInvalid:
            return

        # MATRIX
        elif attrDataType == om2.MFnData.kMatrix:
            return om2.MFnMatrixData(plug.asMObject()).matrix()

        # NUMERIC
        elif attrDataType == om2.MFnData.kNumeric:
            dataWrapper = plug.asMObject()
            dataFn = om2.MFnNumericData(dataWrapper)

            # This will return a list of values (single value numeric types are not supported by typed attributes whose purpose is to encapsulate complex data)
            return dataFn.getData()

        # STRING
        elif attrDataType == om2.MFnData.kString:
            data = plug.asString()

            try:
                return json.loads(data)
            except ValueError:
                return data

        # STRING ARRAY
        elif attrDataType == om2.MFnData.kStringArray:
            dataWrapper = plug.asMObject()
            stringData = om2.MFnStringArrayData(dataWrapper).array()
            data = []

            for string in stringData:
                try:
                    data.append(json.loads(string))
                except ValueError:
                    data.append(string)

            return data

        # DOUBLE ARRAY
        elif attrDataType == om2.MFnData.kDoubleArray:
            # The returned MDoubleArray is a non-reference counted reference to the internal MObject data
            # Once the scope is destroyed, the referent is lost, invalidating the reference (therefore a copy must be made)
            dataWrapper = plug.asMObject()
            doubleArrayRef = om2.MFnDoubleArrayData(dataWrapper).array()
            return om2.MDoubleArray(doubleArrayRef)

        # INT ARRAY
        elif attrDataType == om2.MFnData.kIntArray:
            dataWrapper = plug.asMObject()
            intArrayRef = om2.MFnIntArrayData(dataWrapper).array()
            return om2.MIntArray(intArrayRef)

        # POINT ARRAY
        elif attrDataType == om2.MFnData.kPointArray:
            dataWrapper = plug.asMObject()
            pointArrayRef = om2.MFnPointArrayData(dataWrapper).array()
            return om2.MPointArray(pointArrayRef)

        # VECTOR ARRAY
        elif attrDataType == om2.MFnData.kVectorArray:
            dataWrapper = plug.asMObject()
            vectorArrayRef = om2.MFnVectorArrayData(dataWrapper).array()
            return om2.MVectorArray(vectorArrayRef)

        # COMPONENT LIST
        elif attrDataType == om2.MFnData.kComponentList:
            # A component list is encapsulated by a single MObject at index zero
            dataWrapper = plug.asMObject()
            mFnCompListData = om2.MFnComponentListData(dataWrapper)
            return mFnCompListData.get(0)

        else:
            raise EXC.MayaTypeError("{}: Plug references typed attribute with unsupported data type: OpenMaya.MFnData.{}".format(NAME.getPlugFullName(plug), CONST.DATA_CONSTANT_NAME_MAPPING[attrDataType]))

    raise EXC.MayaTypeError("{}: Plug references attribute with unsupported type: OpenMaya.MFn.{}".format(NAME.getPlugFullName(plug), CONST.CONSTANT_NAME_MAPPING[attrType]))


# --------------------------------------------------------------
# --- Set ---
# --------------------------------------------------------------

def setValue(plug, value, forceLocked=False):
    """Set the value held by a plug.

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
        If ``plug`` references a typed attribute with :attr:`OpenMaya.MFnData.kString` or :attr:`OpenMaya.MFnData.kStringArray` data type,
        an attempt will be made to :mod:`json` serialize the ``value`` if it does not reference :class:`str` castable data.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        value (any): Data used to update the value held by ``plug``. The type must be compatible with the data type of the ``plug`` attribute.
        forceLocked (:class:`bool`, optional): Whether to force set the value if ``plug`` is locked. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is an array.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` is a compound with a child array or compound.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` references a typed attribute which holds :attr:`OpenMaya.MFnData.kComponentList` type data
            and the :class:`OpenMaya.MObject` ``value`` does not reference :attr:`OpenMaya.MFn.kComponent` type data.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` references an unsupported attribute type.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``plug`` references a numeric or typed attribute with an unsupported data type.
        :exc:`~exceptions.TypeError`: If the ``value`` type is not supported by ``plug``.
        :exc:`~exceptions.ValueError`: If ``plug`` requires a sequence of values which has a different length to the ``value`` sequence.
        :exc:`~exceptions.RuntimeError`: If ``plug`` has an input connection.
        :exc:`~exceptions.RuntimeError`: If ``plug`` is locked and ``forceLocked`` is :data:`False`.
    """
    if plug.isArray:
        raise EXC.MayaTypeError("{}: Array plugs are not supported".format(NAME.getPlugFullName(plug)))

    if plug.isDestination:
        raise RuntimeError("{}: Plug has input connection".format(NAME.getPlugFullName(plug)))

    # Checks the ancestor hierarchy (the lock state of an unconnected descendant does not automatically update when an ancestor is locked)
    isLocked_ = isLocked(plug)
    if isLocked_ and not forceLocked:
        raise RuntimeError("{}: Plug is locked. Use 'forceLocked=True' to temporarily unlocked".format(NAME.getPlugFullName(plug)))

    dgMod = OM.MDGModifier()
    dataType = type(value)
    attr = plug.attribute()
    attrType = attr.apiType()

    # NUMBERS
    if attrType == om2.MFn.kNumericAttribute:
        numAttrFn = om2.MFnNumericAttribute(attr)
        attrDataType = numAttrFn.numericType()

        if attrDataType == om2.MFnNumericData.kBoolean:
            try:
                dgMod.newPlugValueBool(plug, value)
            except TypeError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), bool, dataType))
        elif attrDataType in [om2.MFnNumericData.kChar, om2.MFnNumericData.kByte, om2.MFnNumericData.kShort, om2.MFnNumericData.kInt, om2.MFnNumericData.kLong, om2.MFnNumericData.kAddr, om2.MFnNumericData.kInt64]:
            try:
                dgMod.newPlugValueInt(plug, value)
            except TypeError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), int, dataType))
        elif attrDataType in [om2.MFnNumericData.kFloat, om2.MFnNumericData.kDouble]:
            try:
                dgMod.newPlugValueFloat(plug, value)
            except TypeError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), float, dataType))
        else:
            raise TypeError("{}: Plug references numeric attribute with unsupported data type : OpenMaya.MFnNumericData.{}".format(NAME.getPlugFullName(plug), CONST.NUMERIC_DATA_CONSTANT_NAME_MAPPING[attrDataType]))

    # GROUP data (kAttribute<numChildren><numericType>) eg. Translate, Rotate, Scale
    elif attrType in [om2.MFn.kAttribute2Double, om2.MFn.kAttribute2Float, om2.MFn.kAttribute2Int, om2.MFn.kAttribute2Short,
                      om2.MFn.kAttribute3Double, om2.MFn.kAttribute3Float, om2.MFn.kAttribute3Int, om2.MFn.kAttribute3Short,
                      om2.MFn.kAttribute4Double]:
        numAttrFn = om2.MFnNumericAttribute(attr)
        attrDataType = numAttrFn.numericType()
        attrDataSize = CONST.NUMERIC_DATA_CONSTANT_SIZE_MAPPING[attrDataType]

        if len(value) != attrDataSize:
            raise ValueError("{}: Plug requires sequence of length {}. Received sequence of length {} instead.".format(NAME.getPlugFullName(plug), attrDataSize, len(value)))

        numDataFn = om2.MFnNumericData()
        dataWrapper = numDataFn.create(attrDataType)
        numDataFn.setData(tuple(value))

        try:
            dgMod.newPlugValue(plug, dataWrapper)
        except TypeError:
            raise TypeError("{}: Plug requires sequence of {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), CONST.NUMERIC_DATA_CONSTANT_TYPE_MAPPING[attrDataType], [type(x) for x in value]))

    # COMPOUNDS
    elif attrType == om2.MFn.kCompoundAttribute:
        childPlugs = []

        # Complete checks before setting values
        for i in xrange(plug.numChildren()):
            childPlug = plug.child(i)

            if childPlug.isArray:
                raise EXC.MayaTypeError("{}: Compound plugs with child arrays are not supported".format(NAME.getPlugFullName(plug)))
            elif childPlug.isCompound:
                raise EXC.MayaTypeError("{}: Compound plugs with child compounds are not supported".format(NAME.getPlugFullName(plug)))
            else:
                childPlugs.append(childPlug)

        if len(childPlugs) != len(value):
            raise ValueError("{}: Compound plug requires sequence of length {}. Received sequence of length {} instead".format(NAME.getPlugFullName(plug), len(childPlugs), len(value)))

        for index, childPlug in enumerate(childPlugs):
            setValue(childPlug, value[index])

    # DISTANCE
    elif attrType in [om2.MFn.kDoubleLinearAttribute, om2.MFn.kFloatLinearAttribute]:
        if not isinstance(value, om2.MDistance):
            try:
                value = om2.MDistance(value, om2.MDistance.uiUnit())
            except ValueError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), om2.MDistance, type(value)))

            log.debug("Value converted to {} using the default UI unit: OpenMaya.MDistance.{}".format(om2.MDistance, CONST.DISTANCE_UNIT_CONSTANT_NAME_MAPPING[om2.MDistance.uiUnit()]))

        dgMod.newPlugValueMDistance(plug, value)

    # ANGLE
    elif attrType in [om2.MFn.kDoubleAngleAttribute, om2.MFn.kFloatAngleAttribute]:
        if not isinstance(value, om2.MAngle):
            try:
                value = om2.MAngle(value, om2.MAngle.uiUnit())
            except ValueError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), om2.MAngle, type(value)))

            log.debug("Value converted to {} using the default UI unit: OpenMaya.MAngle.{}".format(om2.MAngle, CONST.ANGLE_UNIT_CONSTANT_NAME_MAPPING[om2.MAngle.uiUnit()]))

        dgMod.newPlugValueMAngle(plug, value)

    # TIME
    elif attrType == om2.MFn.kTimeAttribute:
        if not isinstance(value, om2.MTime):
            try:
                value = om2.MTime(value, om2.MTime.uiUnit())
            except ValueError:
                raise TypeError("{}: Plug requires {} castable data. Received {} instead".format(NAME.getPlugFullName(plug), om2.MTime, type(value)))

            log.debug("Value converted to {} using the default UI unit: OpenMaya.MTime.{}".format(om2.MTime, CONST.TIME_UNIT_CONSTANT_NAME_MAPPING[om2.MTime.uiUnit()]))

        dgMod.newPlugValueMTime(plug, value)

    # MATRIX
    elif attrType in [om2.MFn.kMatrixAttribute, om2.MFn.kFloatMatrixAttribute]:
        if isinstance(value, om2.MFloatMatrix):
            value = om2.MMatrix(value)

        dataFn = om2.MFnMatrixData()
        dataWrapper = dataFn.create(value)
        dgMod.newPlugValue(plug, dataWrapper)

    # ENUM
    elif attrType == om2.MFn.kEnumAttribute:
        dgMod.newPlugValueInt(plug, value)

    # TYPED
    elif attrType == om2.MFn.kTypedAttribute:
        typedAttrFn = om2.MFnTypedAttribute(attr)
        attrDataType = typedAttrFn.attrType()

        # INVALID
        if attrDataType == om2.MFnData.kInvalid:
            return

        # MATRIX
        elif attrDataType == om2.MFnData.kMatrix:
            if isinstance(value, om2.MFloatMatrix):
                value = om2.MMatrix(value)

            dataFn = om2.MFnMatrixData()
            dataWrapper = dataFn.create(value)
            dgMod.newPlugValue(plug, dataWrapper)

        # STRING
        elif attrDataType == om2.MFnData.kString:
            if not isinstance(value, basestring):
                try:
                    value = json.dumps(value)
                except TypeError:
                    raise TypeError("{}: Plug requires {} castable or json serializable data. Received {} instead".format(NAME.getPlugFullName(plug), str, type(value)))

            dgMod.newPlugValueString(plug, value)

        # STRING ARRAY
        elif attrDataType == om2.MFnData.kStringArray:
            stringArray = []

            for x in value:
                if isinstance(x, basestring):
                    stringArray.append(x)
                else:
                    try:
                        stringArray.append(json.dumps(x))
                    except TypeError:
                        raise TypeError("{}: Plug requires sequence of {} castable or json serializable data. Received {} instead".format(NAME.getPlugFullName(plug), str, [type(x) for x in value]))

            dataFn = om2.MFnStringArrayData()
            dataWrapper = dataFn.create(stringArray)
            dgMod.newPlugValue(plug, dataWrapper)

        # DOUBLE ARRAY
        elif attrDataType == om2.MFnData.kDoubleArray:
            dataFn = om2.MFnDoubleArrayData()
            dataWrapper = dataFn.create(value)
            dgMod.newPlugValue(plug, dataWrapper)

        # INT ARRAY
        elif attrDataType == om2.MFnData.kIntArray:
            dataFn = om2.MFnIntArrayData()
            dataWrapper = dataFn.create(value)
            dgMod.newPlugValue(plug, dataWrapper)

        # POINT ARRAY
        elif attrDataType == om2.MFnData.kPointArray:
            for index, point in enumerate(value):
                try:
                    value[index] = om2.MPoint(point)
                except ValueError:
                    raise TypeError("{}: Plug requires sequence of {} castable data".format(NAME.getPlugFullName(plug), om2.MPoint))

            dataFn = om2.MFnPointArrayData()
            dataWrapper = dataFn.create(value)
            dgMod.newPlugValue(plug, dataWrapper)

        # VECTOR ARRAY
        elif attrDataType == om2.MFnData.kVectorArray:
            for index, vector in enumerate(value):
                try:
                    value[index] = om2.MVector(vector)
                except ValueError:
                    raise TypeError("{}: Plug requires sequence of {} castable data".format(NAME.getPlugFullName(plug), om2.MVector))

            dataFn = om2.MFnVectorArrayData()
            dataWrapper = dataFn.create(value)
            dgMod.newPlugValue(plug, dataWrapper)

        # COMPONENT LIST
        elif attrDataType == om2.MFnData.kComponentList:
            # We expect the value to be a component encapsulation of indices and type
            if isinstance(value, om2.MObject):
                if not value.hasFn(om2.MFn.kComponent):
                    raise EXC.MayaTypeError("{}: Plug requires component data. Received `OpenMaya.MFn.{}` type object instead".format(NAME.getPlugFullName(plug), value.apiTypeStr))
            else:
                raise TypeError("{}: Plug requires an {} component data wrapper".format(NAME.getPlugFullName(plug), om2.MObject))

            dataFn = om2.MFnComponentListData()
            dataWrapper = dataFn.create()
            dataFn.add(value)
            dgMod.newPlugValue(plug, dataWrapper)

        else:
            raise EXC.MayaTypeError("{}: Plug references typed attribute with unsupported data type : OpenMaya.MFnData.{}".format(NAME.getPlugFullName(plug), CONST.DATA_CONSTANT_NAME_MAPPING[attrDataType]))

    else:
        raise EXC.MayaTypeError("{}: Plug references attribute with unsupported type : OpenMaya.MFn.{}".format(NAME.getPlugFullName(plug), CONST.CONSTANT_NAME_MAPPING[attrType]))

    context = CONTEXT.UnlockPlug(plug) if isLocked_ else PY_CONTEXT.Null()
    with context:
        dgMod.doIt()


def setProperties(plug, **kwargs):
    """Set properties corresponding to any writable property on :class:`OpenMaya.MPlug` for any encapsulated plug. Changes are placed on the undo queue.

    Note:
        See :ref:`note-1 <note_1>`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        **kwargs: Keyword arguments where each argument corresponds to a writable property on :class:`OpenMaya.MPlug` such as
            :attr:`OpenMaya.MPlug.isCaching`, :attr:`OpenMaya.MPlug.isChannelBox`, :attr:`OpenMaya.MPlug.isKeyable`, :attr:`OpenMaya.MPlug.isLocked`.

    Examples:
        .. code-block:: python

            # Unlock `plug` and set keyable
            setProperties(plug, isKeyable=True, isLocked=False)
    """
    _PropertyModifier(plug, **kwargs)


# --------------------------------------------------------------
# --- Modify ---
# --------------------------------------------------------------

def unlockGlobal(plug):
    """Globally unlock a plug by ensuring any locked ancestor is also unlocked.

    Note:
        The global lock state of a plug is influenced by the lock state of each ancestor.
        A plug can be globally locked whilst also being internally unlocked. See :ref:`note-5 <note_5>`.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

    Returns:
        :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs that have been unlocked, ordered from the furthest ancestor of ``plug``.
    """
    try:
        plugHierarchy = list(iterAncestors(plug))
        plugHierarchy.insert(0, plug)
    except EXC.MayaTypeError:
        plugHierarchy = [plug]

    # Must unlock ancestors one at a time so we can determine which are internally locked and which are globally locked
    unlockedPlugHierarchy = []

    for plug in plugHierarchy[::-1]:
        if plug.isLocked:
            setProperties(plug, isLocked=False)
            unlockedPlugHierarchy.append(plug)

    return unlockedPlugHierarchy


def unlockRelatives(plug):
    """Unlock all ancestors and descendants of a plug.

    Designed for use before removing an attribute.
    Any descendant plug which is locked and connected must be unlocked in order to remove an attribute.

    Args:
        plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.

    Returns:
        :class:`list` [:class:`OpenMaya.MPlug`]: Encapsulations of dependency node plugs that have been unlocked, ordered from furthest ancestor to furthest descendant of ``plug``.
    """
    try:
        plugHierarchy = list(iterDescendants(plug, forceInitialElements=False))[::-1]
        plugHierarchy.append(plug)
    except EXC.MayaTypeError:
        plugHierarchy = [plug]

    try:
        plugHierarchy += list(iterAncestors(plug))
    except EXC.MayaTypeError:
        pass

    # Must unlock ancestors one at a time so we can determine which are internally locked and which are globally locked
    unlockedPlugHierarchy = []

    for plug in plugHierarchy[::-1]:
        if plug.isLocked:
            setProperties(plug, isLocked=False)
            unlockedPlugHierarchy.append(plug)

    return unlockedPlugHierarchy


# --------------------------------------------------------------
# --- Remove ---
# --------------------------------------------------------------

@DECORATOR.undoOnError(StandardError)
def removeElement(elementPlug, forceConnected=False, forceLocked=False):
    """Remove an element plug.

    Args:
        elementPlug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node element plug.
        forceConnected (:class:`bool`, optional): Whether to force the removal if ``elementPlug`` or one of its descendants is connected. Defaults to :data:`False`.
        forceLocked (:class:`bool`, optional): Whether to force the removal if ``elementPlug`` is locked. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``elementPlug`` is not an element plug.
        :exc:`~exceptions.RuntimeError`: If ``elementPlug`` is locked and ``forceLocked`` is :data:`False`.
        :exc:`~exceptions.RuntimeError`: If ``elementPlug`` or one of its descendants is connected and ``forceConnected`` is :data:`False`.
    """
    if not elementPlug.isElement:
        raise EXC.MayaTypeError("Expected element plug")

    # Checks the ancestor hierarchy (the lock state of an unconnected descendant does not automatically update when an ancestor is locked)
    unlockedAncestors = []
    for ancestorPlug in list(iterAncestors(elementPlug))[::-1]:
        if ancestorPlug.isLocked:
            setProperties(ancestorPlug, isLocked=False)
            unlockedAncestors.append(ancestorPlug)

    if not forceLocked and (unlockedAncestors or elementPlug.isLocked):
        raise RuntimeError("'{}': Plug is locked. Use `forceLocked=True`".format(NAME.getPlugFullName(elementPlug)))

    setProperties(elementPlug, isLocked=False)

    # Only check descendants if specified (Maya should error if a descendant is locked and connected)
    if forceLocked:
        try:
            for descendantPlug in iterDescendants(elementPlug, forceInitialElements=False):
                setProperties(descendantPlug, isLocked=False)
        except EXC.MayaTypeError:
            pass

    try:
        mDGMod = OM.MDGModifier()
        mDGMod.removeMultiInstance(elementPlug, forceConnected)
        mDGMod.doIt()
    except RuntimeError:
        # Implement a descriptive error for connections
        if not forceConnected:
            if elementPlug.isConnected:
                raise RuntimeError("{}: Plug is connected. Use 'forceConnected=True'".format(NAME.getPlugFullName(elementPlug)))
            elif elementPlug.isCompound and elementPlug.numConnectedChildren():
                # numConnectedChildren accounts for all descendant element plugs as well
                raise RuntimeError("{}: Plug has descendant connections. Use 'forceConnected=True'".format(NAME.getPlugFullName(elementPlug)))
        raise

    for unlockedAncestor in unlockedAncestors:
        setProperties(unlockedAncestor, isLocked=True)


# --------------------------------------------------------------
# --- DEPRECATED ---
# --------------------------------------------------------------

# Use dg_utils functions to traverse inputs and outputs

# def getInputs(plugs, skipConversionNodes=False, nodeFilterTypes=None, attrFilterTypes=None):
#     """Return the inputs for a sequence of dependency node plugs.

#     Args:
#         plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
#         skipConversionNodes (:class:`bool`, optional): Whether to skip over input connections from unitConversion nodes, instead returning their input.
#             Defaults to :data:`False`.
#         nodeFilterTypes (iterable [:class:`int`], optional): Filter inputs based on :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
#             Defaults to :data:`None` - no node type filtering will occur.
#         attrFilterTypes (iterable [:class:`int`], optional): Filter inputs based on :class:`OpenMaya.MObject` attribute compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kCompoundAttribute`.
#             Defaults to :data:`None` - no attribute type filtering will occur.

#     Returns:
#         :class:`list` [:class:`OpenMaya.MPlug`]: Dependency node plug encapsulations for the inputs of ``plugs``.
#     """
#     plugSet = OM.MPlugSet(plugs)
#     inputPlugSet = OM.MPlugSet()

#     for plug in plugSet:
#         if plug.isDestination:
#             if skipConversionNodes:
#                 inputPlug = plug.source()
#             else:
#                 inputPlug = plug.sourceWithConversion()

#             inputPlugSet.add(inputPlug)

#     inputPlugs = list(inputPlugSet)

#     if nodeFilterTypes:
#         inputPlugs = OM.filterPlugsByNodeType(inputPlugs, filterTypes=nodeFilterTypes)
#     if attrFilterTypes:
#         inputPlugs = OM.filterPlugsByAttributeType(inputPlugs, filterTypes=attrFilterTypes)

#     return inputPlugs


# def getOutputs(plugs, skipConversionNodes=False, nodeFilterTypes=None, attrFilterTypes=None):
#     """Return the outputs for a sequence of dependency node plugs.

#     Args:
#         plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
#         skipConversionNodes (:class:`bool`, optional): Whether to skip over output connections to unitConversion nodes, instead returning their output.
#             Defaults to :data:`False`.
#         nodeFilterTypes (iterable [:class:`int`], optional): Filter outputs based on :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
#             Defaults to :data:`None` - no node type filtering will occur.
#         attrFilterTypes (iterable [:class:`int`], optional): Filter outputs based on :class:`OpenMaya.MObject` attribute compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kCompoundAttribute`.
#             Defaults to :data:`None` - no attribute type filtering will occur.

#     Returns:
#         :class:`list` [:class:`OpenMaya.MPlug`]: Dependency node plug encapsulations for the outputs of ``plugs``.
#     """
#     plugSet = OM.MPlugSet(plugs)
#     outputPlugs = []

#     for plug in plugSet:
#         if plug.isSource:
#             # Destination plugs can only have a single connection, we do not need to use a MPlugSet
#             if skipConversionNodes:
#                 outputPlugs += plug.destinations()
#             else:
#                 outputPlugs += plug.destinationsWithConversions()

#     if nodeFilterTypes:
#         outputPlugs = OM.filterPlugsByNodeType(outputPlugs, filterTypes=nodeFilterTypes)
#     if attrFilterTypes:
#         outputPlugs = OM.filterPlugsByAttributeType(outputPlugs, filterTypes=attrFilterTypes)

#     return outputPlugs


# def getInputNodes(plugs, skipConversionNodes=False, nodeFilterTypes=None, attrFilterTypes=None):
#     """Return the input nodes for a sequence of dependency node plugs.

#     Args:
#         plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
#         skipConversionNodes (:class:`bool`, optional): Whether to skip over input connections from unitConversion nodes, instead returning their input.
#             Defaults to :data:`False`.
#         nodeFilterTypes (iterable [:class:`int`], optional): Filter inputs based on :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
#             Defaults to :data:`None` - no node type filtering will occur.
#         attrFilterTypes (iterable [:class:`int`], optional): Filter inputs based on :class:`OpenMaya.MObject` attribute compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kCompoundAttribute`.
#             Defaults to :data:`None` - no attribute type filtering will occur.

#     Returns:
#         :class:`list` [:class:`OpenMaya.MObject`]: Wrappers of dependency nodes for the inputs of ``plugs``.
#     """
#     inputPlugs = getInputs(plugs, skipConversionNodes=skipConversionNodes, nodeFilterTypes=nodeFilterTypes, attrFilterTypes=attrFilterTypes)
#     inputNodes = OM.MObjectSet()

#     for inputPlug in inputPlugs:
#         inputNode = inputPlug.node()
#         inputNodes.add(inputNode)

#     return list(inputNodes)


# def getOutputNodes(plugs, skipConversionNodes=False, nodeFilterTypes=None, attrFilterTypes=None):
#     """Return the output nodes for a sequence of dependency node plugs.

#     Args:
#         plugs (iterable [:class:`OpenMaya.MPlug`]): Encapsulations of dependency node plugs.
#         skipConversionNodes (:class:`bool`, optional): Whether to skip over output connections to unitConversion nodes, instead returning their output.
#             Defaults to :data:`False`.
#         nodeFilterTypes (iterable [:class:`int`], optional): Filter outputs based on :class:`OpenMaya.MObject` node compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kMesh`.
#             Defaults to :data:`None` - no node type filtering will occur.
#         attrFilterTypes (iterable [:class:`int`], optional): Filter outputs based on :class:`OpenMaya.MObject` attribute compatibility with type constants from :class:`OpenMaya.MFn`.
#             Exclusions can be given as negated type constants making it is possible to exclude specific inheriting types such as :attr:`~OpenMaya.MFn.kCompoundAttribute`.
#             Defaults to :data:`None` - no attribute type filtering will occur.

#     Returns:
#         :class:`list` [:class:`OpenMaya.MObject`]: Wrappers of dependency nodes for the outputs of ``plugs``.
#     """
#     outputPlugs = getOutputs(plugs, skipConversionNodes=skipConversionNodes, nodeFilterTypes=nodeFilterTypes, attrFilterTypes=attrFilterTypes)
#     outputNodes = OM.MObjectSet()

#     for outputPlug in outputPlugs:
#         outputNode = outputPlug.node()
#         outputNodes.add(outputNode)

#     return list(outputNodes)
