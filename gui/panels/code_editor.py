"""gui/panels/code_editor.py — Raw bpy code editor with validate + execute."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTextEdit, QGroupBox)
from utils.async_runner import run_in_thread
from utils.code_validator import validate_bpy_code


class CodeEditorPanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._client = None
        self._worker = None
        self._build()

    def set_client(self, client):
        self._client = client

    def _build(self):
        layout = QVBoxLayout(self)

        title = QLabel("Code Editor")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3a7bd5;")
        layout.addWidget(title)

        eg = QGroupBox("Python / bpy Code")
        egl = QVBoxLayout(eg)
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "# Write bpy code and click Execute\n"
            "import bpy\n\n"
            "bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))\n"
            "print('Cube added')"
        )
        self._editor.setMinimumHeight(260)
        self._editor.setFontFamily("Consolas")
        self._editor.setFontPointSize(11)
        egl.addWidget(self._editor)
        layout.addWidget(eg)

        btn_row = QHBoxLayout()
        val_btn  = QPushButton("Validate")
        self._exec_btn = QPushButton("Execute")
        clr_btn  = QPushButton("Clear")
        clr_btn.setMaximumWidth(70)
        val_btn.clicked.connect(self._validate)
        self._exec_btn.clicked.connect(self._execute)
        clr_btn.clicked.connect(self._editor.clear)
        btn_row.addWidget(val_btn)
        btn_row.addWidget(self._exec_btn)
        btn_row.addWidget(clr_btn)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        layout.addWidget(self._status)

        og = QGroupBox("Output")
        ogl = QVBoxLayout(og)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(120)
        ogl.addWidget(self._output)
        layout.addWidget(og)

    def _validate(self):
        r = validate_bpy_code(self._editor.toPlainText())
        if r.ok:
            msg = "Valid"
            if r.warnings:
                msg += " | Warnings: " + "; ".join(r.warnings)
            self._status.setStyleSheet("color: #4caf50;")
        else:
            msg = "Error: " + "; ".join(r.errors)
            self._status.setStyleSheet("color: #f44336;")
        self._status.setText(msg)

    def _execute(self):
        if not self._client:
            self._output.setText("Not connected.")
            return
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._exec_btn.setEnabled(False)
        self._output.setText("Executing...")

        def do():
            return self._client.exec_code(code)

        self._worker = run_in_thread(
            do,
            on_result=lambda r: (self._output.setText(r.text()),
                                 self._exec_btn.setEnabled(True)),
            on_error=lambda e: (self._output.setText(f"ERROR:\n{e}"),
                                self._exec_btn.setEnabled(True)),
        )
