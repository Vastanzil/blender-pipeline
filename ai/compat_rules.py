"""
ai/compat_rules.py
Version-aware Blender API compatibility rules injected into every AI prompt.
Detects major version at runtime and injects the correct API surface.
"""


def get_compat_block(ver: tuple) -> str:
    """Return a compat rules string for the given Blender version tuple."""
    major = ver[0] if ver else 4

    common = (
        "BPS_COMPAT_RULES:\n"
        "- Always 'import bpy' at the top of every snippet.\n"
        "- Use bpy.context.view_layer.objects.active to get/set active object.\n"
        "- Use bpy.ops.object.select_all(action='DESELECT') before selecting.\n"
        "- Check object existence: if name not in bpy.data.objects: ...\n"
        "- For collections: bpy.data.collections.new(name) then link.\n"
    )

    if major >= 5:
        version_rules = (
            "BLENDER_5x_API:\n"
            "- Geometry Nodes new socket: ng.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')\n"
            "- Render engine identifier: 'BLENDER_EEVEE_NEXT' (not BLENDER_EEVEE)\n"
            "- Shader output node: bpy.data.materials[name].node_tree.nodes['Material Output']\n"
            "- Object data access: obj.data (mesh), obj.data.materials for material slots.\n"
            "- GN modifier: obj.modifiers.new(name, 'NODES'); mod.node_group = ng\n"
            "- Use outputs[0] index for value nodes (not named socket in 5.x).\n"
        )
    else:
        version_rules = (
            "BLENDER_4x_API:\n"
            "- Geometry Nodes new socket: ng.inputs.new('NodeSocketFloat', name)\n"
            "- Render engine identifier: 'BLENDER_EEVEE'\n"
            "- Shader output node: material.node_tree.nodes.get('Material Output')\n"
            "- GN modifier: obj.modifiers.new(name, 'NODES'); mod.node_group = ng\n"
            "- Named socket access: node.inputs['Value'] syntax works in 4.x.\n"
        )

    return common + version_rules
