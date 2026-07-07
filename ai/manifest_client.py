"""
ai/manifest_client.py
Manifest AI router client (http://localhost:2099).

Modified for v3.0 to support image reference upload and vision input.
Modified for v3.2: plan() uses numbered list (no JSON), describe() added,
_chat() has exponential backoff on 500/502/503 errors.
"""
from __future__ import annotations

import json
import os
import re
import time
import requests


def _encode_image(path: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) for vision URL encoding."""
    import base64, mimetypes
    data = open(path, "rb").read()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return base64.b64encode(data).decode(), mime


class ManifestClient:
    def __init__(self, host: str = "http://localhost:2099",
                 token: str = "",
                 model: str = "auto",
                 timeout: int = 120):
        self.host    = host.rstrip("/")
        # Strip whitespace/newlines — config fields can pick up trailing
        # whitespace from copy-paste, which causes requests to reject the
        # Authorization header with "Invalid leading whitespace".
        raw_token    = token or os.getenv("MANIFEST_TOKEN", "")
        self.token   = raw_token.strip().replace("\n", "").replace("\r", "")
        self.model   = model.strip() if model else "auto"
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _build_content(self, text: str, images: list[str] | None) -> list | str:
        if not images:
            return text
        parts = [{"type": "text", "text": text}]
        for img_path in images:
            try:
                b64, mime = _encode_image(img_path)
                parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
            except Exception:
                continue
        return parts

    def _chat(self, messages: list, images: list[str] | None = None) -> str:
        if messages and images:
            messages[-1] = {**messages[-1], "content": self._build_content(messages[-1]["content"], images)}
        payload = {"model": self.model, "messages": messages}
        last_err = None
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{self.host}/v1/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in (500, 502, 503):
                    last_err = e
                    time.sleep(2 ** attempt)   # 1s, 2s, 4s
                    continue
                raise
        raise last_err

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_code(self, prompt: str, images: list[str] | None = None) -> str:
        return self._chat([
            {
                "role":    "system",
                "content": (
                    "You are an expert Blender Python (bpy) scene builder with deep knowledge of "
                    "3D modeling, procedural geometry, PBR materials, and architectural modeling.\n"
                    "Produce geometrically correct, visually rich scene objects using:\n"
                    "- Subdivision Surface for organic shapes (terrain, rocks, trees)\n"
                    "- Solidify + Bevel modifiers for architectural geometry (walls, towers, roofs)\n"
                    "- Principled BSDF materials with base_color, roughness, metallic, normal map slots\n"
                    "- Correct scale (real-world metres: a door is 2m tall, a tower is 8-15m)\n"
                    "Rules:\n"
                    "- Always 'import bpy' first.\n"
                    "- Name every created object immediately: bpy.context.object.name = '...'\n"
                    "- Link new meshes to bpy.context.scene.collection.\n"
                    "- Call bpy.context.view_layer.update() at the end.\n"
                    "- NEVER delete existing objects. NEVER call select_all + delete.\n"
                    "Return ONLY executable Python code. No markdown, no explanation."
                ),
            },
            {"role": "user", "content": self._build_content(prompt, images)},
        ])

    def plan(self, prompt: str, images: list[str] | None = None) -> list[str]:
        resp = self._chat([
            {
                "role":    "system",
                "content": (
                    "You are a professional Blender pipeline planner and 3D scene director. "
                    "Return ONLY a numbered list of steps, one per line, 20-40 steps max. "
                    "Each step must specify: what to create, exact dimensions, position, "
                    "material (color/roughness/metallic), and any modifiers needed. "
                    "No JSON, no code blocks, no extra text. "
                    "Example:\n1. Create base terrain plane 40x40m, green grass material roughness 0.9\n"
                    "2. Add cylindrical tower base r=2m h=12m at (0,0,0), stone material gray roughness 0.9\n"
                    "3. Bevel tower top edges, add battlements (8 merlons 0.3x0.5x0.4m)"
                ),
            },
            {"role": "user", "content": self._build_content(prompt, images)},
        ])
        # Primary: numbered list — no JSON parsing, no fence stripping needed
        lines = [
            re.sub(r'^\d+[.)]\s*', '', l).strip()
            for l in resp.splitlines()
            if re.match(r'^\d+[.)]', l.strip())
        ]
        if lines:
            return lines
        # Fallback: greedy JSON array search (greedy .* not .*? avoids truncation on ] in text)
        m = re.search(r'\[.*\]', resp, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(0))
                if isinstance(result, list):
                    return [str(s) for s in result]
            except json.JSONDecodeError:
                pass
        # Last resort: strip markdown fences and parse whole response as JSON
        clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', resp.strip(),
                       flags=re.IGNORECASE | re.MULTILINE)
        try:
            result = json.loads(clean)
            if isinstance(result, list):
                return [str(s) for s in result]
        except json.JSONDecodeError:
            pass
        # Plain line split — skip fence lines, return whatever is left
        return [l.strip() for l in resp.splitlines()
                if l.strip() and not l.strip().startswith('`')]

    def describe(self, prompt: str, images: list[str] | None = None) -> str:
        """Return a short plain-text description — no code, no JSON."""
        return self._chat([
            {
                "role":    "system",
                "content": "Describe the task in 1-3 sentences. No code.",
            },
            {"role": "user", "content": self._build_content(prompt, images)},
        ])

    def fix_error(self, code: str, error: str, context: str = "", images: list[str] | None = None) -> str:
        return self._chat([
            {
                "role":    "system",
                "content": (
                    "You are an expert Blender Python (bpy) developer fixing a runtime error. "
                    "The code runs inside Blender's bpy environment. "
                    "Fix ONLY the error — preserve all working parts of the code. "
                    "After object creation call bpy.context.view_layer.update(). "
                    "NEVER delete existing scene objects as part of the fix. "
                    "Return ONLY the corrected executable Python code. No markdown, no explanation."
                ),
            },
            {
                "role":    "user",
                "content": (
                    f"CODE:\n```python\n{code}\n```\n\n"
                    f"ERROR:\n{error}\n\n"
                    f"CONTEXT:\n{context}"
                ),
            },
        ], images=images or None)

    def is_available(self) -> bool:
        """Return True if Manifest is running and reachable."""
        try:
            r = requests.get(
                f"{self.host}/v1/models",
                headers=self._headers(),
                timeout=3,
            )
            return r.status_code == 200
        except Exception:
            try:
                r = requests.get(f"{self.host}/", timeout=3)
                return r.status_code < 500
            except Exception:
                return False
