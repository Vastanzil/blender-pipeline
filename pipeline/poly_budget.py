"""
pipeline/poly_budget.py
Triangle-budget management per object class.
Decimation snippets are appended after each successful step.
"""
from __future__ import annotations
from enum import Enum


class ObjectClass(Enum):
    HERO = "hero"   # main subject: 8 000 tris
    MID  = "mid"    # supporting: 2 500 tris
    PROP = "prop"   # clutter: 400 tris


_HERO_KEYWORDS  = {"house", "cabin", "tower", "castle", "building", "tree", "dragon",
                   "character", "vehicle", "boat", "ship", "monument", "statue"}
_PROP_KEYWORDS  = {"flower", "rock", "stone", "pebble", "clutter", "debris",
                   "mushroom", "grass", "leaf", "twig", "post", "nail", "bolt"}

_TRI_LIMITS: dict[ObjectClass, int] = {
    ObjectClass.HERO: 8_000,
    ObjectClass.MID:  2_500,
    ObjectClass.PROP: 400,
}


class PolyBudgetManager:

    def classify(self, label: str) -> ObjectClass:
        key = label.lower().replace("_", " ").split()[0]
        if key in _HERO_KEYWORDS:
            return ObjectClass.HERO
        if key in _PROP_KEYWORDS:
            return ObjectClass.PROP
        return ObjectClass.MID

    def budget_for(self, label: str) -> int:
        return _TRI_LIMITS[self.classify(label)]

    def decimate_snippet(self, obj_name: str, label: str,
                         is_organic: bool = True) -> str:
        limit  = self.budget_for(label)
        method = "COLLAPSE" if is_organic else "PLANAR"
        return (
            f"# poly-budget: keep {obj_name} under {limit} tris\n"
            f"_o = bpy.data.objects.get('{obj_name}')\n"
            f"if _o:\n"
            f"    _tc = sum(len(p.vertices) - 2 for p in _o.data.polygons)\n"
            f"    if _tc > {limit}:\n"
            f"        _mod = _o.modifiers.new('DecimateV31', 'DECIMATE')\n"
            f"        _mod.decimate_type = '{method}'\n"
            f"        _mod.ratio = {limit} / max(_tc, 1)\n"
            f"        import bpy\n"
            f"        bpy.ops.object.select_all(action='DESELECT')\n"
            f"        bpy.context.view_layer.objects.active = _o\n"
            f"        _o.select_set(True)\n"
            f"        bpy.ops.object.modifier_apply(modifier='DecimateV31')\n"
        )
