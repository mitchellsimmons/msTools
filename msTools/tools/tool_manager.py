"""
Install and uninstall tools through a common interface.

----------------------------------------------------------------

Terminology
-----------

    The following terminology is adopted by this module.

    .. list-table::
       :widths: 25 75
       :header-rows: 1

       * - Term
         - Description
       * - `Tool type`
         - An identifier for a specific type of tool, consisting of a namespace and a name.
       * - `Installer`:
         - A callable which has been registered to a `tool type` via the :func:`installer` decorator factory.
           The callable is responsible for creating tools associated with the specified `tool type`.
       * - `Uninstaller`:
         - A callable which has been registered to a `tool type` via the :func:`uninstaller` decorator factory.
           The callable is responsible for removing tools associated with the specified `tool type`.

----------------------------------------------------------------

Decoration
----------

    Once a pair of `installer` and `uninstaller` callables have been decorated, the associated `tool type` is considered registered to this interface.
    A registered `tool type` can be used to install, uninstall and retrieve tools via this interface.

    Example:
        .. code-block:: python

            @installer("MyToolNamespace", "MyToolName")
            def installMyTool(parent=None, force=False):
                \"""Creates a tool under the given `parent` and registers it with the interface.\"""
                return QtWidgets.QDialog(parent=parent)

            @uninstaller("MyToolNamespace", "MyToolName")
            def uninstallMyTool(tool):
                \"""Removes a tool and deregisters it from the interface.\"""
                tool.deleteLater()

            # Create a tool under a parent
            parent = QtWidgets.QMainWindow()
            tool = installMyTool(parent=parent, force=False)

            # Returns the existing tool since `force=False`
            tool = install(namespace="MyToolNamespace", name="MyToolName", parent=parent, force=False)

            # Reinstalls the tool since `force=True`
            tool = installMyTool(parent=parent, force=True)

            # Uninstalls the tool
            uninstallMyTool(tool)

----------------------------------------------------------------

Installation
------------

    A tool can be installed by directly invoking a decorated `installer` or by indirectly invoking the `installer` by passing the registered `tool type` to :func:`install`.
    Either invocation will result in the installed tool being tracked within the internal tool data registry.
    Any action which results in the removal of the tool will result in the removal of the internal tool data for that tool.

----------------------------------------------------------------

Considerations
--------------

    Registered tools are retrieved dynamically from a static identifier (memory address of the c++ object).
    Refer to :func:`msTools.coreUI.qt.widget_utils.retain` for details relating to the safe handling of `Qt`_ objects.

----------------------------------------------------------------
"""
import inspect
import logging
log = logging.getLogger(__name__)

from msTools.vendor import decorator
from msTools.vendor.Qt import QtCompat

from msTools.coreUI.qt import event_utils as QT_EVENT


# ----------------------------------------------------------------------------
# --- Globals ---
# ----------------------------------------------------------------------------

# _ToolType -> _ToolCallables
_toolCallablesRegistry = {}

# _ToolType -> set([_ToolData, ...])
_toolDataRegistry = {}


# ----------------------------------------------------------------------------
# --- Decorators ---
# ----------------------------------------------------------------------------

def installer(namespace, name):
    """Decorator factory for producing a decorator which can be used to register a callable as a tool installer.

    A tool `installer` must be implemented in accordance with the following guidelines:

    1. The return value must be the installed tool, whose type is a non-strict subclass of :class:`PySide2.QtCore.QObject`.
    2. The first argument must be named ``parent`` and is responsible for receiving the tool's parent. It can be an optional argument whose default value is :data:`None`.
    3. The `installer` is allowed to implement an optional ``force`` argument which accepts a :class:`bool` value.
       The argument determines whether a tool should be reinstalled if there is already an existing tool under ``parent``.
       When an existing tool is found under ``parent``, installation will be skipped if ``force`` is :data:`False` and the existing tool will be returned.
       This argument defaults to :data:`False` if the `installer` does not choose to reimplement it.

    Args:
        namespace (:class:`basestring`): The tool namespace used to register the decorated tool `installer` within the internal `tool type` registry.
        name (:class:`basestring`): The tool name used to register the decorated tool `installer` within the internal `tool type` registry.

    Raises:
        :exc:`~exceptions.RuntimeError`: If the first argument is not named ``parent``.
        :exc:`~exceptions.RuntimeError`: If there is already an `installer` registered to the given ``namespace`` and ``name`` combination.
    """
    def decoratorGenerator(func):
        args = inspect.getargspec(func).args

        if not args or args[0] != "parent":
            raise RuntimeError("{}: Installer must implement `parent` as its first argument".format(func))

        toolType = _ToolType(namespace=namespace, name=name)

        try:
            toolCallables = _toolCallablesRegistry[toolType]
        except KeyError:
            toolCallables = _toolCallablesRegistry[toolType] = _ToolCallables()

        if toolCallables.installer:
            raise RuntimeError("Installer already registered for tool type: {}".format(toolType))
        else:
            log.debug("Registering installer for tool type: {}".format(toolType))
            toolCallables.installer = func

        return decorator.decorate(func, _InstallCaller(toolType))

    return decoratorGenerator


def uninstaller(namespace, name):
    """Decorator factory for producing a decorator which can be used to register a callable as a tool `uninstaller`.

    A tool `uninstaller` must be implemented in accordance with the following guidelines:

    1. The first argument must be named ``tool`` and is responsible for receiving the tool to uninstall.

    Args:
        namespace (:class:`basestring`): The tool namespace used to register the decorated tool `uninstaller` within the internal `tool type` registry.
        name (:class:`basestring`): The tool name used to register the decorated tool `uninstaller` within the internal `tool type` registry.

    Raises:
        :exc:`~exceptions.RuntimeError`: If the first argument is not named ``tool``.
        :exc:`~exceptions.RuntimeError`: If there is already an `uninstaller` registered to the given ``namespace`` and ``name`` combination.
    """
    def decoratorGenerator(func):
        args = inspect.getargspec(func).args

        if not args or args[0] != "tool":
            raise RuntimeError("{}: Uninstaller must implement `tool` as its first argument".format(func))

        toolType = _ToolType(namespace=namespace, name=name)

        try:
            toolCallables = _toolCallablesRegistry[toolType]
        except KeyError:
            toolCallables = _toolCallablesRegistry[toolType] = _ToolCallables()

        if toolCallables.uninstaller:
            raise RuntimeError("Uninstaller already registered for tool type: {}".format(toolType))
        else:
            log.debug("Registering uninstaller for tool type: {}".format(toolType))
            toolCallables.uninstaller = func

        return decorator.decorate(func, _UninstallCaller(toolType))

    return decoratorGenerator


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def isInstalled(namespace, name, parent=None):
    """Check if a tool corresponding to the given `tool type` is installed to a given parent.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.
        parent (T <= :class:`PySide2.QtCore.QObject`, optional): The parent object to check for a registered tool. Defaults to :data:`None` - the tool has no parent.

    Returns:
        :class:`bool`: :data:`True` if ``parent`` is the parent of a tool whose `tool type` corresponds to the given ``namespace`` and ``name``, otherwise :data:`False`.
    """
    toolType = _ToolType(namespace=namespace, name=name)
    toolDataCache = _toolDataRegistry.get(toolType, set())

    for toolData in toolDataCache:
        # We are not taking ownership of the parent therefore this tool instance is no longer safe to use
        tool = toolData.toTool()
        toolParent = tool.parent()

        if (toolParent is None) == (parent is None):
            if toolParent is None and parent is None or QtCompat.getCppPointer(toolParent) == QtCompat.getCppPointer(parent):
                return True

    return False


def install(namespace, name, parent=None, force=False):
    """Install a tool to a given parent by indirectly invoking the registered `installer` which corresponds to the given `tool type`.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.
        parent (T <= :class:`PySide2.QtCore.QObject`, optional): The parent object for the tool. Defaults to :data:`None` - the tool has no parent.
        force (:class:`bool`): Whether to reinstall the tool if one already exists under ``parent``.
            If :data:`False`, skip installation if a tool whose `tool type` corresponds to the given ``namespace`` and ``name`` already exists under ``parent``.
            Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.RuntimeError`: If the given ``namespace`` and ``name`` do not correspond to a registered `tool type`.

    Returns:
        T <= :class:`PySide2.QtCore.QObject`: A tool parented under ``parent`` whose registered `tool type` corresponds to the given ``namespace`` and ``name``.
        If ``force`` is :data:`False`, this could be an existing tool.
    """
    toolType = _ToolType(namespace=namespace, name=name)

    try:
        toolCallables = _toolCallablesRegistry[toolType]
    except KeyError:
        raise RuntimeError("{}: Tool type callables have not been registered".format(toolType))

    if not toolCallables.isComplete:
        raise RuntimeError("{}: Tool type callable is missing: {}".format(toolType, toolCallables))

    return _InstallCaller(toolType)(toolCallables.installer, parent, force=force)


def uninstall(namespace, name, parent=None):
    """Uninstall a tool from a given parent by indirectly invoking the registered `uninstaller` which corresponds to the given `tool type`.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.
        parent (T <= :class:`PySide2.QtCore.QObject`, optional): The parent object for the tool. Defaults to :data:`None` - the tool has no parent.

    Raises:
        :exc:`~exceptions.RuntimeError`: If the given ``namespace`` and ``name`` do not correspond to a registered `tool type`.

    Returns:
        The result of the registered `uninstaller`.
    """
    toolType = _ToolType(namespace=namespace, name=name)

    try:
        toolCallables = _toolCallablesRegistry[toolType]
    except KeyError:
        raise RuntimeError("{}: Tool type callables have not been registered".format(toolType))

    if not toolCallables.isComplete:
        raise RuntimeError("{}: Tool type callable is missing: {}".format(toolType, toolCallables))

    toolDataCache = _toolDataRegistry.get(toolType, set())

    for toolData in list(toolDataCache):
        # We are not taking ownership of the parent therefore this tool instance is no longer safe to use
        tool = toolData.toTool()
        toolParent = tool.parent()

        if (toolParent is None) == (parent is None):
            if toolParent is None and parent is None or QtCompat.getCppPointer(toolParent) == QtCompat.getCppPointer(parent):
                return _UninstallCaller(toolType)(toolCallables.uninstaller, toolData.toTool())


def uninstallFromAll(namespace, name):
    """Uninstall all tools corresponding to the given `tool type` by indirectly invoking the registered `uninstaller` for each existing parent.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.

    Raises:
        :exc:`~exceptions.RuntimeError`: If the given ``namespace`` and ``name`` do not correspond to a registered `tool type`.
    """
    toolType = _ToolType(namespace=namespace, name=name)

    try:
        toolCallables = _toolCallablesRegistry[toolType]
    except KeyError:
        raise RuntimeError("{}: Tool type callables have not been registered".format(toolType))

    if not toolCallables.isComplete:
        raise RuntimeError("{}: Tool type callable is missing: {}".format(toolType, toolCallables))

    toolDataCache = _toolDataRegistry.get(toolType, set())

    for toolData in list(toolDataCache):
        _UninstallCaller(toolType)(toolCallables.uninstaller, toolData.toTool())


def iterInstalled(namespace=None, name=None):
    """Iterate over tools corresponding to the given `tool type`.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.

    Yields:
        T <= :class:`PySide2.QtCore.QObject`: A tool whose `tool type` corresponds to the given ``namespace`` and ``name``.
    """
    for toolType, toolDataCache in _toolDataRegistry.items():
        if namespace is None or toolType.namespace == namespace:
            if name is None or toolType.name == name:
                for toolData in toolDataCache:
                    yield toolData.toTool()


def iterToolTypes(namespace=None):
    """Iterate over registered `tool types`.

    Args:
        namespace (:class:`basestring`, optional): A registered `tool type` namespace, used to filter the results to a specific namespace.
            Defaults to :data:`None` - yield `tool types` for all registered `tool type` namespaces.

    Yields:
        (:class:`str`, :class:`str`): A two :class:`tuple` for each `tool type`:

        1. The namespace of a registered `tool type`.
        2. The name of a registered `tool type` under the namespace.
    """
    for toolType, toolCallables in _toolCallablesRegistry.items():
        if toolCallables.isComplete:
            if namespace is None or toolType.namespace == namespace:
                yield toolType.namespace, toolType.name


def deregisterToolType(namespace=None, name=None):
    """Deregister a `tool type`.

    Designed for use when developing a tool as it is necessary to deregister a tool before reloading a module.

    Args:
        namespace (:class:`basestring`): A registered `tool type` namespace.
        name (:class:`basestring`): A registered `tool type` name.
    """
    toolType = _ToolType(namespace=namespace, name=name)

    _toolCallablesRegistry.pop(toolType, None)
    _toolDataRegistry.pop(toolType, None)


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

class _InstallCaller(object):

    def __init__(self, toolType):
        self._toolType = toolType

    def __call__(self, func, parent, force=False):
        toolCallables = _toolCallablesRegistry[self._toolType]

        if not toolCallables.isComplete:
            raise RuntimeError("{}: Tool type callable is missing: {}".format(self._toolType, toolCallables))

        try:
            toolDataCache = _toolDataRegistry[self._toolType]
        except KeyError:
            toolDataCache = _toolDataRegistry[self._toolType] = set()
        else:
            for toolData in toolDataCache:
                # We are not taking ownership of the parent therefore this tool instance is no longer safe to use
                tool = toolData.toTool()
                toolParent = tool.parent()

                if (toolParent is None) == (parent is None):
                    if toolParent is None and parent is None or QtCompat.getCppPointer(toolParent) == QtCompat.getCppPointer(parent):
                        if force:
                            _UninstallCaller(self._toolType)(toolCallables.uninstaller, toolData.toTool())
                            break
                        else:
                            log.debug("Returning existing {} tool for given parent. Use `force=True` to reinstall".format(self._toolType))
                            return toolData.toTool()

        log.debug("Installing: {}".format(self._toolType))

        tool = func(parent)
        # tool.setObjectName("{}_{}".format(tool.__class__.__name__, uuid.uuid4()))

        toolData = _ToolData.fromTool(tool)
        toolDataCache.add(toolData)
        tool.destroyed.connect(lambda: self._discardToolData(toolData))
        log.debug("Registered tool data for installed tool: {}".format(toolData))

        return tool

    def _discardToolData(self, toolData):
        try:
            _toolDataRegistry[self._toolType].remove(toolData)
            log.debug("Deregistered tool data for destroyed tool: {}".format(toolData))
        except KeyError:
            log.debug("Already deregistered tool data for destroyed tool: {}".format(toolData))


class _UninstallCaller(object):

    def __init__(self, toolType):
        self._toolType = toolType

    def __call__(self, func, tool):
        toolData = _ToolData.fromTool(tool)
        toolCallables = _toolCallablesRegistry[self._toolType]

        if not toolCallables.isComplete:
            raise RuntimeError("{}: Tool type callable is missing: {}".format(self._toolType, toolCallables))

        log.debug("Uninstalling: {}".format(self._toolType))
        QT_EVENT.postAsEvent(self._assertUninstalled, toolData, priority=QT_EVENT.EventPriority.IDLE)

        return func(tool)

    def _assertUninstalled(self, toolData):
        toolDataCache = _toolDataRegistry[self._toolType]
        assert toolData not in toolDataCache, "{}: Tool data for uninstalled tool was never removed from the internal registry".format(toolData)


class _ToolType(object):

    def __init__(self, namespace, name):
        self._namespace = namespace
        self._name = name

    def __repr__(self):
        return "{{namespace={_namespace!r}, name={_name!r}}}".format(**self.__dict__)

    def __eq__(self, other):
        if type(self) is type(other):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __hash__(self):
        return hash((self._namespace, self._name))

    @property
    def namespace(self):
        return self._namespace

    @property
    def name(self):
        return self._name


class _ToolCallables(object):

    def __init__(self, installer=None, uninstaller=None):
        self._installer = installer
        self._uninstaller = uninstaller

    def __repr__(self):
        return "{{installer={_installer}, uninstaller={_uninstaller}}}".format(**self.__dict__)

    @property
    def isComplete(self):
        return self._installer and self._uninstaller

    @property
    def installer(self):
        return self._installer

    @installer.setter
    def installer(self, installer):
        self._installer = installer

    @property
    def uninstaller(self):
        return self._uninstaller

    @uninstaller.setter
    def uninstaller(self, uninstaller):
        self._uninstaller = uninstaller


class _ToolData(object):
    """Store data required to retrieve a `Qt`_ object representation of a tool."""

    def __init__(self, ptr, class_):
        self._class = class_
        self._ptr = ptr

    def __repr__(self):
        return "{{address={_ptr}, class={_class}}}".format(**self.__dict__)

    def __eq__(self, other):
        if type(self) is type(other):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __hash__(self):
        # A class that uses multiple inheritance will produce objects that wrap multiple c++ instances
        # It cannot be guaranteed that a single pointer will uniquely identify a Python object
        # The registry using this class is responsible for ensuring each pointer identifies a unique object
        return self._ptr

    @staticmethod
    def fromTool(tool):
        return _ToolData(QtCompat.getCppPointer(tool), tool.__class__)

    def toTool(self):
        # The caller is responsible for ensuring the tool is still valid otherwise this will crash
        # Retrive by pointer to provide support for QObject tools (ie. can only get widgets by name)
        return QtCompat.wrapInstance(self._ptr, self._class)
