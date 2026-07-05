"""Tests for CheckpointManager resume API."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.stages import Stage


def test_mark_complete_and_is_complete(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    cp = Checkpoint("test_run")
    assert not cp.is_complete(Stage.ASSET_GEN)
    cp.mark_complete(Stage.ASSET_GEN, {"step": 1})
    assert cp.is_complete(Stage.ASSET_GEN)


def test_next_stage_returns_first_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    cp = Checkpoint("test_next")
    cp.mark_complete(Stage.VISION_DETECT)
    cp.mark_complete(Stage.SPATIAL_LAYOUT)
    nxt = cp.next_stage()
    assert nxt == Stage.ASSET_GEN


def test_next_stage_none_when_all_done(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    cp = Checkpoint("test_all")
    for s in Stage:
        cp.mark_complete(s)
    assert cp.next_stage() is None


def test_set_project_name_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    cp = Checkpoint("test_name")
    cp.set_project_name("cottage_hill_20260706")
    assert cp.state.project_name == "cottage_hill_20260706"


def test_load_resume_context_merges_logger(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    from pipeline.pipeline_logger import PipelineLogger

    cp = Checkpoint("test_resume")
    cp.set_project_name("my_project")

    lg = PipelineLogger(tmp_path, context_snapshot_fn=lambda: {"goal": "build cabin"})
    lg.log("goal", "response", "I will build a cabin")

    ctx = cp.load_resume_context(lg)
    assert ctx["project_name"] == "my_project"
    assert ctx["goal"] == "build cabin"


def test_legacy_save_still_works(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    import config.registry as reg
    reg.set("output_dir", str(tmp_path))

    from pipeline.checkpoint import Checkpoint
    from pipeline.step import PipelineStep

    cp = Checkpoint("test_legacy")
    steps = [
        PipelineStep(index=0, description="Create cube", success=True),
        PipelineStep(index=1, description="Add material", success=False,
                     error="AttributeError"),
    ]
    cp.save(steps)
    assert cp.path
    import json
    data = json.loads(open(cp.path).read())
    assert len(data["steps"]) == 2
    assert data["steps"][0]["description"] == "Create cube"
