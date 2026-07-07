"""
pipeline/terrain_builder.py
One-mesh terrain system.  All ground features (hills, ponds, roads, rivers)
are modifications of a single subdivided 'Terrain' mesh — never stacked
separate planes.  Objects are placed at the correct Z via ray_cast.
"""
from __future__ import annotations
from enum import Enum


TERRAIN_KEYWORDS: set[str] = {
    "ground", "plane", "terrain", "road", "path", "pond", "lake",
    "river", "stream", "hill", "valley", "cliff", "field", "meadow",
}


class TerrainFeature(Enum):
    GROUND = "ground"
    HILL   = "hill"
    VALLEY = "valley"
    ROAD   = "road"
    POND   = "pond"
    RIVER  = "river"


class TerrainBuilder:

    # ------------------------------------------------------------------
    # Step 0 — called once before the AI plan if terrain was detected

    def base_terrain_snippet(self, size_m: float = 40.0) -> str:
        """Create the single shared Terrain mesh (idempotent — skips if already exists)."""
        half = size_m / 2
        return (
            "import bpy, bmesh\n"
            "if 'Terrain' not in bpy.data.objects:\n"
            "    # Remove only the default startup cube/plane by exact name\n"
            "    for _n in ['Cube', 'Plane']:\n"
            "        if _n in bpy.data.objects:\n"
            "            bpy.data.objects.remove(bpy.data.objects[_n], do_unlink=True)\n"
            "    bpy.ops.mesh.primitive_plane_add(size=1, location=(0,0,0))\n"
            "    _terrain = bpy.context.active_object\n"
            "    _terrain.name = 'Terrain'\n"
            f"    _terrain.scale = ({half}, {half}, 1)\n"
            "    bpy.ops.object.transform_apply(scale=True)\n"
            "    # Subdivide for feature resolution\n"
            "    _bm = bmesh.new()\n"
            "    _bm.from_mesh(_terrain.data)\n"
            "    bmesh.ops.subdivide_edges(_bm, edges=_bm.edges, cuts=32, use_grid_fill=True)\n"
            "    _bm.to_mesh(_terrain.data)\n"
            "    _bm.free()\n"
            "    _terrain.data.update()\n"
            "    # Smooth shading\n"
            "    for _p in _terrain.data.polygons: _p.use_smooth = True\n"
            "    # Green grass material\n"
            "    _mat = bpy.data.materials.new('TerrainMat')\n"
            "    _mat.use_nodes = True\n"
            "    _mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.15, 0.45, 0.05, 1)\n"
            "    _mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9\n"
            "    _terrain.data.materials.append(_mat)\n"
            "else:\n"
            "    _terrain = bpy.data.objects['Terrain']\n"
            "bpy.context.view_layer.update()\n"
        )

    # ------------------------------------------------------------------
    # Feature modifications — all operate on the existing 'Terrain' mesh

    def feature_snippet(self, feature: TerrainFeature,
                        world_pos: tuple[float, float, float],
                        size_m: float) -> str:
        x, y, _ = world_pos
        if feature == TerrainFeature.HILL:
            return self._hill_snippet(x, y, size_m)
        if feature == TerrainFeature.VALLEY:
            return self._valley_snippet(x, y, size_m)
        if feature == TerrainFeature.ROAD:
            return self._road_snippet(x, y, size_m)
        if feature == TerrainFeature.POND:
            return self._pond_snippet(x, y, size_m)
        if feature == TerrainFeature.RIVER:
            return self._river_snippet(x, y, size_m)
        return ""   # GROUND — base mesh is enough

    def place_on_terrain_snippet(self, obj_name: str,
                                 world_xy: tuple[float, float]) -> str:
        """Snap an object's Z to the terrain surface via ray_cast."""
        x, y = world_xy
        return (
            f"import bpy\n"
            f"_terrain = bpy.data.objects.get('Terrain')\n"
            f"_obj     = bpy.data.objects.get('{obj_name}')\n"
            f"if _terrain and _obj:\n"
            f"    _hit, _loc, _nrm, _idx = bpy.context.scene.ray_cast(\n"
            f"        bpy.context.view_layer.depsgraph,\n"
            f"        origin=({x}, {y}, 50.0),\n"
            f"        direction=(0, 0, -1)\n"
            f"    )\n"
            f"    if _hit:\n"
            f"        _obj.location.x = {x}\n"
            f"        _obj.location.y = {y}\n"
            f"        _obj.location.z = _loc.z\n"
            f"    bpy.context.view_layer.update()\n"
        )

    # ------------------------------------------------------------------
    # Private feature generators

    @staticmethod
    def _hill_snippet(cx: float, cy: float, radius: float) -> str:
        height = radius * 0.6
        return (
            "import bpy, bmesh, math\n"
            "_terrain = bpy.data.objects['Terrain']\n"
            "_bm = bmesh.new()\n"
            "_bm.from_mesh(_terrain.data)\n"
            f"for _v in _bm.verts:\n"
            f"    _d = math.hypot(_v.co.x - {cx}, _v.co.y - {cy})\n"
            f"    if _d < {radius}:\n"
            f"        _w = (1 - _d / {radius}) ** 2\n"
            f"        _v.co.z += {height} * _w\n"
            "_bm.to_mesh(_terrain.data)\n"
            "_bm.free()\n"
            "_terrain.data.update()\n"
        )

    @staticmethod
    def _valley_snippet(cx: float, cy: float, radius: float) -> str:
        depth = radius * 0.4
        return (
            "import bpy, bmesh, math\n"
            "_terrain = bpy.data.objects['Terrain']\n"
            "_bm = bmesh.new()\n"
            "_bm.from_mesh(_terrain.data)\n"
            f"for _v in _bm.verts:\n"
            f"    _d = math.hypot(_v.co.x - {cx}, _v.co.y - {cy})\n"
            f"    if _d < {radius}:\n"
            f"        _w = (1 - _d / {radius}) ** 2\n"
            f"        _v.co.z -= {depth} * _w\n"
            "_bm.to_mesh(_terrain.data)\n"
            "_bm.free()\n"
            "_terrain.data.update()\n"
        )

    @staticmethod
    def _road_snippet(cx: float, cy: float, length: float) -> str:
        half_w = 1.0
        return (
            "import bpy, bmesh\n"
            "_terrain = bpy.data.objects['Terrain']\n"
            "_bm = bmesh.new()\n"
            "_bm.from_mesh(_terrain.data)\n"
            f"for _v in _bm.verts:\n"
            f"    if abs(_v.co.x - {cx}) < {half_w} and abs(_v.co.y - {cy}) < {length/2}:\n"
            f"        _v.co.z = 0.0  # flatten road strip\n"
            "_bm.to_mesh(_terrain.data)\n"
            "_bm.free()\n"
            "_terrain.data.update()\n"
        )

    @staticmethod
    def _pond_snippet(cx: float, cy: float, radius: float) -> str:
        depth = 0.5
        return (
            "import bpy, bmesh, math\n"
            "_terrain = bpy.data.objects['Terrain']\n"
            "_bm = bmesh.new()\n"
            "_bm.from_mesh(_terrain.data)\n"
            f"for _v in _bm.verts:\n"
            f"    if math.hypot(_v.co.x - {cx}, _v.co.y - {cy}) < {radius}:\n"
            f"        _v.co.z = -{depth}\n"
            "_bm.to_mesh(_terrain.data)\n"
            "_bm.free()\n"
            "_terrain.data.update()\n"
            "# Water surface plane\n"
            f"bpy.ops.mesh.primitive_plane_add(size={radius*2}, location=({cx},{cy},-0.02))\n"
            "_water = bpy.context.active_object\n"
            "_water.name = 'Pond_Water'\n"
            "_wmat = bpy.data.materials.new('WaterMat')\n"
            "_wmat.use_nodes = True\n"
            "_wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.2, 0.6, 1)\n"
            "_wmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.05\n"
            "_wmat.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.8\n"
            "_water.data.materials.append(_wmat)\n"
        )

    @staticmethod
    def _river_snippet(cx: float, cy: float, length: float) -> str:
        half_w = 0.8
        depth  = 0.3
        return (
            "import bpy, bmesh\n"
            "_terrain = bpy.data.objects['Terrain']\n"
            "_bm = bmesh.new()\n"
            "_bm.from_mesh(_terrain.data)\n"
            f"for _v in _bm.verts:\n"
            f"    if abs(_v.co.x - {cx}) < {half_w} and abs(_v.co.y - {cy}) < {length/2}:\n"
            f"        _v.co.z = -{depth}\n"
            "_bm.to_mesh(_terrain.data)\n"
            "_bm.free()\n"
            "_terrain.data.update()\n"
            "# River water plane\n"
            f"bpy.ops.mesh.primitive_plane_add(size=1, location=({cx},{cy},-0.05))\n"
            "_river_w = bpy.context.active_object\n"
            f"_river_w.scale = ({half_w}, {length/2}, 1)\n"
            "_river_w.name = 'River_Water'\n"
            "bpy.ops.object.transform_apply(scale=True)\n"
            "_rwmat = bpy.data.materials.new('RiverMat')\n"
            "_rwmat.use_nodes = True\n"
            "_rwmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.25, 0.55, 1)\n"
            "_rwmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.1\n"
            "_river_w.data.materials.append(_rwmat)\n"
        )
