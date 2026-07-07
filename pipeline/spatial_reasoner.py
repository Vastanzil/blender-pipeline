"""
pipeline/spatial_reasoner.py
Converts a list of detected object labels into a 3D layout graph before any
code is generated.  The result is injected as 'SPATIAL LAYOUT:' into every
plan and code-gen prompt.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Domain knowledge: which objects physically connect vs. must stay apart
# ---------------------------------------------------------------------------

ATTACHMENT_GROUPS: dict[str, list[str]] = {
    "bridge": ["bridge_plank", "bridge_rope", "bridge_post", "railing"],
    "cabin":  ["cabin_wall", "cabin_roof", "cabin_door", "cabin_window", "cabin_chimney"],
    "dock":   ["dock_plank", "dock_post", "dock_rope"],
    "tower":  ["tower_base", "tower_wall", "tower_parapet", "tower_stairs"],
    "fence":  ["fence_post", "fence_rail"],
}

EXCLUSION_PAIRS: set[frozenset] = {
    frozenset({"tree",  "house"}),
    frozenset({"tree",  "cabin"}),
    frozenset({"tree",  "tower"}),
    frozenset({"pond",  "road"}),
    frozenset({"pond",  "path"}),
    frozenset({"rock",  "fence_post"}),
    frozenset({"tree",  "fence"}),
    frozenset({"house", "pond"}),
    frozenset({"cabin", "pond"}),
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DetectedObject:
    label: str
    estimated_scale: float = 1.0   # metres (rough)


@dataclass
class SpatialNode:
    label: str
    world_pos: tuple[float, float, float]
    world_scale: float
    depth_rank: int
    parent: Optional[str] = None
    attachment_group: Optional[str] = None
    exclusion_enforced: bool = False


# ---------------------------------------------------------------------------
# Scale presets — (min_separation_m, spacing_multiplier)
# ---------------------------------------------------------------------------

_SCALE_PRESETS: dict[str, tuple[float, float]] = {
    "furniture":     (0.5,  1.5),   # chairs, tables, shelves — tight interior spacing
    "architectural": (3.0,  4.0),   # castles, towers, bridges — wide structural gaps
    "landscape":     (5.0,  6.0),   # islands, forests, mountains — very wide gaps
    "diorama":       (0.15, 1.2),   # small isometric tabletop scenes
    "default":       (0.75, 2.0),
}

# Keywords that map a scene to a scale preset (checked against style_block/prompt)
_SCALE_KEYWORDS: dict[str, list[str]] = {
    "furniture":     ["chair", "table", "shelf", "furniture", "vintage", "sofa",
                      "desk", "cabinet", "wardrobe", "bed", "lamp", "couch"],
    "architectural": ["medieval", "castle", "tower", "fortress", "dungeon",
                      "bridge", "wall", "gate", "keep", "citadel", "building"],
    "landscape":     ["island", "ocean", "forest", "nature", "landscape",
                      "mountain", "terrain", "wilderness", "beach", "jungle"],
    "diorama":       ["diorama", "isometric", "miniature", "tabletop", "voxel",
                      "low poly scene", "low-poly scene"],
}


def detect_scene_scale(text: str) -> str:
    """Return the best-matching scale preset name from a combined prompt/style text."""
    lower = text.lower()
    for preset, keywords in _SCALE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return preset
    return "default"


# ---------------------------------------------------------------------------
# Core reasoner
# ---------------------------------------------------------------------------

class SpatialReasoner:
    EXCLUSION_EXTRA: float = 2.0   # multiplier on min_sep for excluded pairs
    MIN_SEPARATION_M: float = 0.75  # class-level default for tests

    def build_layout(
        self,
        detections: list[DetectedObject],
        scene_scale: str = "default",
    ) -> list[SpatialNode]:
        """Return a list of SpatialNode objects with non-overlapping world positions."""
        min_sep, _spacing_mult = _SCALE_PRESETS.get(scene_scale, _SCALE_PRESETS["default"])
        self._min_sep   = min_sep
        self._scene_scale = scene_scale

        nodes: list[SpatialNode] = []
        placed: list[SpatialNode] = []

        for rank, det in enumerate(detections):
            group = self._find_group(det.label)
            parent = self._find_parent(det.label, group, placed)

            if parent:
                base_pos = parent.world_pos
                offset   = self._radial_offset(rank, det.estimated_scale * 0.5)
                raw_pos  = (base_pos[0] + offset[0],
                            base_pos[1] + offset[1],
                            base_pos[2])
            else:
                raw_pos = self._grid_pos(rank, det.estimated_scale, scene_scale)

            final_pos = self._resolve_collision(
                raw_pos, placed, det.label, [d.label for d in detections]
            )

            node = SpatialNode(
                label=det.label,
                world_pos=final_pos,
                world_scale=det.estimated_scale,
                depth_rank=rank,
                parent=parent.label if parent else None,
                attachment_group=group,
            )
            nodes.append(node)
            placed.append(node)

        return nodes

    # ------------------------------------------------------------------

    def _find_group(self, label: str) -> Optional[str]:
        for group, members in ATTACHMENT_GROUPS.items():
            if label in members or label == group:
                return group
        return None

    def _find_parent(self, label: str, group: Optional[str],
                     placed: list[SpatialNode]) -> Optional[SpatialNode]:
        if not group:
            return None
        for node in placed:
            if node.attachment_group == group and node.parent is None:
                return node
        return None

    def _grid_pos(self, rank: int, scale: float,
                  scene_scale: str = "default") -> tuple[float, float, float]:
        """Spiral-like grid placement using scale-preset spacing."""
        min_sep, mult = _SCALE_PRESETS.get(scene_scale, _SCALE_PRESETS["default"])
        spacing = max(scale * mult, min_sep * 2)
        # Rank 0 → offset slightly from origin so nothing lands exactly at (0,0,0)
        if rank == 0:
            return (round(spacing * 0.5, 2), 0.0, 0.0)
        cols = max(1, int(math.ceil(math.sqrt(rank + 1))))
        x = (rank % cols) * spacing - cols * spacing / 2
        y = (rank // cols) * spacing
        return (round(x, 2), round(y, 2), 0.0)

    def _radial_offset(self, rank: int, radius: float) -> tuple[float, float]:
        angle = (rank * 2.399) % (2 * math.pi)   # golden-angle distribution
        r     = max(radius, self.MIN_SEPARATION_M)
        return (round(r * math.cos(angle), 2), round(r * math.sin(angle), 2))

    def _resolve_collision(self, pos: tuple, placed: list[SpatialNode],
                           label: str, all_labels: list[str]) -> tuple:
        x, y, z = pos
        max_iters = 50
        for _ in range(max_iters):
            conflict = self._find_conflict(x, y, placed, label)
            if conflict is None:
                break
            sep = self._required_separation(label, conflict.label)
            dx  = x - conflict.world_pos[0]
            dy  = y - conflict.world_pos[1]
            dist = math.hypot(dx, dy) or 1e-6
            x += (dx / dist) * sep
            y += (dy / dist) * sep
        return (round(x, 2), round(y, 2), z)

    def _find_conflict(self, x: float, y: float, placed: list[SpatialNode],
                       label: str) -> Optional[SpatialNode]:
        for node in placed:
            sep  = self._required_separation(label, node.label)
            dist = math.hypot(x - node.world_pos[0], y - node.world_pos[1])
            if dist < sep:
                return node
        return None

    def _required_separation(self, a: str, b: str) -> float:
        min_sep = getattr(self, "_min_sep", 0.75)
        if frozenset({a, b}) in EXCLUSION_PAIRS:
            return min_sep * self.EXCLUSION_EXTRA
        return min_sep

    # ------------------------------------------------------------------
    # Prompt helper

    def to_prompt_block(self, nodes: list[SpatialNode]) -> str:
        lines = ["SPATIAL LAYOUT (use these world positions — do not place at origin):"]
        for n in nodes:
            x, y, z = n.world_pos
            att = f"  [attached to {n.parent}]" if n.parent else ""
            lines.append(f"  {n.label}: location=({x}, {y}, {z}), "
                         f"scale={n.world_scale:.2f}m{att}")
        return "\n".join(lines)
