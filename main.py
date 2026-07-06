"""
main.py — Entry point for BlenderCopilot.

Launch sequence
───────────────
1. Create QApplication
2. Show StartupCheckDialog  (env checks + optional Blender ping)
   └─ all OK → "SYSTEM READY", auto-continues in 3 s
3. First run only → ConnectionPanel (enter host/port, saved permanently)
4. Show BlenderCopilot main window

Usage
─────
    python main.py
"""
import os
import sys

# Make project root importable from any working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("BlenderCopilot")
    app.setOrganizationName("VASTDEVLAB")

    # ── 1. Startup self-test ──────────────────────────────────────────────────
    from gui.panels.startup_dialog import StartupCheckDialog
    dlg = StartupCheckDialog()
    dlg.show()
    dlg.run_checks()
    dlg.exec()          # blocks until user clicks Continue / auto-close

    # ── 2. First-run connection setup ─────────────────────────────────────────
    from config.registry import get
    if not get("mcp_host", ""):
        from gui.panels.connection_panel import ConnectionPanel
        ConnectionPanel().exec()

    # ── 3. Main window ────────────────────────────────────────────────────────
    from gui.app import BlenderCopilot
    win = BlenderCopilot()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
