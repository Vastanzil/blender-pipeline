"""
ai/router.py
AIRouter — runtime-switchable AI backend.
Backends: ollama (default), openai, anthropic, gemini.
"""
from config.registry import get
from .ollama_client   import OllamaClient
from .openai_client   import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client   import GeminiClient


class AIRouter:
    def __init__(self):
        self._backends: dict = {}
        self._active:   str  = get("ai_backend", "ollama")
        self._build_backends()

    def _build_backends(self):
        self._backends = {
            "ollama":    OllamaClient(
                host          = get("ollama_host", "http://localhost:11434"),
                model         = get("coder_model",   "qwen2.5-coder:7b"),
                planner_model = get("planner_model",  "qwen3:8b"),
            ),
            "openai":    OpenAIClient(api_key=get("openai_api_key", "")),
            "anthropic": AnthropicClient(api_key=get("anthropic_api_key", "")),
            "gemini":    GeminiClient(api_key=get("gemini_api_key", "")),
        }

    @property
    def active(self):
        return self._backends[self._active]

    @property
    def active_name(self) -> str:
        return self._active

    def switch(self, backend: str):
        if backend not in self._backends:
            raise ValueError(f"Unknown backend: {backend!r}. "
                             f"Choose from {list(self._backends)}")
        self._active = backend

    def generate_code(self, prompt: str) -> str:
        return self.active.generate_code(prompt)

    def plan(self, prompt: str) -> list:
        return self.active.plan(prompt)

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self.active.fix_error(code, error, context)

    def available_backends(self) -> dict:
        """Return {name: is_available} for all backends."""
        return {name: b.is_available() for name, b in self._backends.items()}
