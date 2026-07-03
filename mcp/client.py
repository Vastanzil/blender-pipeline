"""
mcp/client.py — HTTP JSON-RPC 2.0 client for blender-mcp.
Default port: 9876. Every call is POST /mcp JSON-RPC 2.0.
"""
import json
import re
import time
import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ToolResult


class MCPConnectionError(Exception):
    pass


class BlenderMCPClient:
    def __init__(self, host="localhost", port=9876, timeout=30.0):
        self.base_url = f"http://{host}:{port}"
        self.timeout  = timeout
        self._host    = host
        self._port    = port
        self._session = self._make_session()
        self._version_cache = None

    @staticmethod
    def _make_session():
        s = requests.Session()
        retry = Retry(
            total=3, backoff_factor=0.3,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods={"POST"},
        )
        s.mount("http://", HTTPAdapter(max_retries=retry,
                                       pool_connections=4, pool_maxsize=8))
        s.headers["Content-Type"] = "application/json"
        return s

    def _call(self, method, params=None):
        payload = {
            "jsonrpc": "2.0",
            "id":      str(uuid.uuid4()),
            "method":  method,
            "params":  params or {},
        }
        try:
            r = self._session.post(f"{self.base_url}/mcp",
                                   json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as e:
            raise MCPConnectionError(
                f"Cannot reach blender-mcp at {self.base_url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise MCPConnectionError(f"Timeout ({self.timeout}s): {e}") from e
        except requests.exceptions.HTTPError as e:
            raise MCPConnectionError(f"HTTP error: {e}") from e

    def call_tool(self, name, arguments=None):
        t0  = time.perf_counter()
        raw = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        dt  = (time.perf_counter() - t0) * 1000
        err = raw.get("error")
        if err:
            return ToolResult(tool_name=name, success=False,
                              error=str(err), raw=raw, duration_ms=dt)
        result   = raw.get("result", {})
        output   = self._extract_output(result)
        err_text = self._extract_error(result)
        return ToolResult(tool_name=name, success=not bool(err_text),
                          output=output, error=err_text, raw=raw, duration_ms=dt)

    @staticmethod
    def _extract_output(result):
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list) and content:
                return (content[0].get("text", "")
                        if isinstance(content[0], dict) else content[0])
            return result.get("output") or result.get("result") or result
        return result

    @staticmethod
    def _extract_error(result):
        if isinstance(result, dict):
            err = result.get("error") or result.get("stderr") or ""
            if isinstance(err, dict):
                return err.get("message", str(err))
            return str(err) if err else ""
        return ""

    def ping(self):
        try:
            self._call("ping")
            return True
        except MCPConnectionError:
            try:
                self._call("tools/list")
                return True
            except Exception:
                return False
        except Exception:
            return False

    def list_tools(self):
        raw   = self._call("tools/list")
        tools = raw.get("result", {})
        if isinstance(tools, dict):
            tools = tools.get("tools", [])
        return tools if isinstance(tools, list) else []

    def exec_code(self, code):
        return self.call_tool("execute_blender_code", {"code": code})

    def get_scene_info(self):
        return self.call_tool("get_scene_info")

    def get_object_info(self, object_name):
        return self.call_tool("get_object_info", {"object_name": object_name})

    def create_object(self, object_type="MESH", name="", location=(0, 0, 0)):
        args = {"type": object_type, "location": list(location)}
        if name:
            args["name"] = name
        return self.call_tool("create_object", args)

    def set_material(self, object_name, material_name, color=None):
        args = {"object_name": object_name, "material_name": material_name}
        if color:
            args["color"] = list(color)
        return self.call_tool("set_material", args)

    def export_scene(self, filepath, fmt="GLB"):
        return self.call_tool("export_scene",
                              {"filepath": filepath, "export_format": fmt})

    def render_scene(self, output_path=""):
        args = {}
        if output_path:
            args["output_path"] = output_path
        return self.call_tool("render_scene", args)

    def get_blender_version(self):
        if self._version_cache:
            return self._version_cache
        result = self.exec_code(
            "import bpy, json; print(json.dumps(list(bpy.app.version)))")
        try:
            text = str(result.output or "")
            m = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', text)
            if m:
                ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                self._version_cache = ver
                return ver
        except Exception:
            pass
        return (4, 0, 0)

    def __repr__(self):
        return f"BlenderMCPClient({self._host}:{self._port})"
