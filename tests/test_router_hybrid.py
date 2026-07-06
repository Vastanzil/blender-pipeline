"""Tests for hybrid AI routing logic."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.router import _resolve


# ── _resolve() routing table ──────────────────────────────────────────────

def test_hybrid_off_routes_all_to_manifest():
    for kind in ("plan", "generate_code", "fix_error"):
        assert _resolve(kind, None, hybrid_on=False) == "manifest"


def test_hybrid_on_routes_codegen_and_fix_to_blenderllm():
    assert _resolve("generate_code", None, hybrid_on=True) == "blenderllm"
    assert _resolve("fix_error",     None, hybrid_on=True) == "blenderllm"


def test_hybrid_on_keeps_plan_on_manifest():
    assert _resolve("plan", None, hybrid_on=True) == "manifest"


def test_material_hint_hardpins_to_manifest_regardless_of_hybrid():
    for hint in ("material setup", "PBR shader", "texture painting"):
        assert _resolve("generate_code", hint, hybrid_on=True)  == "manifest"
        assert _resolve("fix_error",     hint, hybrid_on=True)  == "manifest"
        assert _resolve("generate_code", hint, hybrid_on=False) == "manifest"


def test_non_material_hint_respects_hybrid():
    assert _resolve("generate_code", "add tree", hybrid_on=True)  == "blenderllm"
    assert _resolve("generate_code", "add tree", hybrid_on=False) == "manifest"


# ── BlenderLLMClient never sends images ───────────────────────────────────

def test_blenderllm_client_never_sends_images(monkeypatch):
    """BlenderLLMClient._chat() must not include an 'images' key in the payload."""
    import json
    from ai.blenderllm_client import BlenderLLMClient

    captured = {}

    class _MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "import bpy"}}]}

    def _fake_post(url, json=None, timeout=None, **kw):
        captured["payload"] = json
        return _MockResponse()

    import requests
    monkeypatch.setattr(requests, "post", _fake_post)

    client = BlenderLLMClient("http://localhost:8080")
    client.generate_code("create cube", visual_context="a small cube at origin")

    assert "images" not in captured["payload"]
    assert "image_url" not in str(captured["payload"])


# ── AIRouter falls back to Manifest when BlenderLLM raises ───────────────

def test_router_falls_back_to_manifest_on_blenderllm_error(monkeypatch):
    """If BlenderLLMClient.generate_code raises, AIRouter should use Manifest."""
    import importlib
    monkeypatch.setenv("HOME", "/tmp")
    monkeypatch.setattr("config.registry._config_path", lambda: __import__("pathlib").Path("/tmp/bc_test_cfg.json"))

    from config.registry import set as reg_set
    reg_set("hybrid_mode", True)
    reg_set("blenderllm_server_url", "http://localhost:9999")

    from ai.router import AIRouter

    class _BrokenLLM:
        def generate_code(self, *a, **kw):
            raise RuntimeError("connection refused")

    class _ManifestOK:
        def generate_code(self, prompt, images=None):
            return "import bpy  # from manifest"
        def is_available(self):
            return True

    router = AIRouter.__new__(AIRouter)
    router._manifest   = _ManifestOK()
    router._blenderllm = _BrokenLLM()

    result = router.generate_code("create cube")
    assert "manifest" in result
