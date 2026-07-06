"""
ai/blenderllm_client.py
Thin HTTP client for a locally-served BlenderLLM endpoint.

BlenderLLM (Qwen2.5-Coder-7B fine-tune) is TEXT-ONLY — no image_url payloads
are ever sent. visual_context (a short textual description of spatial/visual
requirements) is injected into the prompt instead.

The server is expected to expose an OpenAI-compatible /v1/chat/completions
endpoint (llama-server, Ollama, or routed through Manifest as a custom provider).
"""
from __future__ import annotations

import requests


class BlenderLLMClient:
    def __init__(self, base_url: str, timeout: int = 180):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------

    def generate_code(self, prompt: str, visual_context: str = "") -> str:
        """Generate bpy Python code for the given step description."""
        user_content = prompt
        if visual_context:
            user_content = f"Visual/spatial context: {visual_context}\n\n{prompt}"
        return self._chat([
            {"role": "system", "content": (
                "You are BlenderLLM, an expert Blender Python code generator. "
                "Return ONLY executable bpy Python code. No explanations, no markdown fences."
            )},
            {"role": "user", "content": user_content},
        ])

    def fix_error(self, code: str, error: str, context: str = "",
                  visual_context: str = "") -> str:
        """Fix a traceback in the given bpy code."""
        parts = []
        if context:
            parts.append(f"Context: {context}")
        if visual_context:
            parts.append(f"Visual/spatial context: {visual_context}")
        parts.append(f"The following Blender Python code raised an error:\n\n{code}")
        parts.append(f"Error:\n{error}")
        parts.append("Return ONLY the corrected bpy Python code.")
        return self._chat([
            {"role": "system", "content": (
                "You are BlenderLLM. Fix the Blender Python code. "
                "Return ONLY executable bpy Python code. No explanations, no markdown fences."
            )},
            {"role": "user", "content": "\n\n".join(parts)},
        ])

    def health(self) -> bool:
        """Return True if the server responds to a minimal request."""
        try:
            r = requests.post(
                f"{self._base}/v1/chat/completions",
                json={"model": "blenderllm", "messages": [
                    {"role": "user", "content": "ping"}
                ], "max_tokens": 1},
                timeout=5,
            )
            return r.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------

    def _chat(self, messages: list) -> str:
        payload = {"model": "blenderllm", "messages": messages}
        # NOTE: no images key — BlenderLLM is text-only
        r = requests.post(
            f"{self._base}/v1/chat/completions",
            json=payload,
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
