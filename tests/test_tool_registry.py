"""Tests for ToolRegistry — uses a mock MCP client."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class MockClient:
    def list_tools(self):
        return [
            {
                "name": "execute_blender_code",
                "description": "Execute bpy Python code",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code"}
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "get_scene_info",
                "description": "Return scene hierarchy",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "create_object",
                "description": "Create a mesh object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type":     {"type": "string", "enum": ["MESH", "CURVE", "EMPTY"]},
                        "name":     {"type": "string"},
                        "location": {"type": "array"},
                    },
                    "required": ["type"],
                },
            },
        ]


def test_registry_discovers_all_tools():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    assert reg.count() == 3


def test_registry_names():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    names = reg.names()
    assert "execute_blender_code" in names
    assert "get_scene_info" in names
    assert "create_object" in names


def test_registry_parses_required_param():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    tool = reg.get("execute_blender_code")
    assert tool is not None
    assert len(tool.params) == 1
    assert tool.params[0].name == "code"
    assert tool.params[0].required is True
    assert tool.params[0].type == "string"


def test_registry_parses_enum():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    tool = reg.get("create_object")
    type_param = next(p for p in tool.params if p.name == "type")
    assert type_param.enum == ["MESH", "CURVE", "EMPTY"]


def test_registry_optional_param():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    tool = reg.get("create_object")
    name_param = next(p for p in tool.params if p.name == "name")
    assert name_param.required is False


def test_registry_search():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    results = reg.search("scene")
    assert len(results) == 1
    assert results[0].name == "get_scene_info"


def test_registry_search_case_insensitive():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    results = reg.search("BLENDER")
    assert any(t.name == "execute_blender_code" for t in results)


def test_registry_get_nonexistent_returns_none():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    assert reg.get("no_such_tool") is None


def test_registry_all_returns_list():
    from mcp.tool_registry import ToolRegistry
    reg = ToolRegistry(MockClient()).refresh()
    all_tools = reg.all()
    assert isinstance(all_tools, list)
    assert len(all_tools) == 3


def test_registry_empty_client():
    from mcp.tool_registry import ToolRegistry
    class EmptyClient:
        def list_tools(self): return []
    reg = ToolRegistry(EmptyClient()).refresh()
    assert reg.count() == 0
    assert reg.all() == []
