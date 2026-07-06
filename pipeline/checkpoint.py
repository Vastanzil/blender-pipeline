"""
pipeline/checkpoint.py
Full resume-capable checkpoint manager.
Backward-compat: save(steps) still works unchanged.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from config.registry import get
from pipeline.stages import Stage

if TYPE_CHECKING:
    from pipeline.pipeline_logger import PipelineLogger


class _State:
    """Mutable checkpoint state kept in memory and persisted to JSON."""
    def __init__(self):
        self.project_name: str          = ""
        self.completed: dict[str, Any]  = {}   # stage.value → output
        self.stage_order: list[str]     = [s.value for s in Stage]
        self.steps: list[dict]          = []   # legacy step records

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "completed":    self.completed,
            "stage_order":  self.stage_order,
            "steps":        self.steps,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "_State":
        s = cls()
        s.project_name = d.get("project_name", "")
        s.completed    = d.get("completed", {})
        s.stage_order  = d.get("stage_order", [st.value for st in Stage])
        s.steps        = d.get("steps", [])
        return s


class Checkpoint:
    def __init__(self, run_id: str = ""):
        self._run_id = run_id or f"run_{int(time.time())}"
        out_base = get("output_dir", "") or str(Path.home() / "blender_pipeline_output")
        self._dir  = Path(out_base) / "checkpoints"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{self._run_id}.json"

        # Load existing state if resuming
        if self._path.exists():
            try:
                raw        = json.loads(self._path.read_text(encoding="utf-8"))
                self.state = _State.from_dict(raw)
            except Exception:
                self.state = _State()
        else:
            self.state = _State()

    # ------------------------------------------------------------------
    # Resume API

    def mark_complete(self, stage: Stage, output: Any = None):
        self.state.completed[stage.value] = output
        self._flush()

    def is_complete(self, stage: Stage) -> bool:
        return stage.value in self.state.completed

    def next_stage(self) -> Optional[Stage]:
        """Return the first Stage not yet marked complete, or None."""
        for s in Stage:
            if s.value not in self.state.completed:
                return s
        return None

    def set_project_name(self, name: str):
        self.state.project_name = name
        self._flush()

    def load_resume_context(self, logger: "PipelineLogger") -> dict:
        """Merge checkpoint state with the last logger context snapshot."""
        ctx = logger.get_resume_context()
        ctx.setdefault("project_name", self.state.project_name)
        ctx.setdefault("completed_stages", list(self.state.completed.keys()))
        return ctx

    # ------------------------------------------------------------------
    # Legacy save() — still works for orchestrator step history

    def save(self, steps: list):
        self.state.steps = [
            {
                "index":       s.index,
                "description": s.description,
                "success":     s.success,
                "attempts":    s.attempts,
                "error":       s.error,
                "output":      (s.output or "")[:500],
            }
            for s in steps
        ]
        self._flush()

    # ------------------------------------------------------------------

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def run_id(self) -> str:
        return self._run_id

    def exists_on_disk(self) -> bool:
        return self._path.exists()

    def _flush(self):
        data = {"run_id": self._run_id, "timestamp": time.time(),
                **self.state.to_dict()}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    # ------------------------------------------------------------------
    # Discovery

    @classmethod
    def list_runs(cls, output_dir: str = "") -> list[dict]:
        """Return recent checkpoint records newest-first.

        Each record: {run_id, project_name, timestamp, step_count, path}
        """
        base   = output_dir or get("output_dir", "") or str(Path.home() / "blender_pipeline_output")
        ck_dir = Path(base) / "checkpoints"
        if not ck_dir.exists():
            return []
        results = []
        for f in sorted(ck_dir.glob("*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "run_id":       data.get("run_id", f.stem),
                    "project_name": data.get("project_name", ""),
                    "timestamp":    data.get("timestamp", 0),
                    "step_count":   len(data.get("steps", [])),
                    "path":         str(f),
                })
            except Exception:
                continue
        return results[:50]   # cap at 50 entries
