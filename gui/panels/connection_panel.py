"""
Connection + AI backend setup dialog.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QLabel,
    QGroupBox, QFrame, QFileDialog, QRadioButton, QButtonGroup,
    QComboBox, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from config.registry import get, set as reg_set


class ConnectionPanel(QDialog):
    def __init__(self, parent=None, on_connect=None, on_saved=None):
        super().__init__(parent)
        self.on_connect = on_connect
        self.on_saved   = on_saved
        self.setWindowTitle("BlenderCopilot — Connection Setup")
        self.setMinimumWidth(580)
        self.setMinimumHeight(500)
        self._build()

    def _build(self):
        # Outer layout: scroll area + fixed button bar at bottom
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable content pane
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # ── Status label MUST be created FIRST ───────────────────────
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(32)

        # Header
        title = QLabel("BlenderCopilot — Setup")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3a7bd5;")
        layout.addWidget(title)

        sub = QLabel("Configure your MCP server and Manifest AI backend. Saved permanently.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(sub)

        # ── MCP connection mode ───────────────────────────────────────
        mode_group = QGroupBox("MCP Connection Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_buttons = QButtonGroup(self)
        self._mode_radios  = {}
        saved_mode = get("connection_mode", "auto")
        _MODE_HINTS = {
            "mcpo":   "mcpo wraps blender-mcp as OpenAPI REST on port 8000.\n"
                      "Run:  mcpo --port 8000 -- blender-mcp.exe",
            "direct": "Connect directly to the blender-mcp addon JSON-RPC server on port 9876.\n"
                      "Enable: Blender → N panel → MCP tab → Start MCP Server.",
            "auto":   "Tries mcpo (port 8000) first, then direct (port 9876).",
        }
        _MODE_PORTS = {"mcpo": 8000, "direct": 9876, "auto": 8000}

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

        # ── Manifest AI backend ──────────────────────────────────────
        ai_group = QGroupBox("Manifest AI Backend")
        ai_form = QFormLayout(ai_group)

        self.manifest_host  = QLineEdit(get("manifest_host",  "http://localhost:2099"))
        self.manifest_token = QLineEdit(get("manifest_token", ""))
        self.manifest_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.manifest_token.setPlaceholderText("mnfst_xxx...")
        self.manifest_model = QLineEdit(get("manifest_model", "auto"))
        self.manifest_model.setPlaceholderText("auto")

        ai_form.addRow("Manifest URL:", self.manifest_host)
        ai_form.addRow("Token:",        self.manifest_token)
        ai_form.addRow("Model:",        self.manifest_model)

        hint = QLabel(
            "Token from your Manifest dashboard.\n"
            "Model 'auto' lets Manifest choose the best provider."
        )
        hint.setStyleSheet("color:#777; font-size:10px;")
        hint.setWordWrap(True)
        ai_form.addRow("", hint)

        self._manifest_test_btn = QPushButton("Test Manifest Connection")
        self._manifest_test_btn.clicked.connect(self._test_manifest)
        ai_form.addRow("", self._manifest_test_btn)

        layout.addWidget(ai_group)

        # ── AI Routing ───────────────────────────────────────────────
        routing_group = QGroupBox("AI Routing")
        routing_form  = QFormLayout(routing_group)

        planner_lbl = QLabel("Manifest (fixed)")
        planner_lbl.setStyleSheet("color:#aaa;")
        routing_form.addRow("Planner:", planner_lbl)

        self._coder_combo = QComboBox()
        self._coder_combo.addItem("Manifest (cloud)", "manifest")
        self._coder_combo.addItem("BlenderLLM (local)", "blenderllm")
        saved_coder = "blenderllm" if get("hybrid_mode", False) else "manifest"
        self._coder_combo.setCurrentIndex(0 if saved_coder == "manifest" else 1)
        self._coder_combo.currentIndexChanged.connect(self._on_coder_changed)
        routing_form.addRow("Coder:", self._coder_combo)

        # BlenderLLM sub-group (shown only when BlenderLLM selected)
        self._blenderllm_box = QGroupBox("BlenderLLM Settings")
        blm_form = QFormLayout(self._blenderllm_box)

        self._blm_url = QLineEdit(get("blenderllm_server_url", "http://127.0.0.1:8080"))
        self._blm_url.setPlaceholderText("http://127.0.0.1:8080")
        blm_form.addRow("Server URL:", self._blm_url)

        self._blm_timeout = QSpinBox()
        self._blm_timeout.setRange(30, 600)
        self._blm_timeout.setSuffix(" s")
        self._blm_timeout.setValue(int(get("blenderllm_timeout", 180)))
        blm_form.addRow("Timeout:", self._blm_timeout)

        blm_home_row = QHBoxLayout()
        self._blm_home = QLineEdit(get("blenderllm_home", ""))
        self._blm_home.setPlaceholderText("(optional) path to blenderllm folder")
        blm_browse_btn = QPushButton("Browse...")
        blm_browse_btn.setFixedWidth(70)
        blm_browse_btn.clicked.connect(self._browse_blm_home)
        blm_home_row.addWidget(self._blm_home)
        blm_home_row.addWidget(blm_browse_btn)
        blm_form.addRow("Install dir:", blm_home_row)

        self._blm_test_btn = QPushButton("Test BlenderLLM Connection")
        self._blm_test_btn.clicked.connect(self._test_blenderllm)
        blm_form.addRow("", self._blm_test_btn)

        self._blm_status = QLabel("")
        self._blm_status.setWordWrap(True)
        blm_form.addRow("", self._blm_status)

        routing_form.addRow("", self._blenderllm_box)
        self._blenderllm_box.setVisible(saved_coder == "blenderllm")

        layout.addWidget(routing_group)
        ps_group = QGroupBox("Pipeline Settings")
        ps_form  = QFormLayout(ps_group)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 20)
        self.retries_spin.setValue(int(get("max_retries", 5)))
        ps_form.addRow("Max retries:", self.retries_spin)

        self.poll_spin = QDoubleSpinBox()
        self.poll_spin.setRange(0.5, 30.0)
        self.poll_spin.setSingleStep(0.5)
        self.poll_spin.setDecimals(1)
        self.poll_spin.setSuffix(" s")
        self.poll_spin.setValue(float(get("poll_interval", 2.0)))
        ps_form.addRow("Scene poll:", self.poll_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(int(get("ai_timeout", 120)))
        ps_form.addRow("AI timeout:", self.timeout_spin)

        out_row = QHBoxLayout()
        self.outdir_input = QLineEdit(get("output_dir", ""))
        self.outdir_input.setPlaceholderText("(default: ~/blender_pipeline_output)")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(self.outdir_input)
        out_row.addWidget(browse_btn)
        ps_form.addRow("Output dir:", out_row)

        self._outdir_warn = QLabel("⚠ Output directory is required before running a pipeline.")
        self._outdir_warn.setStyleSheet("color: #ff9800; font-size: 10px;")
        self._outdir_warn.setVisible(not bool(get("output_dir", "")))
        self.outdir_input.textChanged.connect(
            lambda t: self._outdir_warn.setVisible(not bool(t.strip())))
        ps_form.addRow("", self._outdir_warn)

        rag_row = QHBoxLayout()
        self.ragdir_input = QLineEdit(get("rag_corpus_dir", ""))
        self.ragdir_input.setPlaceholderText("(default: <output_dir>/_rag_corpus/)")
        rag_browse_btn = QPushButton("Browse…")
        rag_browse_btn.setFixedWidth(70)
        rag_browse_btn.clicked.connect(self._browse_rag_dir)
        rag_row.addWidget(self.ragdir_input)
        rag_row.addWidget(rag_browse_btn)
        ps_form.addRow("RAG corpus dir:", rag_row)

        layout.addWidget(ps_group)
        layout.addStretch()

        # ── Fixed bottom bar (outside scroll area) ────────────────────
        bottom = QFrame()
        bottom.setFrameShape(QFrame.Shape.NoFrame)
        bottom.setStyleSheet("border-top: 1px solid #2a2a2a; padding: 6px;")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(12, 6, 12, 6)
        bl.setSpacing(4)
        bl.addWidget(self.status)   # created at top of _build()

        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.save_btn = QPushButton("Save && Connect")
        self.save_btn.setStyleSheet(
            "QPushButton { background: #3a7bd5; color: #fff; "
            "font-weight: bold; padding: 6px 20px; border-radius: 4px; }"
            "QPushButton:hover { background: #4a8be5; }"
        )
        self.test_btn.clicked.connect(self._test)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.test_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        bl.addLayout(btn_row)
        outer.addWidget(bottom)

    # ------------------------------------------------------------------
    # Test / Save methods (simplified for Manifest-only)
    # ------------------------------------------------------------------

    def _test(self):
        host = self.host_input.text().strip()
        port = self.port_input.value()

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
            self.status.setText(f"{found}  ✓   Blender {v}  —  {len(tools)} tools")
            self.status.setStyleSheet("color:#4caf50; font-weight:bold;")
        except Exception as e:
            self.status.setText(f"{found} detected but error: {e}")
            self.status.setStyleSheet("color:#ff9800;")

    def _on_test_error(self, err: str):
        self.test_btn.setEnabled(True)
        self.status.setText(f"Error: {err[:120]}")
        self.status.setStyleSheet("color:#f44336;")

    def _test_manifest(self):
        host  = self.manifest_host.text().strip()
        token = self.manifest_token.text().strip()
        self._manifest_test_btn.setEnabled(False)
        self.status.setText("Testing Manifest…")
        self.status.setStyleSheet("color:#ff9800;")

        from utils.async_runner import run_in_thread

        def _check():
            from ai.manifest_client import ManifestClient
            return ManifestClient(host=host, token=token).is_available()

        run_in_thread(
            _check,
            on_result=lambda ok: self._on_manifest_test(ok),
            on_error=lambda e: self._on_manifest_test(False, str(e)),
        )

    def _on_manifest_test(self, ok: bool, err: str = ""):
        self._manifest_test_btn.setEnabled(True)
        if ok:
            self.status.setText("Manifest ✓  connected")
            self.status.setStyleSheet("color:#4caf50; font-weight:bold;")
        else:
            self.status.setText(
                f"Manifest ✗  {err or 'not reachable'}\n"
                "Check that Manifest is running on the configured URL."
            )
            self.status.setStyleSheet("color:#f44336;")

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select output directory", self.outdir_input.text() or "")
        if d:
            self.outdir_input.setText(d)

    def _browse_rag_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select RAG corpus directory", self.ragdir_input.text() or "")
        if d:
            self.ragdir_input.setText(d)

    def _on_mode_change(self, key: str, checked: bool):
        if checked:
            self.port_input.setValue({"mcpo": 8000, "direct": 9876, "auto": 8000}[key])

    def _save(self):
        reg_set("mcp_host",        self.host_input.text().strip())
        reg_set("mcp_port",        self.port_input.value())
        reg_set("connection_mode", self._current_mode())

        coder  = self._coder_combo.currentData()
        hybrid = (coder == "blenderllm")
        reg_set("ai_backend",  coder)
        reg_set("hybrid_mode", hybrid)
        if hybrid:
            reg_set("blenderllm_server_url", self._blm_url.text().strip())
            reg_set("blenderllm_timeout",    self._blm_timeout.value())
            reg_set("blenderllm_home",       self._blm_home.text().strip())
        else:
            reg_set("blenderllm_server_url", "")

        reg_set("manifest_host",  self.manifest_host.text().strip())
        token = self.manifest_token.text().strip()
        token = token.replace("\n", "").replace("\r", "").replace(" ", "")
        reg_set("manifest_token", token)
        reg_set("manifest_model", self.manifest_model.text().strip() or "auto")

        # Pipeline settings
        reg_set("max_retries",   self.retries_spin.value())
        reg_set("poll_interval", self.poll_spin.value())
        reg_set("ai_timeout",    self.timeout_spin.value())
        reg_set("output_dir",    self.outdir_input.text().strip())
        reg_set("rag_corpus_dir", self.ragdir_input.text().strip())

        if self.on_saved:
            self.on_saved()
        if self.on_connect:
            self.on_connect(self.host_input.text().strip(), self.port_input.value())
        self.accept()

    def _on_coder_changed(self, idx: int):
        self._blenderllm_box.setVisible(
            self._coder_combo.itemData(idx) == "blenderllm"
        )

    def _browse_blm_home(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select BlenderLLM install directory", self._blm_home.text() or "")
        if d:
            self._blm_home.setText(d)

    def _test_blenderllm(self):
        url = self._blm_url.text().strip() or "http://127.0.0.1:8080"
        self._blm_test_btn.setEnabled(False)
        self._blm_status.setText("Testing BlenderLLM...")
        self._blm_status.setStyleSheet("color:#ff9800;")

        from utils.async_runner import run_in_thread

        def _check():
            from ai.blenderllm_client import BlenderLLMClient
            return BlenderLLMClient(url, timeout=10).health()

        run_in_thread(
            _check,
            on_result=lambda ok: self._on_blm_test(ok),
            on_error=lambda e: self._on_blm_test(False, str(e)),
        )

    def _on_blm_test(self, ok: bool, err: str = ""):
        self._blm_test_btn.setEnabled(True)
        if ok:
            self._blm_status.setText("BlenderLLM server OK")
            self._blm_status.setStyleSheet("color:#4caf50; font-weight:bold;")
        else:
            self._blm_status.setText(
                f"Not reachable: {err or 'no response'}\n"
                "Run start_blenderllm.bat first."
            )
            self._blm_status.setStyleSheet("color:#f44336;")

    def _current_mode(self) -> str:
        for key, rb in self._mode_radios.items():
            if rb.isChecked():
                return key
        return "auto"