"""gui/panels/tool_browser.py — Searchable list of all MCP tools discovered at runtime."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget,
                              QListWidgetItem, QLineEdit, QLabel, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal


class ToolBrowserPanel(QWidget):
    tool_selected = pyqtSignal(object)

    def __init__(self, bus=None, parent=None):
        super().__init__(parent)
        self._tools = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        hdr = QLabel("Tools")
        hdr.setStyleSheet("font-weight: bold; font-size: 13px; color: #3a7bd5;")
        layout.addWidget(hdr)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tools...")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._count = QLabel("0 tools")
        self._count.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._count)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_click)
        layout.addWidget(self._list)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setMaximumHeight(28)
        layout.addWidget(self._refresh_btn)

    def set_refresh_callback(self, fn):
        self._refresh_btn.clicked.connect(fn)

    def load_tools(self, tools: list):
        self._tools = tools
        self._render(tools)

    def _render(self, tools):
        self._list.clear()
        for tool in tools:
            item = QListWidgetItem(f"  {tool.name}")
            item.setData(Qt.ItemDataRole.UserRole, tool)
            item.setToolTip(tool.description or tool.name)
            self._list.addItem(item)
        n = len(tools)
        self._count.setText(f"{n} tool{'s' if n != 1 else ''}")

    def _filter(self, text):
        if not text:
            self._render(self._tools)
            return
        q = text.lower()
        matched = [t for t in self._tools
                   if q in t.name.lower() or q in (t.description or "").lower()]
        self._render(matched)
        total = len(self._tools)
        n = len(matched)
        self._count.setText(f"{n} of {total} tool{'s' if total != 1 else ''}")

    def _on_click(self, item):
        tool = item.data(Qt.ItemDataRole.UserRole)
        if tool:
            self.tool_selected.emit(tool)
