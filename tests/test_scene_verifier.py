"""Tests for SceneVerifier — camera angle setup, capture, verify_realism."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.scene_verifier import SceneVerifier, CAMERA_ANGLES, RealismReport


def test_camera_angles_count():
    assert len(CAMERA_ANGLES) == 4


def test_camera_angle_names():
    names = {a[0] for a in CAMERA_ANGLES}
    assert names == {"front", "side", "top", "iso"}


def test_capture_returns_empty_on_client_failure():
    class FailClient:
        def exec_code(self, code):
            from mcp.models import ToolResult
            return ToolResult("exec", False, output="", error="Blender crashed")

    sv    = SceneVerifier()
    paths = sv.capture_all(FailClient(), "/tmp/output")
    assert paths == []


def test_capture_parses_output_paths():
    class OKClient:
        def exec_code(self, code):
            from mcp.models import ToolResult
            out = "VERIFY_PATHS:/tmp/verify_front.png,/tmp/verify_side.png,/tmp/verify_top.png,/tmp/verify_iso.png"
            return ToolResult("exec", True, output=out)

    sv    = SceneVerifier()
    paths = sv.capture_all(OKClient(), "/tmp/output")
    assert len(paths) == 4
    assert all(p.endswith(".png") for p in paths)


def test_verify_realism_no_screenshots():
    sv     = SceneVerifier()
    report = sv.verify_realism(None, [], [], "test_project")
    assert isinstance(report, RealismReport)
    assert report.passed


def test_verify_realism_parses_json():
    class MockAI:
        def generate_code(self, prompt, images=None):
            return json.dumps({
                "issues": [
                    {"type": "merged", "objects": ["tree", "house"],
                     "fix_hint": "Move tree 2m away from house"}
                ]
            })

    sv     = SceneVerifier()
    report = sv.verify_realism(MockAI(), ["fake.png"], [], "test")
    assert len(report.issues) == 1
    assert report.issues[0].type == "merged"
    assert "tree" in report.issues[0].objects
    assert not report.passed


def test_verify_realism_handles_malformed_json():
    class BadAI:
        def generate_code(self, prompt, images=None):
            return "not json at all"

    sv     = SceneVerifier()
    report = sv.verify_realism(BadAI(), ["fake.png"], [], "test")
    assert isinstance(report, RealismReport)
    assert report.passed   # graceful fallback


def test_verify_realism_strips_markdown_fences():
    class FencedAI:
        def generate_code(self, prompt, images=None):
            return '```json\n{"issues": []}\n```'

    sv     = SceneVerifier()
    report = sv.verify_realism(FencedAI(), ["fake.png"], [], "test")
    assert report.passed
