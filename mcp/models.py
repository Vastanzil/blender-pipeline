"""
mcp/models.py — Pure dataclasses, no external dependencies.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolParam:
    name:        str
    type:        str            = "string"
    description: str            = ""
    required:    bool           = False
    enum:        Optional[list] = None
    default:     Any            = None


@dataclass
class Tool:
    name:        str
    description: str             = ""
    params:      list            = field(default_factory=list)

    def required_params(self) -> list:
        return [p for p in self.params if p.required]

    def optional_params(self) -> list:
        return [p for p in self.params if not p.required]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "params": [
                {"name": p.name, "type": p.type,
                 "required": p.required, "description": p.description}
                for p in self.params
            ],
        }


@dataclass
class ToolResult:
    tool_name:   str
    success:     bool
    output:      Any   = None
    error:       str   = ""
    raw:         dict  = field(default_factory=dict)
    duration_ms: float = 0.0

    def text(self) -> str:
        if self.success:
            if isinstance(self.output, str):
                return self.output
            return json.dumps(self.output, indent=2, default=str)
        return f"ERROR: {self.error}"
