"""
pipeline/layout_planner.py
Optional local GGUF layout LLM integration.

When `local_layout_llm_url` is configured (pointing at a llama-server running a
small model like Qwen2.5-Coder-1.5B-Instruct Q4), this module calls it to
produce a whole-plan spatial layout in one shot, returning
{step_description → (x, y, z)}.

Falls back silently to {} on any error — callers must handle the empty-dict case.
"""
from __future__ import annotations
import json
import re
import requests


_SYSTEM_PROMPT = (
    "You are a 3D spatial layout engine for Blender scenes. "
    "Given a list of scene construction steps and the scene type, "
    "output ONLY a valid JSON array where each entry is:\n"
    '  {"step": "<exact step text>", "x": <float>, "y": <float>, "z": 0.0, '
    '"dx": <width_m>, "dy": <depth_m>, "dz": <height_m>}\n'
    "Rules:\n"
    "- Use real-world metre scale.\n"
    "- Objects must not overlap — their bounding boxes (centred on x,y,z) "
    "must not intersect.\n"
    "- First object should NOT be at (0,0,0) — offset by at least half its footprint.\n"
    "- Terrain/ground/ocean planes can be centred at (0,0,0) since they are flat.\n"
    "- Lighting and camera steps get x=y=z=0 (they are non-physical).\n"
    "Return ONLY the JSON array. No explanation."
)


class LayoutPlanner:
    def __init__(self, llm_url: str, timeout: int = 30):
        self._url     = llm_url.rstrip("/")
        self._timeout = timeout

    def plan_layout(
        self,
        steps: list[str],
        scene_scale: str = "default",
    ) -> dict[str, tuple[float, float, float]]:
        """Return {step_description → (x, y, z)}.  Empty dict on failure."""
        if not self._url or not steps:
            return {}

        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        user_msg = (
            f"Scene type: {scene_scale}\n\n"
            f"Steps to lay out:\n{numbered}\n\n"
            "Return the JSON array as specified."
        )

        payload = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        try:
            r = requests.post(
                f"{self._url}/v1/chat/completions",
                json=payload,
                timeout=self._timeout,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except Exception:
            return {}

        return self._parse(content, steps)

    def _parse(
        self, content: str, steps: list[str]
    ) -> dict[str, tuple[float, float, float]]:
        # Strip markdown fences
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(),
                         flags=re.IGNORECASE | re.MULTILINE)
        try:
            arr = json.loads(content)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", content, re.DOTALL)
            if not m:
                return {}
            try:
                arr = json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}

        if not isinstance(arr, list):
            return {}

        result: dict[str, tuple[float, float, float]] = {}
        for entry in arr:
            if not isinstance(entry, dict):
                continue
            step_text = str(entry.get("step", ""))
            x = float(entry.get("x", 0.0))
            y = float(entry.get("y", 0.0))
            z = float(entry.get("z", 0.0))
            if step_text:
                result[step_text] = (round(x, 3), round(y, 3), round(z, 3))

        # Also index by step index for fuzzy matching
        for i, step in enumerate(steps):
            if step not in result and i < len(arr):
                entry = arr[i]
                if isinstance(entry, dict):
                    x = float(entry.get("x", 0.0))
                    y = float(entry.get("y", 0.0))
                    z = float(entry.get("z", 0.0))
                    result[step] = (round(x, 3), round(y, 3), round(z, 3))

        return result
