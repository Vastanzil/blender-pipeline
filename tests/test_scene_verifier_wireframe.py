"""Tests for wireframe capture extension in SceneVerifier."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.models import ToolResult
from pipeline.scene_verifier import SceneVerifier


class _SolidClient:
    """Returns 4 solid paths then succeeds for each wireframe call."""
    def exec_code(self, code):
        if "VERIFY_PATHS" in code or "_CAPTURE_CODE" in code or "_angles" in code:
            paths = [f"/tmp/verify_{n}.png" for n in ("front","side","top","iso")]
            return ToolResult("exec", True,
                              output="VERIFY_PATHS:" + ",".join(paths))
        if "WIRE_PATH" in code or "WIREFRAME" in code:
            # Extract name from the injected code
            import re
            m = re.search(r"_name\s*=\s*'([^']+)'", code)
            name = m.group(1) if m else "unknown"
            return ToolResult("exec", True,
                              output=f"WIRE_PATH:/tmp/verify_wire_{name}.png")
        return ToolResult("exec", True, output="")


class _WireFailClient(_SolidClient):
    """Wireframe render always fails."""
    def exec_code(self, code):
        if "WIREFRAME" in code:
            return ToolResult("exec", False, output="", error="opengl fail")
        return super().exec_code(code)


def test_capture_all_returns_8_interleaved_paths_when_wireframe_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr("config.registry.get",
                        lambda key, default=None: True if key == "capture_wireframe" else default)
    v = SceneVerifier()
    paths = v.capture_all(_SolidClient(), str(tmp_path))
    assert len(paths) == 8
    # Interleaved: even indices solid, odd indices wire
    for i, p in enumerate(paths):
        if i % 2 == 0:
            assert "verify_wire" not in p
        else:
            assert "verify_wire" in p


def test_capture_all_returns_4_paths_when_wireframe_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr("config.registry.get",
                        lambda key, default=None: False if key == "capture_wireframe" else default)
    v = SceneVerifier()
    paths = v.capture_all(_SolidClient(), str(tmp_path))
    assert len(paths) == 4
    assert all("wire" not in p for p in paths)


def test_capture_all_falls_back_to_solid_on_wireframe_fail(monkeypatch, tmp_path):
    """When wireframe render fails, the solid path is duplicated (no crash)."""
    monkeypatch.setattr("config.registry.get",
                        lambda key, default=None: True if key == "capture_wireframe" else default)
    v = SceneVerifier()
    paths = v.capture_all(_WireFailClient(), str(tmp_path))
    # Still 8 entries — solid duplicated for failed wire slots
    assert len(paths) == 8
    # Odd slots should be solid paths (fallback)
    for i in range(1, 8, 2):
        assert "wire" not in paths[i]


def test_verify_realism_prompt_mentions_wireframe_when_8_paths():
    """verify_realism prompt must mention wireframe when >4 images are given."""
    prompts_seen = []

    class _CapturingAI:
        def generate_code(self, prompt, images=None):
            prompts_seen.append(prompt)
            return '{"issues": []}'

    v = SceneVerifier()
    fake_paths = [f"/tmp/img{i}.png" for i in range(8)]
    v.verify_realism(_CapturingAI(), fake_paths, [], "test")
    assert prompts_seen
    assert "wireframe" in prompts_seen[0].lower()


def test_verify_realism_prompt_does_not_mention_wireframe_when_4_paths():
    prompts_seen = []

    class _CapturingAI:
        def generate_code(self, prompt, images=None):
            prompts_seen.append(prompt)
            return '{"issues": []}'

    v = SceneVerifier()
    fake_paths = [f"/tmp/img{i}.png" for i in range(4)]
    v.verify_realism(_CapturingAI(), fake_paths, [], "test")
    assert "wireframe" not in prompts_seen[0].lower()
