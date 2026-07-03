"""
gui/app.py
Main application window — wires all components together.
Auto-connects from saved config on startup; shows ConnectionPanel on first run.
"""
import sys
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                              QVBoxLayout, QTabWidget, QSplitter, QStatusBar,
                              QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from config.registry import get, set as reg_set
from mcp.factory import make_client
from mcp.tool_registry import ToolRegistry
from mcp.tool_executor import ToolExecutor
from ai.router import AIRouter
from pipeline.orchestrator import Orchestrator
from realtime.event_bus import EventBus
from realtime.data_bridge import DataBridge
from realtime.websocket_server import WebSocketServer

from gui.panels.connection_panel import ConnectionPanel
from gui.panels.tool_browser     import ToolBrowserPanel
from gui.panels.tool_runner      import ToolRunnerPanel
from gui.panels.ai_chat          import AIChatPanel
from gui.panels.scene_tree       import SceneTreePanel
from gui.panels.code_editor      import CodeEditorPanel
from gui.panels.log_panel        import LogPanel
from gui.panels.render_panel     import RenderPanel
from gui.widgets.status_bar      import StatusBarWidget
from utils.logger import get_logger
from utils.async_runner import run_in_thread
from realtime.qt_bridge import QtBridge

log = get_logger("app")


class BlenderPipelineStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blender Pipeline Studio")
        self.resize(1600, 960)
        self.setMinimumSize(1000, 600)

        self.client       = None
        self.registry     = None
        self.executor     = None
        self.ai           = None
        self.orchestrator = None
        self.bridge       = None
        self.ws_server    = None
        self.bus          = EventBus()
        self._workers     = []   # legacy — async_runner._live now handles lifetime

        self._build_ui()
        self._build_menu()
        self._apply_theme()

        # All bus→widget bindings go through QtBridge so background-thread
        # emits are marshalled to the GUI thread via Qt's queued connection.
        self._bus_relays = [
            QtBridge.subscribe(self.bus, "connection.ok",
                               lambda d: self.status_widget.set_connected(d["host"], d["port"])),
            QtBridge.subscribe(self.bus, "connection.fail",
                               lambda _: self.status_widget.set_disconnected()),
            QtBridge.subscribe(self.bus, "connection.error",
                               lambda _: self.status_widget.set_disconnected()),
        ]

        host = get("mcp_host", "")
        port = int(get("mcp_port", 9876))
        if host and get("auto_connect", True):
            QTimer.singleShot(400, lambda: self._connect_async(host, port))
        else:
            QTimer.singleShot(400, self._show_connection_dialog)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        main_split = QSplitter(Qt.Orientation.Horizontal)

        self.tool_browser = ToolBrowserPanel(self.bus)
        self.tool_browser.setMinimumWidth(180)
        self.tool_browser.setMaximumWidth(280)
        self.tool_browser.tool_selected.connect(self._on_tool_selected)
        self.tool_browser.set_refresh_callback(self._refresh_tools)
        main_split.addWidget(self.tool_browser)

        right_split = QSplitter(Qt.Orientation.Vertical)

        self.tabs = QTabWidget()
        self.ai_chat      = AIChatPanel(self.bus)
        self.tool_runner  = ToolRunnerPanel(self.bus)
        self.code_editor  = CodeEditorPanel(self.bus)
        self.scene_tree   = SceneTreePanel(self.bus)
        self.render_panel = RenderPanel(self.bus)
        self.tabs.addTab(self.ai_chat,      "AI Pipeline")
        self.tabs.addTab(self.tool_runner,  "Tool Runner")
        self.tabs.addTab(self.code_editor,  "Code")
        self.tabs.addTab(self.scene_tree,   "Scene")
        self.tabs.addTab(self.render_panel, "Render")
        right_split.addWidget(self.tabs)

        self.log_panel = LogPanel(self.bus)
        self.log_panel.setMaximumHeight(200)
        right_split.addWidget(self.log_panel)
        right_split.setSizes([720, 180])

        main_split.addWidget(right_split)
        main_split.setSizes([230, 1370])
        root.addWidget(main_split)

        self.status_widget = StatusBarWidget()
        sb = QStatusBar()
        sb.addPermanentWidget(self.status_widget)
        self.setStatusBar(sb)

    def _build_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        a = QAction("&Connect / Setup…", self)
        a.triggered.connect(self._show_connection_dialog)
        fm.addAction(a)
        fm.addSeparator()
        q = QAction("&Quit", self)
        q.triggered.connect(self.close)
        fm.addAction(q)

        vm = mb.addMenu("&View")
        t = QAction("Toggle Theme", self)
        t.triggered.connect(self._toggle_theme)
        vm.addAction(t)

        tm = mb.addMenu("&Tools")
        r = QAction("Refresh Tool List", self)
        r.triggered.connect(self._refresh_tools)
        tm.addAction(r)
        w = QAction("Start WebSocket Server (port 8765)", self)
        w.triggered.connect(self._start_ws)
        tm.addAction(w)

        hm = mb.addMenu("&Help")
        ab = QAction("About", self)
        ab.triggered.connect(self._show_about)
        hm.addAction(ab)

    def _apply_theme(self):
        theme = get("theme", "dark")
        p = Path(__file__).parent / "theme" / f"{theme}.qss"
        if p.exists():
            self.setStyleSheet(p.read_text(encoding="utf-8"))

    def _show_connection_dialog(self):
        ConnectionPanel(self, on_connect=self._connect).exec()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect_async(self, host: str, port: int):
        """Start connection in a background thread so the GUI stays responsive."""
        self.status_widget.set_connecting(host, port)
        log.info(f"Connecting to {host}:{port} …")

        def _do():
            client = make_client(host, port, timeout=10.0)
            ok = client.ping()
            return client, ok

        w = run_in_thread(
            _do,
            on_result=lambda r: self._on_connect_result(r[0], r[1], host, port),
            on_error=lambda e: self._on_connect_error(e, host, port),
        )
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)

    def _on_connect_result(self, client, ok: bool, host: str, port: int):
        """Called on the GUI thread after the background ping returns."""
        if not ok:
            self.bus.emit("connection.fail", {"host": host, "port": port})
            log.warning(f"blender-mcp not reachable at {host}:{port}")
            self._show_connect_fail_dialog(host, port)
            return
        self._finish_connect(client, host, port)

    def _on_connect_error(self, err: str, host: str, port: int):
        """Called on the GUI thread when the background thread raised an exception."""
        self.bus.emit("connection.error", {"error": err})
        log.error(f"Connection error: {err}")
        self._show_connect_fail_dialog(host, port, detail=err)

    def _show_connect_fail_dialog(self, host: str, port: int, detail: str = ""):
        """Show a friendly error dialog and offer to open the setup dialog."""
        msg = (
            f"<b>Cannot connect to blender-mcp</b><br><br>"
            f"Address: <code>{host}:{port}</code><br><br>"
            f"<b>To fix:</b><ol>"
            f"<li>Open <b>Blender</b></li>"
            f"<li>Press <b>N</b> to open the side panel</li>"
            f"<li>Click the <b>MCP</b> tab</li>"
            f"<li>Click <b>Start MCP Server</b></li>"
            f"</ol>"
        )
        if detail:
            msg += f"<br><small>Error: {detail}</small>"

        dlg = QMessageBox(self)
        dlg.setWindowTitle("Blender MCP — Connection Failed")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(msg)
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Retry |
            QMessageBox.StandardButton.Open  |
            QMessageBox.StandardButton.Cancel
        )
        dlg.button(QMessageBox.StandardButton.Open).setText("Connection Setup…")
        dlg.button(QMessageBox.StandardButton.Retry).setText("Retry")
        choice = dlg.exec()

        if choice == QMessageBox.StandardButton.Retry:
            self._connect_async(host, port)
        elif choice == QMessageBox.StandardButton.Open:
            self._show_connection_dialog()

    def _finish_connect(self, client, host: str, port: int):
        """Complete a successful connection — runs on the GUI thread."""
        try:
            self.client   = client
            self.registry = ToolRegistry(client).refresh()
            self.executor = ToolExecutor(client)
            self.ai       = AIRouter()
            self.orchestrator = Orchestrator(client, self.ai, self.bus)

            if self.bridge:
                self.bridge.stop()
            self.bridge = DataBridge(client, self.bus,
                                     interval=float(get("poll_interval", 2.0)))
            self.bridge.start()

            ver = client.get_blender_version()
            self.tool_runner.set_client(client, self.executor)
            self.code_editor.set_client(client)
            self.scene_tree.set_client(client)
            self.render_panel.set_client(client, ver)
            self.ai_chat.set_orchestrator(self.orchestrator, self.ai)
            self.tool_browser.load_tools(self.registry.all())

            self.status_widget.set_connected(host, port)
            self.status_widget.set_version(ver)
            self.status_widget.set_ai(self.ai.active_name)
            self.bus.emit("connection.ok", {"host": host, "port": port})
            log.info(f"Connected: Blender {ver}, {self.registry.count()} tools")

        except Exception as e:
            self.bus.emit("connection.error", {"error": str(e)})
            log.error(f"Post-connect setup error: {e}")
            self._show_connect_fail_dialog(host, port, detail=str(e))

    def _connect(self, host: str, port: int):
        """Public entry point — used by ConnectionPanel callback and menu."""
        self._connect_async(host, port)

    def _on_tool_selected(self, tool):
        self.tool_runner.load_tool(tool)
        self.tabs.setCurrentIndex(1)

    def _refresh_tools(self):
        if not self.client or not self.registry:
            return
        w = run_in_thread(
            self.registry.refresh,
            on_result=lambda _: self.tool_browser.load_tools(self.registry.all()),
        )
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)

    def _start_ws(self):
        if self.ws_server:
            return
        self.ws_server = WebSocketServer(self.bus)
        self.ws_server.start()
        log.info("WebSocket server started on ws://localhost:8765")

    def _toggle_theme(self):
        new = "light" if get("theme", "dark") == "dark" else "dark"
        reg_set("theme", new)
        self._apply_theme()

    def _show_about(self):
        QMessageBox.about(self, "About Blender Pipeline Studio",
            "<b>Blender Pipeline Studio</b><br>"
            "Full-authority Blender control via blender-mcp<br><br>"
            "Geometry Nodes · Materials · Animation · Physics · Rendering<br>"
            "AI Backends: Ollama · OpenAI · Anthropic · Gemini<br>"
            "Real-time scene sync · WebSocket streaming")

    def closeEvent(self, event):
        if self.bridge:
            self.bridge.stop()
        reg_set("window_geometry", f"{self.width()}x{self.height()}")
        event.accept()


def launch():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("BlenderPipelineStudio")
    app.setOrganizationName("VASTDEVLAB")
    win = BlenderPipelineStudio()
    win.show()
    sys.exit(app.exec())
