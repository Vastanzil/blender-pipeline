"""
ai/context_builder.py
Builds an AI prompt context string from the live Blender scene.
Caps at 30 objects to keep token count manageable.
"""
import json
from .compat_rules import get_compat_block


class ContextBuilder:
    MAX_OBJECTS = 30

    def __init__(self, client, blender_version=(4, 0, 0)):
        self._client  = client
        self._version = blender_version

    def build(self, extra: str = "") -> str:
        scene_text = self._get_scene_text()
        compat     = get_compat_block(self._version)
        parts = [
            f"BLENDER_VERSION: {'.'.join(str(v) for v in self._version)}",
            compat,
            "CURRENT_SCENE:",
            scene_text,
        ]
        if extra:
            parts.append(f"EXTRA_CONTEXT:\n{extra}")
        return "\n".join(parts)

    def _get_scene_text(self) -> str:
        try:
            result = self._client.get_scene_info()
            raw = result.output
            if isinstance(raw, str):
                data = json.loads(raw)
            elif isinstance(raw, dict):
                data = raw
            else:
                return "(no scene data)"
            objects = data.get("objects", [])[:self.MAX_OBJECTS]
            lines = []
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                lines.append(
                    f"  {obj.get('name','?')} [{obj.get('type','?')}]"
                    + (f" @ {obj.get('location','')}" if obj.get('location') else "")
                )
            return "\n".join(lines) if lines else "(empty scene)"
        except Exception as e:
            return f"(scene fetch error: {e})"
