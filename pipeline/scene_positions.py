"""
pipeline/scene_positions.py
Live position + bounding-box registry for the scene.

Queries Blender after each step for actual object locations and sizes,
building a growing registry used to:
  - Inject "PLACED OBJECTS" into every code_prompt so the AI knows
    where everything already sits.
  - Run AABB collision checks before proposing a new placement.
  - Return the next guaranteed non-overlapping grid position.
"""
from __future__ import annotations
import json
import math
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlacedObject:
    name: str
    loc: tuple[float, float, float]
    dim: tuple[float, float, float]   # (dx, dy, dz) world-space bounding box
    planned: bool = False             # True if seeded from blueprint, not live


# Blender code run inside exec_code to query object positions + dimensions
_QUERY_CODE = (
    "import bpy, json\n"
    "out = {}\n"
    "for o in bpy.data.objects:\n"
    "    if o.type not in ('MESH','CURVE','FONT','META','SURFACE','GPENCIL'):\n"
    "        continue\n"
    "    try:\n"
    "        dim = list(o.dimensions)\n"
    "    except Exception:\n"
    "        dim = [0.0, 0.0, 0.0]\n"
    "    out[o.name] = {'loc': list(o.location), 'dim': dim}\n"
    "print('__POS__:' + json.dumps(out))\n"
)


class ScenePositions:
    def __init__(self, client):
        self._client = client
        self._registry: dict[str, PlacedObject] = {}

    # ------------------------------------------------------------------
    # Querying Blender

    def refresh(self, new_names: set[str] | None = None):
        """Query Blender and update registry.

        If *new_names* is given, only update entries for those names (faster
        post-step diff).  If None, refresh all MESH-type objects.
        """
        try:
            result = self._client.exec_code(_QUERY_CODE)
            m = re.search(r'__POS__:(\{.*\})', str(result.output or ""), re.DOTALL)
            if not m:
                return
            raw: dict = json.loads(m.group(1))
            for name, info in raw.items():
                if new_names is not None and name not in new_names:
                    continue
                loc = tuple(float(v) for v in (info.get("loc") or [0, 0, 0])[:3])
                dim = tuple(float(v) for v in (info.get("dim") or [1, 1, 1])[:3])
                self._registry[name] = PlacedObject(
                    name=name, loc=loc, dim=dim, planned=False
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Seeding from blueprint (Layer 0 → Layer 1 integration)

    def seed_from_blueprint(self, slots: list) -> None:
        """Seed registry with blueprint slot positions before any real geometry.

        Accepts a list of BlueprintSlot-like objects (must have .label, .pos,
        .footprint attributes).
        """
        for slot in slots:
            self._registry[f"BP_{slot.label}"] = PlacedObject(
                name=f"BP_{slot.label}",
                loc=slot.pos,
                dim=slot.footprint,
                planned=True,
            )

    # ------------------------------------------------------------------
    # Prompt formatting

    def to_prompt_block(self, max_entries: int = 20) -> str:
        """Return a prompt block listing placed objects with positions and sizes."""
        if not self._registry:
            return ""
        entries = [
            obj for obj in self._registry.values()
            if not obj.planned  # show real objects, not blueprint placeholders
        ][-max_entries:]
        if not entries:
            # Fall back to planned slots if nothing real yet
            entries = list(self._registry.values())[-max_entries:]
        lines = ["PLACED OBJECTS (do NOT overlap — position and size shown):"]
        for obj in entries:
            x, y, z = obj.loc
            dx, dy, dz = obj.dim
            tag = " [blueprint]" if obj.planned else ""
            lines.append(
                f"  {obj.name}{tag} @ ({x:.2f}, {y:.2f}, {z:.2f})"
                f"  size ({dx:.2f}×{dy:.2f}×{dz:.2f}) m"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Collision detection

    def overlaps(
        self,
        candidate_pos: tuple[float, float, float],
        candidate_dim: tuple[float, float, float] = (1.0, 1.0, 1.0),
        margin: float = 0.15,
    ) -> Optional[str]:
        """AABB overlap test against all registry entries.

        Returns the name of the first colliding object, or None if clear.
        The margin expands the candidate box by that fraction of each axis.
        """
        cx, cy, cz = candidate_pos
        cdx, cdy, cdz = candidate_dim
        # half-extents + margin
        chx = cdx / 2 * (1 + margin)
        chy = cdy / 2 * (1 + margin)

        for obj in self._registry.values():
            ox, oy, oz = obj.loc
            odx, ody, odz = obj.dim
            ohx = odx / 2 * (1 + margin)
            ohy = ody / 2 * (1 + margin)

            # 2D AABB (ignore Z — vertical stacking is intentional for some objects)
            if abs(cx - ox) < chx + ohx and abs(cy - oy) < chy + ohy:
                return obj.name
        return None

    # ------------------------------------------------------------------
    # Next-free-position search

    def next_free_pos(
        self,
        candidate_dim: tuple[float, float, float] = (1.0, 1.0, 1.0),
        min_spacing: float = 1.5,
    ) -> tuple[float, float, float]:
        """Return the next grid position not overlapping any placed object."""
        spacing = max(min_spacing, max(candidate_dim[0], candidate_dim[1]) * 1.5)
        for rank in range(300):
            cols = max(1, int(math.ceil(math.sqrt(rank + 1))))
            x = (rank % cols) * spacing - cols * spacing / 2
            y = (rank // cols) * spacing
            pos = (round(x, 2), round(y, 2), 0.0)
            if self.overlaps(pos, candidate_dim) is None:
                return pos
        # Fallback: push far enough that nothing could be there
        return (rank * spacing, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Helpers

    @property
    def count(self) -> int:
        return len(self._registry)

    def has(self, name: str) -> bool:
        return name in self._registry
