"""
ai/router.py
AIRouter — runtime-switchable AI backend.
Backends: ollama (default), openai, anthropic, gemini, manifest.
"""
from config.registry import get
from .ollama_client    import OllamaClient
from .openai_client    import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client    import GeminiClient
from .manifest_client  import ManifestClient


class AIRouter:
    def __init__(self):
        self._backends: dict = {}
        self._active:   str  = get("ai_backend", "ollama")
        self._build_backends()

    def _build_backends(self):
        self._backends = {
            "ollama":    OllamaClient(
                host          = get("ollama_host", "http://localhost:11434"),
                model         = get("coder_model",   ""),
                planner_model = get("planner_model",  ""),
            ),
            "openai":    OpenAIClient(api_key=get("openai_api_key", "")),
            "anthropic": AnthropicClient(api_key=get("anthropic_api_key", "")),
            "gemini":    GeminiClient(api_key=get("gemini_api_key", "")),
            "manifest":  ManifestClient(
                host  = get("manifest_host",  "http://localhost:2099"),
                token = get("manifest_token", ""),
                model = get("manifest_model", "auto"),
            ),
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

    def rebuild(self):
        """Re-read config and recreate all backends.

        Call this after the user saves new settings (model selection, API keys,
        Manifest token, etc.) so changes take effect without needing to reconnect.
        The active backend name is preserved.
        """
        self._build_backends()
        # Sync active_name in case it was cleared somehow
        if self._active not in self._backends:
            self._active = get("ai_backend", "ollama")

    def generate_code(self, prompt: str) -> str:
        return self.active.generate_code(prompt)

    def plan(self, prompt: str) -> list:
        return self.active.plan(prompt)

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self.active.fix_error(code, error, context)

    def available_backends(self) -> dict:
        """Return {name: is_available} for all backends."""
        return {name: b.is_available() for name, b in self._backends.items()}
