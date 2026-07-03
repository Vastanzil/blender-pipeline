"""gui/widgets/status_bar.py — Connection + engine status widget for the status bar."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StatusBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(20)

        self._conn  = QLabel("● Disconnected")
        self._ver   = QLabel("")
        self._ai    = QLabel("")
        for lbl in (self._conn, self._ver, self._ai):
            lbl.setStyleSheet("color: #888;")
            layout.addWidget(lbl)
        layout.addStretch()

    def set_connected(self, host, port):
        self._conn.setText(f"● {host}:{port}")
        self._conn.setStyleSheet("color: #4caf50; font-weight: bold;")

    def set_disconnected(self):
        self._conn.setText("● Disconnected")
        self._conn.setStyleSheet("color: #f44336; font-weight: bold;")

    def set_version(self, ver):
        self._ver.setText(f"Blender {'.'.join(str(v) for v in ver)}")
        self._ver.setStyleSheet("color: #aaa;")

    def set_ai(self, name):
        self._ai.setText(f"AI: {name}")
        self._ai.setStyleSheet("color: #aaa;")
