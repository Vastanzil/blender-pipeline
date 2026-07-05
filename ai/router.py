"""
AIRouter — Manifest-only AI backend for v3.0.

All multi-backend code was deleted in phase 1. This router now
delegates to a single ManifestClient instance.
"""
from __future__ import annotations

from config.registry import get
from .manifest_client import ManifestClient


class AIRouter:
    def __init__(self):
        self._client: ManifestClient | None = None
        self.rebuild()

    def rebuild(self) -> None:
        """Instantiate ManifestClient from live config."""
        self._client = ManifestClient(
            host=get("manifest_host", "http://localhost:2099"),
            token=get("manifest_token", ""),
            model=get("manifest_model", "auto"),
            timeout=int(get("ai_timeout", 120)),
        )

    @property
    def active_name(self) -> str:
        return "manifest"

    @property
    def active_display_name(self) -> str:
        """Human-readable name, e.g. 'manifest / auto'."""
        if not self._client:
            return "manifest"
        model = getattr(self._client, "_model", None)
        if not model:
            model = self._client.model
        return f"manifest / {model}" if model else "manifest"

    @property
    def active(self):
        """Return the active backend client (ManifestClient)."""
        return self._client

    def available_backends(self) -> dict[str, bool]:
        """Return {name: is_available} for all backends."""
        return {"manifest": self._client.is_available() if self._client else False}

    def generate_code(self, prompt: str, images: list[str] | None = None) -> str:
        return self._client.generate_code(prompt, images=images)

    def plan(self, prompt: str, images: list[str] | None = None) -> list[str]:
        return self._client.plan(prompt, images=images)

    def fix_error(self, code: str, error: str, context: str = "") -> str:
        return self._client.fix_error(code, error, context)

    def is_available(self) -> bool:
        return bool(self._client and self._client.is_available())