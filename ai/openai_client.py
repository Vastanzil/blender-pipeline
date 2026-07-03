"""
ai/openai_client.py — OpenAI chat completions backend.
"""
import json
import os
import re
import requests


class OpenAIClient:
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key="", model="gpt-4o", timeout=120):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model   = model
        self.timeout = timeout

    def _chat(self, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }
        payload = {"model": self.model, "messages": messages}
        r = requests.post(self.API_URL, headers=headers,
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def generate_code(self, prompt: str) -> str:
        return self._chat([
            {"role": "system", "content": "You are a Blender Python (bpy) expert. Return only executable Python code."},
            {"role": "user",   "content": prompt},
        ])

    def plan(self, prompt: str) -> list:
        resp = self._chat([
            {"role": "system", "content": "You are a Blender pipeline planner. Return a JSON array of step description strings."},
            {"role": "user",   "content": prompt},
        ])
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return [l.strip() for l in resp.splitlines() if l.strip()]

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self._chat([
            {"role": "system", "content": "Fix the bpy Python code error. Return only corrected code."},
            {"role": "user",   "content": f"CODE:\n{code}\n\nERROR:\n{error}\n\nCONTEXT:\n{context}"},
        ])

    def is_available(self) -> bool:
        return bool(self.api_key)
