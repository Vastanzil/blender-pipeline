"""blender/materials.py — Code-gen helpers for Blender materials (bpy strings)."""


class MaterialBuilder:
    def create_pbr(self, name, base_color=(0.8, 0.8, 0.8, 1.0),
                   roughness=0.5, metallic=0.0):
        r, g, b, a = base_color
        return (
            "import bpy\n"
            f"mat = bpy.data.materials.new(name='{name}')\n"
            "mat.use_nodes = True\n"
            "nodes = mat.node_tree.nodes\n"
            "bsdf  = nodes.get('Principled BSDF')\n"
            f"bsdf.inputs['Base Color'].default_value = ({r}, {g}, {b}, {a})\n"
            f"bsdf.inputs['Roughness'].default_value  = {roughness}\n"
            f"bsdf.inputs['Metallic'].default_value   = {metallic}\n"
            f"print('Material created: {name}')\n"
        )

    def assign(self, obj_name, mat_name):
        return (
            "import bpy\n"
            f"obj = bpy.data.objects['{obj_name}']\n"
            f"mat = bpy.data.materials.get('{mat_name}') or bpy.data.materials.new('{mat_name}')\n"
            "if obj.data.materials:\n"
            "    obj.data.materials[0] = mat\n"
            "else:\n"
            "    obj.data.materials.append(mat)\n"
            f"print('Material assigned: {mat_name} -> {obj_name}')\n"
        )

    def add_image_texture(self, mat_name, filepath, uv_map="UVMap"):
        return (
            "import bpy\n"
            f"mat   = bpy.data.materials['{mat_name}']\n"
            "nodes = mat.node_tree.nodes\n"
            "links = mat.node_tree.links\n"
            "bsdf  = nodes.get('Principled BSDF')\n"
            "tex   = nodes.new('ShaderNodeTexImage')\n"
            f"tex.image = bpy.data.images.load(r'{filepath}')\n"
            "uv    = nodes.new('ShaderNodeUVMap')\n"
            f"uv.uv_map = '{uv_map}'\n"
            "links.new(uv.outputs['UV'],       tex.inputs['Vector'])\n"
            "links.new(tex.outputs['Color'],   bsdf.inputs['Base Color'])\n"
            "print('Image texture added')\n"
        )

    def set_emission(self, mat_name, color=(1.0, 0.5, 0.0, 1.0), strength=1.0):
        r, g, b, a = color
        return (
            "import bpy\n"
            f"mat  = bpy.data.materials['{mat_name}']\n"
            "bsdf = mat.node_tree.nodes.get('Principled BSDF')\n"
            f"bsdf.inputs['Emission Color'].default_value    = ({r},{g},{b},{a})\n"
            f"bsdf.inputs['Emission Strength'].default_value = {strength}\n"
        )
