"""gui/panels/log_panel.py — Real-time colour-coded log panel, subscribed to EventBus.

Log lines are also written to disk via LogWriter:
  ~/blender_pipeline_output/logs/<YYYYMMDD_HHMMSS>.log
A 📂 button in the header opens the log folder in the system file manager.
"""
import os
import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QTextEdit, QPushButton, QLabel)
from PyQt6.QtGui import QTextCursor
from realtime.qt_bridge import QtBridge
from utils.log_writer import LogWriter


class LogPanel(QWidget):
    MAX_LINES = 1000

    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._lines      = 0
        self._relays     = []   # keep QtBridge relay refs alive
        self._log_writer = LogWriter()
        self._build()
        if bus:
            def _sub(event, fn):
                self._relays.append(QtBridge.subscribe(bus, event, fn))

            _sub("pipeline.start",
                 lambda d: self.info(f"Pipeline: {d.get('prompt','')[:70]}"))
            _sub("pipeline.plan",
                 lambda d: self.info(f"Plan ready — {d.get('total',0)} steps"))
            _sub("pipeline.step.start",
                 lambda d: self.info(
                     f"  [{d.get('index',0)+1}/{d.get('total',1)}] "
                     f"{d.get('description','')[:60]}"))
            _sub("pipeline.step.done",  self._on_step_done)
            _sub("pipeline.done",
                 lambda d: self.success(
                     f"Pipeline complete — {d.get('total_steps',0)} steps "
                     f"in {d.get('elapsed_s',0):.1f}s"))
            _sub("pipeline.aborted",
                 lambda d: self.warning(
                     f"Pipeline aborted: {d.get('reason','')[:80]}"))
            _sub("mcp.error",
                 lambda d: self.error(f"MCP: {d.get('error','')[:100]}"))
            _sub("scene.updated",       lambda _: self.debug("Scene updated"))
            _sub("connection.ok",
                 lambda d: self.success(
                     f"Connected: {d.get('host')}:{d.get('port')}"))
            _sub("connection.fail",
                 lambda d: self.error(
                     f"Connection failed: {d.get('host')}:{d.get('port')}"))
            _sub("connection.error",
                 lambda d: self.error(
                     f"Connection error: {d.get('error','')}"))

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr = QHBoxLayout()
        lbl = QLabel("Log")
        lbl.setStyleSheet("font-weight: bold; color: #aaa; padding: 4px 8px;")

        open_btn = QPushButton("📂")
        open_btn.setFixedWidth(32)
        open_btn.setToolTip("Open log folder")
        open_btn.clicked.connect(self._open_log_folder)

        clr = QPushButton("Clear")
        clr.setFixedWidth(60)
        clr.clicked.connect(self._clear)

        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(open_btn)
        hdr.addWidget(clr)
        layout.addLayout(hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._log)

    def _open_log_folder(self):
        log_dir = self._log_writer.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(log_dir))          # Windows
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", str(log_dir)])  # Linux / macOS

    def _clear(self):
        self._log.clear()
        self._lines = 0

    def _append(self, text: str, color: str = "#e0e0e0"):
        ts = time.strftime("%H:%M:%S")
        plain = f"[{ts}] {text}"
        self._log.append(
            f'<span style="color:#555">[{ts}]</span> '
            f'<span style="color:{color}">{text}</span>'
        )
        self._log.moveCursor(QTextCursor.MoveOperation.End)
        self._lines += 1
        if self._lines > self.MAX_LINES:
            cursor = self._log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down,
                                QTextCursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()
            self._lines -= 100
        # Persist to disk (non-blocking — file write is fast)
        try:
            self._log_writer.write(plain)
        except Exception:
            pass  # never let log I/O crash the GUI

    def _on_step_done(self, d):
        if d.get("success"):
            self.success(f"  OK   {d.get('description','')[:60]}")
        else:
            self.error(
                f"  FAIL {d.get('description','')[:60]}: "
                f"{d.get('error','')[:60]}")

    def info(self,    msg): self._append(msg, "#e0e0e0")
    def success(self, msg): self._append(msg, "#4caf50")
    def warning(self, msg): self._append(msg, "#ff9800")
    def error(self,   msg): self._append(msg, "#f44336")
    def debug(self,   msg): self._append(msg, "#607d8b")
