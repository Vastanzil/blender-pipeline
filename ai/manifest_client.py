"""
ai/manifest_client.py
=====================
Manifest AI router client (http://localhost:2099).

Manifest is a local LLM proxy/router that speaks both OpenAI-compatible
and Anthropic-compatible APIs. This client uses the OpenAI-compatible
endpoint (/v1/chat/completions) with a Bearer token.

When model="auto", Manifest decides which underlying model/provider to use
(it can route to local Ollama, Claude, GPT-4, etc. based on its own config).

Setup:
  1. Install Manifest: https://github.com/mnfst/manifest
  2. Start it on port 2099
  3. Copy your mnfst_xxx token from Manifest's dashboard
  4. Add to app: Connection Setup → AI Backend → manifest

env fallback: MANIFEST_TOKEN=mnfst_xxx
"""
from __future__ import annotations

import json
import os
import re
import requests


class ManifestClient:
    def __init__(self, host: str = "http://localhost:2099",
                 token: str = "",
                 model: str = "auto",
                 timeout: int = 120):
        self.host    = host.rstrip("/")
        self.token   = token or os.getenv("MANIFEST_TOKEN", "")
        self.model   = model   # "auto" = let Manifest decide
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _chat(self, messages: list) -> str:
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
    # Public interface (same as all other AI clients)
    # ------------------------------------------------------------------

    def generate_code(self, prompt: str) -> str:
        return self._chat([
            {
                "role":    "system",
                "content": (
                    "You are a Blender Python (bpy) expert. "
                    "Return ONLY executable Python code, no explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ])

    def plan(self, prompt: str) -> list:
        resp = self._chat([
            {
                "role":    "system",
                "content": (
                    "You are a Blender pipeline planner. "
                    "Return a JSON array of step description strings only. "
                    "Example: [\"Create base mesh\", \"Add material\", \"Set lighting\"]"
                ),
            },
            {"role": "user", "content": prompt},
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

    def fix_error(self, code: str, error: str, context: str = "") -> str:
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
        ])

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
