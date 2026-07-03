"""
ai/anthropic_client.py — Anthropic Claude messages backend.
"""
import json
import os
import re
import requests


class AnthropicClient:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key="", model="claude-sonnet-4-6", timeout=120):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model   = model
        self.timeout = timeout

    def _message(self, system: str, user: str) -> str:
        headers = {
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        payload = {
            "model":      self.model,
            "max_tokens": 4096,
            "system":     system,
            "messages":   [{"role": "user", "content": user}],
        }
        r = requests.post(self.API_URL, headers=headers,
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["content"][0]["text"]

    def generate_code(self, prompt: str) -> str:
        return self._message(
            "You are a Blender Python (bpy) expert. Return only executable Python code.",
            prompt,
        )

    def plan(self, prompt: str) -> list:
        resp = self._message(
            "You are a Blender pipeline planner. Return a JSON array of step description strings only.",
            prompt,
        )
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return [l.strip() for l in resp.splitlines() if l.strip()]

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self._message(
            "Fix the bpy Python error. Return only the corrected code.",
            f"CODE:\n{code}\n\nERROR:\n{error}\n\nCONTEXT:\n{context}",
        )

    def is_available(self) -> bool:
        return bool(self.api_key)
