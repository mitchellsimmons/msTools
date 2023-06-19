"""
Enviornment setup for the msTools package:

- Update system paths.
- Load plugins.
- Configure custom logging.
- Install tools.

----------------------------------------------------------------
"""
import imp
import os
import sys
import logging

from maya import utils, cmds


# ----------------------------------------------------------------------------
# --- CONSTANTS ---
# ----------------------------------------------------------------------------

PACKAGE_NAME = "msTools"
UI_PACKAGE_NAME = "msToolsUI"

# All userSetup.py files are executed with an `execfile` call from %PROGRAMFILES%\Autodesk\Maya2019\Python\Lib\site-packages\maya\app\startup\basic.py
# The file is executed from `__main__` therefore `__file__` is not part of its namespace
# We can query the path with `cmds.getModulePath` or we could set an environment variable in the .mod file using the relative `+:=` path syntax and query with `os.environ`
MODULE_DIR_NAME = os.path.abspath(cmds.getModulePath(moduleName=PACKAGE_NAME))
ROOT_PACKAGE_DIR_NAME = os.path.dirname(MODULE_DIR_NAME)
CONFIG_FILE_NAME = os.path.join(MODULE_DIR_NAME, "config.py")

# Settings
CONFIG = imp.load_source('msTools_config', CONFIG_FILE_NAME)


# ----------------------------------------------------------------------------
# --- Paths ---
# ----------------------------------------------------------------------------

def _addRootPackagePath():
    """Adds the root `msTools` package to the Python system paths"""
    if ROOT_PACKAGE_DIR_NAME not in sys.path:
        logging.info("Adding to system paths: {}".format(ROOT_PACKAGE_DIR_NAME))
        sys.path.append(ROOT_PACKAGE_DIR_NAME)


# ----------------------------------------------------------------------------
# --- Plugins ---
# ----------------------------------------------------------------------------

def _loadPlugins(*pluginNames):
    """Loads plugin dependencies"""
    for pluginName in pluginNames:
        if not cmds.pluginInfo(pluginName, q=True, loaded=True):
            try:
                cmds.loadPlugin(pluginName)
            except RuntimeError:
                raise RuntimeError("Plug-in, \"{}\", was not found on MAYA_PLUG_IN_PATH and is required for use with {}. Ensure it is available then restart Maya.".format(pluginName, PACKAGE_NAME))


# ----------------------------------------------------------------------------
# --- Logging ---
# ----------------------------------------------------------------------------

def _configureLogging():
    """Configures a logging handler for the `msTools` package.

    Logging must be setup before any of the `msTools` module loggers are created (ie. before imports).
    This is because we are extending the default capability of all future logger instances.

    This setup does not alter the functionality of existing handlers.
    """
    # Maya creates two default handlers for the root logger (see implementation: https://github.com/cgrebeld/pymel/blob/master/maya/utils.py)
    # - GUI handler (script editor), outputs using OpenMaya.MGlobal
    # - Shell handler (sys.stdout stream), outputs critical log records only
    # To prevent the GUI handler from outputting messages produced by `msTools`
    # - We can disable propagation from our package loggers and add the shell handler directly
    # - Or add a filter to the root logger to ignore log records from our package

    logging.info("Configuring logging for {}".format(PACKAGE_NAME))

    # Load module directly, avoiding additional module imports
    # We want to set our custom logger class before instantiating of loggers
    loggingUtilsPath = os.path.abspath(os.path.join(ROOT_PACKAGE_DIR_NAME, "msTools", "core", "py", "logging_utils.py"))
    LOG = imp.load_source("msTools_py_logging_utils", loggingUtilsPath)

    # Extend the current logging class
    logging.setLoggerClass(LOG.Logger)

    # Retrieve loggers
    packageLogger = logging.getLogger(PACKAGE_NAME)
    uiPackageLogger = logging.getLogger(UI_PACKAGE_NAME)

    # Set level
    packageLogger.setLevel(CONFIG.LOGGING_LEVEL)
    uiPackageLogger.setLevel(CONFIG.LOGGING_LEVEL)

    # Add a handler for our package
    packageHandler = logging.StreamHandler(sys.stdout)
    packageFormatter = logging.Formatter(CONFIG.LOGGING_FORMAT)
    packageHandler.setFormatter(packageFormatter)
    packageLogger.addHandler(packageHandler)
    uiPackageLogger.addHandler(packageHandler)

    # Disable propagation to the root logger (GUI and shell handlers)
    packageLogger.propagate = False
    uiPackageLogger.propagate = False

    # Enable outputting to the shell only
    packageLogger.addHandler(utils.shellLogHandler())
    uiPackageLogger.addHandler(utils.shellLogHandler())


# ----------------------------------------------------------------------------
# --- Install ---
# ----------------------------------------------------------------------------

def _installMenu():
    """Creates a menu for for the toolset"""
    from msTools.tools.menu import setup
    setup.install()


def _installNodeEditorExtensions():
    from msTools.tools.nodeEditorExtensions import setup
    setup.install()


def _installUuidManager():
    from msTools.tools import uuid_manager
    cmds.evalDeferred(uuid_manager.install, lowestPriority=True)


# ----------------------------------------------------------------------------
# --- Setup ---
# ----------------------------------------------------------------------------

def _setup():
    logging.info("Initialising {}".format(PACKAGE_NAME))

    # Paths
    _addRootPackagePath()

    # Plugins
    _loadPlugins('polymorphicCmd', 'matrixNodes')

    # Logging
    _configureLogging()

    # Tools
    if CONFIG.INSTALL_MENU:
        _installMenu()
    if CONFIG.INSTALL_NODE_EDITOR_EXTENSIONS:
        _installNodeEditorExtensions()
    if CONFIG.INSTALL_UUID_MANAGER:
        _installUuidManager()


if __name__ == "__main__":
    utils.executeDeferred(_setup)
