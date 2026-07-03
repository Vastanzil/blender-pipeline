"""
ai/gemini_client.py — Google Gemini generateContent backend.
"""
import json
import os
import re
import requests


class GeminiClient:
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key="", model="gemini-2.0-flash", timeout=120):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model   = model
        self.timeout = timeout

    def _generate(self, prompt: str) -> str:
        url = f"{self.BASE}/{self.model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def generate_code(self, prompt: str) -> str:
        return self._generate(
            f"You are a Blender Python expert. Return only executable bpy code.\n\n{prompt}")

    def plan(self, prompt: str) -> list:
        resp = self._generate(
            f"You are a Blender pipeline planner. Return a JSON array of step strings.\n\n{prompt}")
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return [l.strip() for l in resp.splitlines() if l.strip()]

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self._generate(
            f"Fix this bpy code error. Return only corrected code.\nCODE:\n{code}\nERROR:\n{error}")

    def is_available(self) -> bool:
        return bool(self.api_key)
