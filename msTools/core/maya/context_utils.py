"""
Create context managers for use in Maya.

----------------------------------------------------------------

Usage
-----

    Context managers are used to encapsulate a code block in a specific context.
    They allow for a temporary state to exist while code is being executed and are initialised as follows::

        with Context(args):
            completeActionsWithinContext()

.. -------------------------------------------------------------

    Dev Notes
    ---------

    There are three special methods to consider:

        ``__init__``:
            - Cache any args which are required to enter/exit the temporary state.

        ``__enter__``:
            - Implicitly called when a context instance comes after a ``with`` statement.
            - Used to enter the temporary context.

        ``__exit__``:
            - Implicitly called once the code block terminates.
            - Used to exit the temporary context.
            - Usually restores an initial state that was previously cached upon initialisation.
            - Can be used to handle exceptions that may have been raised within the context.
            - Exception status is passed via three arguments:
                - The exception type - eg. ``RuntimeError``.
                - The exception value - instance of the exception type, allows you to test if the exception was raised with a value (ie. ``str(exc_val)``).
                    ``exc_type == type(exc_value)``.
                - The traceback object - info on source of exception.
            - If the function returns a falsy value, any exception it receives will be propogated up the calling stack.
            - If the function returns a truthy value, the exception will be supressed.

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

# Absolute imports relative to root - avoid circular references
import msTools


# --------------------------------------------------------------
# --- Disable ---
# --------------------------------------------------------------

class DisableCycleChecks(object):
    """Context manager for temporarily disabling cycle checks.

    Designed for situations where a benign cycle is known to momentarily occur.
    Should not be used to supress warnings resulting from malign cycles.
    """

    def __init__(self):
        """Initialize the context."""
        pass

    def __enter__(self):
        self._cycleState = cmds.cycleCheck(q=True, evaluation=True)
        cmds.cycleCheck(evaluation=False)

    def __exit__(self, *_):
        cmds.cycleCheck(evaluation=self._cycleState)
        if self._cycleState is False:
            log.info("Cycle checks are disabled after exiting context, use the following to enable : `cmds.cycleCheck(e=True)`")


class DisableFilePrompting(object):
    """Context manager for temporarily disabling file prompting.

    Note:
        File prompting dialogs include error messages that require user confirmation and missing file reference dialogs.
    """

    def __init__(self):
        """Initialize the context."""
        pass

    def __enter__(self):
        self._oldstate = cmds.file(q=True, prompt=True)
        cmds.file(prompt=False)

    def __exit__(self, *_):
        cmds.file(prompt=self._oldstate)
        if self._oldstate is False:
            log.info("File prompting is disabled after exiting context, use the following to enable : `cmds.file(prompt=True)`")


class DisableUndoQueue(object):
    """Context manager for temporarily disabling the undo queue."""

    def __init__(self, flush=True):
        """Initialize the context by specifying whether the undo queue will be flushed upon entering the context.

        Warning:
            Performing destructive operations whilst the undo queue is disabled and unflushed can produce an unstable state once the queue is re-enabled.
            Maya may be unable to properly reconstruct the former state of the scene when undoing operations that try to bypass some destructive action.

        Args:
            flush (:class:`bool`, optional): If :data:`True`, flush the undo queue upon entering the context, otherwise leave the queue unflushed.
                Defaults to :data:`True`.
        """
        self._flush = flush

    def __enter__(self):
        self._undoState = cmds.undoInfo(q=True, stateWithoutFlush=True)

        if self._flush:
            cmds.undoInfo(state=False)
        else:
            cmds.undoInfo(stateWithoutFlush=False)

    def __exit__(self, *_):
        if self._flush:
            cmds.undoInfo(state=self._undoState)
        else:
            cmds.undoInfo(stateWithoutFlush=self._undoState)

        if self._undoState is False:
            log.info("Undo queue is disabled after exiting context, use the following command to enable : `cmds.undoInfo(stateWithoutFlush=True)`")


# --------------------------------------------------------------
# --- Restore ---
# --------------------------------------------------------------

class RestoreSelection(object):
    """Context manager for restoring an initial selection after completing some actions which affect the active selection list."""

    def __init__(self):
        """Initialize the context."""
        pass

    def __enter__(self):
        self._initialSelection = om2.MGlobal.getActiveSelectionList()

    def __exit__(self, *_):
        om2.MGlobal.setActiveSelectionList(self._initialSelection)


# --------------------------------------------------------------
# --- Set ---
# --------------------------------------------------------------

class SetActiveNamespace(object):
    """Context manager for temporarily changing the active namespace.

    Useful if you want to create some nodes and have them automatically assigned to a namespace.
    """

    def __init__(self, namespace):
        """Initialize the context with a namespace to activate upon entering.

        Args:
            namespace (:class:`basestring`): Absolute or relative namespace.

                - If absolute, a leading ``':'`` representing the root namespace must be used.
                - If relative, ``namespace`` must be a child of the current namespace.
        """
        self._namespace = namespace

    def __enter__(self):
        self._oldNamespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=self._namespace)

    def __exit__(self, *_):
        cmds.namespace(setNamespace=self._oldNamespace)


class SetActiveUnit(object):
    """Context manager for temporarily changing the current units."""

    def __init__(self, angle=None, linear=None, time=None):
        """Initialize the context with units to set upon entering.

        Only unit types with non-:data:`None` values will be changed upon entering the context.

        Args:
            angle (:class:`basestring`, optional): Set the current angular unit. Valid values are
                ``'deg'``, ``'degree'``, ``'rad'``, ``'radian'``. Defaults to :data:`None`.
            linear (:class:`basestring`, optional): Set the current linear unit. Valid values are
                ``'mm'``, ``'millimeter'``, ``'cm'``, ``'centimeter'``, ``'m'``, ``'meter'``, ``'km'``, ``'kilometer'``,
                ``'in'``, ``'inch'``, ``'ft'``, ``'foot'``, ``'yd'``, ``'yard'``, ``'mi'``, ``'mile'``. Defaults to :data:`None`.
            time (:class:`basestring`, optional): Set the current time unit. Valid values are
                ``'hour'``, ``'min'``, ``'sec'``, ``'millisec'``, ``'game'``, ``'film'``, ``'pal'``, ``'ntsc'``, ``'show'``, ``'palf'``,
                ``'ntscf'``, ``'23.976fps'``, ``'29.97fps'``, ``'29.97df'``, ``'47.952fps'``, ``'59.94fps'``, ``'44100fps'``, ``'48000fps'``. Defaults to :data:`None`.
        """
        self._newUnits = {"angle": angle, "linear": linear, "time": time}

    def __enter__(self):
        self._oldUnits = {
            "angle": cmds.currentUnit(q=True, angle=True),
            "linear": cmds.currentUnit(q=True, linear=True),
            "time": cmds.currentUnit(q=True, time=True)
        }

        cmds.currentUnit(**self._newUnits)

    def __exit__(self, *_):
        cmds.currentUnit(**self._oldUnits)


# --------------------------------------------------------------
# --- Undo ---
# --------------------------------------------------------------

class Undo(object):
    """Context manager for encapsulating Maya commands in a chunk which will be undone upon exiting the context. Mostly useful for testing purposes.

    Note:
        The chunk is undone regardless of any exceptions raised whilst inside the context.
    """

    def __init__(self):
        """Initialize the context."""
        pass

    def __enter__(self):
        cmds.undoInfo(openChunk=True)

    def __exit__(self, *_):
        cmds.undoInfo(closeChunk=True)
        if not cmds.undoInfo(undoQueueEmpty=True, q=True):
            cmds.undo()


class UndoChunk(object):
    """Context manager for encapsulating Maya commands in an undoable chunk."""

    def __init__(self):
        """Initialize the context."""
        pass

    def __enter__(self):
        cmds.undoInfo(openChunk=True)

    def __exit__(self, *_):
        cmds.undoInfo(closeChunk=True)


class UndoOnError(object):
    """Context manager for encapsulating Maya commands in a chunk which will be undone if certain types of unhandled exceptions are raised from within the context."""

    def __init__(self, *excTypes):
        """Initialize the context with exception types to catch when entered.

        Args:
            *excTypes: Sequence of class types which are (non-strict) subclasses of :exc:`~exceptions.BaseException`.
                Unhandled exceptions of these types or any subtypes will result in all encapsulated operations being undone before the exception is propagated further.
        """
        self._excTypes = excTypes

    def __enter__(self):
        cmds.undoInfo(openChunk=True)

    def __exit__(self, excType, excVal, excTb):
        cmds.undoInfo(closeChunk=True)

        # Exception will propogate (returning None is falsy)
        if excType and issubclass(excType, self._excTypes):
            if not cmds.undoInfo(undoQueueEmpty=True, q=True):
                cmds.undo()
                log.error('{} : Unhandled exception has been caught, undo chunk has been executed before propogation'.format(excType))
            else:
                log.error('{} : Unhandled exception has been caught, no commands to undo, propogating exception'.format(excType))


class UndoItOnError(object):
    """Context manager for calling the ``undoIt()`` method on a given Maya modifier instance if certain types of unhandled exceptions are raised from within the context."""

    def __init__(self, modifier, *excTypes):
        """Initialize the context with exception types to catch when entered.

        Args:
            modifier (T): Any instance of some generic type ``T`` which conforms to Maya's modifier interface.
                Specifically implementation of ``T.doIt()`` and ``T.undoIt()`` methods are required.
                Examples of valid types ``T`` are :class:`OpenMaya.MDGModifier`, :class:`OpenMaya.MDagModifier`, ``U`` <= :class:`msTools.core.maya.om_utils.Modifier`.
            *excTypes: Sequence of class types which are (non-strict) subclasses of :exc:`~exceptions.BaseException`.
                Unhandled exceptions of these types or any subtypes will result in the invocation of ``modifier.undoIt()`` before the exception is propagated further.
        """
        self._modifier = modifier
        self._excTypes = excTypes

    def __enter__(self):
        pass

    def __exit__(self, excType, excVal, excTb):
        if excType and issubclass(excType, self._excTypes):
            self._modifier.undoIt()
            log.error('{} : Unhandled exception has been caught, undoIt function has been executed before propogation'.format(excType))


# --------------------------------------------------------------
# --- Unlock ---
# --------------------------------------------------------------

class UnlockNode(object):
    """Context manager for temporarily unlocking a dependency node.

    Note:
        Instantiated contexts are designed to be entered immediately.
        The user must ensure the encapsulated dependency node remains valid.
    """

    def __init__(self, node):
        """Intialize the context with a dependency node to unlock upon entering.

        Args:
            node (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dependency node.
        """
        msTools.core.maya.om_utils.validateNodeType(node)

        self._lockState = None
        self._node = node
        self._nodeHandle = om2.MObjectHandle(node)

    def __enter__(self):
        if not self._nodeHandle.isValid():
            raise RuntimeError("Cached dependency node is invalid")

        self._lockState = om2.MFnDependencyNode(self._node).isLocked
        if self._lockState:
            DGMod = msTools.core.maya.om_utils.MDGModifier()
            DGMod.setNodeLockState(self._node, False)
            DGMod.doIt()

    def __exit__(self, *_):
        if not self._nodeHandle.isValid():
            raise RuntimeError("Cached dependency node was deleted before the context could exit")

        if self._lockState:
            DGMod = msTools.core.maya.om_utils.MDGModifier()
            DGMod.setNodeLockState(self._node, True)
            DGMod.doIt()


class UnlockPlug(object):
    """Context manager for temporarily unlocking a plug.

    Note:
        In order to globally unlock a plug, any internally locked ancestor plug will also be unlocked.

        Instantiated contexts are designed to be entered immediately.
        The user must ensure the encapsulated dependency node plug remains valid.
    """

    def __init__(self, plug):
        """Intialize the context with a plug to unlock upon entering.

        Args:
            plug (:class:`OpenMaya.MPlug`): Encapsulation of a dependency node plug.
        """
        self._plug = plug
        self._nodeHandle = om2.MObjectHandle(plug.node())

    def __enter__(self):
        if not self._nodeHandle.isValid():
            raise RuntimeError("Cached dependency node plug is invalid")

        self._unlockedPlugHierarchy = msTools.core.maya.plug_utils.unlockGlobal(self._plug)

    def __exit__(self, *_):
        if not self._nodeHandle.isValid():
            raise RuntimeError("Cached dependency node was deleted before the context could exit")

        for unlockedPlug in self._unlockedPlugHierarchy:
            msTools.core.maya.plug_utils.setProperties(unlockedPlug, isLocked=True)
