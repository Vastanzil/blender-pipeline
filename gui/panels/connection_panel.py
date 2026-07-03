"""
gui/panels/connection_panel.py
==============================
Connection + AI backend setup dialog.

MCP connection modes:
  mcpo   — mcpo OpenAPI proxy (port 8000)  ← recommended
  direct — raw blender-mcp JSON-RPC (port 9876)
  auto   — try mcpo first, then direct

AI backends (5):
  ollama    — local Ollama with live model picker
  openai    — OpenAI API key
  anthropic — Anthropic API key
  gemini    — Google Gemini API key
  manifest  — Manifest AI router (http://localhost:2099)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel,
    QGroupBox, QComboBox, QRadioButton, QButtonGroup,
    QFrame, QStackedWidget, QWidget,
)
from PyQt6.QtCore import Qt  # noqa: F401
from config.registry import get, set as reg_set

_MODE_PORTS = {"mcpo": 8000, "direct": 9876, "auto": 8000}

_MODE_HINTS = {
    "mcpo":   "mcpo wraps blender-mcp as OpenAPI REST on port 8000.\n"
               "Run:  mcpo --port 8000 -- blender-mcp.exe",
    "direct": "Connect directly to the blender-mcp addon JSON-RPC server on port 9876.\n"
               "Enable: Blender → N panel → MCP tab → Start MCP Server.",
    "auto":   "Tries mcpo (port 8000) first, then direct (port 9876).",
}


class ConnectionPanel(QDialog):
    def __init__(self, parent=None, on_connect=None):
        super().__init__(parent)
        self.on_connect = on_connect
        self.setWindowTitle("Blender Pipeline Studio — Connection Setup")
        self.setMinimumWidth(540)
        self._build()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        title = QLabel("Blender Pipeline Studio — Setup")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3a7bd5;")
        layout.addWidget(title)

        sub = QLabel("Configure your MCP server and AI backend. Saved permanently.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(sub)

        # ── MCP connection mode ───────────────────────────────────────
        mode_group = QGroupBox("MCP Connection Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_buttons = QButtonGroup(self)
        self._mode_radios  = {}
        saved_mode = get("connection_mode", "auto")
        for key, hint in _MODE_HINTS.items():
            rb = QRadioButton(key + ("  (recommended)" if key == "mcpo" else ""))
            if key == saved_mode:
                rb.setChecked(True)
            self._mode_buttons.addButton(rb)
            self._mode_radios[key] = rb
            mode_layout.addWidget(rb)
            hl = QLabel(hint)
            hl.setStyleSheet("color:#777; font-size:10px; margin-left:20px;")
            hl.setWordWrap(True)
            mode_layout.addWidget(hl)
            rb.toggled.connect(lambda checked, k=key: self._on_mode_change(k, checked))
        layout.addWidget(mode_group)

        # ── Server address ────────────────────────────────────────────
        addr_group = QGroupBox("Server Address")
        addr_form  = QFormLayout(addr_group)
        self.host_input = QLineEdit(get("mcp_host", "localhost"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(get("mcp_port", 8000)))
        addr_form.addRow("Host:", self.host_input)
        addr_form.addRow("Port:", self.port_input)
        layout.addWidget(addr_group)

        # ── AI backend ────────────────────────────────────────────────
        ai_group = QGroupBox("AI Backend")
        ai_outer = QVBoxLayout(ai_group)

        ai_top = QFormLayout()
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["ollama", "openai", "anthropic", "gemini", "manifest"])
        self.backend_combo.setCurrentText(get("ai_backend", "ollama"))
        ai_top.addRow("Backend:", self.backend_combo)
        ai_outer.addLayout(ai_top)

        # Stacked pages — one per backend that needs config
        self._ai_stack = QStackedWidget()

        # Page 0 — ollama
        self._ai_stack.addWidget(self._build_ollama_page())
        # Page 1 — openai
        self._ai_stack.addWidget(self._build_key_page("openai_api_key", "OpenAI API Key:"))
        # Page 2 — anthropic
        self._ai_stack.addWidget(self._build_key_page("anthropic_api_key", "Anthropic API Key:"))
        # Page 3 — gemini
        self._ai_stack.addWidget(self._build_key_page("gemini_api_key", "Gemini API Key:"))
        # Page 4 — manifest
        self._ai_stack.addWidget(self._build_manifest_page())

        ai_outer.addWidget(self._ai_stack)
        layout.addWidget(ai_group)

        self.backend_combo.currentTextChanged.connect(self._on_backend_change)
        self._on_backend_change(self.backend_combo.currentText())  # set initial page

        # ── Status ───────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(32)
        layout.addWidget(self.status)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.save_btn = QPushButton("Save && Connect")
        self.test_btn.clicked.connect(self._test)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.test_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Backend-specific pages
    # ------------------------------------------------------------------

    def _build_ollama_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 6, 0, 0)

        self.ollama_host = QLineEdit(get("ollama_host", "http://localhost:11434"))
        form.addRow("Ollama Host:", self.ollama_host)

        # Coder model row with Refresh button
        coder_row = QHBoxLayout()
        self.coder_combo = QComboBox()
        self.coder_combo.setEditable(True)
        self.coder_combo.setMinimumWidth(200)
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedWidth(30)
        self._refresh_btn.setToolTip("Refresh model list from Ollama")
        self._refresh_btn.clicked.connect(self._refresh_ollama_models)
        coder_row.addWidget(self.coder_combo)
        coder_row.addWidget(self._refresh_btn)
        form.addRow("Coder model:", coder_row)

        self.planner_combo = QComboBox()
        self.planner_combo.setEditable(True)
        self.planner_combo.setMinimumWidth(200)
        form.addRow("Planner model:", self.planner_combo)

        # Populate models immediately (non-blocking best-effort)
        self._refresh_ollama_models()
        return w

    def _build_key_page(self, config_key: str, label: str) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 6, 0, 0)
        field = QLineEdit(get(config_key, ""))
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText("sk-..." if "openai" in config_key else "")
        form.addRow(label, field)
        # Store ref on widget so _save() can find it
        w._config_key = config_key
        w._field      = field
        return w

    def _build_manifest_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 6, 0, 0)

        self.manifest_host  = QLineEdit(get("manifest_host",  "http://localhost:2099"))
        self.manifest_token = QLineEdit(get("manifest_token", ""))
        self.manifest_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.manifest_token.setPlaceholderText("mnfst_xxx...")
        self.manifest_model = QLineEdit(get("manifest_model", "auto"))
        self.manifest_model.setPlaceholderText("auto")

        form.addRow("Manifest URL:", self.manifest_host)
        form.addRow("Token:",        self.manifest_token)
        form.addRow("Model:",        self.manifest_model)

        hint = QLabel(
            "Token from your Manifest dashboard.\n"
            "Model 'auto' lets Manifest choose the best provider."
        )
        hint.setStyleSheet("color:#777; font-size:10px;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return w

    # ------------------------------------------------------------------
    # Ollama model refresh (background thread)
    # ------------------------------------------------------------------

    def _refresh_ollama_models(self):
        host = self.ollama_host.text().strip()
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("…")

        from utils.async_runner import run_in_thread

        def _fetch():
            from ai.ollama_client import OllamaClient
            return OllamaClient(host=host).available_models()

        run_in_thread(
            _fetch,
            on_result=self._on_models_loaded,
            on_error=lambda _: self._on_models_loaded([]),
        )

    def _on_models_loaded(self, models: list):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("↻")

        saved_coder   = get("coder_model",   "")
        saved_planner = get("planner_model", "")

        for combo, saved in [(self.coder_combo,   saved_coder),
                              (self.planner_combo, saved_planner)]:
            combo.clear()
            combo.addItem("(auto-detect)")
            for m in models:
                combo.addItem(m)
            # Select saved value if present
            idx = combo.findText(saved)
            combo.setCurrentIndex(idx if idx >= 0 else 0)

        if not models:
            self.status.setText("Ollama not reachable — models unavailable.")
            self.status.setStyleSheet("color:#ff9800;")
        else:
            self.status.setText(f"{len(models)} Ollama model(s) found.")
            self.status.setStyleSheet("color:#4caf50;")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_change(self, key: str, checked: bool):
        if checked:
            self.port_input.setValue(_MODE_PORTS[key])

    def _on_backend_change(self, backend: str):
        idx = {"ollama": 0, "openai": 1, "anthropic": 2,
                "gemini": 3, "manifest": 4}.get(backend, 0)
        self._ai_stack.setCurrentIndex(idx)
        self.status.setText("")

    def _current_mode(self) -> str:
        for key, rb in self._mode_radios.items():
            if rb.isChecked():
                return key
        return "auto"

    # ------------------------------------------------------------------
    # Test connection
    # ------------------------------------------------------------------

    def _test(self):
        host = self.host_input.text().strip()
        port = self.port_input.value()
        mode = self._current_mode()

        self.test_btn.setEnabled(False)
        self.status.setText(f"Testing {host}:{port}…")
        self.status.setStyleSheet("color:#ff9800;")

        from utils.async_runner import run_in_thread
        from mcp.factory import detect_mode

        run_in_thread(
            lambda: detect_mode(host, port, timeout=5.0),
            on_result=lambda found: self._on_test_done(found, host, port),
            on_error=lambda e: self._on_test_error(str(e)),
        )

    def _on_test_done(self, found: str, host: str, port: int):
        self.test_btn.setEnabled(True)
        if found == "none":
            self.status.setText(
                f"No response at {host}:{port}\n"
                "Check that mcpo (or blender-mcp) is running."
            )
            self.status.setStyleSheet("color:#f44336;")
            return
        try:
            from mcp.factory import make_client
            c     = make_client(host, port, timeout=5.0)
            tools = c.list_tools()
            ver   = c.get_blender_version()
            v     = ".".join(str(x) for x in ver)
            self.status.setText(
                f"{found}  ✓   Blender {v}  —  {len(tools)} tools"
            )
            self.status.setStyleSheet("color:#4caf50; font-weight:bold;")
        except Exception as e:
            self.status.setText(f"{found} detected but error: {e}")
            self.status.setStyleSheet("color:#ff9800;")

    def _on_test_error(self, err: str):
        self.test_btn.setEnabled(True)
        self.status.setText(f"Error: {err[:120]}")
        self.status.setStyleSheet("color:#f44336;")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        reg_set("mcp_host",        self.host_input.text().strip())
        reg_set("mcp_port",        self.port_input.value())
        reg_set("connection_mode", self._current_mode())

        backend = self.backend_combo.currentText()
        reg_set("ai_backend", backend)

        if backend == "ollama":
            reg_set("ollama_host", self.ollama_host.text().strip())
            # "(auto-detect)" → save as empty string so OllamaClient auto-picks
            coder   = self.coder_combo.currentText()
            planner = self.planner_combo.currentText()
            reg_set("coder_model",   "" if coder   == "(auto-detect)" else coder)
            reg_set("planner_model", "" if planner == "(auto-detect)" else planner)

        elif backend == "manifest":
            reg_set("manifest_host",  self.manifest_host.text().strip())
            reg_set("manifest_token", self.manifest_token.text().strip())
            reg_set("manifest_model", self.manifest_model.text().strip() or "auto")

        else:
            # openai / anthropic / gemini — find the key field on the stack page
            page = self._ai_stack.currentWidget()
            if hasattr(page, "_config_key"):
                reg_set(page._config_key, page._field.text().strip())

        if self.on_connect:
            self.on_connect(self.host_input.text().strip(), self.port_input.value())
        self.accept()
