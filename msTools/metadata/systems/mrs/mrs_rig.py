"""
--------------------------------

Module contains the MRS_Rig subclass of Meta (the main mClassSystem used by mrs modules)
Designed to provide a consistent framework for building rigs and interfacing with rig data
This framework enforces a specific structure which is designed to create extensible, modular rigs with clear inputs and outputs

--------------------------------
"""

from maya.api import OpenMaya as om2

from msTools.metadata import base as BASE


# ----------------------------------------------------------------------------
# --- Search ---
# ----------------------------------------------------------------------------

def iterRigs(asMeta=True):
    """
    Generator for conveniently iterating over all mNodes that inherit from MRS_Rig

    :param <asMeta>             [bool] If True, yield each retrieved mNode as an instantiated mClass object

    :yield                      [mNode] The retrieved mNodes, as MObjects or instantiated mClass objects
    """
    return BASE.iterMetaNodes(mTypeBases=META_TYPE.MRS_Rig, asMeta=asMeta)


def iterConnectedRigs(inputs=None, selected=False, asMeta=True):
    """
    Generator for conveniently iterating over all mNodes that inherit from MRS_Rig and are connected (directly/indirectly) to any of the inputs or currently selected nodes

    :param <inputs>             [MObject, <iterable>(MObject)] Search the given dependency nodes for connected mNodes
    :param <selected>           [bool] If True, search selected dependency nodes as well as any of the inputs for connected mNodes
    :param <asMeta>             [bool] If True, yield each retrieved mNode as an instantiated mClass object

    :yield                      [mNode] The retrieved mNodes, as MObjects or instantiated mClass objects
    """
    return BASE.iterConnectedMNodes(inputs, selected=selected, downstream=True, upstream=True, walk=True, mTypeBases=META_TYPE.MRS_Rig, asMeta=asMeta)


def iterRigSystems(asMeta=True):
    """
    Generator for conveniently iterating over all mNodes that belong to the MRS_Rig mClassSystem (eg. MRS_Component, MRS_Module, MRS_Rig)

    :param <asMeta>             [bool] If True, yield each retrieved mNode as an instantiated mClass object

    :yield                      [mNode] The retrieved mNodes, as MObjects or instantiated mClass objects
    """
    return BASE.iterMetaNodes(mTypeSystems=META_TYPE.MRS_Rig, asMeta=asMeta)


def getRigFromNode(node, asMeta=True):
    pass


# ----------------------------------------------------------------------------
# --- MRS_Rig (rigging mClassSystem) ---
# ----------------------------------------------------------------------------

class MRS_Rig(BASE.Meta):
    """
    Designed to initialise a new root object for a rig system
    Tracks default settings for a rig which would ususally be set by the user in the initial stages of a rig pipeline
    Tracks existing modules
    """
    mClassID = "MRS_Rig"
    mClassSystemID = "MRS_Rig"
    mSystemRoot = True

    def __init__(self, node=None, name=None, completions=True, **kwargs):
        """
        :param <name>       [str] If given, this should be the global name of the rig
        """
        log.debug("MRS_Rig.__init__(node = {}, name = {}, completions = {}, kwargs = {})".format(node, name, completions, kwargs))

        if name:
            name = name + "_metaRig"
        super(MRS_Rig, self).__init__(node=node, name=name, tag=True, completions=completions, **kwargs)

        # --- Settings ----------------------------------

        # Eg : Filter available modules in UI based on rigType (eg. biped, quadruped)
        self.addTypedAttribute(longName="rigType", value="")
        # Eg : Build modules using the scale unit
        self.addTypedAttribute(longName="scaleUnit", value="")
        # Eg : Build modules using given axis, mirror rig data across axis
        fields = {"+x": 0, "+y": 1, "+z": 2, "-x": 3, "-y": 4, "-z": 5}
        self.addEnumAttribute(fields=fields, longName="axisAim", default="+z")
        self.addEnumAttribute(fields=fields, longName="axisUp", default="+y")
        self.addEnumAttribute(fields=fields, longName="axisOut", default="+x")

        # --- Messages ----------------------------------

        self.addMessageAttribute(longName="master_hrc")
        self.addMessageAttribute(longName="moduleChildren", array=True)

        # --- Finalise ----------------------------------

        # Any mNode which is a network node and is part of a rigging system should be locked
        self.isLocked = True

    def addModule(self, moduleType, side):
        """Adds a new module to the rig based on the given data"""

    def delete(self):
        pass


class MRS_Module(BASE.MetaDag):
    """Designed to provide a consistent interface/framework for building modules
    A module should represent a specific combination of components which together form a rig sub-system (eg. L_Arm, L_Leg, C_Spine)
    A module has a clear input/output interface which allows it to transfer data to other modules
    """
    mClassID = "MRS_Module"
    mClassSystemID = "MRS_Rig"
    mSystemRoot = False


class MRS_Component(BASE.MetaDag):
    """Designed to provide a consistent interface/framework for building components
    A component should represent the lowest level encapsulation of rig data which provides a specific function within a module (eg. L_Arm_IK)
    A component has a clear input/output interface which allows it to communicate data to other components within the same module
    """
    mClassID = "MRS_Component"
    mClassSystemID = "MRS_Rig"
    mSystemRoot = False

    def __init__(self, node=None, name=None, completions=True, **kwargs):
        """
        :param <name>       [str] If given, this should be the global name of the rig
        """
        log.debug("MRS_Component.__init__(node = {}, name = {}, completions = {}, kwargs = {})".format(node, name, completions, kwargs))

        super(MRS_Rig, self).__init__(node=node, name=name, nType="dagContainer", tag=True, completions=completions, **kwargs)

    def assetise(self):
        pass


# ----------------------------------------------------------------------------
# --- Setup ---
# ----------------------------------------------------------------------------


# Update the mType registry
BASE.registerMTypeEnumeration()
# Update the node types registry to include DAG container nodes
BASE.registerMNodeTypes(nTypes={"dagContainer": om2.MFn.kDagContainer})
