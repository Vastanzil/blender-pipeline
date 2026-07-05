"""
pipeline/pipeline_logger.py
JSONL session logger — one file per run.
Each record is a self-contained RAG/OKF training example with full context.
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional


class PipelineLogger:
    def __init__(
        self,
        log_dir: str | Path,
        session_id: str | None = None,
        context_snapshot_fn: Optional[Callable[[], dict]] = None,
    ):
        self.session_id          = session_id or uuid.uuid4().hex[:8]
        self._context_snapshot   = context_snapshot_fn or (lambda: {})
        self._seq                = 0
        self._last_context: dict = {}

        log_dir = Path(log_dir).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp     = time.strftime("%Y%m%d_%H%M%S")
        self._path = log_dir / f"session_{stamp}_{self.session_id}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------

    def log(self,
            stage: str,
            role: str,
            content: str,
            tokens: Optional[int] = None,
            meta: Optional[dict] = None) -> dict:
        """Append one record; return the dict for callers that want it."""
        ctx = self._context_snapshot()
        self._last_context = ctx
        record = {
            "seq":        self._seq,
            "ts":         time.time(),
            "session_id": self.session_id,
            "stage":      stage,
            "role":       role,
            "tokens":     tokens,
            "content":    content,
            "context":    ctx,
            "meta":       meta or {},
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._seq += 1
        return record

    def rename_artifact(self, src_path: str | Path,
                        stage: str, common_dir: str | Path) -> Path:
        """Move a generated file into common_dir with a session-stamped name."""
        src  = Path(src_path)
        dest = Path(common_dir).expanduser() / f"{self.session_id}_{stage}{src.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return dest

    def get_resume_context(self) -> dict:
        """Read own JSONL; return the most-recent full context snapshot."""
        if not self._path.exists():
            return {}
        last: dict = {}
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("context"):
                        last = rec["context"]
                except json.JSONDecodeError:
                    pass
        return last
