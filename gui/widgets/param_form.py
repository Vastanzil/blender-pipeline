"""
gui/widgets/param_form.py
Auto-generates a Qt form from a Tool's JSON schema parameter list.
Used by ToolRunnerPanel to build the correct input widget for every MCP tool.
"""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QSpinBox,
                              QDoubleSpinBox, QComboBox, QTextEdit,
                              QCheckBox, QLabel)
from mcp.models import Tool, ToolParam


class ParamForm(QWidget):
    def __init__(self, tool: Tool, parent=None):
        super().__init__(parent)
        self.tool    = tool
        self._fields: dict = {}
        self._build()

    def _build(self):
        layout = QFormLayout(self)
        layout.setSpacing(8)
        if not self.tool.params:
            layout.addRow(QLabel("(no parameters)"))
            return
        for param in self.tool.params:
            widget = self._make_widget(param)
            self._fields[param.name] = widget
            req = " *" if param.required else ""
            lbl = QLabel(f"{param.name}{req}:")
            if param.description:
                lbl.setToolTip(param.description)
            layout.addRow(lbl, widget)

    def _make_widget(self, p: ToolParam):
        if p.enum:
            w = QComboBox()
            w.addItems([str(e) for e in p.enum])
            if p.default is not None:
                w.setCurrentText(str(p.default))
            return w
        if p.type == "integer":
            w = QSpinBox()
            w.setRange(-9_999_999, 9_999_999)
            if p.default is not None:
                try: w.setValue(int(p.default))
                except Exception: pass
            return w
        if p.type == "number":
            w = QDoubleSpinBox()
            w.setRange(-9_999_999.0, 9_999_999.0)
            w.setDecimals(4)
            if p.default is not None:
                try: w.setValue(float(p.default))
                except Exception: pass
            return w
        if p.type == "boolean":
            w = QCheckBox()
            if p.default:
                w.setChecked(bool(p.default))
            return w
        if p.type in ("object", "array") or p.name in ("code", "script"):
            w = QTextEdit()
            w.setMinimumHeight(80)
            w.setMaximumHeight(200)
            if p.default:
                w.setText(str(p.default))
            return w
        w = QLineEdit()
        if p.default is not None:
            w.setText(str(p.default))
        if p.description:
            w.setPlaceholderText(p.description[:70])
        return w

    def get_values(self) -> dict:
        out = {}
        for name, widget in self._fields.items():
            if isinstance(widget, QComboBox):
                out[name] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                out[name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                out[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                out[name] = widget.isChecked()
            elif isinstance(widget, QTextEdit):
                out[name] = widget.toPlainText()
            else:
                out[name] = widget.text()
        return out

    def clear_values(self):
        for w in self._fields.values():
            if isinstance(w, QLineEdit):
                w.clear()
            elif isinstance(w, QTextEdit):
                w.clear()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(0)
            elif isinstance(w, QCheckBox):
                w.setChecked(False)
