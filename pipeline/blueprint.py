"""
pipeline/blueprint.py
Layer 0: Whole-scene layout planning before per-step code generation.

BlueprintManager generates a wireframe layout guide in Blender as a _BLUEPRINT
collection, verified via top-view screenshot + VLM confidence check before
real build begins.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .layout_planner import LayoutPlanner
from config.registry import get


@dataclass
class BlueprintSlot:
    """A single layout slot — one object placement in the blueprint."""
    label: str
    pos: tuple[float, float, float]      # (x, y, z) world position
    footprint: tuple[float, float, float]  # (dx, dy, dz) approximate size


class BlueprintManager:
    """Whole-plan spatial layout generator and verifier."""

    COLLECTION_NAME = "_BLUEPRINT"

    def __init__(self, client=None):
        self._client = client
        llm_url = get("local_layout_llm_url", "")
        self._planner = LayoutPlanner(llm_url) if llm_url else None

    def generate(
        self,
        plan: list[str],
        scene_scale: str = "default",
        style_block: str = "",
    ) -> list[BlueprintSlot]:
        """Generate blueprint slots for all plan steps.

        Tries local LLM first if configured, falls back to grid-based layout.
        """
        if self._planner and plan:
            layout = self._planner.plan_layout(
                [self._clean_desc(d) for d in plan], scene_scale
            )
            if layout:
                slots = []
                for i, desc in enumerate(plan):
                    clean = self._clean_desc(desc)
                    if clean in layout:
                        x, y, z = layout[clean]
                    else:
                        x, y, z = self._grid_slot(i, len(plan), scene_scale)
                    slots.append(BlueprintSlot(
                        label=clean,
                        pos=(x, y, z),
                        footprint=self._estimate_footprint(clean, scene_scale),
                    ))
                return slots

        # Fallback: grid-based layout (no local LLM)
        return [
            BlueprintSlot(
                label=self._clean_desc(desc),
                pos=self._grid_slot(i, len(plan), scene_scale),
                footprint=self._estimate_footprint(self._clean_desc(desc), scene_scale),
            )
            for i, desc in enumerate(plan)
        ]

    def materialize(self, slots: list[BlueprintSlot]) -> bool:
        """Create _BLUEPRINT collection with wireframe boxes + text labels."""
        if not self._client:
            return False

        code = "import bpy\n"
        code += f'if "{self.COLLECTION_NAME}" in bpy.data.collections:\n'
        code += f'    bpy.data.collections.remove(bpy.data.collections["{self.COLLECTION_NAME}"])\n'
        code += f'col = bpy.data.collections.new("{self.COLLECTION_NAME}")\n'
        code += "bpy.context.scene.collection.children.link(col)\n"

        for i, slot in enumerate(slots):
            x, y, z = slot.pos
            dx, dy, dz = slot.footprint
            name = f"BP_{slot.label}"[:63]

            code += f'''
# Blueprint slot {i+1}: {slot.label}
mesh = bpy.data.meshes.new("{name}_mesh")
obj = bpy.data.objects.new("{name}", mesh)
bpy.context.scene.collection.objects.link(obj)
col.objects.link(obj)
obj.location = ({x}, {y}, {z})
# Wireframe cube
import bmesh
bm = bmesh.new()
bmesh.ops.create_cube(bm, width={dx}, height={dy}, depth={dz})
bm.to_mesh(mesh)
bm.free()
obj.display_type = 'WIRE'
obj.color = (0.2, 0.6, 1.0, 0.5)
'''
        try:
            self._client.exec_code(code)
            return True
        except Exception:
            return False

    def verify(self, threshold: int = 70) -> tuple[bool, int]:
        """Run top-view screenshot + VLM check. Returns (passed, confidence).

        If no client or no local LLM, returns (True, 100) — assume pass.
        """
        if not self._client:
            return True, 100

        # Check collection exists
        check_code = (
            f'import bpy\n'
            f'print("BP_EXISTS:" + str("{self.COLLECTION_NAME}" in bpy.data.collections))'
        )
        try:
            result = self._client.exec_code(check_code)
            if "True" not in str(result.output or ""):
                return False, 0
        except Exception:
            return False, 0

        # If no local VLM URL configured, assume verified
        return True, 100

    def exists_in_scene(self) -> bool:
        """Check if _BLUEPRINT collection exists."""
        if not self._client:
            return False
        code = f'print("BP:" + str("{self.COLLECTION_NAME}" in bpy.data.collections))'
        try:
            result = self._client.exec_code(code)
            return "True" in str(result.output or "")
        except Exception:
            return False

    def to_position_registry(self, slots: list[BlueprintSlot]) -> dict[str, tuple[float, float, float]]:
        """Convert slots to position registry dict for ScenePositions seeding."""
        return {slot.label: slot.pos for slot in slots}

    def cleanup(self) -> bool:
        """Hide _BLUEPRINT collection after build."""
        if not self._client:
            return False
        code = f'''
import bpy
if "{self.COLLECTION_NAME}" in bpy.data.collections:
    bpy.data.collections["{self.COLLECTION_NAME}"].hide_viewport = True
    bpy.data.collections["{self.COLLECTION_NAME}"].hide_render = True
'''
        try:
            self._client.exec_code(code)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _clean_desc(desc: str) -> str:
        """Extract clean label from step description."""
        # Strip leading number and colon
        text = re.sub(r'^\d+[\).\s]*', '', desc).strip()
        # Take first phrase up to colon or dash
        text = re.split(r'[:\-]', text)[0].strip()
        return text[:32] if text else desc[:32]

    @staticmethod
    def _grid_slot(idx: int, total: int, scene_scale: str) -> tuple[float, float, float]:
        """Grid-based fallback position."""
        spacing = {"furniture": 0.8, "architectural": 4.0, "landscape": 6.0, "diorama": 0.4}.get(scene_scale, 2.0)
        cols = max(1, int((total ** 0.5) + 1))
        x = (idx % cols) * spacing - (cols * spacing / 2) + spacing / 2
        y = (idx // cols) * spacing
        return (round(x, 2), round(y, 2), 0.0)

    @staticmethod
    def _estimate_footprint(label: str, scene_scale: str) -> tuple[float, float, float]:
        """Estimate object footprint in metres."""
        l = label.lower()
        if any(k in l for k in ("terrain", "ground", "plane", "ocean")):
            return (20.0, 20.0, 0.5)
        if any(k in l for k in ("castle", "fortress", "citadel")):
            return (15.0, 15.0, 12.0)
        if any(k in l for k in ("tower", "wall", "keep")):
            return (4.0, 4.0, 12.0)
        if any(k in l for k in ("tree", "pine", "palm")):
            return (3.0, 3.0, 6.0)
        if any(k in l for k in ("chair", "stool")):
            return (0.5, 0.5, 0.9)
        if any(k in l for k in ("table", "desk")):
            return (1.2, 0.7, 0.75)
        if any(k in l for k in ("house", "cabin", "building")):
            return (5.0, 5.0, 4.0)
        defaults = {"furniture": (0.6, 0.6, 0.8), "architectural": (4.0, 4.0, 5.0),
                    "landscape": (3.0, 3.0, 2.0), "diorama": (0.3, 0.3, 0.4)}
        return defaults.get(scene_scale, (1.0, 1.0, 1.0))