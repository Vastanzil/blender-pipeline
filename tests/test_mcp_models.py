"""Tests for MCP data models (ToolParam, Tool, ToolResult)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_tool_required_optional_split():
    from mcp.models import Tool, ToolParam
    t = Tool(name="test", description="desc", params=[
        ToolParam(name="req",  type="string",  required=True),
        ToolParam(name="opt",  type="integer", required=False, default=0),
    ])
    assert len(t.required_params()) == 1
    assert t.required_params()[0].name == "req"
    assert len(t.optional_params()) == 1
    assert t.optional_params()[0].name == "opt"


def test_tool_no_params():
    from mcp.models import Tool
    t = Tool(name="empty", description="")
    assert t.required_params() == []
    assert t.optional_params() == []
    assert t.params == []


def test_tool_result_text_success():
    from mcp.models import ToolResult
    r = ToolResult(tool_name="exec", success=True, output="Cube added")
    assert r.text() == "Cube added"


def test_tool_result_text_error():
    from mcp.models import ToolResult
    r = ToolResult(tool_name="exec", success=False, error="Object not found")
    assert "Object not found" in r.text()
    assert "ERROR" in r.text()


def test_tool_result_text_dict_output():
    from mcp.models import ToolResult
    r = ToolResult(tool_name="scene", success=True, output={"objects": 3})
    text = r.text()
    assert "objects" in text


def test_tool_to_dict():
    from mcp.models import Tool, ToolParam
    t = Tool(name="create_object", description="Creates an object",
             params=[ToolParam(name="type", type="string", required=True)])
    d = t.to_dict()
    assert d["name"] == "create_object"
    assert len(d["params"]) == 1
    assert d["params"][0]["name"] == "type"
    assert d["params"][0]["required"] is True


def test_tool_param_defaults():
    from mcp.models import ToolParam
    p = ToolParam(name="x")
    assert p.type == "string"
    assert p.required is False
    assert p.enum is None
    assert p.default is None
