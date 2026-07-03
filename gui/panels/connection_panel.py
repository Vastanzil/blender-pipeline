"""
gui/panels/connection_panel.py
==============================
Connection setup dialog.

Supports two server modes:
  • mcpo   — MCP→OpenAPI proxy (default port 8000).  Your setup: mcpo wrapping blender-mcp.
  • direct — Raw blender-mcp JSON-RPC server (default port 9876).  Older / manual setup.
  • auto   — Try mcpo first, fall back to direct (default).

Settings are saved permanently — never asked again after first run.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                              QLineEdit, QSpinBox, QPushButton, QLabel,
                              QGroupBox, QComboBox, QRadioButton, QButtonGroup,
                              QFrame)
from PyQt6.QtCore import Qt, QTimer
from config.registry import get, set as reg_set


# Default ports per mode
_MODE_PORTS = {
    "mcpo":   8000,
    "direct": 9876,
    "auto":   8000,
}

_MODE_LABELS = {
    "mcpo":   (
        "mcpo  (recommended)",
        "mcpo wraps blender-mcp as OpenAPI REST — port 8000.\n"
        "Run:  mcpo --port 8000 -- blender-mcp.exe"
    ),
    "direct": (
        "Direct blender-mcp",
        "Connect straight to the blender-mcp addon JSON-RPC server — port 9876.\n"
        "Enable: Blender → N panel → MCP tab → Start MCP Server."
    ),
    "auto":   (
        "Auto-detect",
        "Try mcpo (port 8000) first, then direct (port 9876).\n"
        "Good when you switch between setups."
    ),
}


class ConnectionPanel(QDialog):
    def __init__(self, parent=None, on_connect=None):
        super().__init__(parent)
        self.on_connect = on_connect
        self.setWindowTitle("Blender Pipeline Studio — Connection Setup")
        self.setMinimumWidth(520)
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Header
        title = QLabel("Blender MCP Connection")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #3a7bd5;")
        layout.addWidget(title)

        sub = QLabel(
            "Configure how the app talks to Blender. "
            "Settings are saved permanently — you will not be asked again."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(sub)

        # ── Mode selector ──────────────────────────────────────────────
        mode_group = QGroupBox("Connection mode")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_buttons = QButtonGroup(self)
        self._mode_radios  = {}

        saved_mode = get("connection_mode", "auto")
        for key, (label_text, hint_text) in _MODE_LABELS.items():
            rb = QRadioButton(label_text)
            if key == saved_mode:
                rb.setChecked(True)
            self._mode_buttons.addButton(rb)
            self._mode_radios[key] = rb
            mode_layout.addWidget(rb)
            hint = QLabel(hint_text)
            hint.setStyleSheet("color: #777; font-size: 10px; margin-left: 20px;")
            hint.setWordWrap(True)
            mode_layout.addWidget(hint)
            rb.toggled.connect(lambda checked, k=key: self._on_mode_change(k, checked))

        layout.addWidget(mode_group)

        # ── Host / port ────────────────────────────────────────────────
        conn_group = QGroupBox("Server address")
        form = QFormLayout(conn_group)
        self.host_input = QLineEdit(get("mcp_host", "localhost"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(get("mcp_port", 8000)))
        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        layout.addWidget(conn_group)

        # ── AI backend ─────────────────────────────────────────────────
        ai_group = QGroupBox("AI Backend (optional)")
        ai_form = QFormLayout(ai_group)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["ollama", "openai", "anthropic", "gemini"])
        self.backend_combo.setCurrentText(get("ai_backend", "ollama"))
        self.ollama_host = QLineEdit(get("ollama_host", "http://localhost:11434"))
        ai_form.addRow("Backend:", self.backend_combo)
        ai_form.addRow("Ollama Host:", self.ollama_host)
        layout.addWidget(ai_group)

        # ── Status label ───────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(36)
        layout.addWidget(self.status)

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.save_btn = QPushButton("Save && Connect")
        self.test_btn.clicked.connect(self._test)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.test_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_change(self, key: str, checked: bool):
        if not checked:
            return
        # Auto-update the port to the mode default
        self.port_input.setValue(_MODE_PORTS[key])

    def _current_mode(self) -> str:
        for key, rb in self._mode_radios.items():
            if rb.isChecked():
                return key
        return "auto"

    def _test(self):
        host = self.host_input.text().strip()
        port = self.port_input.value()
        mode = self._current_mode()

        self.test_btn.setEnabled(False)
        self.status.setText(f"Testing {host}:{port} ({mode})…")
        self.status.setStyleSheet("color: #ff9800;")

        from utils.async_runner import run_in_thread
        from mcp.factory import detect_mode

        def _detect():
            return detect_mode(host, port, timeout=5.0)

        run_in_thread(_detect,
                      on_result=lambda found: self._on_test_done(found, host, port, mode),
                      on_error=lambda e: self._on_test_error(str(e)))

    def _on_test_done(self, found: str, host: str, port: int, mode: str):
        self.test_btn.setEnabled(True)
        if found == "none":
            self.status.setText(
                f"No response at {host}:{port}\n"
                "Check that mcpo (or blender-mcp) is running and the port is correct."
            )
            self.status.setStyleSheet("color: #f44336;")
        elif found == "mcpo":
            # Try to get tool count
            try:
                from mcp.mcpo_client import MCPOClient
                c = MCPOClient(host, port, timeout=5.0)
                tools = c.list_tools()
                ver   = c.get_blender_version()
                v     = ".".join(str(x) for x in ver)
                self.status.setText(
                    f"mcpo  ✓  Blender {v}  —  {len(tools)} tools available"
                )
            except Exception as e:
                self.status.setText(f"mcpo detected, but error reading tools: {e}")
            self.status.setStyleSheet("color: #4caf50; font-weight: bold;")
        elif found == "direct":
            try:
                from mcp.client import BlenderMCPClient
                c = BlenderMCPClient(host, port, timeout=5.0)
                tools = c.list_tools()
                ver   = c.get_blender_version()
                v     = ".".join(str(x) for x in ver)
                self.status.setText(
                    f"Direct blender-mcp  ✓  Blender {v}  —  {len(tools)} tools"
                )
            except Exception as e:
                self.status.setText(f"Direct MCP detected, but error: {e}")
            self.status.setStyleSheet("color: #4caf50; font-weight: bold;")

    def _on_test_error(self, err: str):
        self.test_btn.setEnabled(True)
        self.status.setText(f"Error: {err[:120]}")
        self.status.setStyleSheet("color: #f44336;")

    def _save(self):
        host = self.host_input.text().strip()
        port = self.port_input.value()
        mode = self._current_mode()
        reg_set("mcp_host",        host)
        reg_set("mcp_port",        port)
        reg_set("connection_mode", mode)
        reg_set("ai_backend",      self.backend_combo.currentText())
        reg_set("ollama_host",     self.ollama_host.text().strip())
        if self.on_connect:
            self.on_connect(host, port)
        self.accept()
