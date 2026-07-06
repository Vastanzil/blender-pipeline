"""
AIRouter — routes AI calls to Manifest (Claude) or local BlenderLLM.

Hybrid mode (hybrid_mode=True in config):
  - plan()           → Manifest (needs vision + broad reasoning)
  - generate_code()  → BlenderLLM (narrow bpy codegen, text-only)
  - fix_error()      → BlenderLLM (same; escalates to Manifest on repeated failure)
  - describe()       → Manifest always (vision call)

Hard-pin: steps whose skill_hint contains "material", "pbr", or "texture" are
always routed to Manifest — BlenderLLM has no material/texture support.

When hybrid_mode=False (default) or BlenderLLM is unreachable, all calls go
to Manifest unchanged.
"""
from __future__ import annotations

import logging

from config.registry import get
from .manifest_client import ManifestClient

log = logging.getLogger(__name__)

_MATERIAL_HINTS = ("material", "pbr", "texture")

ROUTES_HYBRID_ON: dict[str, str] = {
    "plan":          "manifest",
    "generate_code": "blenderllm",
    "fix_error":     "blenderllm",
}
ROUTES_HYBRID_OFF: dict[str, str] = {
    "plan":          "manifest",
    "generate_code": "manifest",
    "fix_error":     "manifest",
}


def _resolve(step_kind: str, skill_hint: str | None, hybrid_on: bool) -> str:
    """Return 'manifest' or 'blenderllm' for the given call type."""
    if skill_hint and any(k in skill_hint.lower() for k in _MATERIAL_HINTS):
        return "manifest"   # hard-pin regardless of toggle
    return (ROUTES_HYBRID_ON if hybrid_on else ROUTES_HYBRID_OFF)[step_kind]


class AIRouter:
    def __init__(self):
        self._manifest: ManifestClient | None = None
        self._blenderllm = None   # BlenderLLMClient | None
        self.rebuild()

    def rebuild(self) -> None:
        """Instantiate clients from live config."""
        self._manifest = ManifestClient(
            host=get("manifest_host", "http://localhost:2099"),
            token=get("manifest_token", ""),
            model=get("manifest_model", "auto"),
            timeout=int(get("ai_timeout", 120)),
        )
        self._blenderllm = None
        if get("hybrid_mode", False):
            url = get("blenderllm_server_url", "")
            if url:
                from .blenderllm_client import BlenderLLMClient
                self._blenderllm = BlenderLLMClient(
                    base_url=url,
                    timeout=int(get("blenderllm_timeout", 180)),
                )

    # ------------------------------------------------------------------
    # Public interface

    @property
    def active_name(self) -> str:
        if self._blenderllm and get("hybrid_mode", False):
            return "hybrid"
        return "manifest"

    @property
    def active_display_name(self) -> str:
        if self._blenderllm and get("hybrid_mode", False):
            model = getattr(self._manifest, "_model", None) or self._manifest.model
            return f"hybrid (manifest/{model} + blenderllm)"
        model = getattr(self._manifest, "_model", None) or self._manifest.model
        return f"manifest / {model}" if model else "manifest"

    @property
    def active(self):
        return self._manifest

    def available_backends(self) -> dict[str, bool]:
        result: dict[str, bool] = {
            "manifest": self._manifest.is_available() if self._manifest else False,
        }
        if self._blenderllm:
            result["blenderllm"] = self._blenderllm.health()
        return result

    def is_available(self) -> bool:
        return bool(self._manifest and self._manifest.is_available())

    # ------------------------------------------------------------------

    def generate_code(self, prompt: str, images: list[str] | None = None,
                      skill_hint: str | None = None,
                      visual_context: str = "") -> str:
        hybrid_on = bool(self._blenderllm and get("hybrid_mode", False))
        backend = _resolve("generate_code", skill_hint, hybrid_on)
        if backend == "blenderllm":
            try:
                return self._blenderllm.generate_code(prompt, visual_context=visual_context)
            except Exception as e:
                log.warning("BlenderLLM generate_code failed (%s); falling back to Manifest", e)
        return self._manifest.generate_code(prompt, images=images)

    def plan(self, prompt: str, images: list[str] | None = None) -> list[str]:
        return self._manifest.plan(prompt, images=images)

    def fix_error(self, code: str, error: str, context: str = "",
                  skill_hint: str | None = None,
                  visual_context: str = "",
                  force_manifest: bool = False) -> str:
        hybrid_on = bool(self._blenderllm and get("hybrid_mode", False))
        backend = "manifest" if force_manifest else _resolve("fix_error", skill_hint, hybrid_on)
        if backend == "blenderllm":
            try:
                return self._blenderllm.fix_error(
                    code, error, context=context, visual_context=visual_context)
            except Exception as e:
                log.warning("BlenderLLM fix_error failed (%s); falling back to Manifest", e)
        return self._manifest.fix_error(code, error, context)

    def describe(self, prompt: str, images: list[str] | None = None) -> str:
        return self._manifest.describe(prompt, images=images)
