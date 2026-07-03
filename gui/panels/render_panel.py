"""gui/panels/render_panel.py — Render engine settings and launch."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QComboBox, QSpinBox, QGroupBox,
                              QFormLayout, QLineEdit)
from utils.async_runner import run_in_thread
from blender.render import RenderBuilder


class RenderPanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._client  = None
        self._version = (5, 0, 0)
        self._builder = RenderBuilder()
        self._build()

    def set_client(self, client, version=(5, 0, 0)):
        self._client  = client
        self._version = version

    def _build(self):
        layout = QVBoxLayout(self)

        title = QLabel("Render")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3a7bd5;")
        layout.addWidget(title)

        sg = QGroupBox("Settings")
        form = QFormLayout(sg)

        self._engine = QComboBox()
        self._engine.addItems(["CYCLES", "EEVEE", "WORKBENCH"])
        form.addRow("Engine:", self._engine)

        self._samples = QSpinBox()
        self._samples.setRange(1, 8192)
        self._samples.setValue(128)
        form.addRow("Samples:", self._samples)

        self._width  = QSpinBox(); self._width.setRange(1, 8192);  self._width.setValue(1920)
        self._height = QSpinBox(); self._height.setRange(1, 8192); self._height.setValue(1080)
        res_row = QHBoxLayout()
        res_row.addWidget(self._width)
        res_row.addWidget(QLabel("x"))
        res_row.addWidget(self._height)
        form.addRow("Resolution:", res_row)

        self._out_path = QLineEdit()
        self._out_path.setPlaceholderText("/path/to/output.png")
        form.addRow("Output Path:", self._out_path)
        layout.addWidget(sg)

        btn_row = QHBoxLayout()
        apply_btn  = QPushButton("Apply Settings")
        render_btn = QPushButton("Render Still")
        anim_btn   = QPushButton("Render Animation")
        apply_btn.clicked.connect(self._apply)
        render_btn.clicked.connect(self._render)
        anim_btn.clicked.connect(self._render_anim)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(render_btn)
        btn_row.addWidget(anim_btn)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #aaa;")
        layout.addWidget(self._status)
        layout.addStretch()

    def _apply(self):
        if not self._client:
            return
        major = self._version[0]
        code = (
            self._builder.set_engine(self._engine.currentText(), major)
            + self._builder.set_resolution(self._width.value(), self._height.value())
            + self._builder.set_samples(self._samples.value())
        )
        if self._out_path.text():
            code += self._builder.set_output(self._out_path.text())
        run_in_thread(
            lambda: self._client.exec_code(code),
            on_result=lambda r: self._status.setText(
                "Settings applied" if r.success else f"Error: {r.error}"),
        )

    def _render(self):
        if not self._client:
            return
        self._status.setText("Rendering...")
        code = self._builder.render_still(self._out_path.text())
        run_in_thread(
            lambda: self._client.exec_code(code),
            on_result=lambda r: self._status.setText(
                "Render complete" if r.success else f"Error: {r.error}"),
        )

    def _render_anim(self):
        if not self._client:
            return
        self._status.setText("Rendering animation...")
        code = self._builder.render_animation()
        run_in_thread(
            lambda: self._client.exec_code(code),
            on_result=lambda r: self._status.setText(
                "Animation render complete" if r.success else f"Error: {r.error}"),
        )
