"""
Operate on registered shading nodes in Maya.

----------------------------------------------------------------

Shading Groups
--------------

    Are nodes with a type identifier of ``'shadingEngine'``.
    They provide an interface for applying connected `shaders` to connected surface geometry `members` using the following setup:

    | shaders |xrarr| shading group
    | members |xrarr| shading group

    They are a type of set node sometimes referred to as renderable sets which use the same setup as object sets:

    member |xrarr| set |xrarr| partition

    - Partitions define a collection of mutually exclusive sets.
    - Members (instances/components) of one set cannot connect to another set in the same partition.

    Any surface geometry that requires shading in the viewport or a render engine must be connected to a shading group as a member.
    Members can be applied as either surface instances or a selection of components for a surface instance.

----------------------------------------------------------------

Shaders
-------

    Provide shading data for shading group members. They are commonly referred to as `materials`.

    There are three categories of shaders which interface with shading groups as follows:

    #. `Surface Shaders` - Connect to the ``'surfaceShader'`` plug of a shading group.
    #. `Volume Shaders` - Connect to the ``'volumeShader'`` plug of a shading group.
    #. `Displacement Shaders` - Connect to the ``'displacementShader'`` plug of a shading group.

    Third party rendering packages usually provide custom materials which interface with shading groups in a similiar way.

----------------------------------------------------------------

Textures
--------

    Provide texture data for shaders.

----------------------------------------------------------------

Creation
--------

    Shading nodes should not be created using :func:`cmds.createNode` or :meth:`OpenMaya.MDGModifier.createNode`.
    Maya provides commands which ensure shading nodes are `registered` upon creation:

    - :func:`cmds.sets`: Allows for creation of shading groups.
      Ensures each shading group is registered with the default ``'renderPartition'`` and ``'lightLinker1'`` nodes.
    - :func:`cmds.shadingNode`: Allows for creation of shaders and textures.
      Ensures each shader is registered with the ``'defaultShaderList1'`` node.
      Ensures each texture is registered with the ``'defaultTextureList1'`` node.

----------------------------------------------------------------
"""
from maya import cmds
from maya.api import OpenMaya as om2

from msTools.core.maya import decorator_utils as DECORATOR
from msTools.core.maya import dg_utils as DG
from msTools.core.maya import exceptions as EXC
from msTools.core.maya import om_utils as OM
from msTools.core.maya import plug_utils as PLUG


# --------------------------------------------------------------
# --- Validate ---
# --------------------------------------------------------------

def isSurfaceMember(surfacePath, shadingGroup):
    """Check if a path to a surface node is connected to a shading group via any of its members.

    Note:
        This method checks all connections from ``surfacePath`` to ``shadingGroup`` regardless of whether ``surfacePath`` is connected via a component list.
        Use :func:`isComponentMember` to check if specific components are assigned to ``shadingGroup``.

    Args:
        surfacePath (:class:`OpenMaya.MDagPath`): Path encapsulation of a surface node.
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``surfacePath`` does not reference a surface node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.

    Returns:
        :class:`bool`: :data:`True` if ``surfacePath`` is connected to ``shadingGroup`` via any of its members, otherwise :data:`False`.
    """
    OM.validateNodeType(surfacePath.node(), nodeType=om2.MFn.kSurface)
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    surfaceDagFn = om2.MFnDagNode(surfacePath)
    shadingGroups, _ = surfaceDagFn.getConnectedSetsAndMembers(surfacePath.instanceNumber(), True)
    return shadingGroup in shadingGroups


def isComponentMember(component, shadingGroup, allowSubset=False):
    """Check if a component selection is a member or sub-member of a shading group.

    Note:
        This method only checks the component members of ``shadingGroup``.
        Use :func:`isSurfaceMember` to complete a broader check of whether a surface node is connected to ``shadingGroup`` via any of its member.

    Args:
        component ((:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`)): A two-element :class:`tuple` representing component data.

            #. Path encapsulation of a surface node.
            #. Wrapper of a component object holding data of type :attr:`OpenMaya.MFn.kComponent`.

        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.
        allowSubset (:class:`bool`): Whether ``component`` should be considered a member if its elements represent a subset of a member assigned to ``shadingGroup``.
            Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``component`` does not provide surface node component data.

    Returns:
        :class:`bool`: :data:`True` if one of the following conditions is met:

        #. ``component`` represents a subset of component elements for a member assigned to ``shadingGroup`` and ``allowSubset`` is :data:`True`.
        #. ``component`` represents the exact component elements of a member assigned to ``shadingGroup``.

        Otherwise :data:`False`.
    """
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)
    if not component[0].node().hasFn(om2.MFn.kSurface) or not component[1].hasFn(om2.MFn.kComponent):
        raise EXC.MayaTypeError("The `component` argument does not point to surface node components")

    shadingGroupSetFn = om2.MFnSet(shadingGroup)
    path, componentWrapper = component

    # NOTE : If one component of a DAG node is in a set, checking if other components of that same DAG node are also in the set will always return true
    # shadingGroupSetFn.isMember(component) <-- ie. This is not reliable (We can check a MSelectionList instead)
    shadingGroupMemberSelection = shadingGroupSetFn.getMembers(False)

    # Check the components are contained within the set
    if shadingGroupMemberSelection.hasItem(component):
        if allowSubset:
            return True
        else:
            # Check if the components are an exact member (cross validation means they are equal)
            componentDataFn = om2.MFnComponentListData()
            _ = componentDataFn.create()
            componentDataFn.add(componentWrapper)

            for index in xrange(shadingGroupMemberSelection.length()):
                memberPath, memberComponent = shadingGroupMemberSelection.getComponent(index)
                if path == memberPath and componentDataFn.has(memberComponent):
                    return True

    return False


def hasMembers(shadingGroup):
    """
    Args:
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.

    Returns:
        :class:`bool`: :data:`True` if ``shadingGroup`` has members.
    """
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    shadingGroupMemberSelection = om2.MFnSet(shadingGroup).getMembers(False)
    return bool(shadingGroupMemberSelection.length())


# --------------------------------------------------------------
# --- Retrieve ---
# --------------------------------------------------------------

def getDefaultShadingGroup():
    """
    Returns:
        :class:`OpenMaya.MObject`: Default shading group.
    """
    return OM.getNodeByName("initialShadingGroup")


def getDefaultSurfaceShader():
    """
    Returns:
        :class:`OpenMaya.MObject`: Default shader.
    """
    return OM.getNodeByName("lambert1")


def getShaderNodeTypes():
    """
    Returns:
        :class:`list` [:class:`str`]: Shader node type identifiers.
    """
    return cmds.listNodeTypes("shader")


def getTextureNodeTypes():
    """
    Returns:
        :class:`list` [:class:`str`]: Texture node type identifiers.
    """
    return cmds.listNodeTypes("texture")


def iterShadingGroups(default=True, user=True, used=True, unused=True):
    """Yield shading group nodes from the scene.

    Note:
        At least one parameter must be :data:`True` from each pair of filter options:

        - Filter shading groups based on creation: ``default``, ``user``.
        - Filter shading groups based on usage: ``used``, ``unused``.

    Args:
        default (:class:`bool`, optional): Whether to include default shading groups (ie. ``'initialShadingGroup'``, ``'initialParticleSE'``). Defaults to :data:`True`.
        user (:class:`bool`, optional): Whether to include user created shading groups. Defaults to :data:`True`.
        used (:class:`bool`, optional): Whether to include shading groups which have members. Defaults to :data:`True`.
        unused (:class:`bool`, optional): Whether to include shading groups which do not have members. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for each pair of filter options.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of shading group nodes for the given parameters.
    """
    if not any([default, user]) or not any([used, unused]):
        raise ValueError("At least one argument must be true from each of the following pairs of filter options: (default, user), (used, unused)")

    # Alternatively we could query the 'renderPartition.sets' array plug
    shadingGroupGen = DG.iterNodes(filterTypes=(om2.MFn.kShadingEngine,))

    # Check which properties need filtering
    filter1 = not (default and user)
    filter2 = not (used and unused)

    for shadingGroup in shadingGroupGen:
        shadingGroupFn = om2.MFnSet(shadingGroup)

        if filter1:
            isDefault = shadingGroupFn.isDefaultNode
            keepDefault = isDefault and default
            keepUser = not isDefault and user
            if not (keepDefault or keepUser):
                continue

        if filter2:
            shadingGroupMemberSelection = shadingGroupFn.getMembers(False)
            isUsed = shadingGroupMemberSelection.length()
            keepUsed = isUsed and used
            keepUnused = not isUsed and unused
            if not (keepUsed or keepUnused):
                continue

        yield shadingGroup


def iterShadingGroupsFromGeometry(surfacePath, default=True, user=True, allInstances=False):
    """Yield shading groups connected to a surface node.

    Note:
        At least one parameter must be :data:`True` from the following pair of filter options:

        - Filter shading groups based on creation: ``default``, ``user``.

    Args:
        surfacePath (:class:`OpenMaya.MDagPath`): Path to a surface node.
        default (:class:`bool`, optional): Whether to include default shading groups connected to ``surfacePath`` (eg. ``'initialShadingGroup'``, ``'initialParticleSE'``).
            Defaults to :data:`True`.
        user (:class:`bool`, optional): Whether to include user created shading groups connected to ``surfacePath``. Defaults to :data:`True`.
        allInstances (:class:`bool`, optional): Whether to search all instances of the node referenced by ``surfacePath`` for connected shading groups.
            Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for the pair of filter options.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``surfacePath`` does not reference a surface node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of shading group nodes connected to ``surfacePath`` for the given parameters.
    """
    if not any([default, user]):
        raise ValueError("At least one argument must be true from the following pair of filter options: (default, user)")

    OM.validateNodeType(surfacePath.node(), nodeType=om2.MFn.kSurface)

    surfaceDagFn = om2.MFnDagNode(surfacePath)

    if allInstances:
        shadingGroupSet = OM.MObjectSet()

        # Parameter 'indirect' is true so that instancing of ancestor nodes contributes to the total number of instances
        for instanceNumber in xrange(surfaceDagFn.instanceCount(True)):
            # Parameter 'renderableSetsOnly' is true so only shading engines are returned
            shadingGroups, _ = surfaceDagFn.getConnectedSetsAndMembers(instanceNumber, True)
            shadingGroupSet.update(shadingGroups)
    else:
        shadingGroupSet, _ = surfaceDagFn.getConnectedSetsAndMembers(surfacePath.instanceNumber(), True)

    # Filter
    for shadingGroup in shadingGroupSet:
        isDefault = om2.MFnDependencyNode(shadingGroup).isDefaultNode
        keepDefault = isDefault and default
        keepUser = not isDefault and user
        if keepDefault or keepUser:
            yield shadingGroup


def iterShaders(default=True, user=True, used=True, unused=True):
    """Yield shader nodes from the scene.

    Note:
        Only registered shaders will be generated. A registered shader is one which is connected to ``'defaultShaderList1'``.

        At least one parameter must be :data:`True` from each pair of filter options:

        - Filter shaders based on creation: ``default``, ``user``.
        - Filter shaders based on usage: ``used``, ``unused``.

    Args:
        default (:class:`bool`, optional): Whether to include default shaders (ie. ``'lambert1'``, ``'particleCloud1'``). Defaults to :data:`True`.
        user (:class:`bool`, optional): Whether to include user created shaders. Defaults to :data:`True`.
        used (:class:`bool`, optional): Whether to include shaders which are currently being used to shade geometry.
            Meaning any shader which is connected upstream of a shading group that has members. Defaults to :data:`True`.
        unused (:class:`bool`, optional): Whether to include shaders which are not currently being used to shade geometry.
            Meaning any shader which is not connected to a shading group or is connected to one which has no members. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for each pair of filter options.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of shader nodes for the given parameters.
    """
    if not any([default, user]) or not any([used, unused]):
        raise ValueError("At least one argument must be true from each of the following pairs of filter options: (default, user), (used, unused)")

    # Alternatively we could query the 'defaultShaderList1.shaders' array plug but we would have to deal with the internal shaders
    shaders = []
    shaderNames = cmds.ls(long=True, materials=True)
    for shaderName in shaderNames:
        shader = OM.getNodeByName(shaderName)
        shaders.append(shader)

    # Check which properties need filtering
    filter1 = not (default and user)
    filter2 = not (used and unused)

    for shader in shaders:
        shaderDepFn = om2.MFnDependencyNode(shader)

        if filter1:
            isDefault = shaderDepFn.isDefaultNode
            keepDefault = isDefault and default
            keepUser = not isDefault and user
            if not (keepDefault or keepUser):
                continue

        if filter2:
            isUsed = False
            for connectedShadingGroup in DG.iterDependenciesByNode(shader, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kShadingEngine,)):
                shadingGroupMemberSelection = om2.MFnSet(connectedShadingGroup).getMembers(False)  # flatten = False
                if shadingGroupMemberSelection.length():
                    isUsed = True
                    break

            keepUsed = isUsed and used
            keepUnused = not isUsed and unused
            if not (keepUsed or keepUnused):
                continue

        yield shader


def iterShadersFromShadingGroup(shadingGroup, default=True, user=True):
    """Yield shaders connected to a shading group node.

    Note:
        Only registered shaders will be generated. A registered shader is one which is connected to ``'defaultShaderList1'``.

        At least one parameter must be :data:`True` from the following pair of filter options:

        - Filter shaders based on creation: ``default``, ``user``.

    Args:
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.
        default (:class:`bool`, optional): Whether to include default shaders connected to ``shadingGroup`` (eg. ``'lambert1'``, ``'particleCloud1'``). Defaults to :data:`True`.
        user (:class:`bool`, optional): Whether to include user created shaders connected to ``shadingGroup``. Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for the pair of filter options.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of shader nodes connected to ``shadingGroup`` for the given parameters.
    """
    if not any([default, user]):
        raise ValueError("At least one argument must be true from the following pair of filter options: (default, user)")

    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    shaders = []
    for connectedNode in DG.iterDependenciesByNode(shadingGroup, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
        # All shaders are connected to the 'defaultShaderList1' node
        for connectedShaderList in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kShaderList,)):
            if om2.MFnDependencyNode(connectedShaderList).name() == "defaultShaderList1":
                shaders.append(connectedNode)

    # Check which properties need filtering
    filter1 = not (default and user)

    for shader in shaders:
        shaderDepFn = om2.MFnDependencyNode(shader)

        if filter1:
            isDefault = shaderDepFn.isDefaultNode
            keepDefault = isDefault and default
            keepUser = not isDefault and user
            if not (keepDefault or keepUser):
                continue

        yield shader


def iterShadersFromGeometry(surfacePath, default=True, user=True, allInstances=False):
    """Yield shaders influencing the shading of a surface node.

    Note:
        Only registered shaders will be generated. A registered shader is one which is connected to ``'defaultShaderList1'``.

        At least one parameter must be :data:`True` from the following pair of filter options:

        - Filter shaders based on creation: ``default``, ``user``.

    Args:
        surfacePath (:class:`OpenMaya.MDagPath`): Path to a surface node.
        default (:class:`bool`, optional): Whether to include default shaders influencing the shading of ``surfacePath`` (eg. ``'lambert1'``, ``'particleCloud1'``). Defaults to :data:`True`.
        user (:class:`bool`, optional): Whether to include user created shaders influencing the shading of ``surfacePath``. Defaults to :data:`True`.
        allInstances (:class:`bool`, optional): Whether to search all instances of the node referenced by ``surfacePath`` for shaders influencing their shading.
            Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for the pair of filter options.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``surfacePath`` does not reference a surface node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of shader nodes influencing the shading of ``surfacePath`` for the given parameters.
    """
    if not any([default, user]):
        raise ValueError("At least one argument must be true from the following pair of filter options: (default, user)")

    shaderSet = OM.MObjectSet()

    # Filter shaders, not shading groups
    for shadingGroup in iterShadingGroupsFromGeometry(surfacePath, allInstances=allInstances):
        for shader in iterShadersFromShadingGroup(shadingGroup, default=default, user=user):
            if shaderSet.add(shader):
                yield shader


def iterTextures(used=True, unused=True, includePlacementNodes=True):
    """Yield texture nodes and there connected placement nodes from the scene.

    Note:
        Only registered textures and there connected placement nodes will be generated. A registered texture is one which is connected to ``'defaultTextureList1'``.

        At least one parameter must be :data:`True` from the following pair of filter options:

        - Filter textures based on usage: ``used``, ``unused``.

    Args:
        used (:class:`bool`, optional): Whether to include textures which are currently being used to shade geometry.
            Meaning any texture which is connected upstream of a shading group that has members. Defaults to :data:`True`.
        unused (:class:`bool`, optional): Whether to include textures which are not currently being used to shade geometry.
            Meaning any texture which is not connected upstream of a shading group or is connected upstream of one which has no members. Defaults to :data:`True`.
        includePlacementNodes (:class:`bool`, optional): Whether to also generate placement nodes (eg. ``place2dTexture``) that are connected to resulting textures.
            Defaults to :data:`True`.

    Raises:
        :exc:`~exceptions.ValueError`: If there is not at least one :data:`True` parameter for each pair of filter options.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of texture nodes and their connected placement nodes for the given parameters.
    """
    if not any([used, unused]):
        raise ValueError("At least one argument must be true from the following pair of filter options: (used, unused)")

    # Alternatively we could query the 'defaultTextureList1.textures' array plug
    textures = []
    textureNames = cmds.ls(long=True, textures=True)
    for textureName in textureNames:
        texture = OM.getNodeByName(textureName)
        textures.append(texture)

    # Ensure each placement node is unique
    placementNodeSet = OM.MObjectSet()

    # Check which properties need filtering
    filter1 = not (used and unused)

    for texture in textures:
        if filter1:
            isUsed = False
            # Verify the texture is directly connected to a shader
            for connectedNode in DG.iterDependenciesByNode(texture, directionType=om2.MItDependencyGraph.kDownstream, walk=False):
                # All shaders are connected to the 'defaultShaderList1' node
                for connectedShaderList in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kShaderList,)):
                    if om2.MFnDependencyNode(connectedShaderList).name() == "defaultShaderList1":
                        for connectedShadingGroup in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kShadingEngine,)):
                            shadingGroupMemberSelection = om2.MFnSet(connectedShadingGroup).getMembers(False)  # flatten = False
                            if shadingGroupMemberSelection.length():
                                isUsed = True
                                break

            keepUsed = isUsed and used
            keepUnused = not isUsed and unused
            if not (keepUsed or keepUnused):
                continue

        yield texture

        if includePlacementNodes:
            for placementNode in DG.iterDependenciesByNode(texture, directionType=om2.MItDependencyGraph.kUpstream, walk=False, filterTypes=(om2.MFn.kPlace2dTexture, om2.MFn.kPlace3dTexture)):
                if placementNodeSet.add(placementNode):
                    yield placementNode


def iterTexturesFromShader(shader, includePlacementNodes=True):
    """Yield textures connected to a shader node.

    Note:
        Only registered textures and there connected placement nodes will be generated. A registered texture is one which is connected to ``'defaultTextureList1'``.

    Args:
        shader (:class:`OpenMaya.MObject`): Wrapper of a shader node.
        includePlacementNodes (:class:`bool`, optional): Whether to also generate placement nodes (eg. ``place2dTexture``) that are connected to resulting textures.
            Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shader`` does not reference a dependency node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of texture nodes connected to ``shader`` and their connected placement nodes.
    """
    OM.validateNodeType(shader)

    # Ensure each placement node is unique
    placementNodeSet = OM.MObjectSet()

    for connectedNode in DG.iterDependenciesByNode(shader, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
        # All textures are connected to the 'defaultTextureList1' node
        for connectedTextureList in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kTextureList,)):
            if om2.MFnDependencyNode(connectedTextureList).name() == "defaultTextureList1":
                yield connectedNode

                if includePlacementNodes:
                    for placementNode in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kUpstream, walk=False, filterTypes=(om2.MFn.kPlace2dTexture, om2.MFn.kPlace3dTexture)):
                        if placementNodeSet.add(placementNode):
                            yield placementNode


def iterTexturesFromShadingGroup(shadingGroup, includePlacementNodes=True):
    """Yield textures connected upstream of a shading group node.

    Note:
        Only registered textures and there connected placement nodes will be generated. A registered texture is one which is connected to ``'defaultTextureList1'``.

    Args:
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.
        includePlacementNodes (:class:`bool`, optional): Whether to also generate placement nodes (eg. ``place2dTexture``) that are connected to resulting textures.
            Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of texture nodes connected upstream of ``shadingGroup`` and their connected placement nodes.
    """
    # Ensure each texture and placement node is unique
    textureSet = OM.MObjectSet()
    placementNodeSet = OM.MObjectSet()

    for shader in iterShadersFromShadingGroup(shadingGroup):
        for connectedNode in DG.iterDependenciesByNode(shader, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
            # All textures are connected to the 'defaultTextureList1' node
            for connectedTextureList in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kTextureList,)):
                if om2.MFnDependencyNode(connectedTextureList).name() == "defaultTextureList1":
                    if textureSet.add(connectedNode):
                        yield connectedNode

                        if includePlacementNodes:
                            for placementNode in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kUpstream, walk=False, filterTypes=(om2.MFn.kPlace2dTexture, om2.MFn.kPlace3dTexture)):
                                if placementNodeSet.add(placementNode):
                                    yield placementNode


def iterTexturesFromGeometry(surfacePath, allInstances=False, includePlacementNodes=True):
    """Yield textures connected upstream of a surface node.

    Note:
        Only registered textures and there connected placement nodes will be generated. A registered texture is one which is connected to ``'defaultTextureList1'``.

    Args:
        surfacePath (:class:`OpenMaya.MDagPath`): Path to a surface node.
        allInstances (:class:`bool`, optional): Whether to search all instances of the node referenced by ``surfacePath`` for textures influencing their shading.
            Defaults to :data:`False`.
        includePlacementNodes (:class:`bool`, optional): Whether to also generate placement nodes (eg. ``place2dTexture``) that are connected to resulting textures.
            Defaults to :data:`True`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``surfacePath`` does not reference a surface node.

    Yields:
        :class:`OpenMaya.MObject`: Wrappers of texture nodes influencing the shading of ``surfacePath`` and their connected placement nodes.
    """
    # Ensure each shader, texture and placement node is unique
    shaderSet = OM.MObjectSet()
    textureSet = OM.MObjectSet()
    placementNodeSet = OM.MObjectSet()

    for shadingGroup in iterShadingGroupsFromGeometry(surfacePath, allInstances=allInstances):
        for shader in iterShadersFromShadingGroup(shadingGroup):
            if shaderSet.add(shader):
                for connectedNode in DG.iterDependenciesByNode(shader, directionType=om2.MItDependencyGraph.kUpstream, walk=False):
                    # All textures are connected to the 'defaultTextureList1' node
                    for connectedTextureList in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kDownstream, walk=False, filterTypes=(om2.MFn.kTextureList,)):
                        if om2.MFnDependencyNode(connectedTextureList).name() == "defaultTextureList1":
                            if textureSet.add(connectedNode):
                                yield connectedNode

                                if includePlacementNodes:
                                    for placementNode in DG.iterDependenciesByNode(connectedNode, directionType=om2.MItDependencyGraph.kUpstream, walk=False, filterTypes=(om2.MFn.kPlace2dTexture, om2.MFn.kPlace3dTexture)):
                                        if placementNodeSet.add(placementNode):
                                            yield placementNode


def getMembersFromShadingGroup(shadingGroup):
    """Return members of a shading group.

    Args:
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.

    Returns:
        (:class:`OpenMaya.MSelectionList`, (:class:`bool`, ...)): A two-element :class:`tuple`.

        #. Contains the members of ``shadingGroup``.
        #. :class:`tuple` of :class:`bool` values for each member in the :class:`OpenMaya.MSelectionList`.

           - A :data:`False` value indicates the member is an :class:`OpenMaya.MDagPath`.
           - A :data:`True` value indicates the member is an (:class:`OpenMaya.MDagPath`, :class:`OpenMaya.MObject`) component tuple.
    """
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    shadingGroupMemberSelection = om2.MFnSet(shadingGroup).getMembers(False)
    shadingGroupMemberTypes = []

    for memberIndex in xrange(shadingGroupMemberSelection.length()):
        component = shadingGroupMemberSelection.getComponent(memberIndex)
        if component[1].apiType() == om2.MFn.kInvalid:
            shadingGroupMemberTypes.append(False)
        else:
            shadingGroupMemberTypes.append(True)

    return shadingGroupMemberSelection, tuple(shadingGroupMemberTypes)


# --------------------------------------------------------------
# --- Connect ---
# --------------------------------------------------------------

def removeMembersFromShadingGroup(memberSelection, shadingGroup):
    """Remove surface node components and instances from a shading group.

    Note:
        If a ``memberSelection`` element represents the components of a surface node instance, any intersecting components of any ``shadingGroup`` member will be removed.
        If a ``memberSelection`` element represents a surface node instance, any ``shadingGroup`` member of that instance will also be removed.

    Args:
        memberSelection (:class:`OpenMaya.MSelectionList`): Selection containing surface node components and instances to remove from ``shadingGroup``.
            Each element must be retrievable via :meth:`OpenMaya.MSelectionList.getDagPath`.
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``memberSelection`` contains elements which do not reference a surface node.
    """
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    for index in xrange(memberSelection.length()):
        try:
            surfacePath = memberSelection.getDagPath(index)
        except TypeError:
            raise EXC.MayaTypeError("Element index {} of `memberSelection` argument is not a surface node".format(index))

        if not surfacePath.node().hasFn(om2.MFn.kSurface):
            raise EXC.MayaTypeError("{}: element of `memberSelection` argument is not a surface node".format(surfacePath.fullPathName()))

    shadingGroupName = om2.MFnDependencyNode(shadingGroup).name()
    memberSelectionStrings = memberSelection.getSelectionStrings()
    cmds.sets(memberSelectionStrings, remove=shadingGroupName)


@DECORATOR.undoOnError(StandardError)
def removeMembersFromAllShadingGroups(memberSelection):
    """Remove surface node components and instances from all connected shading groups.

    Note:
        If a ``memberSelection`` element represents the components of a surface node instance, any intersecting components of any shading group member will be removed.
        If a ``memberSelection`` element represents a surface node instance, any shading group member of that instance will also be removed.

    Args:
        memberSelection (:class:`OpenMaya.MSelectionList`): Selection containing surface node components and instances to remove from any connected shading groups.
            Each element must be retrievable via :meth:`OpenMaya.MSelectionList.getDagPath`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``memberSelection`` contains elements which do not reference a surface node.
    """
    memberDagFn = om2.MFnDagNode()

    for index in xrange(memberSelection.length()):
        try:
            memberPath = memberSelection.getDagPath(index)
            memberComponent = memberSelection.getComponent(index)
        except TypeError:
            raise EXC.MayaTypeError("Element index {} of `memberSelection` argument is not a surface node".format(index))

        if not memberPath.node().hasFn(om2.MFn.kSurface):
            raise EXC.MayaTypeError("{}: element of `memberSelection` argument is not a surface node".format(memberPath.fullPathName()))

        memberDagFn.setObject(memberPath)

        selection = om2.MSelectionList()
        if memberComponent[1].apiType() == om2.MFn.kInvalid:
            selection.add(memberPath)
        else:
            selection.add(memberComponent)

        instanceNumber = memberPath.instanceNumber()
        shadingGroups, _ = memberDagFn.getConnectedSetsAndMembers(instanceNumber, True)
        for shadingGroup in shadingGroups:
            removeMembersFromShadingGroup(selection, shadingGroup)


def addMembersToShadingGroup(memberSelection, shadingGroup, force=False):
    """Add surface node components and instances to a shading group.

    Note:
        If any of the ``memberSelection`` components or instances are already assigned to a shading group, ``force`` must be :data:`True`.
        The components of each ``memberSelection`` element will be removed from their current shading group and assigned to ``shadingGroup``.

    Args:
        memberSelection (:class:`OpenMaya.MSelectionList`): Selection containing surface node components and instances to add to ``shadingGroup``.
            Each element must be retrievable via :meth:`OpenMaya.MSelectionList.getDagPath`.
        shadingGroup (:class:`OpenMaya.MObject`): Wrapper of a shading group node.
        force (:class:`bool`): Whether to force the member assignment of ``memberSelection`` elements to ``shadingGroup``.
            If an element is already a member of a shading group it is necessary to set this :data:`True`. Defaults to :data:`False`.

    Raises:
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``shadingGroup`` does not reference a shading group node.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``memberSelection`` contains elements which do not reference a surface node.
        :exc:`~exceptions.RuntimeError`: If ``memberSelection`` contains an element which is already a member of a shading group and ``force`` is :data:`False`.
    """
    OM.validateNodeType(shadingGroup, nodeType=om2.MFn.kShadingEngine)

    for index in xrange(memberSelection.length()):
        try:
            surfacePath = memberSelection.getDagPath(index)
        except TypeError:
            raise EXC.MayaTypeError("Element index {} of `memberSelection` argument is not a surface node".format(index))

        if not surfacePath.node().hasFn(om2.MFn.kSurface):
            raise EXC.MayaTypeError("{}: element of `memberSelection` argument is not a surface node".format(surfacePath.fullPathName()))

    shadingGroupName = om2.MFnDependencyNode(shadingGroup).name()
    memberSelectionStrings = memberSelection.getSelectionStrings()

    if force:
        cmds.sets(memberSelectionStrings, forceElement=shadingGroupName)
    else:
        # This will raise an error if any of the components already have a shading group assignment
        cmds.sets(memberSelectionStrings, addElement=shadingGroupName)

    # Updating components sometimes will not take effect until the SG connections have been dirtied
    # As long as all components for a geometry instance are connected to a shading group, this will fix any viewport issues caused by disconnecting components
    cmds.evalDeferred("cmds.dgdirty('{}')".format(shadingGroupName))


# --------------------------------------------------------------
# --- Create ---
# --------------------------------------------------------------

@DECORATOR.undoOnError(StandardError)
def createShader(shaderType="lambert", memberSelection=None, force=False):
    """Create a new shader and shading group network. Assign surface node components and instances as members.

    Provides the ability to create shader networks which are built using the same behaviour as the `Create Render Node interface`.

    .. https://help.autodesk.com/view/MAYAUL/2017/ENU/?guid=__files_Writing_a_Shading_Node_Shading_nodes_classification_htm

    Args:
        shaderType (:class:`basestring`, optional): Shader node type identifier. Defaults to ``'lambert'``.
        memberSelection (:class:`OpenMaya.MSelectionList`): Selection containing surface node components and instances to add to the new shading group.
            Each element must be retrievable via :meth:`OpenMaya.MSelectionList.getDagPath`.
        force (:class:`bool`): Whether to force the member assignment of ``memberSelection`` elements to the new shading group.
            If an element is already a member of a shading group it is necessary to set this :data:`True`. Defaults to :data:`False`.

    Raises:
        :exc:`~exceptions.ValueError`: If ``shaderType`` is not a valid shader node type identifier.
        :exc:`msTools.core.maya.exceptions.MayaTypeError`: If ``memberSelection`` contains elements which do not reference a surface node.
        :exc:`~exceptions.RuntimeError`: If ``memberSelection`` contains an element which is already a member of a shading group and ``force`` is :data:`False`.

    Returns:
        (:class:`OpenMaya.MObject`, :class:`OpenMaya.MObject`): A two-element :class:`tuple`.

        #. Wrapper of the new shader node.
        #. Wrapper of the new shading group node.
    """
    classification = om2.MFnDependencyNode.classification(shaderType)
    if not classification:
        raise ValueError("{}: Unkown shader type".format(shaderType))

    isSurfaceShader = "shader/surface" in classification
    isDisplacementShader = "shader/displacement" in classification
    isVolumetricShader = "shader/volume" in classification

    if not any([isSurfaceShader, isDisplacementShader, isVolumetricShader]):
        raise ValueError("{}: Unkown shader type".format(shaderType))

    # Create the shader (this automatically registers it with 'defaultShaderList1')
    shaderName = cmds.shadingNode("lambert", asShader=True)
    shader = OM.getNodeByName(shaderName)

    # Create the shading group (this automatically creates a materialInfo node and registers the SG with the 'renderPartition' and 'lightLinker1')
    shadingGroupName = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shaderType + "SG")
    shadingGroup = OM.getNodeByName(shadingGroupName)

    if isSurfaceShader:
        PLUG.connect(OM.getPlugFromNodeByName(shader, "outColor"), OM.getPlugFromNodeByName(shadingGroup, "surfaceShader"))
    elif isDisplacementShader:
        PLUG.connect(OM.getPlugFromNodeByName(shader, "displacement"), OM.getPlugFromNodeByName(shadingGroup, "displacementShader"))
    elif isVolumetricShader:
        PLUG.connect(OM.getPlugFromNodeByName(shader, "outColor"), OM.getPlugFromNodeByName(shadingGroup, "volumeShader"))

    if memberSelection:
        addMembersToShadingGroup(memberSelection, shadingGroup, force=force)

    return shader, shadingGroup


# --------------------------------------------------------------
# --- Delete ---
# --------------------------------------------------------------

@DECORATOR.undoOnError(StandardError)
def deleteUnusedShadingNodes(shadingGroups=False, shaders=False, textures=False):
    """Delete unused non-default shading nodes.

    Note:
        An unused shading node is defined as any registered shading node which is not currently influencing the shading of geometry.
        For example an unused shading group is one which has no members.

    Args:
        shadingGroups (:class:`bool`, optional): Whether to delete unused shading group nodes. Defaults to :data:`False`.
        shaders (:class:`bool`, optional): Whether to delete unused shader nodes. Defaults to :data:`False`.
        textures (:class:`bool`, optional): Whether to delete unused texture and placement nodes. Defaults to :data:`False`.
    """
    if shadingGroups:
        for shadingGroup in list(iterShadingGroups(used=False, default=False)):
            DG.deleteNode(shadingGroup)

    if shaders:
        for shader in list(iterShaders(used=False, default=False)):
            DG.deleteNode(shader)

    if textures:
        for texture in list(iterTextures(used=False)):
            DG.deleteNode(texture)
