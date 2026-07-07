"""
ai/step_router.py
Selects a specialized code-gen system prompt based on step description keywords.
Used by manifest_client and blenderllm_client to improve per-step generation quality.
"""
from __future__ import annotations

_GEOMETRY_PROMPT = (
    "You are an expert in Blender geometry modeling. "
    "Focus on: mesh primitives, modifiers (Subdivision, Bevel, Solidify, Boolean), "
    "bmesh operations, correct real-world scale, and clean topology. "
    "Always import bpy. Name every object. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_MATERIAL_PROMPT = (
    "You are an expert in Blender PBR materials and shader nodes. "
    "Focus on: Principled BSDF setup, procedural textures (Noise, Musgrave, Voronoi), "
    "color ramps for variation, normal/bump maps from procedural nodes, "
    "and correct material slot assignment to named objects. "
    "Always import bpy. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_LIGHTING_PROMPT = (
    "You are an expert in Blender scene lighting. "
    "Focus on: Sun/Area/Point/Spot lamp setup, HDRI world environments via Sky Texture, "
    "Cycles vs EEVEE render engine settings, light strength and color temperature. "
    "Always import bpy. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_TERRAIN_PROMPT = (
    "You are an expert in Blender terrain and environment modeling. "
    "Focus on: subdivided mesh displacement with bmesh, Displace modifier with "
    "cloud/musgrave textures, particle scatter for vegetation, "
    "correct ocean plane setup (low roughness 0.05, metallic 0.9, Wave texture). "
    "Always import bpy. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_ANIMATION_PROMPT = (
    "You are an expert in Blender animation and rigging. "
    "Focus on: keyframe insertion (insert_keyframe), NLA editor, drivers, constraints, "
    "fcurve interpolation, and timeline settings. "
    "Always import bpy. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_CAMERA_PROMPT = (
    "You are an expert in Blender camera and composition setup. "
    "Focus on: camera placement for cinematic framing (rule of thirds), "
    "focal length (35-85mm), depth of field (aperture, focus distance), "
    "render resolution and aspect ratio. "
    "Always import bpy. Call bpy.context.view_layer.update() at end. "
    "NEVER delete existing scene objects. "
    "Return ONLY executable Python code."
)

_STEP_ROUTES: list[tuple[list[str], str]] = [
    (["material", "shader", "pbr", "texture", "color", "roughness", "metallic"], _MATERIAL_PROMPT),
    (["light", "sun", "lamp", "hdri", "sky", "world", "illuminate", "lighting"],  _LIGHTING_PROMPT),
    (["terrain", "ground", "ocean", "island", "hill", "valley", "water", "plane"], _TERRAIN_PROMPT),
    (["camera", "render", "shot", "composition", "frame", "viewport"],             _CAMERA_PROMPT),
    (["animation", "keyframe", "animate", "driver", "timeline", "motion"],         _ANIMATION_PROMPT),
]


def get_system_prompt(description: str) -> str:
    """Return the best-fit system prompt for a step description."""
    desc_lower = description.lower()
    for keywords, prompt in _STEP_ROUTES:
        if any(kw in desc_lower for kw in keywords):
            return prompt
    return _GEOMETRY_PROMPT
