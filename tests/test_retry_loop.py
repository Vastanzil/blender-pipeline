"""Tests for RetryLoop — execute, fail, AI-fix, retry logic."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp.models import ToolResult


class SequentialClient:
    """Returns pre-programmed ToolResult objects one at a time."""
    def __init__(self, results):
        self._iter = iter(results)

    def exec_code(self, code):
        return next(self._iter)


class MockAI:
    def __init__(self, fix="# fixed"):
        self._fix = fix

    def fix_error(self, code, error, context="", skill_hint=None,
                  visual_context="", force_manifest=False):
        return code + "\n" + self._fix


def ok(output="Done"):
    return ToolResult("exec", True, output=output, error="")


def fail(error="SomeError"):
    return ToolResult("exec", False, output="", error=error)


def test_success_on_first_try():
    from pipeline.retry_loop import RetryLoop
    loop = RetryLoop(SequentialClient([ok("Cube added")]), MockAI(), max_retries=3)
    r = loop.execute("import bpy")
    assert r.success is True
    assert r.attempts == 1
    assert r.output == "Cube added"


def test_retries_then_succeeds():
    from pipeline.retry_loop import RetryLoop
    loop = RetryLoop(SequentialClient([fail(), fail(), ok()]), MockAI(), max_retries=5)
    r = loop.execute("import bpy")
    assert r.success is True
    assert r.attempts == 3


def test_fails_after_max_retries():
    from pipeline.retry_loop import RetryLoop
    loop = RetryLoop(SequentialClient([fail(f"Error {i}") for i in range(5)]),
                     MockAI(), max_retries=5)
    r = loop.execute("import bpy")
    assert r.success is False
    assert r.attempts == 5


def test_max_retries_one_no_fix_called():
    from pipeline.retry_loop import RetryLoop
    called = []
    class SpyAI:
        def fix_error(self, code, error, context=""):
            called.append(1)
            return code
    loop = RetryLoop(SequentialClient([fail()]), SpyAI(), max_retries=1)
    r = loop.execute("import bpy")
    assert r.success is False
    assert called == []   # no fix attempt when max_retries=1


def test_traceback_in_output_treated_as_error():
    from pipeline.retry_loop import RetryLoop
    # success=True but output contains Traceback — should still retry
    bad = ToolResult("exec", True, output="Traceback (most recent call last):\n  ...", error="")
    loop = RetryLoop(SequentialClient([bad, ok()]), MockAI(), max_retries=3)
    r = loop.execute("import bpy")
    assert r.success is True
    assert r.attempts == 2


def test_code_updated_by_ai():
    from pipeline.retry_loop import RetryLoop
    codes_sent = []
    class RecordingClient:
        def __init__(self):
            self._n = 0
        def exec_code(self, code):
            codes_sent.append(code)
            self._n += 1
            return ok() if self._n >= 2 else fail()
    loop = RetryLoop(RecordingClient(), MockAI(fix="# patched"), max_retries=3)
    r = loop.execute("original code")
    assert "# patched" in codes_sent[1]
