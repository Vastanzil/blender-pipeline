"""Tests for ReferenceLoop — render, compare, improve cycle."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.models import ToolResult
from pipeline.reference_loop import ReferenceLoop


class _OKClient:
    def exec_code(self, code):
        return ToolResult("exec", True, output="ok")


class _FailClient:
    def exec_code(self, code):
        return ToolResult("exec", False, output="", error="fail")


class _MockAI:
    def generate_code(self, prompt, images=None):
        return "import bpy"

    def describe(self, prompt, images=None):
        return '{"score": 80, "differences": ["add tree", "fix lighting", "adjust color"]}'

    def plan(self, prompt, images=None):
        return ["1. Fix lighting", "2. Add tree"]


class _LowScoreAI(_MockAI):
    def describe(self, prompt, images=None):
        return '{"score": 30, "differences": ["missing cottage", "wrong color", "no bridge"]}'


class _BadJsonAI(_MockAI):
    def describe(self, prompt, images=None):
        return "not json at all"


def test_run_stops_when_score_above_threshold(tmp_path):
    loop = ReferenceLoop(_OKClient(), _MockAI(), max_iterations=3, score_threshold=75)
    results = loop.run(["fake_ref.png"], str(tmp_path), "test_project", "ctx")
    assert len(results) == 1
    assert results[0]["score"] == 80
    assert results[0]["iteration"] == 0


def test_run_applies_improvements_when_score_low(tmp_path):
    loop = ReferenceLoop(_OKClient(), _LowScoreAI(), max_iterations=2, score_threshold=75)
    results = loop.run(["fake_ref.png"], str(tmp_path), "test_project", "ctx")
    assert len(results) == 2
    for r in results:
        assert r["score"] == 30
    assert len(results[0]["steps_applied"]) > 0


def test_compare_handles_bad_json(tmp_path):
    loop = ReferenceLoop(_OKClient(), _BadJsonAI(), max_iterations=1, score_threshold=75)
    results = loop.run(["fake_ref.png"], str(tmp_path), "test_project", "ctx")
    assert results[0]["score"] == 0
    assert "parse error" in results[0]["feedback"].lower()


def test_run_stops_when_render_fails(tmp_path):
    loop = ReferenceLoop(_FailClient(), _LowScoreAI(), max_iterations=3, score_threshold=75)
    results = loop.run(["fake_ref.png"], str(tmp_path), "test_project", "ctx")
    assert len(results) == 1
    assert results[0]["render_path"] is None


def test_strip_fences():
    code = "```python\nimport bpy\n```"
    assert ReferenceLoop._strip_fences(code) == "import bpy"


def test_strip_fences_no_fence():
    code = "import bpy"
    assert ReferenceLoop._strip_fences(code) == "import bpy"
