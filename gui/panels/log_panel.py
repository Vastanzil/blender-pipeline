"""gui/panels/log_panel.py — Real-time colour-coded log panel, subscribed to EventBus."""
import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QTextEdit, QPushButton, QLabel)
from PyQt6.QtGui import QTextCursor


class LogPanel(QWidget):
    MAX_LINES = 1000

    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._lines = 0
        self._build()
        if bus:
            bus.subscribe("pipeline.start",      lambda d: self.info(f"Pipeline: {d.get('prompt','')[:70]}"))
            bus.subscribe("pipeline.plan",        lambda d: self.info(f"Plan ready — {d.get('total',0)} steps"))
            bus.subscribe("pipeline.step.start",  lambda d: self.info(
                f"  [{d.get('index',0)+1}/{d.get('total',1)}] {d.get('description','')[:60]}"))
            bus.subscribe("pipeline.step.done",   self._on_step_done)
            bus.subscribe("pipeline.done",        lambda d: self.success(
                f"Pipeline complete — {d.get('total_steps',0)} steps in {d.get('elapsed_s',0):.1f}s"))
            bus.subscribe("pipeline.aborted",     lambda d: self.warning("Pipeline aborted"))
            bus.subscribe("mcp.error",            lambda d: self.error(f"MCP: {d.get('error','')[:100]}"))
            bus.subscribe("scene.updated",        lambda _: self.debug("Scene updated"))
            bus.subscribe("connection.ok",        lambda d: self.success(
                f"Connected: {d.get('host')}:{d.get('port')}"))
            bus.subscribe("connection.fail",      lambda d: self.error(
                f"Connection failed: {d.get('host')}:{d.get('port')}"))
            bus.subscribe("connection.error",     lambda d: self.error(
                f"Connection error: {d.get('error','')}"))

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr = QHBoxLayout()
        lbl = QLabel("Log")
        lbl.setStyleSheet("font-weight: bold; color: #aaa; padding: 4px 8px;")
        clr = QPushButton("Clear")
        clr.setFixedWidth(60)
        clr.clicked.connect(self._clear)
        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(clr)
        layout.addLayout(hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._log)

    def _clear(self):
        self._log.clear()
        self._lines = 0

    def _append(self, text, color="#e0e0e0"):
        ts = time.strftime("%H:%M:%S")
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

    def _on_step_done(self, d):
        if d.get("success"):
            self.success(f"  OK   {d.get('description','')[:60]}")
        else:
            self.error(f"  FAIL {d.get('description','')[:60]}: {d.get('error','')[:60]}")

    def info(self,    msg): self._append(msg, "#e0e0e0")
    def success(self, msg): self._append(msg, "#4caf50")
    def warning(self, msg): self._append(msg, "#ff9800")
    def error(self,   msg): self._append(msg, "#f44336")
    def debug(self,   msg): self._append(msg, "#607d8b")
