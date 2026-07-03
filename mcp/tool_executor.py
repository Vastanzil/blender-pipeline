"""
mcp/tool_executor.py
Type-coerces param values from form input, then calls client.call_tool().
"""
from .models import Tool, ToolResult


class ToolExecutor:
    def __init__(self, client):
        self._client = client

    def execute(self, tool: Tool, values: dict) -> ToolResult:
        coerced = {}
        for param in tool.params:
            val = values.get(param.name)
            if val is None or val == "":
                if param.required:
                    return ToolResult(tool_name=tool.name, success=False,
                                      error=f"Missing required param: {param.name}")
                continue
            coerced[param.name] = self._coerce(val, param.type)
        return self._client.call_tool(tool.name, coerced)

    @staticmethod
    def _coerce(val, typ: str):
        try:
            if typ == "integer":
                return int(val)
            if typ == "number":
                return float(val)
            if typ == "boolean":
                if isinstance(val, bool):
                    return val
                return str(val).lower() in ("true", "1", "yes")
            if typ in ("object", "array"):
                import json
                if isinstance(val, str):
                    return json.loads(val)
                return val
        except (ValueError, TypeError, Exception):
            pass
        return val
