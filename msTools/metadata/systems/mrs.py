from datetime import datetime
import getpass
import imp
import json
import logging
import os
import random
import re
import string
log = logging.getLogger(__name__)

from maya import cmds
from maya.api import OpenMaya as om2

from msTools.core.maya import attribute_utils as ATTR
from msTools.core.maya import context_utils as CONTEXT
from msTools.core.maya import dag_utils as DAG
from msTools.core.maya import dg_utils as DG
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import name_utils as NAME
from msTools.core.maya import om_utils as OM
from msTools.core.maya import plug_utils as PLUG
from msTools.core.py import path_utils as PY_PATH
from msTools.coreUI.maya import nodeEditor_utils as UI_NODE_EDITOR
from msTools.metadata.systems import base as BASE

from msTools.vendor.enum import Enum


# ----------------------------------------------------------------------------
# --- Retrieve : Component ---
# ----------------------------------------------------------------------------

def iterComponents(asMeta=False):
    """Yield dagContainer nodes tagged as any (non-strict) subclass of :class:`MetaComponent`.

    Args:
        asMeta (:class:`bool`, optional): Whether to yield each tagged dagContainer node as an `mNode` of its tagged `mType`.
            Defaults to :data:`False` - yield as :class:`OpenMaya.MObject` wrappers.

    Raises:
        :exc:`msTools.metadata.systems.base.MSystemError`: If the `mSystemId` of a tagged dagContainer node does not correspond to a registered `mSystem`.
        :exc:`msTools.metadata.systems.base.MTypeError`: If the `mTypeId` of a tagged dagContainer node does not correspond to a registered `mType` for its `mSystem`.

    Yields:
        :class:`OpenMaya.MObject` | T <= :class:`MetaComponent`: Wrappers or `mNode` encapsulations for tagged dagContainer nodes. Type is determined by ``asMeta``.
    """
    return BASE.iterMetaNodes(mTypeBases=[MetaComponent], asMeta=asMeta)


def getComponentFromMember(member, asMeta=False):
    """Return the dagContainer node of a given member. The dagContainer node must be tagged as a (non-strict) subclass of :class:`MetaComponent`.

    Args:
        member (:class:`OpenMaya.MObject`): Wrapper of a dependency node which is a member of a tagged dagContainer node.
        asMeta (:class:`bool`, optional): Whether to return the component as an `mNode` of its tagged `mType`.
            Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper of the dagContainer node.

    Returns:
        :class:`OpenMaya.MObject` | T <= :class:`MetaComponent`: Wrapper or `mNode` encapsulation of a tagged dagContainer node. Type is determined by ``asMeta``.

    Raises:
        :exc:`MSystemError`: If the `mSystemId` of the dagContainer node does not correspond to a registered `mSystem`.
        :exc:`MTypeError`: If the `mTypeId` of the dagContainer node does not correspond to a registered `mType` for its `mSystem`.
        :exc:`MTypeError`: If the `mType` of the dagContainer node does not correspond to a (non-strict) subclass of :class:`MetaComponent`.
        :exc:`~exceptions.RuntimeError`: If ``member`` is a member of an untagged dagContainer node.
        :exc:`~exceptions.RuntimeError`: If ``member`` is not a member of any dagContainer node.
    """
    memberMessagePlug = om2.MFnDependencyNode(member).findPlug("message", False)
    memberMessageDestPlugs = memberMessagePlug.destinationsWithConversions()

    for memberMessageDestPlug in memberMessageDestPlugs:
        if memberMessageDestPlug.node().hasFn(om2.MFn.kHyperLayout):
            hyperLayoutNode = memberMessageDestPlug.node()
            hyperLayoutMessagePlug = om2.MFnDependencyNode(hyperLayoutNode).findPlug("message", False)
            hyperLayoutMessageDestPlugs = hyperLayoutMessagePlug.destinationsWithConversions()

            for hyperLayoutMessageDestPlug in hyperLayoutMessageDestPlugs:
                if hyperLayoutMessageDestPlug.node().hasFn(om2.MFn.kDagContainer):
                    dagContainerNode = hyperLayoutMessageDestPlug.node()

                    try:
                        mType = BASE.getMTypeFromNode(dagContainerNode)
                    except EXC.MayaLookupError:
                        raise RuntimeError("{}: Node is connected to untagged dagContainer node: {}".format(NAME.getNodeFullName(member), NAME.getNodeFullName(dagContainerNode)))
                    else:
                        if not issubclass(mType, MetaComponent):
                            raise BASE.MTypeError("{}: Node is connected to a dagContainer node ({}) whose `mType` tag does not correspond to a component".format(NAME.getNodeFullName(member), NAME.getNodeFullName(dagContainerNode)))

                    return BASE.getMNode(dagContainerNode) if asMeta else dagContainerNode

    raise RuntimeError("{}: Node is not a component member".format(NAME.getNodeFullName(member)))


# ----------------------------------------------------------------------------
# --- Import : Component ---
# ----------------------------------------------------------------------------

# TODO:
def importComponent(componentType, componentId, wip=False, majorVersion=1, minorVersion=0, mirror=False, loadTabs=True):
    """
    componentType: eg. foot_ik_global
    componentId: eg. leg_L_foot_ik_global
    """
    # Import component by type

    # Retrieve MetaComponent mNode

    # Determine current component name

    # Rename nodes using given component name


# ----------------------------------------------------------------------------
# --- ScriptIdPreset ---
# ----------------------------------------------------------------------------

class ScriptIdPreset(object):
    """Namespace providing preset script identifiers used by the :mod:`~msTools.metadata.systems.mrs` `mSystem` to register scripts that have been designed to interface with certain methods."""

    Mirror = "mirror"
    """:class:`str`: The script identifier that should be used to register mirroring scripts with :class:`MetaComponent` and :class:`MetaModule` `mNodes`.

    Mirroring scripts should be designed to interface with the :meth:`MetaComponent.mirror` or :meth:`MetaModule.mirror` methods.

    :access: R
    """


# ----------------------------------------------------------------------------
# --- MetaComponent ---
# ----------------------------------------------------------------------------

class MetaComponent(BASE.MetaDag):
    """A dagContainer encapsulation designed to provide a high level metadata interface for components.

    **Component:**

        A component represents an encapsulation of a discrete function within a rig, such as the ik function of an arm.
        A component has a clear input and output which allows it to interface with other components.

    **Interface:**

        The metadata interface provides an encapsulation of the component via a dagContainer node.
        It provides the ability to create new components and interface with existing components.

        The interface is designed to operate directly on `OpenMaya`_ inputs as to maintain coherent type dependence.

        This `mType` is part of the `mrs` `mSystem` which also includes :class:`MetaModule` and :class:`MetaRig`.
        Relationships between these `mTypes` are registered within the dependency graph as a result of system level operations.

    **Registration:**

        A persistent tagging system is inherited from :class:`msTools.metadata.systems.base.Meta`.
        This system enables the encapsulated dependency node to be tagged as a :class:`MetaComponent` upon creation.

    **Members:**

        A member represents a node which has been added to the encapsulated dagContainer asset.

        The `class:`MemberType` enumerations correspond to distinct member types which can be used to create members via :meth:`createMemberByType`.
        These special types are used to enforce structural consistentency across component types.

        The following member rules must be followed:

        - :attr:`~MemberType.Hierarchy` group members must be named according to the :attr:`HIERARCHY_GROUP_NAMING_CONVENTION` and are parented directly under the encapsulated dagContainer asset.
        - :attr:`~MemberType.Settings` group members must be named according to the :attr:`SETTINGS_GROUP_NAMING_CONVENTION` and are parented directly under a :attr:`~MemberType.Hierarchy` group.
        - :attr:`~MemberType.Parameters` group members must be named according to the :attr:`PARAMETERS_GROUP_NAMING_CONVENTION` and are parented directly under a :attr:`~MemberType.Hierarchy` group.
        - All other members must be named according to the :attr:`MEMBER_NAMING_CONVENTION`.
        - Each member must be associated with exactly one member category.

    .. _MetaComponent_member_categories:

    **Member Categories:**

        An association between a member and a member category can be made through one of the following processes:

        - A member has a DAG association with a member category if it is a descendant of a :attr:`~MemberType.Hierarchy` group.
        - A member has a DG association with a member category if it has been registered via :meth:`addMembers`.

        Preset member categories defined within the :class:`MemberCategoryPreset` namespace are used to generalise the following features across component types:

        - Encapsulation: Modularisation of components is enforced through strict input and output conventions.
        - Deguiding: A generalised solution for this feature is provided via :meth:`deguide`.

        These features are made possible by enforcing a uniform member structure and imposing the following rules upon preset member categories:

        - :attr:`~MemberCategoryPreset.Input` members are the only members allowed to be the destination of a connection from outside a component.
        - :attr:`~MemberCategoryPreset.Output` members are the only members allowed to be the source of a connection to outside a component.
        - :attr:`~MemberCategoryPreset.Guide` members may only receive external inputs from :attr:`~MemberCategoryPreset.Input` members and may only output to :attr:`~MemberCategoryPreset.Guided` members.
        - :attr:`~MemberCategoryPreset.Guided` members may only receive external inputs from :attr:`~MemberCategoryPreset.Input` members and :attr:`~MemberCategoryPreset.Guide` members.

    **File System:**

        When exporting a `componentType` for the first time, a component sub-directory will be created under the root component directory associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.
        This sub-directory will be used as a container for all files relating the `componentType`.

        This interface makes use of the following component sub-directories:

        - `wip`: Location used to import and export wip component files.
        - `asset`: Location used to import and export assetised component files.
        - `guide`: Location used to import and export component guide files.
        - `data`: Location used to import and export component data files.
        - `scripts`: Location from which component scripts are loaded.

    **Versioning:**

        New components are created in wip mode.
        When exporting a component via :meth:`export`, the user can choose to increment the :attr:`minorVersion` or override the current wip file.

        When assetising a component via :meth:`assetise`, the assetised component will assume the current :attr:`majorVersion` whilst the :attr:`minorVersion` will be reset to ``0``.
        The :attr:`minorVersion` is not included in the file name of the assetised component as it is only used to track changes to wip components.

        When deassetising a component via :meth:`deassetise`, the :attr:`majorVersion` will be incremented whilst the :attr:`minorVersion will be set to ``0``.
        Once a component has been deassetised, it can be exported again in wip mode.

    **Subclassing:**

        All existing subclassing features are inherited from :class:`msTools.metadata.systems.base.Meta`.
        However the :attr:`NODE_TYPE_CONSTANT` and the :attr:`NODE_TYPE_ID` should not be overridden by any further subclass.

        Additionally, the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` attribute may be overridden to define the root component directory of a derived `mType`.
        This allows a subclass that is implemented as part of its own `mSystem` to define a unique location for its component files.
    """

    SYSTEM_ID = "mrs"
    """:class:`basestring`: Defines the `mSystemId` of this `mType`, used as a property for registering `mNodes` and identifying tagged dependency nodes.

    :access: R
    """

    NODE_TYPE_CONSTANT = om2.MFn.kDagContainer
    """:class:`int`: Defines which :class:`OpenMaya.MFn` dependency node types are compatible with this `mType`.

    Type compatibility is determined by calling :meth:`~OpenMaya.MObject.hasFn` on an :class:`OpenMaya.MObject` wrapper of the dependency node.

    :access: R
    """

    EXCLUSIVE = set(["_containerFn", "author", "componentId", "isBlackBoxed", "isGuided"])
    """:class:`set` [:class:`str`]: Defines exclusive instance attributes which can be set using the default :meth:`object.__setattr__` behaviour.

    - Includes the names of property setters defined by this `mType`.

    Invoking :meth:`msTools.metadata.base.Meta.__setattr__` with a non-exclusive attribute will attempt to access the attribute via the encapsulated dependency node.

    :access: R
    """

    COMPONENT_PATH_ENVIRONMENT_VARIABLE = "MRS_COMPONENT_PATH"
    """:class:`str`: Defines the environment variable which has been assigned a path to the root directory used to store components and their associated files.

    This path is used for both the importing and exporting of component files as well as sourcing of scripts relating to components.

    :access: R
    """

    WIP_FILE_NAMING_CONVENTION = "{componentType}_wip_{majorVersion:03d}_{minorVersion:03d}_{modification}.ma"
    """:class:`str`: Defines the naming convention used to generate wip component file names.

    :access: R
    """

    WIP_PATH_NAMING_CONVENTION = "{componentPath}/{componentType}/wip/{fileName}"
    """:class:`str`: Defines the naming convention used to generate a file path for exporting wip component files.

    :access: R
    """

    ASSET_FILE_NAMING_CONVENTION = "{componentType}_asset_{majorVersion:03d}.ma"
    """:class:`str`: Defines the naming convention used to generate assetised component file names.

    :access: R
    """

    ASSET_PATH_NAMING_CONVENTION = "{componentPath}/{componentType}/asset/{fileName}"
    """:class:`str`: Defines the naming convention used to generate a file path for exporting assetised component files.

    :access: R
    """

    SCRIPT_PATH_NAMING_CONVENTION = "{componentPath}/{componentType}/scripts/{fileName}"
    """:class:`str`: Defines the naming convention used to generate a file path for registering, deregistering or executing a component script.

    :access: R
    """

    GUIDE_FILE_NAMING_CONVENTION = "{componentType}_asset_{majorVersion:03d}_guide.ma"
    """:class:`str`: Defines the naming convention used to generate component guide file names.

    :access: R
    """

    GUIDE_PATH_NAMING_CONVENTION = "{componentPath}/{componentType}/guide/{fileName}"
    """:class:`str`: Defines the naming convention used to generate a file path for exporting component guide files.

    :access: R
    """

    GUIDE_DATA_FILE_NAMING_CONVENTION = "{componentType}_asset_{majorVersion:03d}_guide.json"
    """:class:`str`: Defines the naming convention used to generate component guide data file names.

    :access: R
    """

    GUIDE_DATA_PATH_NAMING_CONVENTION = "{componentPath}/{componentType}/data/{fileName}"
    """:class:`str`: Defines the naming convention used to generate a file path for exporting component guide data files.

    :access: R
    """

    COMPONENT_NAMING_CONVENTION = "{componentId}_cmpt"
    """:class:`str`: Naming convention used to name the encapsulated dagContainer node upon creation.

    The ``componentId`` keyword is given by the initialiser argument of the same name.

    :access: R
    """

    MEMBER_NAMING_CONVENTION = "{componentId}_{warble}"
    """:class:`str`: Naming convention used by component validators to ensure existing or potential members have consistent names.

    The ``componentId`` keyword is given by the initialiser argument of the same name.
    The ``warble`` keyword should correspond to a description of the component member.

    :access: R
    """

    HIERARCHY_GROUP_NAMING_CONVENTION = "{memberCategory}"
    """:class:`str`: Naming convention used to create or retrieve hierarchy groups.

    :access: R
    """

    HIERACHY_GROUP_TYPE_ID = om2.MTypeId(1249521)
    """:class:`OpenMaya.MTypeId`: Unique node type identifier corresponding to the node type of hierarchy groups.

    :access: R
    """

    SETTINGS_GROUP_NAMING_CONVENTION = "{componentId}_{memberCategory}_settings"
    """:class:`str`: Naming convention used to create or retrieve the settings node of a specific member category.

    :access: R
    """

    PARAMETERS_GROUP_NAMING_CONVENTION = "{componentId}_{memberCategory}_parameters"
    """:class:`str`: Naming convention used to create or retrieve the parameters node of a specific member category.

    :access: R
    """

    MEMBER_CACHE_NAMING_CONVENTION = "{memberCategory}_members"
    """:class:`str`: Naming convention used to generate attribute names for member registration, deregistration and lookup.

    The ``memberCategory`` keyword is given by the :meth:`addMembers` argument of the same name.

    :access: R
    """

    class MemberCategoryPreset(object):
        """Namespace providing preset :ref:`member categories <MetaComponent_member_categories>` which allow certain features to be generalised across component types by enforcing a uniform member structure."""

        Input = "input"
        """:class:`str`: The member category used to categorise input members.

        :access: R
        """

        Output = "output"
        """:class:`str`: The member category used to categorise output members.

        :access: R
        """

        Guide = "guide"
        """:class:`str`: The member category used to categorise guide members.

        :access: R
        """

        Guided = "guided"
        """:class:`str`: The member category used to categorise guided members.

        :access: R
        """

        Control = "control"
        """:class:`str`: The member category used to categorise control members.

        :access: R
        """

        Internal = "internal"
        """:class:`str`: The member category used to categorise internal members.

        :access: R
        """

        Deform = "deform"
        """:class:`str`: The member category used to categorise deform members.

        :access: R
        """

    class MemberType(Enum):

        Hierarchy = 0
        """`Enum`: Members of this type are designed to provide structure to a component's DAG hierarchy.

        They are named via the :attr:`HIERARCHY_GROUP_NAMING_CONVENTION` so that descendants become associated with a specific :ref:`member category <MetaComponent_member_categories>`.

        :access: R
        """

        Settings = 1
        """`Enum`: Members of this type should be used to consolidate the user defined settings of a specific :ref:`member category <MetaComponent_member_categories>`.

        :access: R
        """

        Parameters = 2
        """`Enum`: Members of this type should be used to consolidate the dynamic parameters of a specific :ref:`member category <MetaComponent_member_categories>`.

        :access: R
        """

    # --- Instantiation ----------------------------------------------------------------------------

    def __init__(self, node=None, componentType=None, componentId=None, stateTracking=True):
        """Initialiser for :class:`MetaComponent` `mNodes`.

        Args:
            node (:class:`OpenMaya.MObject` | :class:`OpenMaya.MDagPath`, optional): Wrapper or path of a tagged dagContainer node to encapsulate.
                Defaults to :data:`None` - A new dagContainer node will be created.
            componentType (:class:`basestring`, optional): Component type identifier, used when ``node`` is :data:`None`, to define a new component type.
                Aim to provide a detailed description (eg. biped_foot_ik) to avoid clashing with other components in the directory associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.
                When importing or exporting a component, the ``componentType`` will be used to locate or create a sub-directory within the directory associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.
                Defaults to :data:`None` - Requiring a ``node`` to be given.
            componentId (:class:`basestring`, optional): Component identifier, used when ``node`` is :data:`None`, to describe the new component in relation to other components within a rig.
                It must be distinct from all components within the active namespace.
                It is used by the :attr:`COMPONENT_NAMING_CONVENTION` to name the new dagContainer node.
                It is also used by the :attr:`MEMBER_NAMING_CONVENTION` to name component members.
                Consider including information such as a module description, component description, locality and index (eg. leg_L_foot_ik).
                Defaults to :data:`None` - Requiring a ``node`` to be given.
            stateTracking (:class:`bool`, optional): Whether to track the state of the encapsulated dagContainer node.
                Defaults to :data:`True` - Access to the interface is conditional upon this state.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``node`` does not reference a dagContainer type node.
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``componentType`` is also :data:`None`.
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``componentType`` is already an existing component type.
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``componentId`` is also :data:`None`.
            :exc:`~exceptions.ValueError`: If ``node`` is :data:`None` and ``componentId`` is already assigned to a component within the active namespace.
            :exc:`~exceptions.RuntimeError`: If a ``node`` is given but it does not have a valid `mType` tag or component tag.
        """
        log.debug("MetaComponent.__init__(node={}, componentType={}, componentId={}, stateTracking={})".format(node, componentType, componentId, stateTracking))

        name = None

        # Explicitly register the mNode if we are dealing with a new component type, otherwise allow the baseclass to determine whether the node has a valid tag and error later if not
        register = node is None

        if node is None:
            if componentType is None:
                raise ValueError("A `componentType` must be given when creating a new {} mNode".format(type(self)))
            elif componentType in type(self).getComponentTypes():
                raise ValueError("{}: `componentType` already exists within the component directory, use `importComponent` instead".format(componentType))

            if componentId is None:
                raise ValueError("A `componentId` must be given when creating a new {} mNode".format(type(self)))

            currentNamespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)

            for component in iterComponents(asMeta=True):
                if component.componentId == componentId and component.absoluteNamespace == currentNamespace:
                    raise ValueError("{}: `componentId` is not unique within current namespace: {}".format(componentId, currentNamespace))

            name = MetaComponent.COMPONENT_NAMING_CONVENTION.format(componentId=componentId)

        super(MetaComponent, self).__init__(node=node, name=name, nType="dagContainer", register=register, stateTracking=stateTracking)

        # Bind exclusive data
        self._containerFn = om2.MFnContainerNode(self._node)

        # Add component tag
        if node is None:
            # State
            self.addNumericAttribute(longName="isMirrored", value=False, dataType=om2.MFnNumericData.kBoolean)
            self.addNumericAttribute(longName="isGuided", value=True, dataType=om2.MFnNumericData.kBoolean)
            self.addNumericAttribute(longName="isDeguided", value=False, dataType=om2.MFnNumericData.kBoolean)
            self.addNumericAttribute(longName="isAsset", value=False, dataType=om2.MFnNumericData.kBoolean)
            # Name
            self.addTypedAttribute(longName="componentType", value=componentType, dataType=om2.MFnData.kString)
            self.addTypedAttribute(longName="componentId", value=componentId, dataType=om2.MFnData.kString)
            # File
            self.addNumericAttribute(longName='minorVersion', value=0, dataType=om2.MFnNumericData.kInt)
            self.addNumericAttribute(longName='majorVersion', value=1, dataType=om2.MFnNumericData.kInt)
            self.addTypedAttribute(longName="fileName", value="", dataType=om2.MFnData.kString)
            # Cache
            self.addTypedAttribute(longName="memberCategoryCache", value=[], dataType=om2.MFnData.kStringArray)
            self.addTypedAttribute(longName="tabDataRegistry", value=[], dataType=om2.MFnData.kStringArray)
            self.addTypedAttribute(longName="scriptRegistry", value="{}", dataType=om2.MFnData.kString)
        elif not self.hasValidTag:
            raise RuntimeError("{!r}: mNode does not have a valid `mType` tag".format(self))
        elif not self.hasValidComponentTag:
            raise RuntimeError("{!r}: mNode does not have a valid component tag".format(self))

    # --- Protected ----------------------------------------------------------------------------

    def _updateExclusiveData(self):
        """Update internally cached node data. Designed to be overloaded by subclasses.
        Called exclusively by :meth:`Meta._validate` if :attr:`isValid` was :data:`False` but the :class:`OpenMaya.MObject` wrapper of the encapsulated dependency node has been revalidated.
        """
        super(MetaComponent, self)._updateExclusiveData()

        self._containerFn = om2.MFnContainerNode(self._node)

    def _setupDirectory(self):
        """Create a directory structure for a new component type upon exporting or assetising a component for the first time.
        Called exclusively by :meth:`export` and :meth:`assetise`.

        The root-level directory is created under the component path associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.
        Sub-directories are then created for organising wip, asset, guide, data and script files.

        Raises:
            :exc:`~exceptions.RuntimeError`: If the component path associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` does not exist.
        """
        componentPath = self.getComponentPath()
        componentTypeDirectory = os.path.join(componentPath, self.componentType)
        componentWipDirectory = os.path.join(componentTypeDirectory, "wip")
        componentAssetDirectory = os.path.join(componentTypeDirectory, "asset")
        componentGuideDirectory = os.path.join(componentTypeDirectory, "guide")
        componentDataDirectory = os.path.join(componentTypeDirectory, "data")
        componentScriptsDirectory = os.path.join(componentTypeDirectory, "scripts")

        paths = [componentTypeDirectory, componentWipDirectory, componentAssetDirectory, componentGuideDirectory, componentDataDirectory, componentScriptsDirectory]

        for path in paths:
            try:
                os.mkdir(path)
            except OSError:
                pass

    def _registerMembers(self, memberCategory, members):
        """Register (non-DAG) members to a member category.
        A DG association will be created via a message connection from each member to a category cache on the encapsulated dagContainer node.
        """
        memberMessagePlugs = [OM.getPlugFromNodeByName(member, "message") for member in members]
        memberCacheAttrName = self.MEMBER_CACHE_NAMING_CONVENTION.format(memberCategory=memberCategory)

        try:
            memberCachePlug = self.getPlug(memberCacheAttrName)
        except EXC.MayaLookupError:
            memberCachePlug = self.addMessageAttribute(longName=memberCacheAttrName, array=True)

        memberCategoryCacheAttr = self.memberCategoryCache
        memberCategories = memberCategoryCacheAttr.get()

        if memberCategory not in memberCategories:
            memberCategories.append(memberCategory)
            memberCategoryCacheAttr.set(memberCategories)

        PLUG.PackArray(memberCachePlug, inputPlugs=memberMessagePlugs)

    def _deregisterMembers(self, members):
        """Deregister (non-DAG) members from their registered member category.
        This will remove the DG associations that were created via :meth:`_registerMembers`.
        """
        memberCategoryCacheAttr = self.memberCategoryCache
        memberCategories = memberCategoryCacheAttr.get()
        memberCategoryAttrNameMap = {self.MEMBER_CACHE_NAMING_CONVENTION.format(memberCategory=memberCategory): memberCategory for memberCategory in memberCategories}
        editedMemberCategoryAttrNames = set()

        for member in members:
            memberMessagePlug = OM.getPlugFromNodeByName(member, "message")
            memberMessageDestPlugs = memberMessagePlug.destinationsWithConversions()

            for memberMessageDestPlug in memberMessageDestPlugs:
                if memberMessageDestPlug.isElement and memberMessageDestPlug.node() == self._node:
                    memberMessageDestAttrName = NAME.getAttributeName(memberMessageDestPlug.attribute())

                    if memberMessageDestAttrName in memberCategoryAttrNameMap:
                        PLUG.disconnect(memberMessagePlug, memberMessageDestPlug)
                        editedMemberCategoryAttrNames.add(memberMessageDestAttrName)

        for editedMemberCategoryAttrName in editedMemberCategoryAttrNames:
            memberCategory = memberCategoryAttrNameMap[editedMemberCategoryAttrName]
            memberCategoryAttr = self.getPlug(editedMemberCategoryAttrName, asMeta=True)
            memberCategoryPacked = memberCategoryAttr.getPacked()

            if not memberCategoryPacked.isConnected:
                memberCategoryAttr.delete()
                memberCategories.remove(memberCategory)
                memberCategoryCacheAttr.set(memberCategories)

    # --- Public : File System ----------------------------------------------------------------------------

    @classmethod
    def getComponentPath(cls):
        """
        Returns:
            :class:`basestring`: The absolute path associated with the highest level (non-strict) subclass implementation of :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.

        Raises:
            :exc:`exceptions.RuntimeError`: If the environment variable assigned to the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` does not exist.
            :exc:`exceptions.RuntimeError`: If the component path associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` does not exist.
        """
        try:
            path = os.path.abspath(os.environ[cls.COMPONENT_PATH_ENVIRONMENT_VARIABLE])
        except KeyError:
            raise RuntimeError("{}: Environment variable does not exist".format(cls.COMPONENT_PATH_ENVIRONMENT_VARIABLE))

        if not os.path.exists(path):
            raise RuntimeError("{}: Component path does not exist".format(path))

        return path

    @classmethod
    def getComponentTypes(cls):
        """
        Returns:
            :class:`list` [:class:`str`]: Names of existing component types within the directory associated with the highest level (non-strict) subclass implementation of :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE`.

        Raises:
            :exc:`exceptions.RuntimeError`: If the environment variable assigned to the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` does not exist.
            :exc:`~exceptions.RuntimeError`: If the component path associated with the :attr:`COMPONENT_PATH_ENVIRONMENT_VARIABLE` does not exist.
        """
        return list(PY_PATH.iterDirectories(cls.getComponentPath(), walk=False, paths=False))

    # --- Public : Properties ----------------------------------------------------------------------------

    @property
    def hasValidComponentTag(self):
        """:class:`bool`: :data:`True` if the encapsulated dagContainer node is tagged with component attributes (ie. node was created via :class:`MetaComponent`),
        otherwise :data:`False`.

        :access: R
        """
        try:
            self.getPlug("isMirrored")
            self.getPlug("isGuided")
            self.getPlug("isDeguided")
            self.getPlug("isAsset")
            self.getPlug("componentType")
            self.getPlug("componentId")
            self.getPlug("minorVersion")
            self.getPlug("majorVersion")
            self.getPlug("fileName")
            self.getPlug("memberCategoryCache")
            self.getPlug("tabDataRegistry")
            self.getPlug("scriptRegistry")
        except EXC.MayaLookupError:
            return False
        else:
            return True

    @property
    def isMirrorable(self):
        """:class:`bool`: :data:`True` if this :attr:`componentType` has a mirror script registered under the :attr:`ScriptIdPreset.Mirror` identifier, otherwise :data:`False`."""
        return self.hasScript(ScriptIdPreset.Mirror)

    @property
    def isMirrored(self):
        """:class:`bool`: :data:`True` if the ``isMirrored`` attribute returns :data:`True`, otherwise :data:`False`."""
        return self.getPlug("isMirrored", asMeta=True).get()

    @property
    def isGuidable(self):
        """:class:`bool`: :data:`True` if the :attr:`~MemberCategoryPreset.Guide` and :attr:`~MemberCategoryPreset.Guided` :attr:`~MemberType.Hierarchy` groups exist,
        as well as the :attr:`~MemberCategoryPreset.Guided` :attr:`~MemberType.Parameters` group, otherwise :data:`False`.
        """
        return (self.hasMemberOfType(self.MemberCategoryPreset.Guide, self.MemberType.Parameters) and self.hasHierarchyGroup(self.MemberCategoryPreset.Guided)
                and self.hasParametersGroup(self.MemberCategoryPreset.Guided))

    @property
    def isGuided(self):
        """:class:`bool`: Whether the component is guided.

        :access: RW
        """
        return self.getPlug("isGuided", asMeta=True).get()

    @isGuided.setter
    def isGuided(self, state):
        if state != self.isGuided:
            self.toggleGuide()

    @property
    def isDeguided(self):
        """:class:`bool`: Whether the component has been deguided.

        :access: R
        """
        return self.getPlug("isDeguided", asMeta=True).get()

    @property
    def isAsset(self):
        """:class:`bool`: :data:`True` if this component is assetised, otherwise :data:`False`.

        An assetised component has a :attr:`filePath` which is associated with an asset file.

        :access: R
        """
        return self.getPlug("isAsset", asMeta=True).get()

    @property
    def isWip(self):
        """:class:`bool`: :data:`True` if this component is in wip mode, otherwise :data:`False`.

        Wip mode includes any exported or non-exported component, whereby the :attr:`filePath` is either associated with a work in progress file or is null.

        :access: R
        """
        return not self.isAsset

    @property
    def isBlackBoxed(self):
        """:class:`bool`: Whether the encapsulated dagContainer node is black-boxed.

        :access: RW
        """
        return self.blackBox.get()

    @isBlackBoxed.setter
    def isBlackBoxed(self, state):
        self.blackBox = state

    @property
    def containerFn(self):
        """:class:`OpenMaya.MFnContainerNode`: Function set encapsulation of the encapsulated dagContainer node.

        :access: R
        """
        return om2.MFnContainerNode(self._node)

    @property
    def componentType(self):
        """:class:`str`: Component type of this component.

        :access: R
        """
        return self.getPlug("componentType", asMeta=True).get()

    @property
    def componentId(self):
        """:class:`str`: Component identifier used to name this component and its members.

        Write access acts as a direct wrapper of :meth:`rename`.

        :access: RW
        """
        return self.getPlug("componentId", asMeta=True).get()

    @componentId.setter
    def componentId(self, componentId):
        self.rename(componentId)

    @property
    def minorVersion(self):
        """:class:`int`: Minor version of this component.

        :access: R
        """
        return self.getPlug("minorVersion", asMeta=True).get()

    @property
    def majorVersion(self):
        """:class:`int`: Major version of this component.

        :access: R
        """
        return self.getPlug("majorVersion", asMeta=True).get()

    @property
    def author(self):
        """Author of this component.

        Access: RW
        """
        return self.creator.get()

    @author.setter
    def author(self, author):
        self.creator = author

    @property
    def creationDate(self):
        """:class:`str`: Date and time of when the file referenced by :attr:`filePath` was created. Formatted as ``DD/MM/YYYY HH:MM:SS``.

        If this component has not yet been exported or assetised, the result will be an empty string.

        :access: R
        """
        return self.getPlug("creationDate", asMeta=True).get()

    @property
    def fileName(self):
        """:class:`str`: Name of the file associated with this component.

        If this component has not yet been exported or assetised, the result will be an empty string.

        :access: R
        """
        return self.getAttr("fileName", asMeta=True).get()

    @property
    def filePath(self):
        """:class:`str`: Path to the file associated with this component.

        If this component has not yet been exported or assetised, the result will be an empty string.

        :access: R
        """
        fileName = self.fileName

        if fileName:
            pathConvention = MetaComponent.ASSET_PATH_NAMING_CONVENTION if self.isAsset else MetaComponent.WIP_PATH_NAMING_CONVENTION
            filePath = pathConvention.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)
            return os.path.abspath(filePath)
        else:
            return ""

    @property
    def componentTypePath(self):
        """:class:`str`: Path to the root directory associated with the :attr:`componentType`.

        If this component has not yet been exported or assetised, the result will be an empty string.

        :access: R
        """
        return os.path.dirname(os.path.dirname(self.filePath))

    # --- Public : Scripts ----------------------------------------------------------------------------

    def hasScript(self, scriptId):
        """Return whether the name of an existing script file is registered with the encapsulated dagContainer node via the given script identifier.

        Args:
            scriptId (:class:`basestring`): Name of a script identifier that was used to register a script file.

        Returns:
            :class:`bool`: :data:`True` if an existing script file is registered to the ``scriptId``, otherwise :data:`False`.
        """
        scriptMap = self.scriptRegistry.get()

        try:
            fileName = scriptMap[scriptId]
        except KeyError:
            return False
        else:
            filePath = self.SCRIPT_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

            return os.path.exists(filePath)

    def registerScript(self, scriptId, fileName):
        """Register the name of an existing script file to a given script identifier so that it can be executed via :meth:`executeScript`.

        If a script is already assigned to the given script identifier, it will be overridden.

        Args:
            scriptId (:class:`basestring`): Name of a script identifier used to register the script file corresponding to ``fileName`` with the encapsulated dagContainer node.
                Preset script identifiers are provided by the :class:`ScriptIdPreset` namespace and should be used to register scripts with pre-defined behaviour.
            fileName (:class:`basestring`): Name of the script file that exists within the script sub-directory of the :attr:`componentTypePath`.
                The registered script file should contain a function corresponding to the ``scriptId`` which is used to execute the script.

        Raises:
            :exc:`~exceptions.ValueError`: If the ``fileName`` does not correspond to an existing script file within the script sub-directory of the :attr:`componentTypePath`.
        """
        filePath = self.SCRIPT_PATH_NAMING_CONVENTION.format(componentType=self.componentType, fileName=fileName)

        if not os.path.exists(filePath):
            raise ValueError("Script file does not exist: {}".format(filePath))

        scriptMap = self.scriptRegistry.get()

        if scriptId in scriptMap:
            log.info("Overriding registered `{}` script for mNode: {!r}".format(scriptId, self))

        scriptMap[scriptId] = fileName
        self.scriptRegistry.set(scriptMap)

    def deregisterScript(self, scriptId):
        """Deregister a script file corresponding to the given script identifier.

        Args:
            scriptId (:class:`basestring`): Name of a script identifier used to deregister a script file that has been registered with the encapsulated dagContainer node.

        Raises:
            :exc:`~exceptions.KeyError`: If there is no script file registered with the encapsulated dagContainer node via the ``scriptId``.
        """
        scriptMap = self.scriptRegistry.get()
        del scriptMap[scriptId]
        self.scriptRegistry.set(scriptMap)

    def executeScript(self, scriptId, *args, **kwargs):
        """Execute a script that has been registered with the encapsulated dagContainer node via a script identifier.

        A function whose name corresponds to the script identifier will be executed from the script file.
        It will be passed this `mNode` as its first argument as well as any given ``args`` or ``kwargs``.

        Args:
            scriptId (:class:`basestring`): Name of a script identifier to which a script file is registered with the encapsulated dagContainer node.
            *args: Positional arguments used to invoke the ``scriptId`` function from the registered script file.
            **kwargs: Keyword arguments used to invoke the ``scriptId`` function from the registered script file.

        Returns:
            any: The result of invoking the ``scriptId`` function from the registered script file.

        Raises:
            :exc:`~exceptions.KeyError`: If there is no script file registered with the encapsulated dagContainer node via the ``scriptId``.
            :exc:`~exceptions.IOError` If the script file registered to the ``scriptId`` does not exist.
            :exc:`~exceptions.AttributeError`: If there is no function within the registered script file that is named after the ``scriptId``.
        """
        scriptMap = self.scriptRegistry.get()
        fileName = scriptMap[scriptId]
        filePath = self.SCRIPT_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        script = imp.load_source("{}.scripts.{}".format(self.componentType, fileName), filePath)
        return getattr(script, scriptId)(self, *args, **kwargs)

    # --- Public : Tabs ----------------------------------------------------------------------------

    def hasTab(self, tabLabel):
        """Return whether a primary Node Editor tab is registered with the encapsulated dagContainer node via its label.

        Args:
            tabLabel (:class:`basestring`): The label of an existing tab within the primary Node Editor.

        Returns:
            :class:`bool`: :data:`True` if the ``tabLabel`` is registered with the encapsulated dagContainer node, otherwise :data:`False`.
        """
        tabData = self.tabDataRegistry.get()
        return tabLabel in tabData

    def registerTab(self, tabLabel):
        """Register a primary Node Editor tab with the encapsulated dagContainer node via its label.

        The metadata of each registered tab will be cached before exporting or assetising this component.
        This metadata will be used to rebuild tabs within the primary Node Editor upon importing this component.

        Args:
            tabLabel (:class:`basestring`): The label of an existing tab within the primary Node Editor to register with the encapsulated dagContainer node.

        Raises:
            :exc:`msTools.coreUI.maya.exceptions.MayaUILookupError`: If a primary Node Editor `editor` could not be identified.
        """
        editorWidget = UI_NODE_EDITOR.getPrimaryNodeEditor()
        tabBarWidget = UI_NODE_EDITOR.getNodeEditorTabBarFromEditor(editorWidget)

        for i in xrange(tabBarWidget.count() - 1):
            if tabBarWidget.tabText(i) == tabLabel:
                break
        else:
            raise ValueError("Node Editor tab with given label does not exist: {}".format(tabLabel))

        tabData = self.tabDataRegistry.get()

        if tabLabel not in tabData:
            tabData[tabLabel] = {}
            self.tabDataRegistry.set(tabData)

    def deregisterTab(self, tabLabel):
        """Deregister a primary Node Editor tab from the encapsulated dagContainer node.

        The metadata of this tab will no longer be cached upon exporting or assetising this component.

        Args:
            tabLabel (:class:`basestring`): The label of an existing tab within the primary Node Editor to deregister from the encapsulated dagContainer node.

        Raises:
            :exc:`~exceptions.KeyError`: If ``tabLabel`` is not registered with the encapsulated dagContainer node.
        """
        tabData = self.tabDataRegistry.get()
        del tabData[tabLabel]
        self.tabDataRegistry.set(tabData)

    # --- Public : Utility ----------------------------------------------------------------------------

    def rename(self, componentId):
        """Rename this component and its members using a new component identifier.

        Args:
            componentId (:class:`basestring`): New identifier used to describe this component in relation to other components within a rig.
                It must be distinct from all components within the :attr:`absoluteNamespace` of this component.
                It is used by the :attr:`COMPONENT_NAMING_CONVENTION` to rename the encapsulated dagContainer node.
                It is also used by the :attr:`MEMBER_NAMING_CONVENTION` to rename existing component members.
                Consider including information such as a module description, component description, locality and index (eg. leg_L_foot_ik).

        Raises:
            :exc:`~exceptions.ValueError`: If ``componentId`` is already assigned to a component within the :attr:`absoluteNamespace` of this component.
            :exc:`~exceptions.RuntimeError`: If a member is not named in accordance with the :attr:`MEMBER_NAMING_CONVENTION`.
        """
        oldComponentId = self.componentId

        if oldComponentId == componentId:
            return

        for component in iterComponents(asMeta=True):
            if component.componentId == componentId and component.absoluteNamespace == self.absoluteNamespace:
                raise ValueError("{}: `componentId` is not unique within current namespace: {}".format(componentId, self.absoluteNamespace))

        for member in self.iterMembers():
            # Skip hierarchy groups
            if om2.MFnDependencyNode(member).typeId == MetaComponent.HIERACHY_GROUP_TYPE_ID and self.hasChild(member):
                continue

            oldMemberName = NAME.getNodeShortName(member)

            if not oldMemberName.startswith(oldComponentId):
                raise RuntimeError("{}: Component member does not comply with member naming conventions, missing `componentId` prefix: {}".format(oldMemberName, oldComponentId))

            newMemberName = componentId + oldMemberName[len(oldComponentId):]
            DG.renameNode(member, newMemberName)

        self.getPlug("componentId", asMeta=True).set(componentId)

    def mirror(self, componentId=None):
        """Mirror this component via its registered :attr:`ScriptIdPreset.Mirror` script and optionally rename the resulting component.

        Args:
            componentId (:class:`basestring`, optional): New identifier used to rename this component in order reflect the change in locality due to mirroring.
                It must be distinct from all components within the :attr:`absoluteNamespace` of this component.
                It is used by the :attr:`COMPONENT_NAMING_CONVENTION` to rename the encapsulated dagContainer node.
                It is also used by the :attr:`MEMBER_NAMING_CONVENTION` to rename existing component members.
                Consider including information such as a module description, component description, locality and index (eg. leg_L_foot_ik).
                Defaults to :data:`None` - Do not rename this component after mirroring.

        Raises:
            :exc:`~exceptions.RuntimeError`: If this component does not have a registered :attr:`ScriptIdPreset.Mirror` script.
            :exc:`~exceptions.ValueError`: If ``componentId`` is already assigned to a component within the :attr:`absoluteNamespace` of this component.
            :exc:`~exceptions.RuntimeError`: If a member is not named in accordance with the :attr:`MEMBER_NAMING_CONVENTION`.
        """
        if not self.isMimorrable:
            raise RuntimeError("Component is not mirrorable.")

        self.executeScript(ScriptIdPreset.Mirror)

        if componentId:
            self.rename(componentId)

        isMirroredAttr = self.getPlug("isMirrored", asMeta=True)
        isMirroredAttr.set(not isMirroredAttr.get())

    def toggleBlackBox(self):
        """Toggle the black-box state of this component.

        When black-boxing is enabled, only published attributes and nodes will be visible to the user.
        """
        self.isBlackBoxed = not self.isBlackBoxed

    def toggleGuide(self):
        """Toggle the guide state of this component.

        Unguiding the component will disconnect any :attr:`~MemberCategoryPreset.Guide` -> :attr:`~MemberCategoryPreset.Guided` connections.
        Guiding the component will reinstate the :attr:`~MemberCategoryPreset.Guide` -> :attr:`~MemberCategoryPreset.Guided` connections.

        A guide cache on the :attr:`~MemberCategoryPreset.Guided` :attr:`~MemberType.Parameters` group is used to intermediate this process.

        - If the component is in a guided wip state, the cache will be updated before breaking guide connections.
        - If the component is in a guided asset state, guide connections will be immediately broken.
        - If the component is in an unguided state, cached guide connections will be reinstated.

        Raises:
            :exc:`~exceptions.RuntimeError`: If this component does not have a guide (ie. :attr:`isGuidable` returns :data:`False`).
            :exc:`~exceptions.RuntimeError`: If this component is in a wip state and its guide is malformed (ie. :meth:`inspectGuide` returns :data:`False`).
        """
        if not self.isGuidable:
            raise RuntimeError("Component is not guidable")

        # Assume assetised guide is valid
        if self.isWip and not self.inspectGuide():
            raise RuntimeError("Component guide has issues that must be resolved, see warning log for details")

        guidedParametersGroup = self.getMemberByType(self.MemberCategoryPreset.Guided, self.MemberType.Parameters, asMeta=True)

        # If component is in unguided mode, reinstate (guide -> guided) connections from cache
        if not self.isGuided:
            # Component should not be unguided without this attribute
            guideCacheAttr = guidedParametersGroup.guideCache
            guideCachePacked = guideCacheAttr.getPackedCompound()

            for (guideSourcePlug, guidedDestPlug) in guideCachePacked.getInputPlugGroups():
                PLUG.connect(guideSourcePlug, guidedDestPlug)

        # If component is guided, break (guide -> guided) connections
        else:
            # Assume tracking has either not been setup or is stale
            if self.isWip:
                guideCachePacked = self.updateGuideTracking()
            else:
                guideCachePacked = guidedParametersGroup.guideCache

            for (guideSourcePlug, guidedDestPlug) in guideCachePacked.getInputPlugGroups():
                PLUG.disconnect(guideSourcePlug, guidedDestPlug)

        isGuidedPlug = self.getPlug("isGuided", asMeta=True)
        isGuidedPlug.set(not isGuidedPlug.get())

    def deguide(self):
        """Disconnect and remove the guide from this component.

        Deguiding is designed to optimise the rig before animation. As such, it is only valid for assetised components.

        Raises:
            :exc:`~exceptions.RuntimeError`: If this component is not assetised (ie. :attr:`isAsset` returns :data:`False`).
            :exc:`~exceptions.RuntimeError`: If this component is already deguided (ie. :attr:`isDeguided` returns :data:`True`).
            :exc:`~exceptions.RuntimeError`: If this component does not have a guide (ie. :attr:`isGuidable` returns :data:`False`).
        """
        if self.isWip:
            raise RuntimeError("{!r}: Wip component cannot be deguided".format(self))

        if self.isDeguided:
            raise RuntimeError("{!r}: Component is already deguided".format(self))

        if not self.isGuidable:
            raise RuntimeError("{!r}: Component does not have a guide".format(self))

        # Disconnect guided outputs
        if self.isGuided:
            self.toggleGuide()

        # Disconnect inputs and remaining message outputs
        guideMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Guide))

        for guideMember in guideMembers:
            for (sourcePlug, destPlug) in DG.iterDependenciesByEdge(guideMember, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                if destPlug.node() not in guideMembers:
                    PLUG.disconnect(sourcePlug, destPlug, forceLocked=True)

            for (sourcePlug, destPlug) in DG.iterDependenciesByEdge(guideMember, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
                if sourcePlug.node() not in guideMembers:
                    PLUG.disconnect(sourcePlug, destPlug, forceLocked=True)

        # Delete guide
        self.selectMembersByCategory(self.MemberCategoryPreset.Guide)
        cmds.delete()

        self.getPlug("isGuided", asMeta=True).set(False)
        self.getPlug("isDeguided", asMeta=True).set(True)

    def reguide(self):
        """Import and reconnect the guide for this component.

        Note:
            This component will be reset to its default assetised state.
            The transforms of any guidable animation controls will be reset.

        Raises:
            :exc:`~exceptions.RuntimeError`: If this component is not assetised (ie. :attr:`isAsset` returns :data:`False`).
            :exc:`~exceptions.RuntimeError`: If this component is not deguided (ie. :attr:`isDeguided` returns :data:`False`).
        """
        if self.isWip:
            raise RuntimeError("{!r}: Wip component should not be deguided".format(self))

        if not self.isDeguided:
            raise RuntimeError("{!r}: Component is not deguided".format(self))

        # Import guide
        fileName = MetaComponent.GUIDE_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=self.majorVersion)
        filePath = MetaComponent.GUIDE_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        try:
            rig = self.getRig(asMeta=True)
        except RuntimeError:
            rigNamespace = ":"
        else:
            rigNamespace = rig.absoluteNamespace

        while True:
            tempNamespace = ":" + "".join(random.choice(string.ascii_letters) for _ in range(10))

            if not cmds.namespace(exists=tempNamespace):
                break

        with CONTEXT.SetActiveNamespace(tempNamespace):
            cmds.file(filePath, i=True)

            guideNodeNames = cmds.namespaceInfo(listOnlyDependencyNodes=True, dagPath=True)
            guideNodes = [OM.getNodeByName(guideNodeName) for guideNodeName in guideNodeNames]
            guideHierarchyGroupPath = OM.getPathByName(tempNamespace + ":guide")

            self.addChild(guideHierarchyGroupPath)

            # Remove temp namespace from DAG nodes and move non-DAG nodes into rig namespace
            for guideNode in guideNodes:
                if guideNode.hasFn(om2.MFn.kDagNode):
                    guideNodeName = NAME.getNodeShortName(guideNode)
                    DG.renameNode(guideNode, guideNodeName)
                else:
                    guideNodeName = ":".join([rigNamespace, NAME.getNodeShortName(guideNode)])
                    DG.renameNode(guideNode, guideNodeName)

        # Delete temp namespace
        cmds.namespace(removeNamespace=tempNamespace)

        # Load guide data and use to reconnect the guide
        fileName = MetaComponent.GUIDE_DATA_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=self.majorVersion)
        filePath = MetaComponent.GUIDE_DATA_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        with open(filePath, 'r') as f:
            guideData = json.load(f)

        cachedComponentId = guideData["componentId"]
        cachedComponentName = MetaComponent.COMPONENT_NAMING_CONVENTION.format(componentId=cachedComponentId)
        componentId = self.componentId
        componentFullPathName = self.fullPathName

        for cachedSourcePlugFullName, cachedDestPlugFullName in guideData["inputEdges"] + guideData["outputEdges"]:
            # Update parent hierarchy of DAG node with current component path
            if cachedSourcePlugFullName.startswith(cachedComponentName):
                sourcePlugFullName = re.sub("^{}".format(cachedComponentName), componentFullPathName, cachedSourcePlugFullName)
            if cachedDestPlugFullName.startswith(cachedComponentName):
                destPlugFullName = re.sub("^{}".format(cachedComponentName), componentFullPathName, cachedDestPlugFullName)

            # Update componentId references for descendant DAG nodes and non-DAG nodes
            sourcePlugFullName = re.sub(cachedComponentId, componentId, sourcePlugFullName)
            destPlugFullName = re.sub(cachedComponentId, componentId, destPlugFullName)

            # Make connection
            sourcePlug = OM.getPlugByName(sourcePlugFullName)
            destPlug = OM.getPlugByName(destPlugFullName)

            PLUG.connect(sourcePlug, destPlug)

        self.getPlug("isGuided", asMeta=True).set(True)
        self.getPlug("isDeguided", asMeta=True).set(False)

    def updateGuideTracking(self):
        """Update the guide tracking plug cache on the :attr:`~MemberCategoryPreset.Guided` :attr:`~MemberType.Parameters` group.

        The cache will be cleared, then updated with connections between :attr:`~MemberCategoryPreset.Guide` and :attr:`~MemberCategoryPreset.Guided` nodes.
        Cached connections are used to toggle the component between a guided and unguided state.
        Guide tracking will be automatically updated upon assetising the component.

        Raises:
            :exc:`~exceptions.RuntimeError`: If this component is already assetised (ie. :attr:`isAsset` returns :data:`True`), meaning its guide tracking is now locked.
            :exc:`~exceptions.RuntimeError`: If this component does not have a guide (ie. :attr:`isGuidable` returns :data:`False`).
            :exc:`~exceptions.RuntimeError`: If this component is unguided (ie. :attr:`isGuided` returns :data:`False`), meaning its guide tracking is in use.
        """
        if self.isAsset:
            raise RuntimeError("Component is already assetised, guide tracking is finalised")

        if not self.isGuidable:
            raise RuntimeError("Component is not guidable")

        if not self.isGuided:
            raise RuntimeError("Component is unguided, guide tracking is in use")

        guidedParametersGroup = self.getMemberByType(self.MemberCategoryPreset.Guided, self.MemberType.Parameters, asMeta=True)

        try:
            guideCacheAttr = guidedParametersGroup.guideCache
        except AttributeError:
            guideSourceAttr = ATTR.createMessageAttribute(longName="guideSource")
            guidedDestAttr = ATTR.createMessageAttribute(longName="guidedDest")
            guideCacheAttr = guidedParametersGroup.addCompoundAttribute((guideSourceAttr, guidedDestAttr), longName="guideCache", resultAsMeta=True, array=True)
            log.info("{}: Component guide tracking plug created".format(guideCacheAttr.partialName))

        guideCachePacked = guideCacheAttr.getPackedCompound()
        guideCachePacked.clear()

        guideMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Guide))
        guidedMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Guided))

        for guideMember in guideMembers:
            for sourcePlug, destPlug in DG.iterDependenciesByEdge(guideMember, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                if destPlug.node() in guidedMembers:
                    guideCachePacked.append((sourcePlug, destPlug))

        return guideCachePacked

    # --- Public : Members ----------------------------------------------------------------------------

    def hasMember(self, member):
        """Return whether a dependency node is a member of this component.

        Args:
            member (:class:`OpenMaya.MObject`): Wrapper of a dependency node.

        Returns:
            :class:`bool`: :data:`True` if ``member`` is a member of this component, otherwise :data:`False`.
        """
        try:
            componentNode = getComponentFromMember(member)
        except (BASE.MTypeError, BASE.MSystemError, RuntimeError):
            return False

        if componentNode != self.node:
            return False

        return True

    def hasMemberOfType(self, memberCategory, memberType):
        """Return whether this component has a member corresponding to a specific category and type.

        Args:
            memberCategory (:class:`basestring`): Member category to check for an existing member.
            memberType (:class:`MemberType`): Member type to check for an existing member.

        Returns:
            :class:`bool`: :data:`True` if this component has a member belonging to ``memberCategory`` and ``memberType``, otherwise :data:`False`.
        """
        try:
            self.getMemberByType(memberCategory, memberType)
        except (BASE.MTypeError, BASE.MSystemError, EXC.MayaLookupError):
            return False

        return True

    def getMemberByType(self, memberCategory, memberType, asMeta=False):
        """Return a member of this component corresponding to a specific category and type.

        Args:
            memberCategory (:class:`basestring`): Member category of an existing member.
            memberType (:class:`MemberType`): Member type of an existing member.
            asMeta (:class:`bool`, optional): Whether to return the member as an `mNode`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper of the dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaLookupError`: If there is no descendant of the encapsulated dagContainer node that corresponds to the given ``memberCategory`` and ``memberType``.
            :exc:`msTools.metadata.systems.base.MSystemError`: If ``asMeta`` is :data:`True` and the member node is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`msTools.metadata.systems.base.MTypeError`: If ``asMeta`` is :data:`True` and the member node is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`msTools.metadata.systems.mrs.Meta`: Wrapper or `mNode` encapsulation of the component member node. Type is determined by ``asMeta``.
        """
        hierarchyName = self.HIERARCHY_GROUP_NAMING_CONVENTION.format(memberCategory=memberCategory)
        hierarchyNode = self.getChildByName(hierarchyName)

        if memberType is MetaComponent.MemberType.Hierarchy:
            return BASE.getMNode(hierarchyNode) if asMeta else hierarchyNode
        else:
            namingConvention = self.SETTINGS_GROUP_NAMING_CONVENTION if memberType is MetaComponent.MemberType.Settings else MetaComponent.PARAMETERS_GROUP_NAMING_CONVENTION
            memberNodeName = namingConvention.format(memberCategory=memberCategory)
            member = DAG.getChildByName(hierarchyNode, memberNodeName)
            return BASE.getMNode(member) if asMeta else member

    def iterMembers(self, asMeta=False):
        """Yield members of this component.

        Args:
            asMeta (:class:`bool`, optional): Whether to yield each member as an `mNode`.
                Defaults to :data:`False` - yield each member as an :class:`OpenMaya.MObject` wrapper of the dependency node.

        Raises:
            :exc:`msTools.metadata.systems.base.MSystemError`: If ``asMeta`` is :data:`True` and a member node is tagged with an `mSystemId` that does not correspond to a registered `mSystem`.
            :exc:`msTools.metadata.systems.base.MTypeError`: If ``asMeta`` is :data:`True` and a member node is tagged with an `mTypeId` that does not correspond to a registered `mType` for its `mSystem`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`msTools.metadata.systems.mrs.Meta`: Wrappers or `mNode` encapsulations of component member nodes. Type is determined by ``asMeta``.
        """
        for member in self._containerFn.getMembers():
            yield BASE.getMNode(member) if asMeta else member

    def iterMembersByCategory(self, memberCategory, asMeta=False):
        """Yield members of this component by member category.

        Args:
            memberCategory (:class:`basestring`): Member category from which to yield existing members.
            asMeta (:class:`bool`, optional): Whether to yield each member as an `mNode`.
                Defaults to :data:`False` - yield each member as an :class:`OpenMaya.MObject` wrapper of the dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If a child of this component is named in accordance with the :attr:`HIERARCHY_GROUP_NAMING_CONVENTION` but its :class:`OpenMaya.MTypeId` does not correspond to the :attr:`HIERACHY_GROUP_TYPE_ID`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`msTools.metadata.systems.mrs.Meta`: Wrappers or `mNode` encapsulations of component member nodes belonging to the given ``memberCategory``.
            Type is determined by ``asMeta``.
        """
        hierarchyNodeName = self.HIERARCHY_GROUP_NAMING_CONVENTION.format(memberCategory=memberCategory)
        memberCacheAttrName = self.MEMBER_CACHE_NAMING_CONVENTION.format(memberCategory=memberCategory)

        try:
            hierarchyNode = self.getChildByName(hierarchyNodeName)
        except EXC.MayaLookupError:
            pass
        else:
            if om2.MFnDependencyNode(hierarchyNode).typeId != self.HIERACHY_GROUP_TYPE_ID:
                raise EXC.MayaTypeError("{}: Component child is not a hierarchy group".format(NAME.getNodeFullName(hierarchyNode)))

            yield BASE.getMNode(hierarchyNode) if asMeta else hierarchyNode

            for descendentNode in DAG.iterDescendants(hierarchyNode):
                yield BASE.getMNode(descendentNode) if asMeta else descendentNode

        try:
            memberCacheArrayPlug = self.getPlug(memberCacheAttrName)
        except EXC.MayaLookupError:
            pass
        else:
            for memberCacheElementPlug in PLUG.iterConnectedElements(memberCacheArrayPlug, checkSource=False):
                member = memberCacheElementPlug.sourceWithConversion().node()
                yield BASE.getMNode(member) if asMeta else member

    def iterMembersByType(self, memberType, asMeta=False):
        """Yield members of this component by member type.

        Args:
            memberType (:class:`MemberType`): Member type of existing members to yield.
            asMeta (:class:`bool`, optional): Whether to yield each member as an `mNode`.
                Defaults to :data:`False` - yield each member as an :class:`OpenMaya.MObject` wrapper of the dependency node.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If a child of this component has an :class:`OpenMaya.MTypeId` that does not correspond to the :attr:`HIERACHY_GROUP_TYPE_ID`.

        Yields:
            :class:`OpenMaya.MObject` | T <= :class:`msTools.metadata.systems.mrs.Meta`: Wrappers or `mNode` encapsulations of component member nodes which correspond to the given ``memberType``.
            Type is determined by ``asMeta``.
        """
        for hierarchyNode in self.iterChildren():
            if om2.MFnDependencyNode(hierarchyNode).typeId != self.HIERACHY_GROUP_TYPE_ID:
                raise EXC.MayaTypeError("{}: Component child is not a hierarchy group".format(NAME.getNodeFullName(hierarchyNode)))

            if memberType == MetaComponent.MemberType.Hierarchy:
                yield BASE.getMNode(hierarchyNode) if asMeta else hierarchyNode
            else:
                memberCategory = NAME.getNodeShortName(hierarchyNode)
                namingConvention = self.SETTINGS_GROUP_NAMING_CONVENTION if memberType is MetaComponent.MemberType.Settings else MetaComponent.PARAMETERS_GROUP_NAMING_CONVENTION
                memberNodeName = namingConvention.format(memberCategory=memberCategory)

                try:
                    member = DAG.getChildByName(hierarchyNode, memberNodeName)
                except EXC.MayaLookupError:
                    pass
                else:
                    yield BASE.getMNode(member) if asMeta else member

    def selectMembers(self, addFirst=False, add=False):
        """Select all members of this component, adding to or replacing the active selection list.

        Args:
            addFirst (:class:`bool`, optional): Whether to add members to the head of the active selection list.
                Defaults to :data:`False`.
            add (:class:`bool`, optional): Whether to add members to the tail of the active selection list.
                Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``addFirst`` and ``add`` are both :data:`True`.
        """
        if addFirst and add:
            raise ValueError("Choose either to add node to head or tail of the active selection")

        members = list(self.iterMembers())
        memberNames = [NAME.getNodePartialName(member) for member in members]

        if addFirst:
            cmds.select(memberNames, addFirst=addFirst)
        elif add:
            cmds.select(memberNames, add=add)
        else:
            cmds.select(memberNames)

    def selectMembersByCategory(self, memberCategory, addFirst=False, add=False):
        """Select members of this component by member category, adding to or replacing the active selection list.

        Args:
            memberCategory (:class:`basestring`): Member category used to filter existing members to select.
            addFirst (:class:`bool`, optional): Whether to add members to the head of the active selection list.
                Defaults to :data:`False`.
            add (:class:`bool`, optional): Whether to add members to the tail of the active selection list.
                Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``addFirst`` and ``add`` are both :data:`True`.
        """
        if addFirst and add:
            raise ValueError("Choose either to add node to head or tail of the active selection")

        members = list(self.iterMembersByCategory(memberCategory))
        memberNames = [NAME.getNodePartialName(member) for member in members]

        if addFirst:
            cmds.select(memberNames, addFirst=addFirst)
        elif add:
            cmds.select(memberNames, add=add)
        else:
            cmds.select(memberNames)

    def selectMembersByType(self, memberType, addFirst=False, add=False):
        """Select members of this component by member type, adding to or replacing the active selection list.

        Args:
            memberType (:class:`MemberType`): Member type used to filter existing members to select.
            addFirst (:class:`bool`, optional): Whether to add members to the head of the active selection list.
                Defaults to :data:`False`.
            add (:class:`bool`, optional): Whether to add members to the tail of the active selection list.
                Defaults to :data:`False`.

        Raises:
            :exc:`~exceptions.ValueError`: If ``addFirst`` and ``add`` are both :data:`True`.
        """
        if addFirst and add:
            raise ValueError("Choose either to add node to head or tail of the active selection")

        members = list(self.iterMembersByType(memberType))
        memberNames = [NAME.getNodePartialName(member) for member in members]

        if addFirst:
            cmds.select(memberNames, addFirst=addFirst)
        elif add:
            cmds.select(memberNames, add=add)
        else:
            cmds.select(memberNames)

    def createMemberByType(self, memberCategory, memberType, resultAsMeta=False):
        """Create a member for a given member category and member type.

        Args:
            memberCategory (:class:`basestring`): Member category of the new member.
            memberType (:class:`MemberType`): Member type of the new member.
            resultAsMeta (:data:`bool`, optional): Whether to return the new member as an `mNode`.
                Defaults to :data:`False` - return an :class:`OpenMaya.MObject` wrapper of the dependency node.

        Raises:
            :exc:`~exceptions.RuntimeError`: If ``memberType`` is equal to :attr:`~MemberType.Settings` or :attr:`~MemberType.Parameters` but a :attr:`~MemberType.Hierarchy` group corresponding to the given ``memberCategory`` does not exist.
            :exc:`~exceptions.RuntimeError`: If a member corresponding to the given ``memberCategory`` and ``memberType`` already exists.
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If a child of this component is named in accordance with the :attr:`HIERARCHY_GROUP_NAMING_CONVENTION` but its :class:`OpenMaya.MTypeId` does not correspond to the :attr:`HIERACHY_GROUP_TYPE_ID`.

        Returns:
            :class:`OpenMaya.MObject` | T <= :class:`msTools.metadata.systems.mrs.Meta`: Wrapper or `mNode` encapsulation of the new component member node. Type is determined by ``asMeta``.
        """
        if memberType == MetaComponent.MemberType.Hierarchy:
            hierarchyName = self.HIERARCHY_GROUP_NAMING_CONVENTION.format(memberCategory=memberCategory)

            try:
                hierarchyNode = self.getChildByName(hierarchyName)
            except EXC.MayaLookupError:
                hierarchyNode = DAG.createNode("transform", parent=self._node)
                DG.renameNode(hierarchyNode, hierarchyName)
            else:
                raise RuntimeError("{}: Hierarchy group already exists".format(NAME.getNodeFullName(hierarchyNode)))

            return BASE.getMNode(hierarchyNode) if resultAsMeta else hierarchyNode
        else:
            hierarchyName = self.HIERARCHY_GROUP_NAMING_CONVENTION.format(memberCategory=memberCategory)

            try:
                hierarchyNode = self.getChildByName(hierarchyName)
            except EXC.MayaLookupError:
                raise RuntimeError("{} hierarchy group must be created before {} group".format(memberCategory.name, memberType.name.lower()))

            if om2.MFnDependencyNode(hierarchyNode).typeId != self.HIERACHY_GROUP_TYPE_ID:
                raise EXC.MayaTypeError("{}: Component child is not a hierarchy group".format(NAME.getNodeFullName(hierarchyNode)))

            namingConvention = self.SETTINGS_GROUP_NAMING_CONVENTION if memberType is MetaComponent.MemberType.Settings else MetaComponent.PARAMETERS_GROUP_NAMING_CONVENTION
            nodeName = namingConvention.format(memberCategory=memberCategory)

            try:
                node = DAG.getChildByName(hierarchyNode, nodeName)
            except EXC.MayaLookupError:
                node = DAG.createNode("transform", parent=hierarchyNode)
                DG.renameNode(node, nodeName)
            else:
                raise RuntimeError("{}: {} group already exists".format(NAME.getNodeFullName(node), memberType.name))

            return BASE.getMNode(node) if resultAsMeta else node

    def addMembers(self, memberCategory, members=None, selected=False, force=True):
        """Add (non-DAG) dependency nodes as members of this component and assign to a given member category.

        Args:
            memberCategory (:class:`basestring`): Member category to assign members.
            members (iterable [:class:`OpenMaya.MObject`], optional): Wrappers of (non-DAG) dependency nodes to add as members of this component. Defaults to :data:`None`.
            selected (:class:`bool`, optional): Whether to add selected dependency nodes as members of this component. Defaults to :data:`False`.
            force (:class:`bool`, optional): Whether to force assign members to this component if they are already assigned to another asset. Defaults to :data:`True`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If an attempt is made to add a DAG node as a member. DAG members must be parented into the component DAG hierarchy.
        """
        memberNames = set()
        memberSet = []

        if members:
            for member in members:
                if member.hasFn(om2.MFn.kDagNode):
                    raise EXC.MayaTypeError("{}: DAG type node should be parented within component hierarchy".format(NAME.getNodeFullName(member)))

                if memberNames.add(NAME.getNodePartialName(member)):
                    memberSet.append(member)

        if selected:
            sel = om2.MGlobal.getActiveSelectionList()
            for i in xrange(sel.length()):
                member = sel.getDependNode(i)

                if member.hasFn(om2.MFn.kDagNode):
                    raise EXC.MayaTypeError("{}: DAG type node should be parented within component hierarchy".format(NAME.getNodeFullName(member)))

                if memberNames.add(NAME.getNodePartialName(member)):
                    memberSet.append(member)

        cmds.container(self.partialPathName, edit=True, addNode=memberNames, force=force)
        self._registerMembers(memberCategory, members=memberSet)

    def removeMembers(self, members=None, selected=False):
        """Remove (non-DAG) members from this component.

        Args:
            members (iterable [:class:`OpenMaya.MObject`], optional): Wrappers of (non-DAG) dependency node members to remove from this component. Defaults to :data:`None`.
            selected (:class:`bool`, optional): Whether to remove selected dependency node members from this component. Defaults to :data:`False`.

        Raises:
            :exc:`msTools.core.maya.exceptions.MayaTypeError`: If an attempt is made to remove a DAG member from this component. DAG members must be unparented from the component DAG hierarchy.
        """
        memberNames = set()
        memberSet = []

        if members:
            for member in members:
                if member.hasFn(om2.MFn.kDagNode):
                    raise EXC.MayaTypeError("{}: DAG type node should be unparented from component hierarchy".format(NAME.getNodeFullName(member)))

                if memberNames.add(NAME.getNodePartialName(member)):
                    memberSet.append(member)

        if selected:
            sel = om2.MGlobal.getActiveSelectionList()
            for i in xrange(sel.length()):
                member = sel.getDependNode(i)

                if member.hasFn(om2.MFn.kDagNode):
                    raise EXC.MayaTypeError("{}: DAG type node should be unparented from component hierarchy".format(NAME.getNodeFullName(member)))

                if memberNames.add(NAME.getNodePartialName(member)):
                    memberSet.append(member)

        cmds.container(self.partialPathName, edit=True, removeNode=memberNames)
        self._deregisterMembers(members=memberSet)

    # --- Public : Introspect ----------------------------------------------------------------------------

    def inspect(self):
        """Inspect the internal structure of this component.

        Warnings will be produced for any invalid state that is identified.

        This method simply invokes and returns the logical conjunction of all specialised inspection methods,
        including :meth:`inspectHierarchy`, :meth:`inspectRegistration`, :meth:`inspectNaming`, :meth:`inspectEncapsulation`, :meth:`inspectGuide` and :meth:`inspectScripts`.

        Returns:
            :class:`bool`: The logical conjunction of :meth:`inspectHierarchy`, :meth:`inspectRegistration`, :meth:`inspectNaming`, :meth:`inspectEncapsulation`, :meth:`inspectGuide` and :meth:`inspectScripts`.
        """
        return self.inspectHierarchy() and self.inspectRegistration() and self.inspectNaming() and self.inspectEncapsulation() and self.inspectGuide() and self.inspectScripts()

    def inspectHierarchy(self):
        """Inspect the DAG hierarchy structure of this component.

        A warning will be produced for any child node that is not a hierarchy group.

        Returns:
            :class:`bool`: :data:`True` if this component has a valid DAG hierarchy, otherwise :data:`False`.
        """
        hasValidHierarchy = True

        for child in self.iterChildren():
            if om2.MFnDependencyNode(child).typeId != MetaComponent.HIERACHY_GROUP_TYPE_ID:
                log.warning("{}: Component child is not a hierarchy group".format(NAME.getNodeFullName(child)))
                hasValidHierarchy = False

        if hasValidHierarchy:
            log.info("{!r}: Component has valid hierarchy".format(self))

        return hasValidHierarchy

    def inspectRegistration(self):
        """Inspect the member registration of this component.

        A warning will be produced for any non-DAG member that is not registered to a member category.

        Returns:
            :class:`bool`: :data:`True` if all non-DAG members of this component are registered to a member category, otherwise :data:`False`.
        """
        hasValidRegistration = True
        memberCategoryCacheAttr = self.memberCategoryCache
        memberCategories = memberCategoryCacheAttr.get()
        memberCategoryAttrNames = [self.MEMBER_CACHE_NAMING_CONVENTION.format(memberCategory) for memberCategory in memberCategories]

        for member in self.iterMembers():
            if not member.hasFn(om2.MFn.kDagNode):
                memberMessagePlug = OM.getPlugFromNodeByName(member, "message")
                memberMessageDestPlugs = memberMessagePlug.destinationsWithConversions()

                for memberMessageDestPlug in memberMessageDestPlugs:
                    if memberMessageDestPlug.isElement and memberMessageDestPlug.node() == self._node:
                        memberMessageDestAttrName = NAME.getAttributeName(memberMessageDestPlug.attribute())

                        if memberMessageDestAttrName in memberCategoryAttrNames:
                            break
                else:
                    log.warning("{}: Component (non-DAG) member is not registered to a member category".format(NAME.getNodeFullName(member)))
                    hasValidRegistration = False

        if hasValidRegistration:
            log.info("{!r}: Component has valid member registration".format(self))

        return hasValidRegistration

    def inspectNaming(self):
        """Inspect the naming of this component and its members.

        A warning will be produced if this component is not named in accordance with the :attr:`COMPONENT_NAMING_CONVENTION`.

        A warning will be produced if a member of this component is not named in accordance with the :attr:`MEMBER_NAMING_CONVENTION`.

        Returns:
            :class:`bool`: :data:`True` if all component and member naming is valid, otherwise :data:`False`.
        """
        hasValidNaming = True
        componentId = self.componentId
        componentName = MetaComponent.COMPONENT_NAMING_CONVENTION.format(componentId=self.componentId)

        if self.shortName != componentName:
            log.warning("{}: Component name must follow `COMPONENT_NAMING_CONVENTION`: {}".format(self.shortName, componentName))
            hasValidNaming = False

        for member in self.iterMembers():
            memberName = NAME.getNodeShortName(member)

            if not memberName.startswith(componentId) and not self.hasChild(member):
                log.warning("{}: Component member name must start with `componentId`: {}".format(NAME.getNodeFullName(member), self.componentId))
                hasValidNaming = False

        if hasValidNaming:
            log.info("{!r}: Component has valid naming".format(self))

        return hasValidNaming

    def inspectEncapsulation(self):
        """Inspect the encapsulation of this component.

        A warning will be produced if a non-input member has an upstream dependency that breaks component encapsulation.

        A warning will be produced if a non-output member has a downstream dependency that breaks component encapsulation.

        Returns:
            :class:`bool`: :data:`True` if this component has a valid input and output structure, otherwise :data:`False`.
        """
        hasValidEncapsulation = True
        members = list(self.iterMembers())
        inputMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Input))
        outputMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Output))

        for member in members:
            if member not in inputMembers:
                for sourcePlug, destPlug in DG.iterDependenciesByEdge(member, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
                    if sourcePlug.node() not in members:
                        log.warning("{}: Component (non-input) member has an upstream dependency that breaks component encapsulation: {} -> {}".format(
                            NAME.getNodeFullName(member), NAME.getPlugPartialName(sourcePlug), NAME.getPlugPartialName(destPlug)))
                        hasValidEncapsulation = False

            if member not in outputMembers:
                for sourcePlug, destPlug in DG.iterDependenciesByEdge(member, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                    if destPlug.node() not in members:
                        log.warning("{}: Component (non-output) member has a downstream dependency that breaks component encapsulation: {} -> {}".format(
                            NAME.getNodeFullName(member), NAME.getPlugPartialName(sourcePlug), NAME.getPlugPartialName(destPlug)))
                        hasValidEncapsulation = False

        if hasValidEncapsulation:
            log.info("{!r}: Component has valid encapsulation".format(self))

        return hasValidEncapsulation

    def inspectGuide(self):
        hasValidGuide = True

        if not self.isGuidable:
            log.info("{!r}: Component does not have a guide".format(self))
            return hasValidGuide

        guidedParametersGroup = self.getMemberByType(self.MemberCategoryPreset.Guided, self.MemberType.Parameters)

        try:
            guideCacheAttr = guidedParametersGroup.guideCache
        except EXC.MayaLookupError:
            if not self.isGuided:
                log.warning("{!r}: Component is unguided but is not tracking guided connections, manual reguiding may be required".format(self))
                hasValidGuide = False
        else:
            if not self.isGuided:
                guideCachePacked = guideCacheAttr.getPackedCompound()

                for (guideSourceElementPlug, guidedDestElementPlug) in guideCachePacked.getChildPlugGroups():
                    if not guideSourceElementPlug.isDestination or not guidedDestElementPlug.isDestination:
                        log.warning("{!r}: Component is unguided but has malformed tracking of guided connections, manual reguiding may be required".format(self))
                        hasValidGuide = False

        guideMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Guide))
        guidedMembers = list(self.iterMembersByCategory(self.MemberCategoryPreset.Guided))

        for guideMember in guideMembers:
            for sourcePlug, destPlug in DG.iterDependenciesByEdge(guideMember, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                if destPlug.node() not in guideMembers and destPlug.node() not in guidedMembers:
                    log.warning("{}: Component guide member has a downstream dependency that breaks guide conventions: {} -> {}".format(
                        NAME.getNodeFullName(guideMember), NAME.getPlugPartialName(sourcePlug), NAME.getPlugPartialName(destPlug)))
                    hasValidGuide = False

        if hasValidGuide:
            log.info("{!r}: Component has valid guide".format(self))

        return hasValidGuide

    def inspectScripts(self):
        hasValidScripts = True
        scriptIds = self.scriptIds.get()

        if not scriptIds:
            log.info("{!r}: Component does not have any registered scripts".format(self))
            return hasValidScripts

        for scriptId in self.scriptIds.get():
            if not self.hasScript(scriptId):
                log.warning("{}: Registered `scriptId` does not correspond to an existing script".format(scriptId))
                hasValidScripts = False

        if hasValidScripts:
            log.info("{!r}: Component has valid scripts for following registered `scriptIds`: {}".format(self, scriptIds))

        return hasValidScripts

    # --- Public : Extrospect ----------------------------------------------------------------------------

    def iterInputComponents(self, asMeta=False):
        seenComponentNodes = OM.MObjectSet()

        for inputMember in self.iterMembersByCategory(self.MemberCategoryPreset.Input):
            for sourceNode in DG.iterDependenciesByNode(inputMember, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
                try:
                    componentNode = getComponentFromMember(sourceNode, asMeta=False)
                except RuntimeError:
                    continue

                if seenComponentNodes.add(componentNode):
                    yield BASE.getMNode(componentNode) if asMeta else componentNode

    def iterOutputComponents(self, asMeta=False):
        seenComponentNodes = OM.MObjectSet()

        for inputMember in self.iterMembersByCategory(self.MemberCategoryPreset.Input):
            for sourceNode in DG.iterDependenciesByNode(inputMember, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
                try:
                    componentNode = getComponentFromMember(sourceNode, asMeta=False)
                except RuntimeError:
                    continue

                if seenComponentNodes.add(componentNode):
                    yield BASE.getMNode(componentNode) if asMeta else componentNode

    def getModule(self, asMeta=False):
        try:
            parent = self.getParent()
        except RuntimeError:
            raise RuntimeError("{!r}: Component is not part of a module".format(self))

        try:
            mType = BASE.getMTypeFromNode(parent)
        except EXC.MayaLookupError:
            raise RuntimeError("{!r}: Component is not part of a module".format(self))

        if issubclass(mType, MetaModule):
            return mType(parent) if asMeta else parent

        raise RuntimeError("{!r}: Component is not part of a module".format(self))

    def getRig(self, asMeta=False):
        try:
            parent = self.getParent()
        except RuntimeError:
            raise RuntimeError("{!r}: Component is not part of a rig".format(self))

        try:
            mType = BASE.getMTypeFromNode(parent)
        except EXC.MayaLookupError:
            raise RuntimeError("{!r}: Component is not part of a rig".format(self))

        if issubclass(mType, MetaModule):
            return mType(parent).getRig(asMeta=asMeta)
        elif issubclass(mType, MetaRig):
            return mType(parent) if asMeta else parent

        raise RuntimeError("{!r}: Component is not part of a rig".format(self))

    # --- Public : Files ----------------------------------------------------------------------------

    def export(self, increment=True, author=None, modification=None):
        if self.isAsset:
            raise RuntimeError("{!r}: Assetised component cannot be exported, deassetise to export changes".format(self))

        if self.isInstanced:
            raise RuntimeError("{!r}: Instanced component cannot be exported".format(self))
        elif not self.iterParents().next().hasFn(om2.MFn.kWorld):
            raise RuntimeError("{!r}: Parented component cannot be exported".format(self))

        if not self.inspect():
            log.warning("{!r}: Component has issues that must be fixed before assetisation, see warning log for details".format(self))

        # Create component type directory for initial export
        self._setupDirectory()

        self.creationDate = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Do not increment for initial export
        if increment and self.fileName:
            self.minorVersion = self.minorVersion + 1

        if author:
            self.author = author
        elif not self.author:
            self.author = getpass.getuser()

        # Assign default modification
        if not modification:
            modification = "new" if self.minorVersion == 0 else "update"

        fileName = MetaComponent.WIP_FILE_NAMING_CONVENTION.format(
            componentType=self.componentType, majorVersion=self.majorVersion, minorVersion=self.minorVersion, modification=modification)
        filePath = MetaComponent.WIP_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        self.fileName = fileName

        # Export component (force overriding existing files only when `increment` is false)
        self.selectMembers()
        self.select(add=True)
        cmds.file(exportSelected=filePath, type="mayaAscii", preserveReferences=True, force=not increment)

        # Export Node Editor tab data

        pass

    def assetise(self, author=None):
        if self.isAsset:
            raise RuntimeError("{!r}: Component is already assetised".format(self))

        if self.isInstanced:
            raise RuntimeError("{!r}: Instanced component cannot be assetised".format(self))
        elif not self.iterParents().next().hasFn(om2.MFn.kWorld):
            raise RuntimeError("{!r}: Parented component cannot be assetised".format(self))

        if self.absoluteNamespace != ":":
            raise RuntimeError("{!r}: Component must be within the root namespace for assetisation")

        if not self.inspect():
            raise RuntimeError("{!r}: Component has issues that must be fixed before assetisation, see warning log for details".format(self))

        # Ensure component type directory exists in case user never exported
        self._setupDirectory()

        self.isAsset = True
        self.minorVersion = 0
        self.creationDate = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if author:
            self.author = author
        elif not self.author:
            self.author = getpass.getuser()

        if self.isGuidable:
            if self.isGuided:
                # Guide tracking is baked once a component is assetised so we must ensure it is current
                self.updateGuideTracking()

                # Export the guide for requiding
                fileName = MetaComponent.GUIDE_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=self.majorVersion)
                filePath = MetaComponent.GUIDE_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

                self.selectMembersByCategory(self.MemberCategoryPreset.Guide)
                guideGroup = self.getMemberByType(self.MemberCategoryPreset.Guide, self.MemberType.Hierarchy, asMeta=True)

                guideGroup.relativeReparent()
                cmds.file(exportSelected=filePath, type="mayaAscii", preserveReferences=True)
                guideGroup.relativeReparent(parent=self._node)

                # Export guided connection data for reguiding
                fileName = MetaComponent.GUIDE_DATA_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=self.majorVersion)
                filePath = MetaComponent.GUIDE_DATA_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

                guideData = {"componentId": self.componentId, "inputEdges": [], "outputEdges": []}

                # Input -> Guide connections
                inputMembers = self.iterMembersByCategory(self.MemberCategoryPreset.Input)
                guideMembers = self.iterMembersByCategory(self.MemberCategoryPreset.Guide)

                for inputMember in inputMembers:
                    for (inputSourcePlug, destPlug) in DG.iterDependenciesByEdge(inputMember, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                        if destPlug.node() in guideMembers:
                            guideData["inputEdges"].append((NAME.getPlugFullName(inputSourcePlug), NAME.getPlugFullName(destPlug)))

                # Guide -> Guided connections
                guidedParametersGroup = self.getMemberByType(self.MemberCategoryPreset.Guided, self.MemberType.Parameters, asMeta=True)
                guideCacheAttr = guidedParametersGroup.guideCache
                guideCachePacked = guideCacheAttr.getPackedCompound()

                for (guideSourcePlug, guidedDestPlug) in guideCachePacked.getInputPlugGroups():
                    guideData["outputEdges"].append((NAME.getPlugFullName(guideSourcePlug), NAME.getPlugFullName(guidedDestPlug)))

                with open(filePath, 'w') as f:
                    json.dump(guideData, f)
            else:
                raise RuntimeError("{!r}: Guidable component must be guided for assetisation to ensure expectations are consistent when importing".format(self))

        # Export component
        fileName = MetaComponent.ASSET_FILE_NAMING_CONVENTION.format(componentType=self.componentType, majorVersion=self.majorVersion)
        filePath = MetaComponent.ASSET_PATH_NAMING_CONVENTION.format(componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        self.fileName = fileName

        self.selectMembers()
        self.select(add=True)
        cmds.file(exportSelected=filePath, type="mayaAscii", preserveReferences=True)

    def deassetise(self, author=None, modification=None):
        if not self.isAsset:
            raise RuntimeError("{!r}: Component is not assetised")

        self.isWip = True
        self.majorVersion = self.majorVersion + 1
        self.minorVersion = 0
        self.creationDate = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if author:
            self.author = author

        # Assign default modification
        if not modification:
            modification = "deassetised"

        fileName = MetaComponent.WIP_FILE_NAMING_CONVENTION.format(
            componentType=self.componentType, majorVersion=self.majorVersion, minorVersion=self.minorVersion, modification=modification)
        filePath = MetaComponent.WIP_PATH_NAMING_CONVENTION.format(
            componentPath=self.getComponentPath(), componentType=self.componentType, fileName=fileName)

        self.fileName = fileName

        # Export component (force overriding existing files only when `increment` is false)
        self.selectMembers()
        self.select(add=True)
        cmds.file(exportSelected=filePath, type="mayaAscii", preserveReferences=True)

    # --- Public : Delete ----------------------------------------------------------------------------

    def delete(self):
        pass


# ----------------------------------------------------------------------------
# --- MetaModule ---
# ----------------------------------------------------------------------------

class MetaModule(BASE.MetaDag):
    pass


# ----------------------------------------------------------------------------
# --- MetaRig ---
# ----------------------------------------------------------------------------

class MetaRig(BASE.MetaDag):
    pass
