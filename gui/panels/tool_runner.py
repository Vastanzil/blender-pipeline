"""gui/panels/tool_runner.py — Dynamic tool runner: schema-driven form → execute → output."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTextEdit, QScrollArea, QGroupBox)
from gui.widgets.param_form import ParamForm
from utils.async_runner import run_in_thread
from mcp.models import Tool


class ToolRunnerPanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._tool     = None
        self._client   = None
        self._executor = None
        self._form     = None
        self._worker   = None
        self._build()

    def set_client(self, client, executor=None):
        self._client   = client
        self._executor = executor

    def load_tool(self, tool: Tool):
        self._tool = tool
        self._tool_name.setText(f"Tool: {tool.name}")
        self._tool_desc.setText(tool.description or "")
        if self._form:
            self._form.setParent(None)
        self._form = ParamForm(tool)
        self._form_area.setWidget(self._form)
        self._output.clear()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._tool_name = QLabel("Select a tool from the list")
        self._tool_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #3a7bd5;")
        self._tool_desc = QLabel("")
        self._tool_desc.setWordWrap(True)
        self._tool_desc.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._tool_name)
        layout.addWidget(self._tool_desc)

        fg = QGroupBox("Parameters")
        fl = QVBoxLayout(fg)
        self._form_area = QScrollArea()
        self._form_area.setWidgetResizable(True)
        self._form_area.setMinimumHeight(120)
        self._form_area.setMaximumHeight(300)
        fl.addWidget(self._form_area)
        layout.addWidget(fg)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Tool")
        self._run_btn.clicked.connect(self._run)
        clr = QPushButton("Clear")
        clr.setMaximumWidth(70)
        clr.clicked.connect(lambda: self._output.clear())
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(clr)
        layout.addLayout(btn_row)

        og = QGroupBox("Output")
        ol = QVBoxLayout(og)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(150)
        ol.addWidget(self._output)
        layout.addWidget(og)

    def _run(self):
        if not self._tool or not self._client:
            self._output.setText("No tool selected or not connected.")
            return
        if not self._form:
            return
        values = self._form.get_values()
        self._run_btn.setEnabled(False)
        self._output.setText("Running...")

        def do():
            if self._executor:
                return self._executor.execute(self._tool, values)
            return self._client.call_tool(self._tool.name, values)

        self._worker = run_in_thread(
            do,
            on_result=self._on_result,
            on_error=self._on_error,
        )

    def _on_result(self, r):
        self._run_btn.setEnabled(True)
        self._output.setText(r.text())

    def _on_error(self, e):
        self._run_btn.setEnabled(True)
        self._output.setText(f"ERROR:\n{e}")
