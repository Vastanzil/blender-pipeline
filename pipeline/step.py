"""pipeline/step.py — PipelineStep dataclass."""
from dataclasses import dataclass, field


@dataclass
class PipelineStep:
    index:       int
    description: str
    code:        str   = ""
    success:     bool  = False
    error:       str   = ""
    output:      str   = ""
    attempts:    int   = 0
    category:    str   = "geometry"

    def summary(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"[{status}] {self.index + 1}. {self.description[:60]}"
