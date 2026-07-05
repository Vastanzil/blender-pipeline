"""Tests for Validator — liveness and validate_step_result."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.models import ToolResult
from pipeline.step import PipelineStep
from pipeline.validator import Validator


class _OKClient:
    def exec_code(self, code):
        if "VALIDATE_OK" in code:
            return ToolResult("exec", True, output="VALIDATE_OK")
        if "EXISTS" in code:
            return ToolResult("exec", True, output="EXISTS:True")
        if "DIMS" in code:
            return ToolResult("exec", True, output="DIMS:True")
        return ToolResult("exec", True, output="ok")


class _DeadClient:
    def exec_code(self, code):
        return ToolResult("exec", False, output="", error="Blender crashed")


class _MissingObjClient:
    def exec_code(self, code):
        if "EXISTS" in code:
            return ToolResult("exec", True, output="EXISTS:False")
        return ToolResult("exec", True, output="VALIDATE_OK")


class _ZeroDimsClient:
    def exec_code(self, code):
        if "EXISTS" in code:
            return ToolResult("exec", True, output="EXISTS:True")
        if "DIMS" in code:
            return ToolResult("exec", True, output="DIMS:False")
        return ToolResult("exec", True, output="VALIDATE_OK")


def test_is_alive_ok():
    v = Validator(_OKClient())
    assert v.is_alive() is True


def test_is_alive_dead():
    v = Validator(_DeadClient())
    assert v.is_alive() is False


def test_validate_no_obj_name_falls_back_to_liveness():
    v    = Validator(_OKClient())
    step = PipelineStep(index=0, description="Do something", success=True)
    ok, reason = v.validate_step_result(step)
    assert ok is True
    assert reason == "no_object_name"


def test_validate_missing_object():
    v    = Validator(_MissingObjClient())
    step = PipelineStep(index=0, description="Create cube",
                        success=True, bpy_object_name="My_Cube")
    ok, reason = v.validate_step_result(step)
    assert ok is False
    assert "My_Cube" in reason


def test_validate_zero_dims():
    v    = Validator(_ZeroDimsClient())
    step = PipelineStep(index=0, description="Create cube",
                        success=True, bpy_object_name="My_Cube")
    ok, reason = v.validate_step_result(step)
    assert ok is False
    assert "zero dimensions" in reason


def test_validate_passes():
    v    = Validator(_OKClient())
    step = PipelineStep(index=0, description="Create cube",
                        success=True, bpy_object_name="My_Cube")
    ok, reason = v.validate_step_result(step)
    assert ok is True
    assert reason == "ok"
