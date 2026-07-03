@echo off
REM Blender Pipeline Studio — silent launcher
REM Double-click this if .pyw doesn't work on your system.
cd /d "%~dp0"
start "" pythonw.exe "%~dp0launch.pyw"
