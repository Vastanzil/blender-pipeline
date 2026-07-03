"""
gui/panels/startup_dialog.py
============================
Startup self-test dialog.

Shown every time the application launches (before the main window).
Runs all environment checks in a background thread so the GUI stays
responsive, then optionally pings the live Blender MCP server.

Status:
  ✓  green   — check passed
  ✗  red     — check failed (blocks launch if critical)
  ⚠  orange  — check passed with warnings
  ●  grey    — pending

Once all checks pass the dialog shows "SYSTEM READY" and either
auto-closes (3 s) or the user clicks Continue.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QProgressBar, QFrame, QSizePolicy
)
from PyQt6.QtCore    import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui     import QFont, QColor

from utils.startup_check import (
    run_environment_checks, check_blender_connection,
    StartupReport, CheckResult,
)
from config.registry import get


# ── Worker thread ──────────────────────────────────────────────────────────────

class CheckWorker(QThread):
    check_done   = pyqtSignal(object)   # CheckResult
    all_done     = pyqtSignal(object)   # StartupReport
    blender_done = pyqtSignal(object)   # CheckResult

    def __init__(self, host: str, port: int, ping_blender: bool):
        super().__init__()
        self._host        = host
        self._port        = port
        self._ping_blender = ping_blender

    def run(self):
        from utils.startup_check import ENVIRONMENT_CHECKS
        report = StartupReport()
        for fn in ENVIRONMENT_CHECKS:
            r = fn()
            report.add(r)
            self.check_done.emit(r)

        self.all_done.emit(report)

        if self._ping_blender and self._host:
            r = check_blender_connection(self._host, self._port)
            self.blender_done.emit(r)


# ── Check row widget ───────────────────────────────────────────────────────────

class CheckRow(QFrame):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(10)

        self._icon = QLabel("●")
        self._icon.setFixedWidth(16)
        self._icon.setStyleSheet("color: #555; font-size: 14px;")

        self._name = QLabel(name)
        self._name.setFixedWidth(240)
        self._name.setStyleSheet("color: #aaa;")

        self._msg = QLabel("")
        self._msg.setStyleSheet("color: #666; font-size: 11px;")
        self._msg.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Preferred)

        self._time = QLabel("")
        self._time.setFixedWidth(50)
        self._time.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._time.setStyleSheet("color: #555; font-size: 10px;")

        layout.addWidget(self._icon)
        layout.addWidget(self._name)
        layout.addWidget(self._msg)
        layout.addWidget(self._time)

    def set_pending(self):
        self._icon.setText("●")
        self._icon.setStyleSheet("color: #555; font-size: 14px;")
        self._msg.setText("")
        self._time.setText("")

    def set_running(self):
        self._icon.setText("⟳")
        self._icon.setStyleSheet("color: #ff9800; font-size: 14px;")

    def set_result(self, r: CheckResult):
        if r.ok:
            has_warning = "warning" in r.message.lower() or "not installed" in r.message.lower()
            if has_warning:
                self._icon.setText("⚠")
                self._icon.setStyleSheet("color: #ff9800; font-size: 14px;")
                self._name.setStyleSheet("color: #ff9800;")
            else:
                self._icon.setText("✓")
                self._icon.setStyleSheet("color: #4caf50; font-size: 14px;")
                self._name.setStyleSheet("color: #e0e0e0;")
            self._msg.setStyleSheet("color: #888; font-size: 11px;")
        else:
            self._icon.setText("✗")
            self._icon.setStyleSheet("color: #f44336; font-size: 14px; font-weight: bold;")
            self._name.setStyleSheet("color: #f44336;")
            self._msg.setStyleSheet("color: #f44336; font-size: 11px;")

        self._msg.setText(r.message)
        ms = r.elapsed * 1000
        self._time.setText(f"{ms:.0f}ms")


# ── Main dialog ────────────────────────────────────────────────────────────────

class StartupCheckDialog(QDialog):
    """
    Startup self-test dialog.
    Emits `ready` when all checks pass and the user clicks Continue
    (or the auto-close timer fires).
    """
    ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Blender Pipeline Studio — System Check")
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)
        self.setModal(True)
        # Prevent closing with X before checks complete
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )

        self._rows:   dict[str, CheckRow] = {}
        self._worker: CheckWorker | None  = None
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._on_continue)
        self._countdown = 3
        self._has_failures = False

        self._build()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #1a1a2e; padding: 18px;")
        hl = QVBoxLayout(header)
        hl.setSpacing(4)
        title = QLabel("BLENDER PIPELINE STUDIO")
        title.setStyleSheet(
            "color: #3a7bd5; font-size: 20px; font-weight: bold; "
            "letter-spacing: 2px; font-family: 'Segoe UI';")
        sub = QLabel("System self-test — verifying environment before launch")
        sub.setStyleSheet("color: #666; font-size: 11px;")
        hl.addWidget(title)
        hl.addWidget(sub)
        layout.addWidget(header)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 13)   # 13 env checks
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: #111; }"
            "QProgressBar::chunk { background: #3a7bd5; }"
        )
        layout.addWidget(self._progress)

        # Scroll area for check rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: #1e1e1e; }"
        )
        container = QWidget()
        container.setStyleSheet("background: #1e1e1e;")
        self._rows_layout = QVBoxLayout(container)
        self._rows_layout.setSpacing(1)
        self._rows_layout.setContentsMargins(0, 8, 0, 8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Status area
        status_frame = QFrame()
        status_frame.setStyleSheet(
            "background: #141414; border-top: 1px solid #2a2a2a; padding: 12px;")
        sl = QVBoxLayout(status_frame)
        sl.setSpacing(8)

        self._status_label = QLabel("Running checks…")
        self._status_label.setStyleSheet(
            "color: #aaa; font-size: 13px; font-weight: bold;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._blender_label = QLabel("")
        self._blender_label.setStyleSheet("color: #555; font-size: 11px;")
        self._blender_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        self._skip_btn     = QPushButton("Skip Blender Check")
        self._continue_btn = QPushButton("Continue  →")
        self._continue_btn.setEnabled(False)
        self._continue_btn.setStyleSheet(
            "QPushButton { background: #3a7bd5; color: #fff; "
            "font-weight: bold; padding: 8px 24px; border-radius: 4px; }"
            "QPushButton:disabled { background: #333; color: #555; }"
            "QPushButton:hover { background: #4a8be5; }"
        )
        self._skip_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #888; "
            "padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background: #333; color: #aaa; }"
        )
        self._skip_btn.clicked.connect(self._skip_blender)
        self._continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._continue_btn)

        sl.addWidget(self._status_label)
        sl.addWidget(self._blender_label)
        sl.addLayout(btn_row)
        layout.addWidget(status_frame)

    def _add_row(self, name: str) -> CheckRow:
        row = CheckRow(name)
        self._rows[name] = row
        self._rows_layout.addWidget(row)
        return row

    # ── Public API ─────────────────────────────────────────────────────────────

    def run_checks(self):
        """Call this after show() to start the background checks."""
        from utils.startup_check import ENVIRONMENT_CHECKS

        # Pre-create all rows in order
        for fn in ENVIRONMENT_CHECKS:
            # derive name: check_python_version → "Python version"
            name = fn.__name__.replace("check_", "").replace("_", " ").title()
            # use actual name from the CheckResult for consistency
            self._add_row(name)

        # Blender row (last)
        host = get("mcp_host", "localhost")
        port = int(get("mcp_port", 9876))
        self._blender_row = self._add_row(f"Blender MCP ({host}:{port})")
        self._blender_row.set_pending()

        # Add a spacer at the bottom
        self._rows_layout.addStretch()

        self._worker = CheckWorker(
            host=host, port=port,
            ping_blender=bool(host),
        )
        self._worker.check_done.connect(self._on_check_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.blender_done.connect(self._on_blender_done)
        self._worker.start()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_check_done(self, r: CheckResult):
        # match row by position (order == ENVIRONMENT_CHECKS order)
        idx = self._progress.value()
        row = list(self._rows.values())[idx]
        row.set_result(r)
        self._progress.setValue(idx + 1)
        self._status_label.setText(f"Checking: {r.name}…")
        if not r.ok:
            self._has_failures = True

    def _on_all_done(self, report: StartupReport):
        self._progress.setRange(0, 14)
        self._progress.setValue(13)
        if self._has_failures:
            self._status_label.setText(
                "⚠  Some checks failed — the application may not work correctly.")
            self._status_label.setStyleSheet(
                "color: #f44336; font-size: 13px; font-weight: bold;")
            self._continue_btn.setEnabled(True)
            self._skip_btn.setEnabled(False)
            self._blender_label.setText("Skipping Blender check due to failures above.")
        else:
            self._status_label.setText("Environment OK — checking Blender MCP…")
            self._status_label.setStyleSheet(
                "color: #aaa; font-size: 13px; font-weight: bold;")
            self._blender_row.set_running()
            self._blender_label.setText(
                f"Connecting to blender-mcp at "
                f"{get('mcp_host','localhost')}:{get('mcp_port',9876)}…")

    def _on_blender_done(self, r: CheckResult):
        self._progress.setValue(14)
        self._blender_row.set_result(r)
        if r.ok:
            self._show_ready()
        else:
            self._blender_label.setText(
                "Blender not reachable — start blender-mcp inside Blender, "
                "or click Skip to configure later.")
            self._blender_label.setStyleSheet("color: #ff9800; font-size: 11px;")
            self._status_label.setText(
                "⚠  Blender MCP not found — you can still launch and connect later.")
            self._status_label.setStyleSheet(
                "color: #ff9800; font-size: 13px; font-weight: bold;")
            self._continue_btn.setEnabled(True)
            self._skip_btn.setEnabled(False)

    def _show_ready(self):
        self._status_label.setText("✓  SYSTEM READY")
        self._status_label.setStyleSheet(
            "color: #4caf50; font-size: 16px; font-weight: bold; "
            "letter-spacing: 1px;")
        self._blender_label.setText(
            "All checks passed — launching in 3 seconds…")
        self._blender_label.setStyleSheet("color: #666; font-size: 11px;")
        self._continue_btn.setEnabled(True)
        self._skip_btn.setEnabled(False)
        self._continue_btn.setText("Continue  (3)")
        self._countdown = 3
        self._auto_timer.start(1000)
        # Tick the countdown text
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._countdown_tick)
        self._tick_timer.start(1000)

    def _countdown_tick(self):
        self._countdown -= 1
        if self._countdown <= 0:
            self._tick_timer.stop()
            self._continue_btn.setText("Continue  →")
        else:
            self._continue_btn.setText(f"Continue  ({self._countdown})")

    def _skip_blender(self):
        if self._worker:
            self._worker.terminate()
        self._blender_row.set_result(
            __import__("utils.startup_check", fromlist=["CheckResult"]).CheckResult(
                name="Blender MCP", ok=True,
                message="Skipped — connect manually via File → Connect"))
        self._show_ready()

    def _on_continue(self):
        if hasattr(self, "_tick_timer"):
            self._tick_timer.stop()
        self._auto_timer.stop()
        self.ready.emit()
        self.accept()
