"""
ai/manifest_client.py
Manifest AI router client (http://localhost:2099).

Modified for v3.0 to support image reference upload and vision input.
"""
from __future__ import annotations

import json
import os
import re
import requests

# NEW: encode image file paths to base64 for OpenAI-like vision input
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
        r = requests.post(
            f"{self.host}/v1/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Public interface (updated signatures to accept images=None)
    # ------------------------------------------------------------------

    def generate_code(self, prompt: str, images: list[str] | None = None) -> str:
        return self._chat([
            {
                "role":    "system",
                "content": (
                    "You are a Blender Python (bpy) expert. "
                    "Return ONLY executable Python code, no explanation."
                ),
            },
            {"role": "user", "content": self._build_content(prompt, images)},
        ])

    def plan(self, prompt: str, images: list[str] | None = None) -> list[str]:
        resp = self._chat([
            {
                "role":    "system",
                "content": (
                    "You are a Blender pipeline planner. "
                    "Return a JSON array of step description strings only. "
                    "Example: [\"Create base mesh\", \"Add material\", \"Set lighting\"]"
                ),
            },
            {"role": "user", "content": self._build_content(prompt, images)},
        ])
        # Try to extract a JSON array
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # Fallback: split by lines
        lines = [l.strip().lstrip("-•*0123456789.) ").strip()
                 for l in resp.splitlines() if l.strip()]
        return [l for l in lines if l]

    def fix_error(self, code: str, error: str, context: str = "", images: list[str] | None = None) -> str:
        return self._chat([
            {
                "role":    "system",
                "content": "Fix the bpy Python code error. Return ONLY the corrected code.",
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
            # Fallback: try root health endpoint
            try:
                r = requests.get(f"{self.host}/", timeout=3)
                return r.status_code < 500
            except Exception:
                return False