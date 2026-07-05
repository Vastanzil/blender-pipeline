"""
Tests for the Pipeline Orchestrator (fully mocked — no Blender required).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp.models import ToolResult


class MockClient:
    def __init__(self, exec_ok=True):
        self._exec_ok = exec_ok

    def exec_code(self, code):
        if "VALIDATE_OK" in code:
            return ToolResult("exec", True, output="VALIDATE_OK")
        if self._exec_ok:
            return ToolResult("exec", True, output="Done")
        return ToolResult("exec", False, output="", error="RuntimeError: bad")

    def get_scene_info(self):
        return ToolResult("scene", True, output={"objects": []})

    def get_blender_version(self):
        return (5, 1, 2)


class MockAI:
    active_name = "mock"

    def plan(self, prompt, images=None):
        return ["Create cube", "Add material", "Set render engine"]

    def generate_code(self, prompt, images=None):
        return "import bpy\nprint('step done')"

    def fix_error(self, code, error, context=""):
        return code + "\n# fixed"

    def available_backends(self):
        return {"mock": True}


def test_orchestrator_runs_all_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    from pipeline.orchestrator import Orchestrator
    from realtime.event_bus import EventBus
    bus = EventBus()
    events = []
    bus.subscribe("pipeline.step.done", lambda d: events.append(d))

    orch = Orchestrator(MockClient(exec_ok=True), MockAI(), bus)
    steps = orch.run("Create a forest")
    assert len(steps) == 3
    assert all(s.success for s in steps)
    assert len(events) == 3


def test_orchestrator_emits_pipeline_done(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    from pipeline.orchestrator import Orchestrator
    from realtime.event_bus import EventBus
    bus = EventBus()
    done_events = []
    bus.subscribe("pipeline.done", lambda d: done_events.append(d))

    orch = Orchestrator(MockClient(), MockAI(), bus)
    orch.run("test prompt")
    assert len(done_events) == 1
    assert done_events[0]["total_steps"] == 3


def test_orchestrator_abort(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    from pipeline.orchestrator import Orchestrator
    from realtime.event_bus import EventBus

    class AbortingAI(MockAI):
        def __init__(self, orch_ref):
            self._ref = orch_ref
            self._n   = 0
        def generate_code(self, prompt, images=None):
            self._n += 1
            if self._n >= 2:
                self._ref.abort()
            return "import bpy"

    bus = EventBus()
    orch = Orchestrator(MockClient(), MockAI(), bus)
    ai   = AbortingAI(orch)
    orch._ai = ai
    orch._retry._ai = ai
    steps = orch.run("test")
    # Should have stopped before completing all 3
    assert len(steps) < 3


def test_orchestrator_empty_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    from pipeline.orchestrator import Orchestrator
    from realtime.event_bus import EventBus

    class EmptyPlanAI(MockAI):
        def plan(self, prompt, images=None): return []

    bus    = EventBus()
    aborted = []
    bus.subscribe("pipeline.aborted", lambda d: aborted.append(d))
    orch   = Orchestrator(MockClient(), EmptyPlanAI(), bus)
    steps  = orch.run("empty")
    assert steps == []
    assert len(aborted) == 1
