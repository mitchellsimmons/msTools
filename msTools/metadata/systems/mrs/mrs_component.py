"""
--------------------------------

Module contains the MRS_Component subclass of Meta (part of the MRS_Rig mClassSystem)
The MRS_Component class provides a consistent framework for building and managing modular rig components
It represents the lowest level encapsulation of rig data which interface with each other to form a module

--------------------------------
"""
from datetime import datetime
from collections import defaultdict
import getpass
import os
import re
import logging
log = logging.getLogger(__name__)

from maya.api import OpenMaya as om2

from msTools.core.maya import dag_utils as DAG
from msTools.core.maya import om_utils as OM
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import decorator_utils as DECORATOR
from msTools.metadata.systems import base as BASE
from msTools.py.utils import path_utils as PY_PATH

from enum import Enum


# ----------------------------------------------------------------------------
# --- Search ---
# ----------------------------------------------------------------------------

def iterComponents(asMeta=True):
    """
    Generator for conveniently iterating over all mNodes that inherit from MRS_Component

    :param <asMeta>             [bool] If True, yield each retrieved mNode as an instantiated mClass object

    :yield                      [mNode] The retrieved mNodes, as MObjects or instantiated mClass objects
    """
    return BASE.iterMetaNodes(mTypeBases=META_TYPE.MRS_Component, asMeta=asMeta)


def iterConnectedComponents(nodes=None, selected=False, asMeta=True):
    """
    Generator for conveniently iterating over all mNodes that inherit from MRS_Component and are directly connected to any of the given inputs or currently selected nodes

    :param <nodes>              [MObject, <iterable>(MObject)] Search the given dependency nodes for connected mNodes
                                [mNode, <iterable>(mNode)] Search the given dependency mNodes for connected mNodes
    :param <selected>           [bool] If True, search selected dependency nodes as well as any of the given inputs for connected mNodes
    :param <asMeta>             [bool] If True, yield each retrieved mNode as an instantiated mClass object

    :yield                      [mNode] The retrieved mNodes, as MObjects or instantiated mClass objects
    """
    return BASE.iterConnectedMNodes(nodes, selected=selected, downstream=True, upstream=True, walk=False, mTypeBases=META_TYPE.MRS_Component, asMeta=asMeta)


def getComponentFromMember(member, asMeta=True):
    """
    Returns the dagContainer for a given member as a MObject or MRS_Component instance
    This method assumes a member is only ever connected to a single dagContainer
    A RuntimeError will be raised if no connection to a dagContainer is found or the dagContainer is not a MRS_Component mNode
    Subsequently, an error will be raised if instantiation of a MRS_Component object from a connected dagContainer fails

    :param <member>     [MObject, mNode] Search the given member for a connected component

    :return             [MObject, MRS_Component] The dagContainer as a MObject or instantiated MRS_Component object
    """
    mObj_member = member if isinstance(member, om2.MObject) else member.mObj_node
    mPlug_memberMessage = om2.MFnDependencyNode(mObj_member).findPlug("message", False)
    mPlugArray_memberMessageDests = mPlug_memberMessage.destinationsWithConversions()

    for mPlug_memberMessageDest in mPlugArray_memberMessageDests:
        if mPlug_memberMessageDest.node().hasFn(om2.MFn.kHyperLayout):
            mObj_hyperLayout = mPlug_memberMessageDest.node()
            mPlug_hyperLayoutMessage = om2.MFnDependencyNode(mObj_hyperLayout).findPlug("message", False)
            mPlugArray_hyperLayoutDests = mPlug_hyperLayoutMessage.destinationsWithConversions()

            for mPlug_hyperLayoutDest in mPlugArray_hyperLayoutDests:
                if mPlug_hyperLayoutDest.node().hasFn(om2.MFn.kDagContainer):
                    mObj_dagContainer = mPlug_hyperLayoutDest.node()
                    if asMeta:
                        return MRS_Component(mObj_dagContainer)
                    else:
                        if BASE.isMNode(mObj_dagContainer, mTypes=BASE.META_TYPE.MRS_Component):
                            return mObj_dagContainer
                        else:
                            raise RuntimeError("{} : Node has a connection to the following dagContainer however it is not tagged as a MRS_Component mNode : {}".format(
                                NAME.getNodeFullName(mObj_member), NAME.getNodeFullName(mObj_dagContainer)))

    raise RuntimeError("{} : Node has no connection to a dagContainer".format(NAME.getNodeFullName(mObj_member)))


def getComponentPath():
    """
    Returns the absolute directory path assigned to the MRS_COMPONENT_PATH environment variable
    Raises a RuntimeError if the environment variable does not exist
    """
    try:
        path = os.environ["MRS_COMPONENT_PATH"]
    except KeyError:
        raise RuntimeError("MRS_COMPONENT_PATH : Environment variable does not exist")

    return os.path.abspath(path)


def getComponentTypes():
    """Returns a list of available component types"""
    return list(PY_PATH.iterDirectories(getComponentPath(), walk=False, paths=False))


# ----------------------------------------------------------------------------
# --- MRS_Component ---
# ----------------------------------------------------------------------------

class MRS_Component(BASE.MetaDag):
    """
    A component should represent the lowest level encapsulation of rig data which provides a specific function within a module (eg. Arm_L_IK)
    A component has a clear input and output which allows it to interface with other components
    It provides functionality for creating new component types or interfacing with existing components that were built by the MRS_Rig mClassSystem

    CATEGORIES:
    A category represents a logical grouping of members based on their function within a component
    A component can choose to implement any of the pre-defined categories given by the Category enumeration
    Each category should fulfill a specific role:
        - input : Members receive data from the outputs of other components
        - output : Members provide data to the inputs of other components
        - guide : Members should provide the rigger with an interface for guiding the component to a mesh
        - guided : Members should act as an intermediary interface between the guide and control interfaces
                   When the guide is removed, its output data should be saved with the guided interface as a static cache
        - control : Members should provide the animator with a graphical interface to the rig
        - deform : Members should allow the rigger to bind a mesh to the rig

    MEMBERS:
    A member represents a node which has been added to a specific component
    A member can become associated with a category through one of the following processes:
        - DAG association : If a member is the descendant of a category hierarchy group
        - Registration : If a member is registered to a category (see registerMembers())
        - Naming : If a member contains the name of a category as a single token in its name

    UNENFORCED RULES:
    These are rules which are not enforced explicitly but are relied upon by the Meta interface for the purpose of generalisation
    If these rules are broken, certain aspects of the interface may unexpectedly fail (it is the responsibility of the user to ensure compliance)
    1. Guide members must be associated to their category through naming
        - This ensures a generalised solution can be applied to guide operations such as toggling, deguiding and reguiding
        - These operations require knowledge of the complete set of guide members

    ENFORCED RULES:
    These are rules which are explicitly enforced by the component
    Upon instantiating a MRS_Component object with an existing mNode, these rules will be enforced in order to verify the validity of the interface
    The user may also choose to complete a manual check at any point by invoking verifyInterface()
    1. Descendant transforms of the input category group are the only members allowed to be the destination of a connection from outside a component
    2. Descendant transforms of the output and deform category groups are the only members allowed to be the source of a connection to outside a component
    3. Guide data must only be sent to descendent transforms of the guided category group (this relies upon the unenforced guide naming rule)
    4. A component must always reference an existing file in the directory structure that was initially setup upon creating the componentType
    5. Each member (with exception of category groups) must be prefixed with the component description (see COMPONENT_DESCRIPTION_NAMING_CONVENTION)

    VERSIONING:
    Upon exporting a wip component, the minorVersion should be incremented unless changes are to be overridden
    Upon assetising a component, the minorVersion will be reset and the isAsset attribute will be set true
    Upon deassetising a component, the major version will be incremented and the isAsset attribute will be set false
    Upon reassetizing the component, the isAsset attribute will be set true again but the major version will remain incremented
    The minorVersion is not included in the filename of an assetised component since it is only used to track changes to wip components
    The convention allows any MRS_Rig system which is referencing a MRS_Component asset to query whether an update is required based on the major version
    """
    mClassID = "MRS_Component"
    mClassSystemID = "MRS_Rig"
    mSystemRoot = False

    # Nodes
    COMPONENT_DESCRIPTION_NAMING_CONVENTION = "{userType}_{locality}_{userSubType}_{index}"
    COMPONENT_NAMING_CONVENTION = "{description}_cmpt"
    MEMBER_NAMING_CONVENTION = "{description}_{warble}"
    MEMBER_REGISTRATION_NAMING_CONVENTION = "{category}_{classification}"
    # Files
    WIP_FILE_NAMING_CONVENTION = "{componentType}_wip_{majorVersion}_{minorVersion}_{modification}.ma"
    WIP_PATH_NAMING_CONVENTION = "{MRS_COMPONENT_PATH}\\{componentType}\\wip\\{fileName}"
    ASSET_FILE_NAMING_CONVENTION = "{componentType}_asset_{majorVersion}.ma"
    ASSET_PATH_NAMING_CONVENTION = "{MRS_COMPONENT_PATH}\\{componentType}\\asset\\{fileName}"

    class Category(Enum):
        input = 0
        output = 1
        guide = 2
        guided = 3
        control = 4
        deform = 5

    def __init__(self, node=None, componentType=None, userType=None, userSubType=None, locality=None, index=None, author=None, **kwargs):
        """
        Initialisation of MRS_Component mNodes

        :param <node>           [None] A new dagContainer node will be created and encapsulated
                                [str, MObject, MDagPath] The existing dependency node will be used by the MRS_Component object
                                    If its node type is not a dagContainer, a TypeError will be raised
                                    If it does not have valid data (eg. if any hasValidComponentType, hasValidName, hasValidMemberNames returns False), a RuntimeError will be raised
        :param <componentType>  [None] If a node is given, this parameter should be ignored
                                [str] The componentType represents a sub-directory that exists within the MRS_COMPONENT_PATH directory (environment variable)
                                    It should aim to provide a detailed description of a component (eg. bipedalLeg) to avoid clashing with other components
                                    It is used by instantiated MRS_Rig/MRS_Module objects to import components
                                    It is also used self-referentially to import/export scripts/data (eg. to reguide a component)
        :param <userType>       [None] If a node is given, this parameter should be ignored
                                [str] The userType represents a required token in the name of a component
                                    It should aim to provide a simple description of the component (eg. leg) to the end user
                                    It should obscure unnecessary detail provided by the componentType which can be inferred from the rig (eg. bipedal)
                                    It should include anatomical detail when there is a chance of repeating components (eg. indexFinger as opposed to finger)
        :param <userSubType>    [None] If a node is given or a subType is not required in the component name, this parameter should be ignored
                                [str] The userSubType represents an optional token in the name of a component
                                    It is usually provided for components which provide an assisting role in the function of another component
                                    A pre-flight component is an example of a component which may require a userSubType
        :param <locality>       [None] If a node is given, this parameter should be ignored
                                [str] The locality represents a required token in the name of a component
                                    It should describe the position of the component in relation to the rig
        :param <index>          [None] If a node is given, this parameter should be ignored
                                [int] The index represents an optional token in the name of a component
                                    It is usually provided when the userType fails to differentiate components of the same componentType (eg. chain_M_01, chain_M_02)
        :param <author>         [None] If a node is given, this parameter should be ignored
                                    If a node is not given, the author will be automatically set to the login name of the user
                                [str] Set the author for a new component
        """
        log.debug("MRS_Component.__init__(node = {}, componentType = {}, userType = {}, userSubType = {}, locality = {}, index = {}, kwargs = {})".format(
            node, componentType, userType, userSubType, locality, index, kwargs))

        name = None
        if node is None:
            # Check a new componentType was given
            if not componentType:
                raise ValueError("MRS_Component : A new componentType was not given")
            elif componentType in getComponentTypes():
                raise RuntimeError("MRS_Component : {} : componentType already exists, use MRS_Module or MRS_Rig to import".format(componentType))

            # This will raise a ValueError if any aspect of the name is invalid
            name = MRS_Component.generateComponentName(userType=userType, locality=locality, userSubType=userSubType, index=index)

        super(MRS_Component, self).__init__(node=node, name=name, nType="dagContainer", tag=True, **kwargs)

        if node is None:
            # Version
            self.addNumericAttribute(longName='minorVersion', value=0, dataType=om2.MFnNumericData.kInt)
            self.addNumericAttribute(longName='majorVersion', value=1, dataType=om2.MFnNumericData.kInt)
            # State
            self.addNumericAttribute("isGuided", value=True, dataType=om2.MFnNumericData.kBoolean)
            self.addNumericAttribute("isAsset", value=False, dataType=om2.MFnNumericData.kBoolean)
            # Name
            self.addTypedAttribute("componentType", value=componentType, dataType=om2.MFnData.kString)
            self.addTypedAttribute("userType", value=userType, dataType=om2.MFnData.kString)
            self.addTypedAttribute("userSubType", value=userSubType, dataType=om2.MFnData.kString)
            self.addTypedAttribute("locality", value=locality, dataType=om2.MFnData.kString)
            self.addNumericAttribute("index", value=index or 0, dataType=om2.MFnNumericData.kInt)  # A value of 0 should be interpreted as not given
            # File
            self.addTypedAttribute("fileName", value="", dataType=om2.MFnData.kString)  # Updated on export

            self.createDirectory(componentType)
            self.export(incrementMinorVersion=False, author=author, modification=None)

    def __repr__(self):
        return "MRS_Component(node = '{}')".format(self.partialPathName)

    def _filterNode(self, node):
        """
        Override of superclass implementation (narrows accepted node types to those inheriting from dagContainer)
        Retrieves both the MObject and MDagPath for the given input data
        To be called exclusively by Meta.__init__

        :param <node>   [str, MObject, MDagPath] The dagContainer dependency node to filter and retrieve data

        :return         [dict] Key, value pairs containing node data which will be passed to the _buildExclusiveData invocation
                            Subclass overrides must always return the following key, value assignments
                                - The MObject of the encapsulated dependency node assigned to the "mObj_node" key
                                - The MPath of the encapsulated dependency node assigned to the "mPath" key
        """
        mPath = None
        if isinstance(node, om2.MDagPath):
            mObj_node = node.node()
            mPath = node
        elif isinstance(node, om2.MObject):
            mObj_node = node
            if mObj_node.hasFn(om2.MFn.kDagNode):
                mPath = om2.MDagPath.getAPathTo(mObj_node)
                if mPath.isInstanced():
                    log.warning(("MRS_Component : Initialised with MObject for instanced DAG node, "
                                 + "all instance specific functionality will apply to the first instance in the DAG hierarchy : {}").format(mPath.partialPathName()))
        else:
            mObj_node = OM.getNodeByName(node)
            if mObj_node.hasFn(om2.MFn.kDagNode):
                mPath = OM.getPathByName(node)

        if not mObj_node.hasFn(om2.MFn.kDagContainer):
            raise TypeError("MRS_Component : Input node argument does not reference a dagContainer node")

        nodeData = {
            "mObj_node": mObj_node,
            "mPath": mPath
        }

        return nodeData

    def _createNode(self, nType):
        """
        Override of baseclass implementation
        Narrows the accepted node types to dagContainers
        To be called exclusively by Meta.__init__

        :param <nType>  [str] This will always be passed "dagContainer"

        :return         [dict] Key, value pairs containing node data which will be passed to the _buildExclusiveData invocation
                            Subclass overrides must always return the following key, value assignments
                                - The MObject of the encapsulated dependency node assigned to the "mObj_node" key
                                - The MPath of the encapsulated dependency node assigned to the "mPath" key
        """
        mObj_node = DAG.createNode(nType)
        mPath = om2.MDagPath.getAPathTo(mObj_node)

        # The "new" key is providing the _postBindUpdate call a signal that the interface does not need to be verified
        nodeData = {
            "mObj_node": mObj_node,
            "mPath": mPath,
            "new": True
        }

        return nodeData

    def _buildExclusiveData(self, **nodeData):
        """
        Overload of baseclass implementation
        To be called exclusively by Meta.__init__

        :param <nodeData>       [dict] The key, value pairs returned from _filterNode or _createNode

        :return                 [dict] The key, value pairs representing the custom data bindings for this instance
        """
        mObj_node = nodeData.get("mObj_node")
        mPath = nodeData.get("mPath")
        exclusiveData = {
            "_mFnContainer": om2.MFnContainerNode(mObj_node)
        }
        exclusiveSuperData = super(MRS_Component, self)._buildExclusiveData(mObj_node=mObj_node)
        exclusiveSuperData.update(exclusiveData)
        return exclusiveSuperData

    def _postBindUpdate(self, **nodeData):
        """
        Invoked by superclass initialisation directly after instance variables have been bound
        Used to check if a given node is compatible with the MRS_Component interface (ie. if the user is attempting to reinstantiate)
        If a certain aspect of the existing component is incompatible with this interface, the user will receive log info describing the issue

        :param <nodeData>       [dict] The key, value pairs returned from _filterNode or _createNode
        """
        if not nodeData.get("new"):
            self.verifyInterface()

    # --- Public Properties ----------------------------------------------------------------------------

    @BASE.Meta_Property
    def mFnContainer(self):
        return self._mFnContainer

    @property
    def componentType(self):
        return self.getAttr("componentType").get()

    @property
    def userType(self):
        return self.getAttr("userType").get()

    @userType.setter
    def userType(self, userType):
        self.rename(userType=userType)

    @property
    def userSubType(self):
        return self.getAttr("userSubType").get() or None

    @userSubType.setter
    def userSubType(self, userSubType):
        self.rename(userSubType=userSubType)

    @property
    def locality(self):
        return self.getAttr("locality").get()

    @locality.setter
    def locality(self, locality):
        self.rename(locality=locality)

    @property
    def index(self):
        return self.getAttr("index").get() or None

    @index.setter
    def index(self, index):
        self.rename(index=index)

    @property
    def minorVersion(self):
        return self.getAttr("minorVersion").get()

    @property
    def majorVersion(self):
        return self.getAttr("majorVersion").get()

    @property
    def author(self):
        return self.creator.get()

    @author.setter
    def author(self, author):
        self.creator = author

    @property
    def creationDate(self):
        return self.getAttr("creationDate").get()

    @property
    def fileName(self):
        return self.getAttr("fileName").get()

    @property
    def filePath(self):
        pathConvention = MRS_Component.ASSET_PATH_NAMING_CONVENTION if self.isAsset else MRS_Component.WIP_PATH_NAMING_CONVENTION
        filePath = pathConvention.format(MRS_COMPONENT_PATH=getComponentPath(), componentType=self.componentType, fileName=self.fileName)
        return os.path.abspath(filePath)

    @property
    def directoryPath(self):
        return os.path.dirname(self.filePath)

    @property
    def rootDirectoryPath(self):
        return os.path.dirname(self.directoryPath)

    @property
    def isAsset(self):
        return self.getAttr("isAsset").get()

    @property
    def isWip(self):
        return not self.isAsset

    @property
    def isBlackBoxed(self):
        return self.blackBox.get()

    @isBlackBoxed.setter
    def isBlackBoxed(self, state):
        self.blackBox = state

    @property
    def isGuided(self):
        return self.getAttr("isGuided").get()

    @isGuided.setter
    def isGuided(self, state):
        if state != self.isGuided:
            self.toggleGuide()

    @property
    def hasGuide(self):
        # Relies upon the unenforced guide naming rule
        return bool(self.getNamedMembers(MRS_Component.Category.guide))

    @property
    def hasValidComponentType(self):
        """
        Returns True if the encapsulated dagContainer has a componentType attribute which references a valid component
        A valid componentType must reference an existing component in the MRS_COMPONENT_PATH directory (environment variable)
        """
        try:
            return self.getAttr("componentType").get() in getComponentTypes()
        except RuntimeError:
            return False

    @property
    def hasValidDirectoryStructure(self):
        return MRS_Component.directoryStructureExists(self.componentType)

    @property
    def hasValidFileName(self):
        """
        Checks if the filename stored on this component references a valid file in the standard directory structure of this component type
        Checks if the filename of this component conforms to the standard component naming conventions
        """
        if not os.path.exists(self.filePath):
            return False

        requiredFileName = self.createFileName(modification="")[:-1]
        return self.fileName.startswith(requiredFileName)

    @property
    def hasValidName(self):
        """Returns True if the encapsulated dagContainer has a valid name (ie. conforms to the COMPONENT_NAMING_CONVENTION)"""
        try:
            requiredName = MRS_Component.generateComponentName(userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)
        except ValueError:
            return False

        return requiredName == self.shortName

    @property
    def hasValidMemberNames(self):
        """Returns True if all members (excluding hierarchy groups) have a valid name (ie. conforms to the MEMBER_NAMING_CONVENTION)"""
        try:
            componentDescription = MRS_Component.generateComponentDescription(
                userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)
        except ValueError:
            return False

        mNodes_members = self.getMembers(asMeta=True)
        for mNode_member in mNodes_members:
            if self.hasChild(mNode_member):
                try:
                    MRS_Component.Category[mNode_member.shortName]
                except KeyError:
                    return False
            else:
                if not mNode_member.shortName.startswith(componentDescription):
                    return False

        return True

    @property
    def hasValidEncapsulation(self):
        mNodes_members = self.getMembers(asMeta=True)
        mNodes_members.append(self)
        mObjs_members = [mNode_member.mObj_node for mNode_member in mNodes_members]
        mObjs_inputMembers = self.getDagMembers(MRS_Component.Category.input)
        mObjs_outputMembers = self.getDagMembers(MRS_Component.Category.output)

        for mNode_member in mNodes_members:
            mObjs_inputs_generator = mNode_member.iterInputNodes(excludeMessage=True)
            mObjs_outputs_generator = mNode_member.iterOutputNodes(excludeMessage=True)

            for mObj_input in mObjs_inputs_generator:
                if mObj_input not in mObjs_members:
                    if mNode_member.mObj_node not in mObjs_inputMembers:
                        return False

            for mObj_output in mObjs_outputs_generator:
                if mObj_output not in mObjs_members:
                    if mNode_member.mObj_node not in mObjs_outputMembers:
                        return False

        return True

    @property
    def hasValidGuide(self):
        # Method relies upon the unenforced guide naming rule
        mNodes_guideMembers = self.getNamedMembers(MRS_Component.Category.guide, asMeta=True)
        mObjs_guideMembers = [mNode_guideMember.mObj_node for mNode_guideMember in mNodes_guideMembers]
        mObjs_inputMembers = self.getDagMembers(MRS_Component.Category.input)
        mObjs_guidedMembers = self.getDagMembers(MRS_Component.Category.guided)

        for mNode_guideMember in mNodes_guideMembers:
            mObjs_inputs_generator = mNode_guideMember.iterInputNodes(excludeMessage=True)
            mObjs_outputs_generator = mNode_guideMember.iterOutputNodes(excludeMessage=True)

            for mObj_input in mObjs_inputs_generator:
                if mObj_input not in mObjs_guideMembers and mObj_input not in mObjs_inputMembers:
                    return False

            for mObj_output in mObjs_outputs_generator:
                if mObj_output not in mObjs_guideMembers and mObj_output not in mObjs_guidedMembers:
                    return False

        return True

    # --- Validation ----------------------------------------------------------------------------

    def validate(self, mNodeID=False):
        """
        Overload of the MetaDag baseclass function

        :param <mNodeID>        [bool] If True, validate the mNodeID (the UUID path to the DAG node) even when the encapsulated MObject is valid
                                    If the reference path to the node has changed, this should be True

        :return                 [bool] True, if the MDagPath was invalid and has been successfully revalidated
        """
        if not self.validation:
            return False

        updated = super(MRS_Component, self).validate(mNodeID)

        if updated:
            self._mFnContainer = om2.MFnContainerNode(self._mObj_node)

        return updated

    def verifyInterface(self):
        if not self.hasValidComponentType:
            raise RuntimeError("MRS_Component : {} : Component has an invalid componentType".format(self.partialPathName))
        if not self.hasValidEncapsulation:
            self.inspectEncapsulation()
            raise RuntimeError("MRS_Component : {} : Component is not encapsulated, see log info".format(self.partialPathName))
        if not self.hasValidGuide:
            self.inspectGuide()
            raise RuntimeError("MRS_Component : {} : Component does not have a valid guide, see log info".format(self.partialPathName))
        if not self.hasValidDirectoryStructure:
            self.inspectDirectoryStructure(self.componentType)
            raise RuntimeError("MRS_Component : {} : Component has an invalid directory structure, see log info".format(self.partialPathName))
        if not self.hasValidFileName:
            self.inspectFileName()
            raise RuntimeError("MRS_Component : {} : Component has an invalid filename, see log info".format(self.partialPathName))
        if not self.hasValidName or not self.hasValidMemberNames:
            self.inspectNaming()
            raise RuntimeError("MRS_Component : {} : Component or component member/s have an invalid name, see log info".format(self.partialPathName))

    # --- Directory Access ----------------------------------------------------------------------------

    @staticmethod
    def directoryStructureExists(componentType):
        componentPath = getComponentPath()
        componentTypePath = os.path.join(componentPath, componentType)
        wipDirectorPath = os.path.join(componentTypePath, "wip")
        wipScriptsDirectorPath = os.path.join(wipDirectorPath, "scripts")
        wipDataDirectorPath = os.path.join(wipDirectorPath, "data")
        assetDirectorPath = os.path.join(componentTypePath, "asset")
        assetScriptsDirectorPath = os.path.join(assetDirectorPath, "scripts")
        assetDataDirectorPath = os.path.join(assetDirectorPath, "data")
        return (os.path.exists(componentTypePath)
                and os.path.exists(wipDirectorPath) and os.path.exists(wipScriptsDirectorPath) and os.path.exists(wipDataDirectorPath)
                and os.path.exists(assetDirectorPath) and os.path.exists(assetScriptsDirectorPath) and os.path.exists(assetDataDirectorPath))

    @staticmethod
    def inspectDirectoryStructure(componentType):
        componentPath = getComponentPath()
        componentTypePath = os.path.join(componentPath, componentType)
        wipDirectorPath = os.path.join(componentTypePath, "wip")
        wipScriptsDirectorPath = os.path.join(wipDirectorPath, "scripts")
        wipDataDirectorPath = os.path.join(wipDirectorPath, "data")
        assetDirectorPath = os.path.join(componentTypePath, "asset")
        assetScriptsDirectorPath = os.path.join(assetDirectorPath, "scripts")
        assetDataDirectorPath = os.path.join(assetDirectorPath, "data")

        predMsg = {False: "does not exist", True: "exists"}
        log.info("MRS_Component : {} : Component directory {}".format(componentTypePath, predMsg[os.path.exists(componentTypePath)]))
        log.info("MRS_Component : {} : Component wip directory {}".format(wipDirectorPath, predMsg[os.path.exists(wipDirectorPath)]))
        log.info("MRS_Component : {} : Component wip scripts directory {}".format(wipScriptsDirectorPath, predMsg[os.path.exists(wipScriptsDirectorPath)]))
        log.info("MRS_Component : {} : Component wip data directory {}".format(wipDataDirectorPath, predMsg[os.path.exists(wipDataDirectorPath)]))
        log.info("MRS_Component : {} : Component asset directory {}".format(assetDirectorPath, predMsg[os.path.exists(assetDirectorPath)]))
        log.info("MRS_Component : {} : Component asset scripts directory {}".format(assetScriptsDirectorPath, predMsg[os.path.exists(assetScriptsDirectorPath)]))
        log.info("MRS_Component : {} : Component asset data directory {}".format(assetDataDirectorPath, predMsg[os.path.exists(assetDataDirectorPath)]))

    @staticmethod
    def createDirectoryStructure(componentType):
        componentPath = getComponentPath()
        componentTypePath = os.path.join(componentPath, componentType)
        wipDirectorPath = os.path.join(componentTypePath, "wip")
        wipScriptsDirectorPath = os.path.join(wipDirectorPath, "scripts")
        wipDataDirectorPath = os.path.join(wipDirectorPath, "data")
        assetDirectorPath = os.path.join(componentTypePath, "asset")
        assetScriptsDirectorPath = os.path.join(assetDirectorPath, "scripts")
        assetDataDirectorPath = os.path.join(assetDirectorPath, "data")

        if os.path.exists(componentTypePath):
            raise RuntimeError("MRS_Component : {} : Component directory already exist".format(componentTypePath))
        else:
            os.mkdir(componentTypePath)
            os.mkdir(wipDirectorPath)
            os.mkdir(wipScriptsDirectorPath)
            os.mkdir(wipDataDirectorPath)
            os.mkdir(assetDirectorPath)
            os.mkdir(assetScriptsDirectorPath)
            os.mkdir(assetDataDirectorPath)

    @staticmethod
    def getWipFiles(componentType, paths=True):
        componentPath = getComponentPath()
        componentTypePath = os.path.join(componentPath, componentType)
        wipDirectorPath = os.path.join(componentTypePath, "wip")

        if not os.path.exists(wipDirectorPath):
            raise RuntimeError("MRS_Component : {} : Component wip directory does not exist".format(wipDirectorPath))

        filteredFiles = []
        for file in PY_PATH.iterFiles(wipDirectorPath, paths=paths):
            fileName = os.path.basename(file)
            nameTokens = fileName.split("_")
            try:
                assert len(nameTokens) >= 5
                assert nameTokens[0] == componentType
                assert nameTokens[1] == "wip"
                assert nameTokens[2].isdigit()
                assert nameTokens[3].isdigit()
            except AssertionError:
                pass
            else:
                filteredFiles.append(file)

        return filteredFiles

    @staticmethod
    def getAssetFiles(componentType, paths=True):
        componentPath = getComponentPath()
        componentTypePath = os.path.join(componentPath, componentType)
        assetDirectorPath = os.path.join(componentTypePath, "asset")

        if not os.path.exists(assetDirectorPath):
            raise RuntimeError("MRS_Component : {} : Component asset directory does not exist".format(assetDirectorPath))

        filteredFiles = []
        for file in PY_PATH.iterFiles(assetDirectorPath, paths=paths):
            fileName = os.path.basename(file)
            nameTokens = fileName.split("_")
            try:
                assert len(nameTokens) == 3
                assert nameTokens[0] == componentType
                assert nameTokens[1] == "asset"
                assert nameTokens[2].isdigit()
            except AssertionError:
                pass
            else:
                filteredFiles.append(file)

        return filteredFiles

    # --- Introspect ----------------------------------------------------------------------------

    def inspectEdges(self):
        hasInputConnections = False
        hasOutputConnections = False
        mNodes_inputMembers = self.getDagMembers(MRS_Component.Category.input, asMeta=True)
        mNodes_outputMembers = self.getDagMembers(MRS_Component.Category.output, asMeta=True)

        for mNode_inputMember in mNodes_inputMembers:
            for mAttr_source, mAttr_dest in mNode_inputMember.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream, walk=False, pruneMessage=True, asMeta=True):
                hasInputConnections = True
                log.info("MRS_Component : {} : Component has the following input connection : {} -> {}".format(
                    self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

        for mNode_outputMember in mNodes_outputMembers:
            for mAttr_source, mAttr_dest in mNode_outputMember.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kDownstream, walk=False, pruneMessage=True, asMeta=True):
                hasOutputConnections = True
                log.info("MRS_Component : {} : Component has the following output connection : {} -> {}".format(
                    self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

        if not hasInputConnections:
            log.info("MRS_Component : {} : Component has no input connections".format(self.partialPathName))
        if not hasOutputConnections:
            log.info("MRS_Component : {} : Component has no output connections".format(self.partialPathName))

    def inspectEncapsulation(self):
        hasValidEncapsulation = True
        mNodes_members = self.getMembers(asMeta=True)
        mNodes_members.append(self)
        mObjs_members = [mNode_member.mObj_node for mNode_member in mNodes_members]
        mObjs_inputMembers = self.getDagMembers(MRS_Component.Category.input)
        mObjs_outputMembers = self.getDagMembers(MRS_Component.Category.output)

        for mNode_member in mNodes_members:
            # Iterate through each direct upstream connection to the member to find which ones break encapsulation
            for mAttr_source, mAttr_dest in mNode_member.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_source.mObj_node not in mObjs_members and mAttr_dest.mObj_node not in mObjs_inputMembers:
                    hasValidEncapsulation = False
                    log.info("MRS_Component : {} : Component encapsulation is broken via the following incoming data dependency : {} -> {}".format(
                        self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

            # Iterate through each direct downstream connection from the member to find which ones break encapsulation
            for mAttr_source, mAttr_dest in mNode_member.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kDownstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_dest.mObj_node not in mObjs_members and mAttr_source.mObj_node not in mObjs_outputMembers:
                    hasValidEncapsulation = False
                    log.info("MRS_Component : {} : Component encapsulation is broken via the following outgoing data dependency : {} -> {}".format(
                        self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

        if hasValidEncapsulation:
            log.info("MRS_Component : {} : Component has valid encapsulation".format(self.partialPathName))

    def inspectGuide(self):
        if not self.hasGuide:
            log.debug("MRS_Component : {} : Component does not have a guide")
            return

        # Method relies upon the unenforced guide naming rule
        hasValidGuide = True
        mNodes_guideMembers = self.getNamedMembers(MRS_Component.Category.guide, asMeta=True)
        mObjs_guideMembers = [mNode_guideMember.mObj_node for mNode_guideMember in mNodes_guideMembers]
        mObjs_inputMembers = self.getDagMembers(MRS_Component.Category.input)
        mObjs_guidedMembers = self.getDagMembers(MRS_Component.Category.guided)

        for mNode_guideMember in mNodes_guideMembers:
            # Iterate through each direct upstream connection to the guide member to find which ones are invalid
            for mAttr_source, mAttr_dest in mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_source.mObj_node not in mObjs_guideMembers and mAttr_source.mObj_node not in mObjs_inputMembers:
                    hasValidGuide = False
                    log.info("MRS_Component : {} : Component guide node has invalid input connection : {} -> {}".format(
                        self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

            # Iterate through each direct downstream connection from the guide member to find which ones are invalid
            for mAttr_source, mAttr_dest in mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kDownstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_dest.mObj_node not in mObjs_guideMembers and mAttr_dest.mObj_node not in mObjs_guidedMembers:
                    hasValidGuide = False
                    log.info("MRS_Component : {} : Component guide node has invalid output connection : {} -> {}".format(
                        self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

        if hasValidGuide:
            log.info("MRS_Component : {} : Component has a valid guide".format(self.partialPathName))

    def inspectNaming(self):
        try:
            requiredComponentDescription = self.generateComponentDescription(userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)
        except ValueError:
            log.info("MRS_Component : {} : Component has invalid cached name data : userType = {userType}, locality = {locality}, userSubType = {userSubType}, index = {index}".format(
                self.partialPathName, userType=userType, locality=locality, userSubType=userSubType, index=index))
            log.info("MRS_Component : {} : Futher inspection of component naming has failed due to invalid cached name data, exiting..".format(self.partialPathName))
            return

        requiredComponentName = cls.COMPONENT_NAMING_CONVENTION.format(description=requiredComponentDescription)

        mNodes_children = list(self.iterChildren())
        mNodes_members = self.getMembers(asMeta=True)

        # Inspect component name
        if self.shortName == requiredComponentName:
            log.info("MRS_Component : {} : Component has valid name composed from cached name data : userType = {userType}, locality = {locality}, userSubType = {userSubType}, index = {index}".format(
                self.partialPathName, userType=userType, locality=locality, userSubType=userSubType, index=index))
        else:
            log.info("MRS_Component : {} : Component name is not composed from cached name data : userType = {userType}, locality = {locality}, userSubType = {userSubType}, index = {index}".format(
                self.partialPathName, userType=userType, locality=locality, userSubType=userSubType, index=index))

        # Inspect component member names
        hasValidMemberNames = True
        for mNode_member in mNodes_members:
            if not mNode_member.shortName.startswith(requiredComponentDescription):
                if mNode_member in mNodes_children:
                    try:
                        MRS_Component.Category[mNode_member.shortName]
                    except KeyError:
                        hasValidMemberNames = False
                        log.info("MRS_Component : {} : Component contains hierarchy group with invalid name : {}".format(
                            self.partialPathName, mNode_member.partialPathName))
                else:
                    hasValidMemberNames = False
                    log.info("MRS_Component : {} : Component contains member with invalid name : {}".format(
                        self.partialPathName, mNode_member.partialPathName))

        if hasValidMemberNames:
            log.info("MRS_Component : {} : All component members have valid names".format(self.partialPathName))

    def inspectFileName(self):
        if os.path.exists(self.filePath):
            log.info("MRS_Component : {} : Component fileName references an existing file : {}".format(self.partialPathName, self.filePath))
        else:
            log.info("MRS_Component : {} : Component fileName does not reference an existing file : {}".format(self.partialPathName, self.filePath))

        requiredFileName = self.createFileName(modification="")[:-1]
        if self.fileName.startswith(requiredFileName):
            if self.isWip:
                log.info("MRS_Component : {} : Component has valid fileName \"{fileName}\" composed from cached data : componentType = {componentType}, majorVersion = {majorVersion}, minorVersion = {minorVersion}".format(
                    self.partialPathName, fileName=self.fileName, componentType=self.componentType, majorVersion=self.majorVersion, minorVersion=self.minorVersion))
            else:
                log.info("MRS_Component : {} : Component has valid fileName \"{fileName}\" composed from cached data : componentType = {componentType}, majorVersion = {majorVersion}".format(
                    self.partialPathName, fileName=self.fileName, componentType=self.componentType, majorVersion=self.majorVersion))
        else:
            if self.isWip:
                log.info("MRS_Component : {} : Component fileName \"{fileName}\" is not composed from cached data : componentType = {componentType}, majorVersion = {majorVersion}, minorVersion = {minorVersion}".format(
                    self.partialPathName, fileName=self.fileName, componentType=self.componentType, majorVersion=self.majorVersion, minorVersion=self.minorVersion))
            else:
                log.info("MRS_Component : {} : Component fileName \"{fileName}\" is not composed from cached data : componentType = {componentType}, majorVersion = {majorVersion}".format(
                    self.partialPathName, fileName=self.fileName, componentType=self.componentType, majorVersion=self.majorVersion))

    def hasCategoryGroup(self, category):
        return self.hasChildWithName(category.name)

    def getCategoryGroup(self, category, asMeta=False):
        return self.getChildByName(category.name)

    def hasMember(self, member):
        try:
            mObj_component = getComponentFromMember(member, asMeta=False)
        except RuntimeError:
            return False

        return mObj_component == self.mObj_node

    def getMembers(self, asMeta=False):
        mObjArray_members = self._mFnContainer.getMembers()
        if asMeta:
            return [BASE.getMeta(mObj_member) for mObj_member in mObjArray_members]
        else:
            return list(mObjArray_members)

    def getDagMembers(self, category, asMeta=False):
        try:
            mNode_categoryGroup = self.getChildByName(category.name)
        except RuntimeError:
            return []

        return mNode_categoryGroup.getRelativeNodes(descendants=True, asMeta=asMeta)

    def getRegisteredMembers(self, category, classification="member", asMeta=False):
        arrayBaseName = MRS_Component.MEMBER_REGISTRATION_NAMING_CONVENTION.format(category=category.name, classification=classification)
        try:
            return self.messageArray_nodes(arrayBaseName, asMeta=asMeta)
        except AttributeError:
            return []

    def getNamedMembers(self, category, asMeta=False):
        categoryName = category.name
        mObjs_members = self.getMembers()
        mObjs_namedMembers = []

        for mObj_member in mObjs_members:
            shortName = NAME.getNodeShortName(mObj_member)
            shortNameTokens = shortName.split("_")
            if categoryName in shortNameTokens:
                mObjs_namedMembers.append(mObj_member)

        if asMeta:
            return [BASE.getMeta(mObj_member) for mObj_member in mObjs_namedMembers]
        else:
            return mObjs_namedMembers

    # --- Extrospect ----------------------------------------------------------------------------

    def getInputComponents(self, asMeta=True):
        mObjs_inputComponents = []
        mNodes_inputMembers = self.getDagMembers(MRS_Component.Category.input, asMeta=True)

        for mNode_inputMember in mNodes_inputMembers:
            for mObj_inputMemberInput in mNode_inputMember.iterInputNodes():
                mObj_inputComponent = getComponentFromMember(mObj_inputMemberInput, asMeta=False)
                if mObj_inputComponent not in mObjs_inputComponents:
                    mObjs_inputComponents.append(mObj_inputComponent)

        if asMeta:
            return [MRS_Component(mObj_inputComponent) for mObj_inputComponent in mObjs_inputComponents]
        return mObjs_inputComponents

    def getOutputComponents(self, asMeta=True):
        mObjs_outputComponents = []
        mNodes_outputMembers = self.getDagMembers(MRS_Component.Category.output, asMeta=True)

        for mNode_outputMember in mNodes_outputMembers:
            for mObj_outputMemberoutput in mNode_outputMember.iterOutputNodes():
                mObj_outputComponent = getComponentFromMember(mObj_outputMemberoutput, asMeta=False)
                if mObj_outputComponent not in mObjs_outputComponents:
                    mObjs_outputComponents.append(mObj_outputComponent)

        if asMeta:
            return [MRS_Component(mObj_outputComponent) for mObj_outputComponent in mObjs_outputComponents]
        return mObjs_outputComponents

    def getModule(self):
        try:
            parentMNode = self.getParent()
        except RuntimeError:
            pass
        else:
            if type(parentMNode) is BASE.getMTypes().MRS_Module:
                return parentMNode

        raise RuntimeError("MRS_Component : {} : Component has no associated module".format(self.partialPathName))

    def getRig(self):
        try:
            parentMNode = self.getParent()
        except RuntimeError:
            pass
        else:
            if type(parentMNode) is BASE.getMTypes().MRS_Rig:
                return parentMNode
            if type(parentMNode) is BASE.getMTypes().MRS_Module:
                try:
                    return parentMNode.getRig()
                except RuntimeError:
                    pass

        raise RuntimeError("MRS_Component : {} : Component has no associated rig".format(self.partialPathName))

    # --- Add ------------------------------------------------------------------------------------

    def addCategoryGroup(self, category):
        if self.hasCategoryGroup(category):
            raise RuntimeError("MRS_Component : {} : Component already has category hierarchy group : {}".format(self.partialPathName, category.name))

        mObj_categoryGroup = DAG.createNode()
        self.addChild(mObj_categoryGroup)
        DG.remameNode(mObj_categoryGroup, category.name)

    @DECORATOR.undoOnError(StandardError)
    def addMembers(self, members=None, selected=False, force=True):
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # Validate
        componentDescription = MRS_Component.generateComponentDescription(
            userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)

        for mObj_member in mObjs_members:
            if mObj_member.hasFn(om2.MFn.kDagNode):
                raise RuntimeError("MRS_Component : {} : DAG node must be parented to component, not added (see parentMembers)".format(NAME.getNodeFullName(mObj_member)))
            if not NAME.getNodeShortName(mObj_member).startswith(componentDescription):
                raise RuntimeError("MRS_Component : {} : Node has invalid member name, must begin with component description : {}".format(
                    NAME.getNodeFullName(mObj_member), componentDescription))

        # Add members to container
        memberNames = set()
        for mObj_member in mObjs_members:
            memberNames.append(NAME.getNodeFullName(mObj_member))

        cmds.container(self.partialPathName, edit=True, addNode=memberNames, force=force)

    def parentMembers(self, category, members=None, selected=False):
        mNode_categoryGroup = self.getCategoryGroup(category)
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # Validate
        componentDescription = MRS_Component.generateComponentDescription(
            userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)

        for mObj_member in mObjs_members:
            if not mObj_member.hasFn(om2.MFn.kDagNode):
                raise RuntimeError("MRS_Component : {} : Non-DAG nodes must be added to component, not parented (see addMembers) ".format(NAME.getNodeFullName(mObj_member)))
            if not NAME.getNodeShortName(mObj_member).startswith(componentDescription):
                raise RuntimeError("MRS_Component : {} : Node has invalid member name, must begin with component description : {}".format(
                    NAME.getNodeFullName(mObj_member), componentDescription))
            for mObj_descendant in DAG.iterDescendants(mObj_member):
                if not NAME.getNodeShortName(mObj_descendant).startswith(componentDescription):
                    raise RuntimeError("MRS_Component : {} : Cannot parent node which has a descendant with an invalid member name, all descendants must begin with component description : {}".format(
                        NAME.getNodeFullName(mObj_member), componentDescription))

        # Parent members to category group
        for index, mObj_member in enumerate(mObjs_members):
            if mObj_member not in mObjs_members[:index]:
                mNode_categoryGroup.addChild(mObj_member)

    # --- Remove ------------------------------------------------------------------------------------

    def removeMembers(self, members=None, selected=False):
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # Validate
        for mObj_member in mObjs_members:
            if mObj_member.hasFn(om2.MFn.kDagNode):
                raise RuntimeError("MRS_Component : {} : DAG node must be unparented from component, not removed (see unparentMembers)".format(NAME.getNodeFullName(mObj_member)))

        # Ensure each member is deregistered from all arrays
        self.deregisterMembersFromAll(members=mObjs_members)

        # Remove members from container
        memberNames = set()
        for mObj_member in mObjs_members:
            memberNames.add(NAME.getNodeFullName(mObj_member))

        cmds.container(self.partialPathName, edit=True, removeNode=memberNames)

    def unparentMembers(self, category, members=None, selected=False):
        mNode_categoryGroup = self.getCategoryGroup(category)
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # Validate
        for mObj_member in mObjs_members:
            if not mObj_member.hasFn(om2.MFn.kDagNode):
                raise RuntimeError("MRS_Component : {} : Non-DAG node must be removed from component, not unparented (see removeMembers)".format(
                    NAME.getNodeFullName(mObj_member)))
            if not mNode_categoryGroup.hasChild(mObj_member):
                raise RuntimeError("MRS_Component : {} : Component category group does not contain child member : {}".format(
                    mNode_categoryGroup.partialPathName, NAME.getNodeFullName(mObj_member)))

        # Ensure each member is deregistered from all arrays
        mObjs_membersToDeregister = mObjs_members
        for mObj_member in mObjs_members:
            mObjs_membersToDeregister += DAG.iterDescendants(mObj_member)
        self.deregisterMembersFromAll(members=mObjs_membersToDeregister)

        # Unparent members from container
        for index, mObj_member in enumerate(mObjs_members):
            if mObj_member not in mObjs_members[:index]:
                DAG.absoluteReparent(mObj_member, parent=None)

    # --- Register ------------------------------------------------------------------------------------

    def registerMembers(self, category, classification="member", members=None, selected=False):
        """
        Provides a way to register a group of related nodes which can later be retrieved using the assigned category and classification
        The user can implement naming conventions such that retrieval provides consistent results across all component types

        :param <classification>      [str] Eg. member, hierarchy, settings, parameters, buffers, transforms, shapes
        """
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # The array will ensure duplicate entries are not created (ie. no current need to check)
        arrayBaseName = MRS_Component.MEMBER_REGISTRATION_NAMING_CONVENTION.format(category=category.name, classification=classification)
        if self.messageArray_exists(arrayBaseName):
            self.messageArray_connect(mObjs_members)
        else:
            self.messageArray_extend(mObjs_members)

    @DECORATOR.undoOnError(StandardError)
    def deregisterMembers(self, category, classification="member", members=None, selected=False):
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        # Ensure we only ever attempt to remove a member from the array once
        arrayBaseName = MRS_Component.MEMBER_REGISTRATION_NAMING_CONVENTION.format(category=category.name, classification=classification)
        for index, mObj_member in enumerate(mObjs_members):
            if mObj_member not in mObjs_members[:index]:
                self.messageArray_remove(arrayBaseName, mObj_member)

    def deregisterMembersFromAll(self, members=None, selected=False):
        mObjs_members = []

        if members is not None:
            if isinstance(members, om2.MObject):
                mObjs_members = [members]
            elif issubclass(type(members), BASE.Meta):
                mObjs_members = [members.mObj_node]
            else:
                mObjs_members = [member if isinstance(member, om2.MObject) else member.mObj_node for member in members]

        if selected:
            mObjs_members += list(DG.iterSelectedNodes())

        deregistrationDict = defaultdict(list)
        for index, mObj_member in enumerate(mObjs_members):
            if mObj_member not in mObjs_members[:index]:
                mPlug_memberMessage = om2.MFnDependencyNode(mObj_member).findPlug("message", False)
                mPlugs_messageDest = mPlug_memberMessage.destinationsWithConversions()
                for mPlug_messageDest in mPlugs_messageDest:
                    if mPlug_messageDest.node() == self.mObj_node:
                        if not mPlug_messageDest.isChild and not mPlug_messageDest.isElement:
                            attrName = om2.MFnAttribute(mPlug_messageDest.attribute()).name
                            attrNameTokens = attrName.split("_")
                            if not len(attrNameTokens) == 3:
                                continue
                            try:
                                category = MRS_Component.Category[attrNameTokens[0]]
                                classification = attrNameTokens[1]
                            except KeyError:
                                continue
                            try:
                                int(tokens[2])
                            except ValueError:
                                continue

                            deregistrationDict[(category, classification)].append(mObj_member)

        for (category, classification), mObjs_members in deregistrationDict.iteritems():
            self.deregisterMembers(category=category, classification=classification, members=mObjs_members)

    # --- Naming ----------------------------------------------------------------------------------

    @classmethod
    def generateComponentDescription(cls, userType, locality, userSubType=None, index=None):
        # Check the required COMPONENT_DESCRIPTION_NAMING_CONVENTION tokens
        if not userType:
            raise ValueError("MRS_Component : userType was not given but is required to name the component")
        if not locality:
            raise ValueError("MRS_Component : locality was not given but is required to name the component")
        if index is not None and index < 1:
            raise ValueError("MRS_Component : Given index must be greater or equal to 1")

        userSubType = "" if userSubType is None else userSubType
        indexStr = "" if index is None else str(index).zfill(2)
        return re.sub(r'(.)\1+', r'\1', cls.COMPONENT_DESCRIPTION_NAMING_CONVENTION.format(
            userType=userType, locality=locality, userSubType=userSubType, index=indexStr))

    @classmethod
    def generateComponentName(cls, userType, locality, userSubType=None, index=None):
        description = cls.generateComponentDescription(userType=userType, locality=locality, userSubType=userSubType, index=index)
        return cls.COMPONENT_NAMING_CONVENTION.format(description=description)

    def generateMemberName(self, warble):
        if not warble:
            raise ValueError("MRS_Component : warble was not given but is required to name a member")

        description = MRS_Component.generateComponentDescription(userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)
        return MRS_Component.MEMBER_NAMING_CONVENTION.format(description=description, warble=warble)

    def createFileName(self, modification):
        majorVersion = str(self.majorVersion).zfill(3)
        minorVersion = str(self.minorVersion).zfill(3)
        if wip:
            fileName = MRS_Component.WIP_FILE_NAMING_CONVENTION.format(
                componentType=self.componentType, majorVersion=majorVersion, minorVersion=minorVersion, modification=modification)
        else:
            fileName = MRS_Component.ASSET_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=majorVersion)

        return fileName

    @DECORATOR.undoOnError(StandardError)
    def rename(self, userType=None, locality=None, userSubType=None, index=None):
        userType = userType if userType is not None else self.userType
        locality = locality if locality is not None else self.locality
        userSubType = userSubType if userSubType is not None else self.userSubType
        index = index if index is not None else self.index

        oldDescription = MRS_Component.generateComponentDescription(userType=self.userType, locality=self.locality, userSubType=self.userSubType, index=self.index)
        newDescription = MRS_Component.generateComponentDescription(userType=userType, locality=locality, userSubType=userSubType, index=index)
        newComponentName = MRS_Component.COMPONENT_NAMING_CONVENTION.format(description=newDescription)

        if oldDescription == newDescription:
            return

        self.rename(newComponentName)
        if self.shortName != newComponentName:
            raise RuntimeError("MRS_Component : {} : Unable to rename component, node already exists : {}".format(self.partialPathName, newComponentName))

        mObjs_members = self.getMembers()
        for mObj_member in mObjs_members:
            oldMemberName = NAME.getNodeShortName(mObj_member)
            if oldMemberName.startswith(oldDescription):
                newMemberName = newDescription + oldMemberName[len(oldDescription):]
            elif mObj_member.hasFn(om2.MFn.kTransform) and self.hasChildWithName(oldMemberName):
                try:
                    MRS_Component.Category[oldMemberName]
                    continue
                except KeyError:
                    self.inspectNaming()
                    raise RuntimeError("MRS_Component : {} : Component has category hierarchy group with invalid name, see log info".format(self.partialPathName))
            else:
                self.inspectNaming()
                raise RuntimeError("MRS_Component : {} : Component has member with invalid name, see log info".format(self.partialPathName))

            DG.renameNode(mObj_member, newMemberName)
            if NAME.getNodeShortName(mObj_member) != newMemberName:
                raise RuntimeError("MRS_Component : {} : Unable to rename component member : {}. Node already exists : {}".format(
                    self.partialPathName, oldMemberName, newMemberName))

        if userType != self.userType:
            self.getAttr("userType").set(userType)
        if locality != self.locality:
            self.getAttr("locality").set(locality)
        if userSubType != self.userSubType:
            self.getAttr("userSubType").set(userSubType)
        if index != self.index:
            self.getAttr("index").set(index)

    # --- Select ----------------------------------------------------------------------------------

    def selectMembers(self, addFirst=False, add=False):
        mObjs_members = self.getMembers()
        mSel_members = om2.MSelectionList()

        for mObj_member in mObjs_members:
            mSel_members.add(mObj_member)

        if addFirst:
            om2.MGlobal.setActiveSelectionList(mSel_members, listAdjustment=om2.MGlobal.kAddToHeadOfList)
        elif add:
            om2.MGlobal.setActiveSelectionList(mSel_members, listAdjustment=om2.MGlobal.kAddToList)
        else:
            om2.MGlobal.setActiveSelectionList(mSel_members)

    # --- Guide ----------------------------------------------------------------------------------

    def updateGuideTracking(self):
        # Method relies upon the unenforced guide naming rule
        mNodes_guideMembers = self.getNamedMembers(MRS_Component.Category.guide, asMeta=True)
        mObjs_guideMembers = [mNode_guideMember.mObj_node for mNode_guideMember in mNodes_guideMembers]
        mObjs_inputMembers = self.getDagMembers(MRS_Component.Category.input)
        mObjs_guidedMembers = self.getDagMembers(MRS_Component.Category.guided)

        for mNode_guideMember in mNodes_guideMembers:
            for mAttr_source, mAttr_dest in mNode_guideMember.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kUpstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_source.mObj_node not in mObjs_guideMembers:
                    if mAttr_source.mObj_node in mObjs_inputMembers:

                    else:
                        self.inspectGuide()
                        raise RuntimeError("MRS_Component : {} : Component does not have a valid guide, see log info".format(self.partialPathName))

            for mAttr_source, mAttr_dest in mNode_guideMember.mNode_guideMember.iterDependenciesByEdge(directionType=om2.MItDependencyGraph.kDownstream, walk=False, pruneMessage=True, asMeta=True):
                if mAttr_dest.mObj_node not in mObjs_guideMembers and mAttr_dest.mObj_node not in mObjs_guidedMembers:
                    hasValidGuide = False
                    log.info("MRS_Component : {} : Component guide node has invalid output connection : {} -> {}".format(
                        self.partialPathName, mAttr_source.partialPathName, mAttr_dest.partialPathName))

    def toggleGuide(self):
        pass

    def deguide(self, outputReguideData=True):
        pass

    def reguide(self):
        pass

    # --- Export --------------------------------------------------------------------------------

    def export(self, incrementMinorVersion=True, incrementMajorVersion=False, author=None, modification=None):
        """
        :warning        If neither version number is incremented, the most current asset will be overridden
        """
        if self.isAsset:
            raise RuntimeError("MRS_Component : {} : Assetised component cannot be exported, deassetise to export changes".format(self.partialPathName))

        if author is None:
            if not self.author:
                self.author = getpass.getuser()
        else:
            self.author = author

        self.creationDate = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if incrementMajorVersion:
            self.majorVersion = self.majorVersion + 1
            self.minorVersion = 0
        elif incrementMinorVersion:
            self.minorVersion = self.minorVersion + 1

        # We check if a modification string was given even if the minor version is 0 (ie. the user could attempt to override the initial export)
        if self.minorVersion == 0 and not modification:
            if self.majorVersion == 1:
                modification = "new"
            else:
                modification = "deassetized"
        else:
            modification = "update" if not modification else modification

        majorVersion = str(self.majorVersion).zfill(3)
        minorVersion = str(self.minorVersion).zfill(3)
        fileName = MRS_Component.WIP_FILE_NAMING_CONVENTION.format(
            componentType=self.componentType, majorVersion=majorVersion, minorVersion=minorVersion, modification=modification)
        filePath = MRS_Component.WIP_PATH_NAMING_CONVENTION.format(
            MRS_COMPONENT_PATH=getComponentPath(), componentType=self.componentType, fileName=fileName)

        self.fileName = fileName

    # --- Assetise ------------------------------------------------------------------------------

    def assetise(self):
        pass

    def deassetise(self):
        pass

    # --- Delete ---------------------------------------------------------------------------------

    def delete(self):
        pass


BASE.registerMTypeEnumeration()
BASE.registerMNodeTypes(nTypes={"dagContainer": om2.MFn.kDagContainer})
