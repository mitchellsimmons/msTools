"""
Register callables to Maya message events. Registered callables are invoked when the corresponding message is processed.

----------------------------------------------------------------

Events
------

    The following :class:`Event` subclasses provide enumerations which map directly to a Maya message event for a specific :class:`OpenMaya.MMessage` subclass:

    - :class:`SceneEvent` |xrarr| :class:`OpenMaya.MSceneMessage`
    - :class:`DGEvent` |xrarr| :class:`OpenMaya.MDGMessage`

    The :class:`UserEvent` enumerations provide custom Maya events:

    - Processing of these events is predicated upon user input (ie. the user is prompted to confirm or cancel an operation).
    - :class:`UserEvent` enumerations such as :attr:`UserEvent.ConfirmSave` are provided as an alternative to :class:`SceneEvent` enumerations when a student version of Maya is being used.
    - Student versions of Maya prompt the user for input, however the events corresponding to the :class:`SceneEvent` enumerations are processed regardless of whether the user cancels the operation.

----------------------------------------------------------------

Registration
------------

    Callbacks for each event are installed as needed (ie. upon registering the initial callable for a specific event).
    Callbacks for each event are removed when there are no longer any callables registered to an event.

    A callable can only be registered once per event, whereby the conditions for registration are are predicated upon object equivalence.
    A special case is made for :obj:`functools.partial` objects which must pass an additional test.
    Each :obj:`functools.partial` object must have unique :attr:`~functools.partial.func`, :attr:`~functools.partial.args` and :attr:`~functools.partial.keywords` member values.

    The interface for this module is designed to be simple.
    Therefore callback initializers which take additional parameters will be passed default values. See :meth:`OpenMaya.MDGMessage.addNodeAddedCallback` as an example.

    .. warning:: Reloading this module will result in any registered callbacks being removed and any registered callables being cleared.
        Data is registered by Enum type, meaning registry keys (ie. class ids) will be invalidated upon reloading.

.. -------------------------------------------------------------

    Globals
    -------

    The following global scope variables are used to store session state:

    - _CALLBACK_DATA : Used to register all callback data for the current session.

----------------------------------------------------------------
"""

import collections
import functools
import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2

from msTools.vendor.enum import Enum
from msTools.vendor.Qt import QtCore, QtWidgets

from msTools.core.py import class_utils as CLASS
from msTools.coreUI.maya import inspect_utils as UI_INSPECT


# --------------------------------------------------------------
# --- Events ---
# --------------------------------------------------------------


class Event(Enum):
    """Baseclass used to construct Maya event enumerations.

    Note:
        Class is designed to be inherited.
    """
    pass


class UserEvent(Event):
    """Derived :class:`Event` enumerations designed for student versions of Maya. Events correspond to Maya messages which produce a dialog prompt.

    Registered callables are executed for the corresponding ``After...`` :class:`SceneEvent`.

    Note:
        There is no ``CreateReference`` event as cancelling still creates a reference, therefore you may as well use the :class:`SceneEvent`.
    """
    ConfirmedOpen = 1
    CancelledOpen = 2
    ConfirmedImport = 3
    CancelledImport = 4
    ConfirmedExport = 5
    CancelledExport = 6
    ConfirmedSave = 7
    CancelledSave = 8
    ConfirmedLoadReference = 9
    CancelledLoadReference = 10


class SceneEvent(Event):
    """Derived :class:`Event` enumerations corresponding to :class:`OpenMaya.MSceneMessage` events"""
    SceneUpdate = 1
    BeforeNew = 2
    AfterNew = 3
    BeforeOpen = 4
    AfterOpen = 5
    BeforeImport = 6
    AfterImport = 7
    BeforeExport = 8
    AfterExport = 9
    BeforeSave = 10
    AfterSave = 11
    BeforeLoadReference = 12
    AfterLoadReference = 13
    BeforeUnloadReference = 14
    AfterUnloadReference = 15
    BeforeImportReference = 16
    AfterImportReference = 17
    BeforeExportReference = 18
    AfterExportReference = 19
    BeforeCreateReference = 20
    AfterCreateReference = 21
    BeforeRemoveReference = 22
    AfterRemoveReference = 23
    BeforePluginLoad = 24
    AfterPluginLoad = 25
    BeforePluginUnload = 26
    AfterPluginUnload = 27


class DGEvent(Event):
    """Derived :class:`Event` enumerations corresponding to :class:`OpenMaya.MDGMessage` events.

    Note:
        This tool is designed to provide a generic interface for registering callbacks, therefore some functionality is removed from the user.

        - For example, the events :attr:`DGEvent.NodeAdded` and :attr:`DGEvent.NodeRemoved` correspond to messages for :meth:`OpenMaya.MDGMessage.addNodeAddedCallback` and :meth:`OpenMaya.MDGMessage.addNodeRemovedCallback`.
        - Callbacks for these events will be registered with ``nodeType='dependNode'``.
    """
    TimeChange = 1
    ForceUpdate = 2
    NodeAdded = 3
    NodeRemoved = 4
    ConnectionChange = 5
    PreConnectionChange = 6


# --------------------------------------------------------------
# --- Public ---
# --------------------------------------------------------------

def isCallableRegistered(event, callable_):
    """Verify a callable object is registered to a derived :class:`Event` enumeration.

    Args:
        event (T <= :class:`Event`): An enumeration of type ``T`` with upper bound :class:`Event`. Corresponds to a Maya message event.
        callable_ (callable[..., any]): A callable object. Can be a :obj:`functools.partial` object.

    Returns:
        :class:`bool`: True if the callable is registered to the event, False otherwise.
    """
    isPartial = isinstance(callable_, functools.partial)
    for registeredCallableData in _CALLBACK_DATA.callableDataRegistry[event]:
        if isPartial and isinstance(registeredCallableData.callable, functools.partial):
            if (callable_.func == registeredCallableData.callable.func and callable_.args == registeredCallableData.callable.args
                    and callable_.keywords == registeredCallableData.callable.keywords):
                return True
        elif callable_ == registeredCallableData.callable:
            return True

    return False


def registerCallable(event, callable_, receivesCallbackArgs=False):
    """Register a callable object to a derived :class:`Event` enumeration corresponding to a Maya message event.

    If this is the first callable to be registered for the :class:`Event` enumeration, a callback associated with that event will be installed.

    Note:
        If the callable is a :obj:`functools.partial` object and ``receivesCallbackArgs=True``, it is the caller's responsibility to ensure:

        #. The :attr:`functools.partial.func` callable can receive the :attr:`~functools.partial.args` and :attr:`~functools.partial.keywords`.
        #. The :attr:`functools.partial.func` callable can receive the callback arguments.

    Args:
        event (T <= :class:`Event`): An enumeration of type ``T`` with upper bound :class:`Event`. Corresponds to a Maya message event.
        callable_ (callable[..., any]): A callable object. Can be a :obj:`functools.partial` object.
        receivesCallbackArgs (:class:`bool`, optional): Whether the callable will receive any callback arguments if they exist. Defaults to False.
            For example, a callable registered to the :attr:`DGEvent.NodeAdded` event can receive the node :class:`OpenMaya.MObject`
            passed to the callback corresponding to :meth:`OpenMaya.MDGMessage.addNodeAddedCallback`.
    """
    global _CALLBACK_DATA

    if isCallableRegistered(event, callable_):
        return

    previousCallableCount = len(_CALLBACK_DATA.callableDataRegistry[event])
    callableData = _CallableData(callable_, receivesCallbackArgs)
    _CALLBACK_DATA.callableDataRegistry[event].add(callableData)

    if previousCallableCount == 0 and len(_CALLBACK_DATA.callableDataRegistry[event]) == 1:
        log.debug("Installing: {} callback".format(event))
        registerCallback = _kRegister[event]
        callbackId = registerCallback()
        _CALLBACK_DATA.idRegistry[event] = callbackId


def deregisterCallable(event, callable_):
    """Deregisters a callable object from a derived :class:`Event` enumeration corresponding to a Maya message event.

    If this was the only callable registered to the derived :class:`Event` enumeration, the callback associated with that event will be removed.

    Args:
        event (T <= :class:`Event`): An enumeration of type ``T`` with upper bound :class:`Event`. Corresponds to a Maya message event.
        callable_ (callable[..., any]): A callable object. Can be a :obj:`functools.partial` object.
    """
    global _CALLBACK_DATA

    for registeredCallableData in _CALLBACK_DATA.callableDataRegistry[event]:
        if registeredCallableData.callable == callable_:
            _CALLBACK_DATA.callableDataRegistry[event].remove(registeredCallableData)
            break
        elif isinstance(callable_, functools.partial) and isinstance(registeredCallableData.callable, functools.partial):
            if (callable_.func == registeredCallableData.callable.func and callable_.args == registeredCallableData.callable.args
                    and callable_.keywords == registeredCallableData.callable.keywords):
                _CALLBACK_DATA.callableDataRegistry[event].remove(registeredCallableData)
                break
    else:
        log.warning("Callable {} was not found in internal registry".format(callable_))
        return

    # Remove the callback if there are no longer any registered callable
    if not _CALLBACK_DATA.callableDataRegistry[event]:
        callbackId = _CALLBACK_DATA.idRegistry[event]
        deregisterCallback = _kDeregister[type(event)]
        deregisterCallback(callbackId)
        _CALLBACK_DATA.idRegistry[event] = None

        log.debug("Removed: {} callback".format(event))


def deregisterCallableByIndex(event, index):
    """Deregisters a callable object from a Maya event based on its indexed position in the internal registry.

    **This may be useful if all references to the callable were lost.**

    If this was the only callable registered to the derived :class:`Event` enumeration, the callback associated with that event will be removed.

    Args:
        event (T <= :class:`Event`): An enumeration of type ``T`` with upper bound :class:`Event`. Corresponds to a Maya message event.
        index (:class:`int`): The index of the callable to remove. Corresponds to the order the callable was registered.
    """
    global _CALLBACK_DATA

    for registeredIndex, registeredCallableData in enumerate(_CALLBACK_DATA.callableDataRegistry[event]):
        if index == registeredIndex:
            _CALLBACK_DATA.callableDataRegistry[event].remove(registeredCallableData)

            # Remove the callback if there are no longer any registered callables
            if not _CALLBACK_DATA.callableDataRegistry[event]:
                callbackId = _CALLBACK_DATA.idRegistry[event]
                deregisterCallback = _kDeregister[type(event)]
                deregisterCallback(callbackId)
                _CALLBACK_DATA.idRegistry[event] = None

                log.debug("Removed: {} callback".format(event))
            break
    else:
        log.warning("There is no callable registered at index: {}".format(index))


def reset():
    """Removes any registered callbacks and clears any registered callables."""
    global _CALLBACK_DATA

    removedEvents = []
    for event, callbackId in _CALLBACK_DATA.idRegistry.iteritems():
        if callbackId is not None:
            deregisterCallback = _kDeregister[type(event)]
            deregisterCallback(callbackId)
            removedEvents.append(event)

    if removedEvents:
        log.debug("Removed: {} callbacks".format(removedEvents))

    _CALLBACK_DATA = _CallbackData()
    log.debug("Cleared registered callables")


# --------------------------------------------------------------
# --- Private ---
# --------------------------------------------------------------

# --- User Events ---

def _addUserEventCallback(beforeMsg, afterMsg, event, action):
    """Registers a ``Before...`` and ``After...`` Maya event for a specific :class:`UserEvent`.

    To be called exclusively by :func:`registerCallable` when a :class:`UserEvent` enumeration is given as the ``event`` argument.

    - The :class:`UserEvent` enumeration will be used to return a :obj:`functools.partial` object from the :data:`_kRegister` registry.
    - The :obj:`functools.partial` object will supply the arguments for this function.

    The :func:`_preUserEvent` callback is registered to the ``Before...`` event and is responsible for determining the user action (eg. confirm/cancel).
    The :func:`_postUserEvent` callback is registered to the ``After...`` event and is responsible for handling registered callables based on the user action.

    Args:
        beforeMsg (int): ``Before...`` message constant on the :class:`OpenMaya.MSceneMessage` class.
        afterMsg (int): ``After...`` message constant on the :class:`OpenMaya.MSceneMessage` class.
        event (:class:`UserEvent`): The event enumeration that was passed to the :func:`registerCallable` function.
        action (str): The action that will determine whether registered callables are invoked by the :func:`_postUserEvent` callback. Possible values are:

        - 'continue': Registered callables will be invoked if the user chooses to continue.
        - 'cancel': Registered callables will be invoked if the user chooses to cancel.

    Returns:
        (:class:`OpenMaya.MCallbackId`, :class:`OpenMaya.MCallbackId`): A two-element :obj:`tuple`.
        The first element is the id corresponding to the registered ``Before...`` Maya event.
        The second element is the id corresponding to the registered ``After...`` Maya event.
    """
    clientData = {"event": event, "filter": None, "action": action}
    beforeMsgCallbackId = om2.MSceneMessage.addCallback(
        beforeMsg, _preUserEvent, clientData=clientData)
    afterMsgCallbackId = om2.MSceneMessage.addCallback(
        afterMsg, _postUserEvent, clientData=clientData)

    return beforeMsgCallbackId, afterMsgCallbackId


def _preUserEvent(clientData):
    """Callback registered to the ``Before...`` Maya event for a specific :class:`UserEvent` upon calling :func:`registerCallable`.

    Args:
        clientData (dict): Data initialised by :func:`_addUserEventCallback` upon registering this callback.
            The ``'filter'`` key should be updated with a :class:`_UserEventFilter` object which holds the outcome of the user action.
            The updated :class:`dict` gets passed to the :func:`_postUserEvent` callback when the corresponding ``After...`` Maya event occurs.
    """
    event = clientData["event"]
    action = clientData["action"]
    mainWindowWidget = UI_INSPECT.getMainWindow()
    _filter = _UserEventFilter(
        event=event, action=action, parent=mainWindowWidget)
    mainWindowWidget.installEventFilter(_filter)
    clientData["filter"] = _filter


def _postUserEvent(clientData):
    """Callback registered to the ``After...`` Maya event for a specific :class:`UserEvent` upon calling :func:`registerCallable`.

    Args:
        clientData (dict): Data initialised by :func:`_addUserEventCallback` upon registering this callback.
            The ``'filter'`` key maps to a :class:`_UserEventFilter` object which was installed by the :func:`_preUserEvent` callback.
            This object should hold the outcome of the user action that corresponds to the original :class:`UserEvent` enumeration.
            If the action is confirmed, the registered callables will be invoked.
    """
    _filter = clientData["filter"]

    if not _filter.dialogSeen:
        log.warning("User prompt dialog was not shown, registered callables were not executed for the event: {}".format(clientData["event"]))

    try:
        if _filter.actionConfirmed:
            _invokeCallables(clientData["event"])
    finally:
        _filter.deleteLater()


class _UserEventFilter(QtCore.QObject):
    """Listens for a ChildAdded event which occurs when Maya calls the confirmDialog command for various events.

    Instances of this class are to be installed exclusively via the :func:`_preUserEvent` callback for a specific :class:`UserEvent` enumeration.
    The confirmDialog command creates a modal dialog in the form of a QMessageBox which prompts the user for input.
    If the user action matches the given action, the action will be confirmed for the given :class:`UserEvent` enumeration via the :attr:`_actionConfirmed` attribute.
    The :attr:`_actionConfirmed` attribute signals to the :func:`_postUserEvent` callback to invoke any registered callables.
    """

    def __init__(self, event, action, parent=None):
        super(_UserEventFilter, self).__init__(parent)
        self._event = event
        self._action = action
        self._dialogSeen = False
        self._actionConfirmed = False

    @property
    def dialogSeen(self):
        return self._dialogSeen

    @property
    def actionConfirmed(self):
        return self._actionConfirmed

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.ChildAdded:
            if isinstance(event.child(), QtWidgets.QMessageBox):
                event.child().buttonClicked.connect(self._buttonClicked)

        return QtCore.QObject.eventFilter(self, watched, event)

    def _buttonClicked(self, button):
        self._dialogSeen = True
        if button.text() == self._action:
            self._actionConfirmed = True


# --- Message Events ---

def _invokeCallables(event, *args, **kwargs):
    """A generic interface used by callbacks to invoke registered callables.

    Args:
        event (T <= :class:`Event`): An enumeration of type ``T`` with upper bound :class:`Event`. Corresponds to a Maya message event.
            Callables registered to this event will be invoked.
    """
    for callableData in _CALLBACK_DATA.callableDataRegistry[event]:
        if callableData.receivesCallbackArgs:
            callableData.callable(*args, **kwargs)
        else:
            callableData.callable()


def _MBasicFunction(*clientData):
    """A basic callback function.

    .. note:: To be used exclusively in the :data:`_kRegister` registry.

    Args:
        clientData (:class:`tuple`): This will always hold just the subclassed :class:`Event` enumeration.
            Callables registered to this event will be invoked.
    """
    event = clientData[0]
    _invokeCallables(event)


def _MStringArrayFunction(strs, *clientData):
    """A callback function that accepts a list of strings.

    .. note:: To be used exclusively in the :data:`_kRegister` registry.

    Args:
        strs (:class:`list` [:class:`str`]: Generated by the Maya event to which this callback was registered.
        clientData (:class:`tuple`): This will always hold just the subclassed :class:`Event` enumeration.
            Callables registered to this event will be invoked.
    """
    event = clientData[0]
    _invokeCallables(event, strs)


def _MTimeFunction(time, *clientData):
    """A callback function that accepts an :class:`OpenMaya.MTime` argument.

    .. note:: To be used exclusively in the :data:`_kRegister` registry.

    Args:
        time (:class:`OpenMaya.MTime`): Generated by the Maya event to which this callback was registered.
        clientData (:class:`tuple`): This will always hold just the subclassed :class:`Event` enumeration.
            Callables registered to this event will be invoked.
    """
    event = clientData[0]
    _invokeCallables(event, time)


def _MNodeFunction(node, *clientData):
    """A callback function that accepts an :class:`OpenMaya.MObject` argument.

    .. note:: To be used exclusively in the :data:`_kRegister` registry.

    Args:
        node (:class:`OpenMaya.MObject`): Generated by the Maya event to which this callback was registered.
        clientData (:class:`tuple`): This will always hold just the subclassed :class:`Event` enumeration.
            Callables registered to this event will be invoked.
    """
    event = clientData[0]
    _invokeCallables(event, node)


def _MPlugFunction(sourcePlug, destPlug, made, *clientData):
    """A callback function that accepts two :class:`OpenMaya.MPlug` objects and a boolean value.

    .. note:: To be used exclusively in the :data:`_kRegister` registry.

    Args:
        sourcePlug (:class:`OpenMaya.MObject`): Plug which is the source the connection. Generated by the Maya event to which this callback was registered.
        destPlug (:class:`OpenMaya.MObject`): Plug which is the destination the connection. Generated by the Maya event to which this callback was registered.
        made (bool): True if the connection is being made, False if the connection is being broken. Generated by the Maya event to which this callback was registered.
        clientData (:class:`tuple`): This will always hold just the subclassed :class:`Event` enumeration.
            Callables registered to this event will be invoked.
    """
    event = clientData[0]
    _invokeCallables(event, sourcePlug, destPlug, made)


# Registry used by registerCallable() to register a callable for a specific subclassed Event enumeration to a Maya event
_kRegister = {
    UserEvent.ConfirmedOpen: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeOpen, afterMsg=om2.MSceneMessage.kAfterOpen, event=UserEvent.ConfirmedOpen, action="Continue"),
    UserEvent.CancelledOpen: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeOpen, afterMsg=om2.MSceneMessage.kAfterOpen, event=UserEvent.CancelledOpen, action="Cancel"),
    UserEvent.ConfirmedImport: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeImport, afterMsg=om2.MSceneMessage.kAfterImport, event=UserEvent.ConfirmedImport, action="Continue"),
    UserEvent.CancelledImport: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeImport, afterMsg=om2.MSceneMessage.kAfterImport, event=UserEvent.CancelledImport, action="Cancel"),
    UserEvent.ConfirmedExport: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeExport, afterMsg=om2.MSceneMessage.kAfterExport, event=UserEvent.ConfirmedExport, action="Continue"),
    UserEvent.CancelledExport: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeExport, afterMsg=om2.MSceneMessage.kAfterExport, event=UserEvent.CancelledExport, action="Cancel"),
    UserEvent.ConfirmedSave: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeSave, afterMsg=om2.MSceneMessage.kAfterSave, event=UserEvent.ConfirmedSave, action="Continue"),
    UserEvent.CancelledSave: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeSave, afterMsg=om2.MSceneMessage.kAfterSave, event=UserEvent.CancelledSave, action="Cancel"),
    UserEvent.ConfirmedLoadReference: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeLoadReference, afterMsg=om2.MSceneMessage.kAfterLoadReference, event=UserEvent.ConfirmedLoadReference, action="Continue"),
    UserEvent.CancelledLoadReference: functools.partial(_addUserEventCallback, beforeMsg=om2.MSceneMessage.kBeforeLoadReference, afterMsg=om2.MSceneMessage.kAfterLoadReference, event=UserEvent.CancelledLoadReference, action="Cancel"),
    # ------
    SceneEvent.SceneUpdate: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kSceneUpdate, _MBasicFunction, clientData=SceneEvent.SceneUpdate),
    SceneEvent.BeforeNew: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeNew, _MBasicFunction, clientData=SceneEvent.BeforeNew),
    SceneEvent.AfterNew: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterNew, _MBasicFunction, clientData=SceneEvent.AfterNew),
    SceneEvent.BeforeOpen: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeOpen, _MBasicFunction, clientData=SceneEvent.BeforeOpen),
    SceneEvent.AfterOpen: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterOpen, _MBasicFunction, clientData=SceneEvent.AfterOpen),
    SceneEvent.BeforeImport: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeImport, _MBasicFunction, clientData=SceneEvent.BeforeImport),
    SceneEvent.AfterImport: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterImport, _MBasicFunction, clientData=SceneEvent.AfterImport),
    SceneEvent.BeforeExport: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeExport, _MBasicFunction, clientData=SceneEvent.BeforeExport),
    SceneEvent.AfterExport: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterExport, _MBasicFunction, clientData=SceneEvent.AfterExport),
    SceneEvent.BeforeSave: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeSave, _MBasicFunction, clientData=SceneEvent.BeforeSave),
    SceneEvent.AfterSave: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterSave, _MBasicFunction, clientData=SceneEvent.AfterSave),
    SceneEvent.BeforeLoadReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeLoadReference, _MBasicFunction, clientData=SceneEvent.BeforeLoadReference),
    SceneEvent.AfterLoadReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterLoadReference, _MBasicFunction, clientData=SceneEvent.AfterLoadReference),
    SceneEvent.BeforeUnloadReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeUnloadReference, _MBasicFunction, clientData=SceneEvent.BeforeUnloadReference),
    SceneEvent.AfterUnloadReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterUnloadReference, _MBasicFunction, clientData=SceneEvent.AfterUnloadReference),
    SceneEvent.BeforeImportReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeImportReference, _MBasicFunction, clientData=SceneEvent.BeforeImportReference),
    SceneEvent.AfterImportReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterImportReference, _MBasicFunction, clientData=SceneEvent.AfterImportReference),
    SceneEvent.BeforeExportReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeExportReference, _MBasicFunction, clientData=SceneEvent.BeforeExportReference),
    SceneEvent.AfterExportReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterExportReference, _MBasicFunction, clientData=SceneEvent.AfterExportReference),
    SceneEvent.BeforeCreateReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeCreateReference, _MBasicFunction, clientData=SceneEvent.BeforeCreateReference),
    SceneEvent.AfterCreateReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterCreateReference, _MBasicFunction, clientData=SceneEvent.AfterCreateReference),
    SceneEvent.BeforeRemoveReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kBeforeRemoveReference, _MBasicFunction, clientData=SceneEvent.BeforeRemoveReference),
    SceneEvent.AfterRemoveReference: functools.partial(om2.MSceneMessage.addCallback, om2.MSceneMessage.kAfterRemoveReference, _MBasicFunction, clientData=SceneEvent.AfterRemoveReference),
    SceneEvent.BeforePluginLoad: functools.partial(om2.MSceneMessage.addStringArrayCallback, om2.MSceneMessage.kBeforePluginLoad, _MStringArrayFunction, clientData=SceneEvent.BeforePluginLoad),
    SceneEvent.AfterPluginLoad: functools.partial(om2.MSceneMessage.addStringArrayCallback, om2.MSceneMessage.kAfterPluginLoad, _MStringArrayFunction, clientData=SceneEvent.AfterPluginLoad),
    SceneEvent.BeforePluginUnload: functools.partial(om2.MSceneMessage.addStringArrayCallback, om2.MSceneMessage.kBeforePluginUnload, _MStringArrayFunction, clientData=SceneEvent.BeforePluginUnload),
    SceneEvent.AfterPluginUnload: functools.partial(om2.MSceneMessage.addStringArrayCallback, om2.MSceneMessage.kAfterPluginUnload, _MStringArrayFunction, clientData=SceneEvent.AfterPluginUnload),
    # ------
    DGEvent.TimeChange: functools.partial(om2.MDGMessage.addTimeChangeCallback, _MTimeFunction, clientData=DGEvent.TimeChange),
    DGEvent.ForceUpdate: functools.partial(om2.MDGMessage.addForceUpdateCallback, _MTimeFunction, clientData=DGEvent.ForceUpdate),
    DGEvent.NodeAdded: functools.partial(om2.MDGMessage.addNodeAddedCallback, _MNodeFunction, "dependNode", clientData=DGEvent.NodeAdded),
    DGEvent.NodeRemoved: functools.partial(om2.MDGMessage.addNodeRemovedCallback, _MNodeFunction, "dependNode", clientData=DGEvent.NodeRemoved),
    DGEvent.ConnectionChange: functools.partial(om2.MDGMessage.addConnectionCallback, _MPlugFunction, clientData=DGEvent.ConnectionChange),
    DGEvent.PreConnectionChange: functools.partial(om2.MDGMessage.addPreConnectionCallback, _MPlugFunction, clientData=DGEvent.PreConnectionChange),
}


# Registry used by deregisterCallable() to deregister a callable for a specific subclassed Event enumeration from a Maya event
_kDeregister = {
    UserEvent: om2.MMessage.removeCallbacks,
    SceneEvent: om2.MMessage.removeCallback,
    DGEvent: om2.MMessage.removeCallback
}


# Cache of all Event subclasses
_kEvents = set(CLASS.iterSubclasses(Event))


# A baseclass template used by _CallableData to create a hashable P.O.D object
_CallableDataBase = collections.namedtuple("_CallableDataBase", ["callable", "receivesCallbackArgs"])


class _CallableData(_CallableDataBase):
    """A simple P.O.D class which stores data passed to :func:`registerCallable`.

    Instances of this class will be registered in the :data:`_CALLBACK_DATA` registry for a specific subclassed :class:`Event` enumeration.
    Instantiation of this class requires two arguments:

    - ``callable``: The callable object that will be invoked when the Maya event corresponding to the registered :class:`Event` enumeration occurs.
    - ``receivesCallbackArgs``: A boolean value that determines whether the callable will receive any callback arguments if they exist.

    Instances of this class are hashable via the identity of the callable member (however this value is not relied upon when checking if a callable is registered).
    """

    def __new__(cls, callable, receivesCallbackArgs=False):
        return _CallableDataBase.__new__(cls, callable, receivesCallbackArgs)

    def __hash__(self):
        return id(self.callable)


# A baseclass template used by _CallbackData to create a P.O.D object
_CallbackDataBase = collections.namedtuple("_CallbackDataBase", ["callableDataRegistry", "idRegistry"])


class _CallbackData(_CallbackDataBase):
    """A simple P.O.D class used exclusively by the global :data:`_CALLBACK_DATA` registry.

    Instances of this class store two internal registries:

    - ``callableDataRegistry``: Maps subclassed :class:`Event` enumerations to :class:`_CallableData` instances generated by :func:`registerCallable`.
        When the Maya event corresponding to a subclassed :class:`Event` enumeration occurs, all registered callables will be invoked.
    - ``idRegistry``: Maps subclassed :class:`Event` enumerations to :class:`maya.api.OpenMaya.MCallbackId` instances.
        When a callback is registered to a Maya event, the returned :class:`maya.api.OpenMaya.MCallbackId` instance is registered to the associated :class:`Event` enumeration.
    """

    def __new__(cls):
        return _CallbackDataBase.__new__(cls, {enumeration: set() for event in _kEvents for enumeration in event}, {enumeration: None for event in _kEvents for enumeration in event})


# --------------------------------------------------------------
# --- Globals ---
# --------------------------------------------------------------

if "_CALLBACK_DATA" in globals():
    # If a reload occurs, we must reset the registry manually since callbacks are registered via Enum type (ie. registry keys are invalidated)
    log.warning("Resetting global due to reload: _CALLBACK_DATA")

    removedEvents = []
    for event, callbackId in _CALLBACK_DATA.idRegistry.iteritems():
        if callbackId is not None:
            for deregisterType in _kDeregister:
                if type(event).__name__ == deregisterType.__name__:
                    deregisterCallback = _kDeregister[deregisterType]
                    deregisterCallback(callbackId)
            removedEvents.append(type(event).__name__)

    if removedEvents:
        log.warning("Removed: {} callbacks due to reload".format(removedEvents))

    _CALLBACK_DATA = _CallbackData()
    log.warning("Cleared any registered callables due to reload")
else:
    log.debug("Initializing global: _CALLBACK_DATA")
    _CALLBACK_DATA = _CallbackData()


# --------------------------------------------------------------
# --- Examples ---
# --------------------------------------------------------------

if __name__ == "__main__":

    def _example(*args, **kwargs):
        print "example", args, kwargs

    # _example will be called with no parameters
    registerCallable(SceneEvent.AfterNew, _example)
    # _example will be called with the [sourcePlug, destPlug, made] callback parameters
    registerCallable(DGEvent.ConnectionChange, _example,
                     receivesCallbackParameters=True)
    # _example will be called with the "param" string as well as the [sourcePlug, destPlug, made] callback parameters
    registerCallable(DGEvent.ConnectionChange, functools.partial(
        _example, "param"), receivesCallbackParameters=True)
