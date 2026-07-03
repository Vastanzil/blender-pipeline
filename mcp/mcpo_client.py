"""
mcp/mcpo_client.py
==================
REST client for mcpo (MCP-to-OpenAPI proxy) running on port 8000.

mcpo wraps a blender-mcp MCP server and exposes every tool as a
plain HTTP POST endpoint:

    GET  http://localhost:8000/openapi.json    → OpenAPI spec + tool list
    POST http://localhost:8000/{tool_name}     → call a tool, JSON body = args
    GET  http://localhost:8000/health          → optional health probe

This client implements the same public interface as BlenderMCPClient so
the rest of the application is unaware of which backend is in use.
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ToolResult

__all__ = ["MCPOClient", "MCPOConnectionError"]


class MCPOConnectionError(Exception):
    pass


class MCPOClient:
    """Talk to a running mcpo instance (MCP → OpenAPI bridge)."""

    def __init__(self, host: str = "localhost", port: int = 8000,
                 timeout: float = 30.0):
        self._host    = host
        self._port    = port
        self.base_url = f"http://{host}:{port}"
        self.timeout  = timeout
        self._session = self._make_session()
        self._version_cache: tuple | None = None
        self._spec_cache: dict | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_session() -> requests.Session:
        s = requests.Session()
        retry = Retry(
            total=2, backoff_factor=0.2,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods={"GET", "POST"},
        )
        s.mount("http://", HTTPAdapter(max_retries=retry,
                                       pool_connections=4, pool_maxsize=8))
        s.headers["Content-Type"] = "application/json"
        return s

    def _get(self, path: str) -> Any:
        try:
            r = self._session.get(f"{self.base_url}/{path.lstrip('/')}",
                                  timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as e:
            raise MCPOConnectionError(
                f"Cannot reach mcpo at {self.base_url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise MCPOConnectionError(f"Timeout ({self.timeout}s): {e}") from e
        except requests.exceptions.HTTPError as e:
            raise MCPOConnectionError(f"HTTP {e.response.status_code}: {e}") from e

    def _post(self, tool_name: str, body: dict) -> Any:
        url = f"{self.base_url}/{tool_name}"
        try:
            r = self._session.post(url, json=body, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as e:
            raise MCPOConnectionError(
                f"Cannot reach mcpo at {self.base_url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise MCPOConnectionError(f"Timeout ({self.timeout}s): {e}") from e
        except requests.exceptions.HTTPError as e:
            # mcpo returns 422 for validation errors — propagate body
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:200]
            raise MCPOConnectionError(
                f"HTTP {e.response.status_code}: {detail}") from e

    # ------------------------------------------------------------------
    # OpenAPI spec
    # ------------------------------------------------------------------

    def _get_spec(self) -> dict:
        if self._spec_cache is None:
            self._spec_cache = self._get("/openapi.json")
        return self._spec_cache

    def _invalidate_spec(self):
        self._spec_cache = None

    # ------------------------------------------------------------------
    # Public interface (matches BlenderMCPClient exactly)
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        try:
            spec = self._get("/openapi.json")
            return isinstance(spec, dict) and "paths" in spec
        except MCPOConnectionError:
            return False
        except Exception:
            return False

    def list_tools(self) -> list[dict]:
        """Return tool dicts with 'name', 'description', 'inputSchema'."""
        try:
            spec = self._get_spec()
        except MCPOConnectionError:
            return []

        tools = []
        paths = spec.get("paths", {})
        schemas = (spec.get("components", {})
                       .get("schemas", {}))

        for path, methods in paths.items():
            post = methods.get("post")
            if not post:
                continue
            name = path.lstrip("/")
            if not name:
                continue
            desc = (post.get("summary") or post.get("description") or "")

            # Extract input schema from requestBody → resolve $ref if needed
            body = (post.get("requestBody", {})
                        .get("content", {})
                        .get("application/json", {})
                        .get("schema", {}))
            body = self._resolve_ref(body, schemas)

            tools.append({
                "name":        name,
                "description": desc,
                "inputSchema": body,
            })
        return tools

    def _resolve_ref(self, schema: dict, defs: dict) -> dict:
        """Resolve a single-level $ref from components/schemas."""
        ref = schema.get("$ref", "")
        if ref:
            # "#/components/schemas/Foo" → "Foo"
            key = ref.split("/")[-1]
            return defs.get(key, schema)
        return schema

    def call_tool(self, name: str, arguments: dict | None = None) -> ToolResult:
        t0   = time.perf_counter()
        body = arguments or {}
        try:
            raw = self._post(name, body)
        except MCPOConnectionError as e:
            dt = (time.perf_counter() - t0) * 1000
            return ToolResult(tool_name=name, success=False,
                              error=str(e), raw={}, duration_ms=dt)

        dt = (time.perf_counter() - t0) * 1000

        # mcpo wraps MCP responses as-is or may return the result directly
        output   = self._extract_output(raw)
        err_text = self._extract_error(raw)
        return ToolResult(tool_name=name,
                          success=not bool(err_text),
                          output=output,
                          error=err_text,
                          raw=raw,
                          duration_ms=dt)

    @staticmethod
    def _extract_output(raw) -> str:
        if isinstance(raw, dict):
            # MCP content list format
            content = raw.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                return first.get("text", "") if isinstance(first, dict) else str(first)
            # Direct result formats
            for key in ("result", "output", "text"):
                if key in raw:
                    val = raw[key]
                    return str(val) if not isinstance(val, str) else val
            return str(raw)
        return str(raw) if raw is not None else ""

    @staticmethod
    def _extract_error(raw) -> str:
        if isinstance(raw, dict):
            for key in ("error", "stderr", "detail"):
                val = raw.get(key)
                if val:
                    if isinstance(val, dict):
                        return val.get("message", str(val))
                    return str(val)
        return ""

    # ------------------------------------------------------------------
    # Convenience wrappers (same as BlenderMCPClient)
    # ------------------------------------------------------------------

    def exec_code(self, code: str) -> ToolResult:
        return self.call_tool("execute_blender_code", {"code": code})

    def get_scene_info(self) -> ToolResult:
        return self.call_tool("get_scene_info", {})

    def get_object_info(self, object_name: str) -> ToolResult:
        return self.call_tool("get_object_info", {"object_name": object_name})

    def create_object(self, object_type: str = "MESH",
                      name: str = "", location=(0, 0, 0)) -> ToolResult:
        args: dict = {"type": object_type, "location": list(location)}
        if name:
            args["name"] = name
        return self.call_tool("create_object", args)

    def set_material(self, object_name: str, material_name: str,
                     color=None) -> ToolResult:
        args: dict = {"object_name": object_name, "material_name": material_name}
        if color:
            args["color"] = list(color)
        return self.call_tool("set_material", args)

    def export_scene(self, filepath: str, fmt: str = "GLB") -> ToolResult:
        return self.call_tool("export_scene",
                              {"filepath": filepath, "export_format": fmt})

    def render_scene(self, output_path: str = "") -> ToolResult:
        args: dict = {}
        if output_path:
            args["output_path"] = output_path
        return self.call_tool("render_scene", args)

    def get_blender_version(self) -> tuple:
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

    def __repr__(self) -> str:
        return f"MCPOClient({self._host}:{self._port})"
