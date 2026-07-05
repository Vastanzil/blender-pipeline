"""
pipeline/validator.py
Layer A validation: liveness check + per-step object existence check.
"""
from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.step import PipelineStep


class Validator:
    PROBE = "print('VALIDATE_OK')"

    def __init__(self, client):
        self._client = client

    def is_alive(self) -> bool:
        try:
            result = self._client.exec_code(self.PROBE)
            return "VALIDATE_OK" in str(result.output or "")
        except Exception:
            return False

    def validate_step_result(self, step: "PipelineStep") -> tuple[bool, str]:
        """
        Check that the object a step claimed to create actually exists and is
        visible (non-zero dimensions).  Returns (passed, reason).
        """
        name = step.bpy_object_name
        if not name:
            # No object name recorded — fall back to liveness check only
            return self.is_alive(), "no_object_name"

        # 1. Existence check
        exists_code = (
            f"import bpy\n"
            f"_e = '{name}' in bpy.data.objects\n"
            f"print('EXISTS:' + str(_e))\n"
        )
        try:
            r = self._client.exec_code(exists_code)
            out = str(r.output or "")
            if "EXISTS:False" in out:
                return False, f"Object '{name}' was not found in bpy.data.objects"
        except Exception as exc:
            return False, f"Existence check raised: {exc}"

        # 2. Non-zero dimensions check
        dim_code = (
            f"import bpy\n"
            f"_o = bpy.data.objects.get('{name}')\n"
            f"if _o:\n"
            f"    _visible = max(_o.dimensions) > 0.001\n"
            f"    print('DIMS:' + str(_visible))\n"
            f"else:\n"
            f"    print('DIMS:False')\n"
        )
        try:
            r2 = self._client.exec_code(dim_code)
            out2 = str(r2.output or "")
            if "DIMS:False" in out2:
                return False, (
                    f"Object '{name}' exists but has zero dimensions — "
                    "check that you assigned obj.location and called "
                    "bpy.context.view_layer.update()"
                )
        except Exception as exc:
            return False, f"Dimension check raised: {exc}"

        return True, "ok"
