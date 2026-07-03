"""gui/panels/scene_tree.py — Live Blender scene hierarchy viewer."""
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTreeWidget, QTreeWidgetItem)


class SceneTreePanel(QWidget):
    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._client = None
        self._build()
        if bus:
            bus.subscribe("scene.updated", lambda d: self._update(d.get("scene")))

    def set_client(self, client):
        self._client = client

    def _build(self):
        layout = QVBoxLayout(self)

        hdr = QHBoxLayout()
        title = QLabel("Scene")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3a7bd5;")
        refresh = QPushButton("Refresh")
        refresh.setMaximumWidth(80)
        refresh.clicked.connect(self._refresh)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(refresh)
        layout.addLayout(hdr)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Type", "Visible"])
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnWidth(1, 90)
        layout.addWidget(self._tree)

    def _refresh(self):
        if not self._client:
            return
        from utils.async_runner import run_in_thread
        run_in_thread(self._client.get_scene_info,
                      on_result=lambda r: self._update(r.output),
                      on_error=lambda _: None)

    def _update(self, scene_data):
        self._tree.clear()
        if not scene_data:
            return
        raw = scene_data
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return
        if not isinstance(raw, dict):
            return
        for obj in raw.get("objects", []):
            if not isinstance(obj, dict):
                continue
            QTreeWidgetItem(self._tree, [
                obj.get("name", "?"),
                obj.get("type", "?"),
                "yes" if obj.get("visible", True) else "no",
            ])
