"""
utils/log_writer.py
===================
Persists log lines to a timestamped file on disk.

File location: ~/blender_pipeline_output/logs/<YYYYMMDD_HHMMSS>.log
The file is created lazily on the first write call (no empty files on startup).
Thread-safe: uses a simple lock so DataBridge / pipeline threads can write safely.
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path


class LogWriter:
    """Append-only log file writer.

    Usage:
        writer = LogWriter()
        writer.write("[12:00:01] Connected")
        writer.write("[12:00:02] Pipeline: create a box")
        writer.close()   # optional — flushes automatically on each write
    """

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path.home() / "blender_pipeline_output" / "logs"
        self._dir  = Path(base_dir)
        self._path: Path | None = None
        self._fh   = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path | None:
        """Path to the current log file, or None if nothing has been written yet."""
        return self._path

    @property
    def log_dir(self) -> Path:
        return self._dir

    def write(self, line: str) -> None:
        """Append one log line (newline added automatically)."""
        with self._lock:
            if self._fh is None:
                self._dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                self._path = self._dir / f"{ts}.log"
                self._fh   = open(self._path, "a", encoding="utf-8")
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        """Close the file handle (safe to call multiple times)."""
        with self._lock:
            if self._fh:
                self._fh.close()
                self._fh = None
