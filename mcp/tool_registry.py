"""
mcp/tool_registry.py
Calls tools/list on the MCP server, parses JSON schema → Tool objects.
"""
from .models import Tool, ToolParam


class ToolRegistry:
    def __init__(self, client):
        self._client = client
        self._tools:  dict = {}  # name → Tool

    def refresh(self) -> "ToolRegistry":
        raw_list = self._client.list_tools()
        self._tools = {}
        for raw in raw_list:
            tool = self._parse(raw)
            if tool:
                self._tools[tool.name] = tool
        return self

    @staticmethod
    def _parse(raw: dict):
        name = raw.get("name", "").strip()
        if not name:
            return None
        desc   = raw.get("description", "")
        schema = raw.get("inputSchema") or raw.get("input_schema") or {}
        props  = schema.get("properties") or {}
        req    = set(schema.get("required") or [])
        params = []
        for pname, pdef in props.items():
            params.append(ToolParam(
                name        = pname,
                type        = pdef.get("type", "string"),
                description = pdef.get("description", ""),
                required    = pname in req,
                enum        = pdef.get("enum"),
                default     = pdef.get("default"),
            ))
        return Tool(name=name, description=desc, params=params)

    def all(self) -> list:
        return list(self._tools.values())

    def get(self, name: str):
        return self._tools.get(name)

    def names(self) -> list:
        return list(self._tools.keys())

    def count(self) -> int:
        return len(self._tools)

    def search(self, query: str) -> list:
        q = query.lower()
        return [t for t in self._tools.values()
                if q in t.name.lower() or q in t.description.lower()]
