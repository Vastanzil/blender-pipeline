"""
gui/panels/ai_chat.py
AI Pipeline panel: natural-language prompt → orchestrator → live step progress.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                              QPushButton, QLabel, QComboBox, QProgressBar,
                              QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt
from utils.async_runner import AsyncWorker
from config.registry import get, set as reg_set
from realtime.qt_bridge import QtBridge


class AIChatPanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._orchestrator = None
        self._ai     = None
        self._worker = None
        self._relays = []   # keep refs so relays aren't GC'd
        self._build()
        if bus:
            def _sub(event, fn):
                self._relays.append(QtBridge.subscribe(bus, event, fn))

            _sub("pipeline.step.start", self._on_step_start)
            _sub("pipeline.step.done",  self._on_step_done)
            _sub("pipeline.done",       self._on_pipeline_done)
            _sub("pipeline.aborted",    lambda _: self._reset_buttons())

    def set_orchestrator(self, orchestrator, ai_router):
        self._orchestrator = orchestrator
        self._ai = ai_router
        self._refresh_backends()

    def _refresh_backends(self):
        if not self._ai:
            return
        self._backend_combo.clear()
        for name, ok in self._ai.available_backends().items():
            suffix = " ✓" if ok else ""
            self._backend_combo.addItem(name + suffix, name)
        for i in range(self._backend_combo.count()):
            if self._backend_combo.itemData(i) == self._ai.active_name:
                self._backend_combo.setCurrentIndex(i)
                break

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("AI Pipeline")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #3a7bd5;")
        layout.addWidget(title)

        hint = QLabel(
            "Describe what you want Blender to create or do. "
            "The AI plans every step and executes them automatically."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        pg = QGroupBox("Prompt")
        pgl = QVBoxLayout(pg)
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Examples:\n"
            "  Create a low-poly pine forest with 30 trees and HDRI lighting\n"
            "  Add cloth simulation to the selected plane\n"
            "  Build city blocks with procedural geometry nodes\n"
            "  Animate a bouncing ball with squash and stretch (frames 1-120)"
        )
        self._prompt.setMinimumHeight(90)
        self._prompt.setMaximumHeight(150)
        self._prompt.setText(get("last_prompt", ""))
        pgl.addWidget(self._prompt)
        layout.addWidget(pg)

        ai_row = QHBoxLayout()
        ai_row.addWidget(QLabel("AI Backend:"))
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["ollama", "openai", "anthropic", "gemini"])
        self._backend_combo.currentIndexChanged.connect(self._switch_backend)
        ai_row.addWidget(self._backend_combo)
        ai_row.addStretch()
        layout.addLayout(ai_row)

        btn_row = QHBoxLayout()
        self._run_btn  = QPushButton("Run Pipeline")
        self._stop_btn = QPushButton("Stop")
        self._run_btn.setObjectName("success")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._run)
        self._stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._progress)
        layout.addWidget(self._status_lbl)

        sg = QGroupBox("Pipeline Steps")
        sgl = QVBoxLayout(sg)
        self._steps = QListWidget()
        self._steps.setMinimumHeight(80)
        sgl.addWidget(self._steps)
        layout.addWidget(sg)

    def _switch_backend(self, idx):
        if self._ai and idx >= 0:
            backend = self._backend_combo.itemData(idx)
            if backend:
                try:
                    self._ai.switch(backend)
                except Exception:
                    pass

    def _run(self):
        if not self._orchestrator:
            self._status_lbl.setText("Not connected to Blender.")
            return
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status_lbl.setText("Enter a prompt first.")
            return
        reg_set("last_prompt", prompt)
        self._steps.clear()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_lbl.setText("Planning...")
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        orch = self._orchestrator

        def execute():
            return orch.run(prompt)

        self._worker = AsyncWorker(execute)
        self._worker.result_ready.connect(
            lambda steps: self._on_pipeline_done({"total_steps": len(steps)}))
        self._worker.error_raised.connect(
            lambda e: (self._status_lbl.setText(f"Error: {e[:80]}"),
                       self._reset_buttons()))
        self._worker.start()

    def _stop(self):
        if self._orchestrator:
            self._orchestrator.abort()
        if self._worker:
            self._worker.quit()
        self._status_lbl.setText("Stopped.")
        self._reset_buttons()

    def _reset_buttons(self):
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_step_start(self, d):
        idx   = d.get("index", 0)
        total = d.get("total", 1)
        desc  = d.get("description", "")
        self._progress.setMaximum(total)
        self._progress.setValue(idx)
        self._status_lbl.setText(f"Step {idx+1}/{total}: {desc[:70]}")
        self._steps.addItem(QListWidgetItem(f"... {idx+1}. {desc[:60]}"))
        self._steps.scrollToBottom()

    def _on_step_done(self, d):
        ok   = d.get("success", False)
        idx  = d.get("index", 0)
        desc = d.get("description", "")
        n = self._steps.count()
        if n > 0:
            icon = "OK" if ok else "FAIL"
            self._steps.item(n - 1).setText(f"[{icon}] {idx+1}. {desc[:60]}")

    def _on_pipeline_done(self, d):
        n = d.get("total_steps", 0)
        self._status_lbl.setText(f"Done — {n} steps completed.")
        self._progress.setVisible(False)
        self._reset_buttons()
