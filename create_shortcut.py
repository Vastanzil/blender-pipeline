"""
create_shortcut.py
==================
Run once:  python create_shortcut.py
Creates a desktop shortcut that launches Blender Pipeline Studio
with NO terminal window.

Requires pywin32:  pip install pywin32
(Already included in requirements-dev.txt — or install manually.)
"""
import sys
import os
from pathlib import Path


def main():
    try:
        import win32com.client
    except ImportError:
        print("Installing pywin32 …")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "-q"])
        import win32com.client

    project_dir  = Path(__file__).parent.resolve()
    pythonw      = Path(sys.executable).parent / "pythonw.exe"
    launcher     = project_dir / "launch.pyw"
    desktop      = Path.home() / "Desktop"
    shortcut_path = desktop / "Blender Pipeline Studio.lnk"

    if not pythonw.exists():
        # Fallback: same dir as python.exe but named pythonw
        pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        print(f"WARNING: pythonw.exe not found next to {sys.executable}")
        print("Shortcut will use python.exe (terminal window will briefly appear).")
        pythonw = Path(sys.executable)

    shell    = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))
    shortcut.TargetPath       = str(pythonw)
    shortcut.Arguments        = f'"{launcher}"'
    shortcut.WorkingDirectory = str(project_dir)
    shortcut.Description      = "Blender Pipeline Studio — AI-powered Blender GUI"

    # Try to use the project icon if it exists, else fall back to pythonw icon
    icon_candidates = [
        project_dir / "assets" / "icon.ico",
        project_dir / "icon.ico",
        pythonw,
    ]
    for ic in icon_candidates:
        if ic.exists():
            shortcut.IconLocation = str(ic)
            break

    shortcut.WindowStyle = 1   # Normal window (not minimised / maximised)
    shortcut.save()

    print(f"Shortcut created:  {shortcut_path}")
    print(f"  Target   : {pythonw}")
    print(f"  Arguments: \"{launcher}\"")
    print(f"  WorkDir  : {project_dir}")
    print()
    print("Double-click 'Blender Pipeline Studio' on your Desktop to launch.")


if __name__ == "__main__":
    main()
