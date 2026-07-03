"""
gui/panels/connection_panel.py
First-run / settings dialog: host+port, test connection, save to OS config.
Shown automatically on first launch when no saved config is found.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                              QLineEdit, QSpinBox, QPushButton, QLabel,
                              QGroupBox, QComboBox)
from PyQt6.QtCore import Qt
from config.registry import get, set as reg_set


class ConnectionPanel(QDialog):
    def __init__(self, parent=None, on_connect=None):
        super().__init__(parent)
        self.on_connect = on_connect
        self.setWindowTitle("Blender Pipeline Studio — Connection Setup")
        self.setMinimumWidth(480)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Blender MCP Connection")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #3a7bd5;")
        layout.addWidget(title)

        sub = QLabel(
            "Configure your blender-mcp server. "
            "Settings are saved permanently — you will never be asked again."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(sub)

        # MCP server
        conn_group = QGroupBox("MCP Server")
        form = QFormLayout(conn_group)
        self.host_input = QLineEdit(get("mcp_host", "localhost"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(get("mcp_port", 9876)))
        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        layout.addWidget(conn_group)

        # AI backend
        ai_group = QGroupBox("AI Backend (optional)")
        ai_form = QFormLayout(ai_group)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["ollama", "openai", "anthropic", "gemini"])
        self.backend_combo.setCurrentText(get("ai_backend", "ollama"))
        self.ollama_host = QLineEdit(get("ollama_host", "http://localhost:11434"))
        ai_form.addRow("Backend:", self.backend_combo)
        ai_form.addRow("Ollama Host:", self.ollama_host)
        layout.addWidget(ai_group)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        btn_row = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        save_btn = QPushButton("Save && Connect")
        test_btn.clicked.connect(self._test)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(test_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _test(self):
        self.status.setText("Testing...")
        self.status.setStyleSheet("color: #888;")
        try:
            from mcp.client import BlenderMCPClient
            c = BlenderMCPClient(self.host_input.text().strip(),
                                 self.port_input.value(), timeout=5.0)
            if c.ping():
                ver = c.get_blender_version()
                v   = ".".join(str(x) for x in ver)
                self.status.setText(f"Connected!  Blender {v}")
                self.status.setStyleSheet("color: #4caf50; font-weight: bold;")
            else:
                self.status.setText("No response — is blender-mcp running?")
                self.status.setStyleSheet("color: #f44336;")
        except Exception as e:
            self.status.setText(f"Error: {str(e)[:90]}")
            self.status.setStyleSheet("color: #f44336;")

    def _save(self):
        reg_set("mcp_host",    self.host_input.text().strip())
        reg_set("mcp_port",    self.port_input.value())
        reg_set("ai_backend",  self.backend_combo.currentText())
        reg_set("ollama_host", self.ollama_host.text().strip())
        if self.on_connect:
            self.on_connect(self.host_input.text().strip(), self.port_input.value())
        self.accept()
