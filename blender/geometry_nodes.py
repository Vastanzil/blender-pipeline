"""blender/geometry_nodes.py — Code-gen helpers for Geometry Nodes (bpy strings)."""


class GeoNodesBuilder:
    def create_modifier(self, obj_name, ng_name):
        return (
            "import bpy\n"
            f"obj = bpy.data.objects['{obj_name}']\n"
            f"ng  = bpy.data.node_groups.new(name='{ng_name}', type='GeometryNodeTree')\n"
            f"mod = obj.modifiers.new(name='{ng_name}', type='NODES')\n"
            "mod.node_group = ng\n"
            f"print('GN modifier created: {ng_name}')\n"
        )

    def add_node(self, ng_name, node_type, label=""):
        lbl = f"node.label = '{label}'\n" if label else ""
        return (
            "import bpy\n"
            f"ng   = bpy.data.node_groups['{ng_name}']\n"
            f"node = ng.nodes.new(type='{node_type}')\n"
            + lbl +
            f"print('Node added: {node_type}')\n"
        )

    def link_nodes(self, ng_name, from_node, from_socket, to_node, to_socket):
        return (
            "import bpy\n"
            f"ng  = bpy.data.node_groups['{ng_name}']\n"
            f"src = ng.nodes['{from_node}']\n"
            f"dst = ng.nodes['{to_node}']\n"
            f"ng.links.new(src.outputs['{from_socket}'], dst.inputs['{to_socket}'])\n"
        )

    def add_input_socket(self, ng_name, socket_type, name, blender_major=5):
        if blender_major >= 5:
            call = f"ng.interface.new_socket(name='{name}', in_out='INPUT', socket_type='{socket_type}')"
        else:
            call = f"ng.inputs.new('{socket_type}', '{name}')"
        return (
            "import bpy\n"
            f"ng = bpy.data.node_groups['{ng_name}']\n"
            f"{call}\n"
        )

    def scatter_instances(self, obj_name, asset_name, count=50, seed=0):
        return (
            "import bpy\n"
            f"obj   = bpy.data.objects['{obj_name}']\n"
            f"asset = bpy.data.objects['{asset_name}']\n"
            f"ng    = bpy.data.node_groups.new('Scatter_{asset_name}', 'GeometryNodeTree')\n"
            "mod   = obj.modifiers.new('Scatter', 'NODES')\n"
            "mod.node_group = ng\n"
            "nodes = ng.nodes\n"
            "inp  = nodes.new('NodeGroupInput')\n"
            "out  = nodes.new('NodeGroupOutput')\n"
            "dist = nodes.new('GeometryNodeDistributePointsOnFaces')\n"
            "inst = nodes.new('GeometryNodeInstanceOnPoints')\n"
            "real = nodes.new('GeometryNodeRealizeInstances')\n"
            f"dist.inputs['Density'].default_value = {count}\n"
            f"dist.inputs['Seed'].default_value    = {seed}\n"
            "ng.links.new(inp.outputs[0],         dist.inputs['Mesh'])\n"
            "ng.links.new(dist.outputs['Points'], inst.inputs['Points'])\n"
            "ng.links.new(inst.outputs[0],        real.inputs[0])\n"
            "ng.links.new(real.outputs[0],        out.inputs[0])\n"
            "print('Scatter setup complete')\n"
        )
