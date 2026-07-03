"""
pipeline/checkpoint.py
Saves pipeline state to JSON after each step so runs can be inspected / resumed.
"""
import json
import time
from pathlib import Path

from config.registry import get


class Checkpoint:
    def __init__(self, run_id: str = ""):
        self._run_id = run_id or f"run_{int(time.time())}"
        out = get("output_dir", "") or str(Path.home() / "blender_pipeline_output")
        self._dir = Path(out) / "checkpoints"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{self._run_id}.json"

    def save(self, steps: list):
        data = {
            "run_id":    self._run_id,
            "timestamp": time.time(),
            "steps": [
                {
                    "index":       s.index,
                    "description": s.description,
                    "success":     s.success,
                    "attempts":    s.attempts,
                    "error":       s.error,
                    "output":      s.output[:500] if s.output else "",
                }
                for s in steps
            ],
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    @property
    def path(self) -> str:
        return str(self._path)
