"""
Inspect application information for the current Maya session.

----------------------------------------------------------------
"""
import sys

from maya import cmds

from msTools.vendor.Qt import __binding__, __qt_version__

from msTools.coreUI.maya import inspect_utils as UI_INSPECT


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isStudentVersion():
    """
    Returns:
        :class:`bool`: Whether the user is running a student version of Maya.
    """
    # NOTE: cmds.fileInfo("license", q=True) will only work if the scene has been saved
    mainWindowWidget = UI_INSPECT.getMainWindow()
    title = mainWindowWidget.windowTitle()
    tokens = title.split(":")
    return "Student" in tokens[0]


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def getMayaVersion():
    """
    Returns:
        :class:`str`: The version of the current Maya session.
    """
    return cmds.about(version=True)


def getOpenMayaVersion():
    """
    Returns:
        :class:`int`: The API version used by the current Maya session.
    """
    return cmds.about(apiVersion=True)


def getPythonVersion():
    """
    Returns:
        (:class:`int`, :class:`int`, :class:`int`): A three-element :class:`tuple` holding Python version data for the current Maya session.

        #. Major version.
        #. Minor version.
        #. Micro version.
    """
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def getQtVersion():
    """
    Returns:
        (:class:`int`, :class:`int`, :class:`int`): A three-element :class:`tuple` holding Qt version data for the current Maya session.

        #. Major version.
        #. Minor version.
        #. Micro version.
    """
    return tuple(int(info) for info in __qt_version__.split("."))


def getQtBinding():
    """
    Returns:
        :class:`str`: The Qt binding used by the current Maya session.
        Possible values are ``PySide``, ``PySide2``, ``PyQt4``, ``PyQt5``.
    """
    return __binding__
