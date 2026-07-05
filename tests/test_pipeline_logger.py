"""Tests for PipelineLogger — JSONL format, context snapshot, get_resume_context."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.pipeline_logger import PipelineLogger


def test_log_creates_file(tmp_path):
    lg = PipelineLogger(tmp_path)
    lg.log("plan", "response", "Do something")
    assert lg.path.exists()


def test_log_valid_jsonl(tmp_path):
    lg = PipelineLogger(tmp_path)
    lg.log("goal", "response", "Build a cabin")
    lg.log("codegen", "prompt", "Write bpy code")
    lines = lg.path.read_text().strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert "seq" in rec
        assert "ts"  in rec
        assert "content" in rec


def test_log_sequential_seq(tmp_path):
    lg = PipelineLogger(tmp_path)
    lg.log("goal",    "response", "a")
    lg.log("codegen", "prompt",   "b")
    lg.log("codegen", "response", "c")
    lines = [json.loads(l) for l in lg.path.read_text().strip().split("\n")]
    seqs  = [l["seq"] for l in lines]
    assert seqs == [0, 1, 2]


def test_context_snapshot_captured(tmp_path):
    called = [0]
    def snap():
        called[0] += 1
        return {"goal": "test_goal", "step": called[0]}

    lg = PipelineLogger(tmp_path, context_snapshot_fn=snap)
    lg.log("test", "prompt", "hello")
    rec = json.loads(lg.path.read_text().strip())
    assert rec["context"]["goal"] == "test_goal"
    assert called[0] == 1


def test_get_resume_context_empty(tmp_path):
    lg = PipelineLogger(tmp_path)
    assert lg.get_resume_context() == {}


def test_get_resume_context_returns_last(tmp_path):
    def snap1():
        return {"goal": "first", "step": 1}
    def snap2():
        return {"goal": "second", "step": 2}

    lg1 = PipelineLogger(tmp_path, context_snapshot_fn=snap1)
    lg1.log("goal",    "response", "first goal")
    lg1._context_snapshot = snap2
    lg1.log("codegen", "response", "second log")

    ctx = lg1.get_resume_context()
    assert ctx["goal"] == "second"


def test_rename_artifact(tmp_path):
    src = tmp_path / "render.png"
    src.write_bytes(b"fake png")
    common = tmp_path / "artifacts"
    lg  = PipelineLogger(tmp_path)
    dst = lg.rename_artifact(src, "verify", common)
    assert dst.exists()
    assert not src.exists()
    assert "verify" in dst.name
