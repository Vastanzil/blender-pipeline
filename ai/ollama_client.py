"""
ai/ollama_client.py — Ollama local inference client.
Calls /api/generate (streaming disabled for simplicity).
"""
import json
import re
import requests


class OllamaClient:
    def __init__(self, host="http://localhost:11434", model="qwen2.5-coder:7b",
                 planner_model="qwen3:8b", timeout=120):
        self.host          = host.rstrip("/")
        self.model         = model
        self.planner_model = planner_model
        self.timeout       = timeout

    def _generate(self, prompt: str, model: str) -> str:
        payload = {"model": model, "prompt": prompt, "stream": False}
        r = requests.post(f"{self.host}/api/generate",
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("response", "")

    def generate_code(self, prompt: str) -> str:
        return self._generate(prompt, self.model)

    def plan(self, prompt: str) -> list:
        resp = self._generate(prompt, self.planner_model)
        # Try to extract a JSON array from the response
        m = re.search(r'\[.*?\]', resp, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # Fallback: split by newlines and clean up
        lines = [l.strip().lstrip("-•*0123456789.) ").strip()
                 for l in resp.splitlines() if l.strip()]
        return [l for l in lines if l]

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        prompt = (
            f"The following bpy Python code raised an error.\n"
            f"Fix it so it runs correctly in Blender.\n\n"
            f"CODE:\n```python\n{code}\n```\n\n"
            f"ERROR:\n{error}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"Return ONLY the corrected Python code, no explanation."
        )
        return self._generate(prompt, self.model)

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False
