"""
launch.pyw — double-click launcher for BlenderCopilot.
Uses pythonw.exe so NO terminal window appears.
Place this file in the project root and double-click it.
"""
import sys
import os

# Make sure the project root is on sys.path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main
main()
