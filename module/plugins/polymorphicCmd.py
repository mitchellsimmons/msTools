"""
All credit to Serguei Kalentchouk

Source: https://medium.com/@k_serguei/maya-python-api-2-0-and-the-undo-stack-80b84de70551
"""

from maya.api import OpenMaya as om2

import _ctypes


def maya_useNewAPI():
    """The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.
    """
    pass


class Polymorphic(om2.MPxCommand):
    """Allows for dynamic injection of 'command-like' objects into a singular hosting command that only has to be registered once.
    The command will only host objects that share the same common interface as the `MPxCommand` base class.
    """

    kPluginCmdName = "polymorphic"

    @staticmethod
    def cmdCreator():
        return Polymorphic()

    def doIt(self, args):
        # Convert the hex string address back to long
        ptr = long(args.asString(0), 0)
        self._imp = _ctypes.PyObj_FromPtr(ptr)
        self.redoIt()

    def redoIt(self):
        self._imp.doIt()

    def undoIt(self):
        self._imp.undoIt()

    def isUndoable(self):
        return True


def initializePlugin(plugin):
    """Initialises the plugin."""
    mFnPlugin = om2.MFnPlugin(plugin)
    try:
        mFnPlugin.registerCommand(Polymorphic.kPluginCmdName, Polymorphic.cmdCreator)
    except StandardError:
        raise RuntimeError("Failed to register command: {}\n".format(Polymorphic.kPluginCmdName))


def uninitializePlugin(plugin):
    """Uninitialises the plugin."""
    mFnPlugin = om2.MFnPlugin(plugin)
    try:
        mFnPlugin.deregisterCommand(Polymorphic.kPluginCmdName)
    except StandardError:
        raise RuntimeError("Failed to unregister command: {}\n".format(Polymorphic.kPluginCmdName))
