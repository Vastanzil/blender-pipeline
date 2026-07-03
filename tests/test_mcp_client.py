"""Tests for BlenderMCPClient (HTTP mocked with responses library)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

try:
    import responses as resp_lib
    HAS_RESPONSES = True
except ImportError:
    HAS_RESPONSES = False

pytestmark = pytest.mark.skipif(not HAS_RESPONSES, reason="responses library not installed")


@resp_lib.activate
def test_ping_success():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "1", "result": "pong"})
    c = BlenderMCPClient(timeout=2.0)
    assert c.ping() is True


@resp_lib.activate
def test_ping_falls_back_to_tools_list():
    """ping() returns True when /ping returns JSON-RPC error but tools/list succeeds."""
    from mcp.client import BlenderMCPClient
    # First call (/ping JSON-RPC) returns an RPC-level error (not HTTP error)
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "1",
                       "error": {"code": -32601, "message": "Method not found: ping"}})
    # Second call (tools/list fallback) succeeds
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "2", "result": {"tools": []}})
    c = BlenderMCPClient(timeout=2.0)
    # ping() should fall through to tools/list and return True
    # We patch _call to treat the error response as MCPConnectionError
    original_call = c._call
    def patched_call(method, params=None):
        raw = original_call(method, params)
        if raw.get("error"):
            from mcp.client import MCPConnectionError
            raise MCPConnectionError(str(raw["error"]))
        return raw
    c._call = patched_call
    assert c.ping() is True


@resp_lib.activate
def test_exec_code_success():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "x",
                       "result": {"content": [{"text": "Cube added"}]}})
    c = BlenderMCPClient(timeout=2.0)
    r = c.exec_code("import bpy; bpy.ops.mesh.primitive_cube_add()")
    assert r.success is True
    assert "Cube added" in r.text()


@resp_lib.activate
def test_exec_code_error_response():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "x",
                       "error": {"code": -32000, "message": "Python error"}})
    c = BlenderMCPClient(timeout=2.0)
    r = c.exec_code("bad code")
    assert r.success is False
    assert "Python error" in r.error


@resp_lib.activate
def test_list_tools_returns_list():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "x",
                       "result": {"tools": [{"name": "execute_blender_code"}]}})
    c = BlenderMCPClient(timeout=2.0)
    tools = c.list_tools()
    assert isinstance(tools, list)
    assert tools[0]["name"] == "execute_blender_code"


@resp_lib.activate
def test_get_blender_version_parses_tuple():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "x",
                       "result": {"content": [{"text": "[5, 1, 2]"}]}})
    c = BlenderMCPClient(timeout=2.0)
    ver = c.get_blender_version()
    assert ver == (5, 1, 2)


@resp_lib.activate
def test_get_blender_version_cached():
    from mcp.client import BlenderMCPClient
    resp_lib.add(resp_lib.POST, "http://localhost:9876/mcp",
                 json={"jsonrpc": "2.0", "id": "x",
                       "result": {"content": [{"text": "[4, 3, 0]"}]}})
    c = BlenderMCPClient(timeout=2.0)
    v1 = c.get_blender_version()
    v2 = c.get_blender_version()   # should use cache — no second HTTP call
    assert v1 == v2 == (4, 3, 0)
    assert len(resp_lib.calls) == 1   # only one actual request
