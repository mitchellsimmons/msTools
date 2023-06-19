"""
Decorators for use in Maya.

----------------------------------------------------------------

Usage
-----

    Decorators are used to modify a function by wrapping it in an outer scope.
    The outer scope is often used to create a temporary context for the decorated function or complete some setup and/or teardown task.

    .. code-block:: python

        @decorator
        def foo():
            completeDecoratedActions()

----------------------------------------------------------------
"""
import logging
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

# Provides signature-preserving function decorators (mainly useful for documentation tools)
from msTools.vendor import decorator

from msTools.core.maya import callback_utils as CALLBACK


# --------------------------------------------------------------
# --- Disable ---
# --------------------------------------------------------------

@decorator.decorator
def disableCycleChecks(func, *args, **kwargs):
    """Decorator for temporarily disabling cycle checks.

    Designed for situations where a benign cycle is known to momentarily occur.
    Should not be used to supress warnings resulting from malign cycles.
    """
    cycleState = cmds.cycleCheck(q=True, evaluation=True)
    cmds.cycleCheck(evaluation=False)

    try:
        return func(*args, **kwargs)
    finally:
        cmds.cycleCheck(evaluation=cycleState)
        if cycleState is False:
            log.info("Cycle checks are disabled after exiting function, use the following to enable: `cmds.cycleCheck(e=True)`")


@decorator.decorator
def disableFilePrompting(func, *args, **kwargs):
    """Decorator for temporarily disabling file prompting.

    Note:
        File prompting dialogs include error messages that require user confirmation and missing file reference dialogs.
    """
    oldstate = cmds.file(q=True, prompt=True)
    cmds.file(prompt=False)

    try:
        return func(*args, **kwargs)
    finally:
        cmds.file(prompt=oldstate)
        if oldstate is False:
            log.info("File prompting is disabled after exiting function, use the following to enable: `cmds.file(prompt=True)`")


def disableUndoQueue(flush=True):
    """Decorator factory for producing a decorator which will temporarily disable the undo queue.

    Allows the user to specify whether the generated decorator will flush the undo queue upon disabling.

    Warning:
        Performing destructive operations whilst the undo queue is disabled and unflushed can produce an unstable state once the queue is re-enabled.
        Maya may be unable to properly reconstruct the former state of the scene when undoing operations that try to bypass some destructive action.

    Args:
        flush (:class:`bool`, optional): If :data:`True`, flush the undo queue upon calling the decorated function, otherwise leave the queue unflushed.
            Defaults to :data:`True`.

    Example:
        .. code-block:: python

            @disableUndoQueue(flush=False)
            def foo():
                \"""Completes some actions with the undo queue disabled but unflushed.\"""
                completeSomeActions()
    """
    def caller(func, *args, **kwargs):
        undoState = cmds.undoInfo(q=True, stateWithoutFlush=True)

        if flush:
            cmds.undoInfo(state=False)
        else:
            cmds.undoInfo(stateWithoutFlush=False)

        try:
            return func(*args, **kwargs)
        finally:
            if flush:
                cmds.undoInfo(state=undoState)
            else:
                cmds.undoInfo(stateWithoutFlush=undoState)

            if undoState is False:
                log.info("Undo queue is disabled after exiting function, use the following command to enable: `cmds.undoInfo(stateWithoutFlush=True)`")

    return decorator.decorator(caller)


# --------------------------------------------------------------
# --- Restore ---
# --------------------------------------------------------------

@decorator.decorator
def restoreSelection(func, *args, **kwargs):
    """Decorator for restoring an initial selection after completing some actions which affect the active selection list.

    Example:
        .. code-block:: python

            @restoreSelection
            def foo():
                \"""Creates a transform then restores the initial selection.\"""
                cmds.createNode('transform')
    """
    initialSelection = om2.MGlobal.getActiveSelectionList()

    try:
        func(*args, **kwargs)
    finally:
        om2.MGlobal.setActiveSelectionList(initialSelection)


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

@decorator.decorator
def returnNodesCreatedBy(func, *args, **kwargs):
    """Decorator whichs returns nodes created during the execution of a function.

    Simple wrapper of :func:`msTools.core.maya.callback_utils.getNodesCreatedBy`.

    Example:
        .. code-block:: python

            @returnNodesCreatedBy
            def foo():
                \"""Creates a couple of transforms and returns a list containing pointers to each.\"""
                cmds.createNode('transform')
                cmds.createNode('transform')
    """
    return CALLBACK.getNodesCreatedBy(func, *args, **kwargs)[0]


# --------------------------------------------------------------
# --- Set ---
# --------------------------------------------------------------

def setActiveNamespace(namespace):
    """Decorator factory for producing a decorator which will temporarily change the active namespace.

    Allows the user to specify which namespace the generated decorator will set active.
    Useful if you want to create some nodes and have them automatically assigned to a namespace.

    Args:
        namespace (:class:`basestring`): Absolute or relative namespace.

            - If absolute, a leading ``':'`` representing the root namespace must be used.
            - If relative, ``namespace`` must be a child of the current namespace.

    Example:
        .. code-block:: python

            @setActiveNamespace(":bar")
            def foo():
                \"""Completes some actions with ":bar" set as the active namespace.\"""
                completeSomeActions()
    """
    def caller(func, *args, **kwargs):
        oldNamespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=namespace)

        try:
            func(*args, **kwargs)
        finally:
            cmds.namespace(setNamespace=oldNamespace)

    return decorator.decorator(caller)


def setActiveUnit(angle=None, linear=None, time=None):
    """Decorator factory for producing a decorator which can temporarily change the current units.

    Allows the user to specify which units the generated decorator will change.
    Only unit types with non-:data:`None` values will be changed upon calling the decorated function.

    Args:
        angle (:class:`basestring`, optional): Set the current angular unit. Valid values are
            ``'deg'``, ``'degree'``, ``'rad'``, ``'radian'``. Defaults to :data:`None`.
        linear (:class:`basestring`, optional): Set the current linear unit. Valid values are
            ``'mm'``, ``'millimeter'``, ``'cm'``, ``'centimeter'``, ``'m'``, ``'meter'``, ``'km'``, ``'kilometer'``,
            ``'in'``, ``'inch'``, ``'ft'``, ``'foot'``, ``'yd'``, ``'yard'``, ``'mi'``, ``'mile'``. Defaults to :data:`None`.
        time (:class:`basestring`, optional): Set the current time unit. Valid values are
            ``'hour'``, ``'min'``, ``'sec'``, ``'millisec'``, ``'game'``, ``'film'``, ``'pal'``, ``'ntsc'``, ``'show'``, ``'palf'``,
            ``'ntscf'``, ``'23.976fps'``, ``'29.97fps'``, ``'29.97df'``, ``'47.952fps'``, ``'59.94fps'``, ``'44100fps'``, ``'48000fps'``. Defaults to :data:`None`.

    Example:
        .. code-block:: python

            @setActiveUnit(linear="meter")
            def foo():
                \"""Completes some actions with the linear unit set to meters.\"""
                completeSomeActions()
    """
    def caller(func, *args, **kwargs):
        newUnits = {"angle": angle, "linear": linear, "time": time}
        oldUnits = {
            "angle": cmds.currentUnit(q=True, angle=True),
            "linear": cmds.currentUnit(q=True, linear=True),
            "time": cmds.currentUnit(q=True, time=True)
        }

        cmds.currentUnit(**newUnits)

        try:
            func(*args, **kwargs)
        finally:
            cmds.currentUnit(**oldUnits)

    return decorator.decorator(caller)


# --------------------------------------------------------------
# --- Undo ---
# --------------------------------------------------------------

@decorator.decorator
def undo(func, *args, **kwargs):
    """Decorator for encapsulating Maya commands in a chunk which will be undone upon exiting the decorated function. Mostly useful for testing purposes.

    Note:
        The chunk is undone regardless of any exceptions raised from within the decorated function.

    Example:
        .. code-block:: python

            @undo
            def foo():
                \"""Creates a transform then immediately undoes the operation.\"""
                cmds.createNode('transform')
    """
    cmds.undoInfo(openChunk=True)

    try:
        func(*args, **kwargs)
    finally:
        cmds.undoInfo(closeChunk=True)
        if not cmds.undoInfo(undoQueueEmpty=True, q=True):
            cmds.undo()


def undoOnError(*exceptionTypes):
    """Decorator factory for producing a decorator which will encapsulate Maya commands in an undoable chunk.
    The chunk will be undone if certain types of unhandled exceptions are raised from within the decorated function.

    Args:
        *exceptionTypes: Sequence of class types which are (non-strict) subclasses of :exc:`~exceptions.Exception`.
            Unhandled exceptions of these types or any subtypes will result in all encapsulated operations being undone before the exception is propagated further.

    Example:
        .. code-block:: python

            @undoOnError(RuntimeError)
            def foo():
                \"""Completes some actions which will be undone if a RuntimeError is raised.\"""
                completeSomeActions()
    """
    def caller(func, *args, **kwargs):
        err = None
        cmds.undoInfo(openChunk=True)

        try:
            return func(*args, **kwargs)
        except exceptionTypes as err:
            raise
        finally:
            cmds.undoInfo(closeChunk=True)

            if err:
                excType = type(err)
                if not cmds.undoInfo(undoQueueEmpty=True, q=True):
                    cmds.undo()
                    log.error('{}: Unhandled exception has been caught during execution of: {}(), undo chunk has been executed before propogation'.format(excType, func.__name__))
                else:
                    log.error('{}: Unhandled exception has been caught during execution of: {}(), no commands to undo, propogating exception'.format(excType, func.__name__))

    return decorator.decorator(caller)
