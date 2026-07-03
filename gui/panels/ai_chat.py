"""
gui/panels/ai_chat.py
AI Pipeline panel: natural-language prompt → orchestrator → live step progress.

Features:
  - Run / Stop pipeline
  - Live backend selector (populated from AIRouter.available_backends())
  - Per-step progress list with pass/fail markers
  - Step detail view — click a step to see generated code + error
  - Abort reason displayed with red label and helpful hint
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                              QPushButton, QLabel, QComboBox, QProgressBar,
                              QGroupBox, QListWidget, QListWidgetItem, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.async_runner import AsyncWorker
from config.registry import get, set as reg_set
from realtime.qt_bridge import QtBridge


class AIChatPanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._orchestrator = None
        self._ai     = None
        self._worker = None
        self._relays = []       # keep QtBridge relays alive (GC protection)
        self._last_steps: list = []   # [{index, description, code, error, attempts, success}]
        self._build()
        if bus:
            def _sub(event, fn):
                self._relays.append(QtBridge.subscribe(bus, event, fn))

            _sub("pipeline.step.start", self._on_step_start)
            _sub("pipeline.step.done",  self._on_step_done)
            _sub("pipeline.done",       self._on_pipeline_done)
            _sub("pipeline.aborted",    self._on_pipeline_aborted)

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
        # Placeholder list — replaced by _refresh_backends() after connect
        self._backend_combo.addItems(["ollama", "openai", "anthropic", "gemini", "manifest"])
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
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._progress)
        layout.addWidget(self._status_lbl)

        # ── Steps list + detail view ──────────────────────────────────
        sg = QGroupBox("Pipeline Steps")
        sgl = QVBoxLayout(sg)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._steps = QListWidget()
        self._steps.setMinimumHeight(80)
        self._steps.currentRowChanged.connect(self._show_step_detail)
        splitter.addWidget(self._steps)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(150)
        self._detail.setVisible(False)
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._detail.setFont(mono)
        self._detail.setPlaceholderText("Click a step to see generated code and error details.")
        splitter.addWidget(self._detail)

        sgl.addWidget(splitter)
        layout.addWidget(sg)

    # ------------------------------------------------------------------
    # Backend switching
    # ------------------------------------------------------------------

    def _switch_backend(self, idx):
        if self._ai and idx >= 0:
            backend = self._backend_combo.itemData(idx)
            if backend:
                try:
                    self._ai.switch(backend)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def _run(self):
        if not self._orchestrator:
            self._status_lbl.setText("Not connected to Blender.")
            self._status_lbl.setStyleSheet("color:#f44336;")
            return
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status_lbl.setText("Enter a prompt first.")
            return
        reg_set("last_prompt", prompt)
        self._steps.clear()
        self._last_steps.clear()
        self._detail.setVisible(False)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_lbl.setText("Planning…")
        self._status_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        orch = self._orchestrator

        self._worker = AsyncWorker(lambda: orch.run(prompt))
        self._worker.result_ready.connect(
            lambda steps: self._on_pipeline_done({"total_steps": len(steps)}))
        self._worker.error_raised.connect(
            lambda e: self._on_pipeline_aborted({"reason": e, "phase": "worker"}))
        self._worker.start()

    def _stop(self):
        if self._orchestrator:
            self._orchestrator.abort()
        if self._worker:
            self._worker.quit()
        self._status_lbl.setText("Stopped.")
        self._status_lbl.setStyleSheet("color:#aaa;")
        self._reset_buttons()

    def _reset_buttons(self):
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_step_start(self, d):
        idx   = d.get("index", 0)
        total = d.get("total", 1)
        desc  = d.get("description", "")
        self._progress.setMaximum(total)
        self._progress.setValue(idx)
        self._status_lbl.setText(f"Step {idx+1}/{total}: {desc[:70]}")
        self._status_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        self._steps.addItem(QListWidgetItem(f"… {idx+1}. {desc[:60]}"))
        self._steps.scrollToBottom()

    def _on_step_done(self, d):
        ok       = d.get("success", False)
        idx      = d.get("index", 0)
        desc     = d.get("description", "")
        attempts = d.get("attempts", 1)
        code     = d.get("code", "")
        error    = d.get("error", "")

        # Store for detail view
        self._last_steps.append({
            "index": idx, "description": desc,
            "code": code, "error": error,
            "attempts": attempts, "success": ok,
        })

        n = self._steps.count()
        if n > 0:
            icon = "✓" if ok else "✗"
            retry_note = f"  ({attempts} attempts)" if attempts > 1 else ""
            self._steps.item(n - 1).setText(
                f"[{icon}] {idx+1}. {desc[:55]}{retry_note}")

    def _on_pipeline_done(self, d):
        n = d.get("total_steps", 0)
        self._status_lbl.setText(f"Done — {n} steps completed.")
        self._status_lbl.setStyleSheet("color:#4caf50; font-size:11px;")
        self._progress.setVisible(False)
        self._reset_buttons()

    def _on_pipeline_aborted(self, d):
        reason = d.get("reason", "unknown error")
        phase  = d.get("phase", "")

        # Friendly hints for common errors
        hint = ""
        reason_lower = reason.lower()
        if "11434" in reason or "ollama" in reason_lower:
            hint = ("\n→ Ollama is not running. Start it, or switch AI Backend "
                    "to 'manifest' in File › Connect / Setup")
        elif "invalid leading whitespace" in reason_lower or "reserved character" in reason_lower:
            hint = ("\n→ Your API token has bad characters. Re-paste it in "
                    "File › Connect / Setup (avoid trailing spaces/newlines)")
        elif any(w in reason_lower for w in
                 ("connection", "refused", "model", "404", "not found", "unreachable")):
            hint = "\n→ Check AI Backend in File › Connect / Setup"

        phase_str = f" ({phase})" if phase else ""
        self._status_lbl.setText(f"Aborted{phase_str}: {reason[:120]}{hint}")
        self._status_lbl.setStyleSheet("color:#f44336; font-size:11px;")
        self._progress.setVisible(False)
        self._reset_buttons()

    # ------------------------------------------------------------------
    # Step detail view
    # ------------------------------------------------------------------

    def _show_step_detail(self, row: int):
        if row < 0 or row >= len(self._last_steps):
            self._detail.setVisible(False)
            return
        s = self._last_steps[row]
        lines = [
            f"Step {s['index']+1} — {s['attempts']} attempt(s) — "
            f"{'OK' if s['success'] else 'FAILED'}",
            "─" * 50,
        ]
        if s["code"]:
            lines += ["", "Generated code:", s["code"]]
        if s["error"]:
            lines += ["", "Error:", s["error"]]
        self._detail.setPlainText("\n".join(lines))
        self._detail.setVisible(True)
