"""pipeline/step.py — PipelineStep dataclass."""
from dataclasses import dataclass, field


@dataclass
class PipelineStep:
    index:            int
    description:      str
    code:             str   = ""
    success:          bool  = False
    error:            str   = ""
    output:           str   = ""
    attempts:         int   = 0
    category:         str   = "geometry"
    # v3.1 additions
    poly_tris_target: int   = 0
    spatial_pos:      tuple = ()
    bpy_object_name:  str   = ""
    screenshot_paths: list  = field(default_factory=list)
    visual_context:   str   = ""   # textual description for BlenderLLM (no image input)

    def summary(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"[{status}] {self.index + 1}. {self.description[:60]}"
