"""
General purpose utility functions relating to modules.

----------------------------------------------------------------
"""
import logging
import sys
import types
log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# --- Reload ---
# ----------------------------------------------------------------------------

@log.timeit(logging.DEBUG)
def deepReload(module):
    """Reload a module then recursively reload everything imported by that module.

    Note:
        Use at your own risk, always take care when reloading modules.

    Args:
        module (:data:`types.ModuleType`): Module to recursively reload.
    """
    reload(module)
    log.debug("Reloaded module: {}".format(module.__name__))

    for attribute in dir(module):
        value = getattr(module, attribute)
        if isinstance(value, types.ModuleType):
            deepReload(value)


@log.timeit(logging.DEBUG)
def reloadPackage(packageName):
    """Reload all imported modules for a given package.

    Note:
        Use at your own risk, always take care when reloading modules.

    Args:
        packageName (:class:`basestring`): The name of a package.
    """
    # Iterate copy in case reloading modifies the dict
    for moduleName, module in sys.modules.items():
        if not moduleName.startswith(packageName):
            continue

        # If the module is not in a package directory (ie. no __init__.py) it will not receive the __file__ attribute
        if not hasattr(module, "__file__"):
            continue

        # sys.modules may contain NoneType entries, see the following post
        # https://stackoverflow.com/questions/1958417/why-are-there-dummy-modules-in-sys-modules
        if not isinstance(module, types.ModuleType):
            continue

        try:
            reload(module)
            log.debug("Reloaded module: {}".format(moduleName))
        except StandardError:
            log.debug("Failed to reload module: {}".format(moduleName))
