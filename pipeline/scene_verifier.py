"""
pipeline/scene_verifier.py
Multi-angle 256x256 viewport screenshots + one AI realism call.
No extra tokens per step — single batch call after pipeline.done.
Supports optional wireframe pass for depth/occlusion disambiguation.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.spatial_reasoner import SpatialNode


@dataclass
class RealismIssue:
    type: str         # "merged" | "missing" | "floating" | "sunk"
    objects: list[str]
    fix_hint: str


@dataclass
class RealismReport:
    issues: list[RealismIssue] = field(default_factory=list)
    screenshots: list[str]     = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0


# Camera setups: (name, location_xyz, rotation_euler_xyz)
CAMERA_ANGLES: list[tuple] = [
    ("front", (0, -8, 4),  (1.1,   0,     0)),
    ("side",  (8,  0, 4),  (1.1,   0,     1.5708)),
    ("top",   (0,  0, 12), (0,     0,     0)),
    ("iso",   (6, -6, 6),  (0.955, 0,     0.7854)),
]

_CAPTURE_CODE = """
import bpy, os, math
_out_dir  = {out_dir!r}
_angles   = {angles!r}
_paths    = []

for _name, _loc, _rot in _angles:
    # Temporary camera
    _cam_data = bpy.data.cameras.new(f'VerifyCam_{{_name}}')
    _cam_obj  = bpy.data.objects.new(f'VerifyCam_{{_name}}', _cam_data)
    bpy.context.scene.collection.objects.link(_cam_obj)
    _cam_obj.location = _loc
    _cam_obj.rotation_euler = _rot
    bpy.context.scene.camera = _cam_obj

    # 256x256 render
    bpy.context.scene.render.resolution_x = 256
    bpy.context.scene.render.resolution_y = 256
    bpy.context.scene.render.resolution_percentage = 100
    _fp = os.path.join(_out_dir, f'verify_{{_name}}.png')
    bpy.context.scene.render.filepath = _fp
    bpy.ops.render.render(write_still=True)
    _paths.append(_fp)

    # Clean up temp camera
    bpy.data.objects.remove(_cam_obj, do_unlink=True)
    bpy.data.cameras.remove(_cam_data)

print('VERIFY_PATHS:' + ','.join(_paths))
"""


_WIREFRAME_CODE = """
import bpy, os
_out_dir     = {out_dir!r}
_name        = {name!r}
_fp          = os.path.join(_out_dir, f'verify_wire_{{_name}}.png')
_scene       = bpy.context.scene
_orig_engine = _scene.render.engine
_orig_shade  = None
try:
    _scene.render.engine = 'BLENDER_WORKBENCH'
    for _area in bpy.context.screen.areas:
        if _area.type == 'VIEW_3D':
            _orig_shade = _area.spaces[0].shading.type
            _area.spaces[0].shading.type = 'WIREFRAME'
            break
    _scene.render.filepath = _fp
    bpy.ops.render.opengl(write_still=True)
finally:
    _scene.render.engine = _orig_engine
    if _orig_shade is not None:
        for _area in bpy.context.screen.areas:
            if _area.type == 'VIEW_3D':
                _area.spaces[0].shading.type = _orig_shade
                break
print('WIRE_PATH:' + _fp)
"""


class SceneVerifier:

    def capture_all(self, client, output_dir: str | Path) -> list[str]:
        """Render solid + optional wireframe screenshots per angle.

        Returns a flat list. When capture_wireframe is enabled:
          [solid_front, wire_front, solid_side, wire_side, ...]
        Otherwise just the 4 solid captures.
        """
        from config.registry import get as _get
        do_wire = _get("capture_wireframe", True)

        out = str(Path(output_dir).expanduser())
        code = _CAPTURE_CODE.format(
            out_dir=out,
            angles=[(n, list(l), list(r)) for n, l, r in CAMERA_ANGLES],
        )
        result = client.exec_code(code)
        if not result.success:
            return []

        solid_paths: list[str] = []
        for line in (result.output or "").splitlines():
            if line.startswith("VERIFY_PATHS:"):
                solid_paths = [p for p in line[len("VERIFY_PATHS:"):].split(",") if p]
                break

        if not solid_paths or not do_wire:
            return solid_paths

        # Interleave wireframe captures: solid_N, wire_N, ...
        combined: list[str] = []
        for solid_path, (name, _, _) in zip(solid_paths, CAMERA_ANGLES):
            combined.append(solid_path)
            wire_code = _WIREFRAME_CODE.format(out_dir=out, name=name)
            wire_result = client.exec_code(wire_code)
            wire_path: str | None = None
            if wire_result.success:
                for line in (wire_result.output or "").splitlines():
                    if line.startswith("WIRE_PATH:"):
                        wire_path = line[len("WIRE_PATH:"):].strip()
                        break
            if wire_path:
                combined.append(wire_path)
            else:
                combined.append(solid_path)   # fallback: duplicate solid
        return combined

    def verify_realism(self, ai, screenshot_paths: list[str],
                       spatial_nodes: list,
                       project_name: str) -> RealismReport:
        """ONE AI call with all 4 screenshots. Returns a RealismReport."""
        if not screenshot_paths:
            return RealismReport()

        layout_lines = []
        for n in spatial_nodes:
            x, y, z = n.world_pos
            layout_lines.append(f"  {n.label}: ({x}, {y}, {z})")
        layout = "\n".join(layout_lines) or "  (no spatial layout)"

        has_wireframe = len(screenshot_paths) > 4
        wire_note = (
            "\nWireframe images are interleaved after each solid-shaded image "
            "(solid_front, wire_front, solid_side, wire_side, ...).\n"
            "Use the wireframe images to disambiguate depth relationships and occlusion.\n"
        ) if has_wireframe else ""

        prompt = (
            f"Project: {project_name}\n"
            f"Expected object layout:\n{layout}\n\n"
            f"You are given {'8' if has_wireframe else '4'} Blender viewport screenshots "
            f"({'solid + wireframe interleaved' if has_wireframe else 'front, side, top, isometric'}).\n"
            f"{wire_note}"
            "Analyse the scene and return ONLY valid JSON in this exact format:\n"
            '{"issues": [{"type": "merged|missing|floating|sunk", '
            '"objects": ["name1", "name2"], "fix_hint": "..."}]}\n\n'
            "Check for:\n"
            "1. Objects that appear merged/overlapping that should be separate\n"
            "2. Objects that are completely missing from the viewport\n"
            "3. Objects floating above terrain\n"
            "4. Objects sunk below terrain surface\n"
            "Return an empty issues array if the scene looks correct."
        )

        try:
            response = ai.generate_code(prompt, images=screenshot_paths)
            # Strip markdown code fences if present
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            issues = [
                RealismIssue(
                    type=i.get("type", "unknown"),
                    objects=i.get("objects", []),
                    fix_hint=i.get("fix_hint", ""),
                )
                for i in data.get("issues", [])
            ]
            return RealismReport(issues=issues, screenshots=screenshot_paths)
        except Exception:
            return RealismReport(screenshots=screenshot_paths)
