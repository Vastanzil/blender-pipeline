"""Tests for PipelineStep dataclass."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_step_summary_success():
    from pipeline.step import PipelineStep
    s = PipelineStep(index=0, description="Create a cube", success=True)
    summary = s.summary()
    assert "OK" in summary
    assert "1" in summary
    assert "Create a cube" in summary


def test_step_summary_failure():
    from pipeline.step import PipelineStep
    s = PipelineStep(index=2, description="Add material", success=False, error="Not found")
    summary = s.summary()
    assert "FAIL" in summary
    assert "3" in summary


def test_step_defaults():
    from pipeline.step import PipelineStep
    s = PipelineStep(index=0, description="test step")
    assert s.success   is False
    assert s.error     == ""
    assert s.output    == ""
    assert s.attempts  == 0
    assert s.category  == "geometry"
    assert s.code      == ""


def test_step_description_truncated_in_summary():
    from pipeline.step import PipelineStep
    long_desc = "A" * 200
    s = PipelineStep(index=0, description=long_desc, success=True)
    # summary should not blow up; description is sliced at 60
    assert len(s.summary()) < 120
