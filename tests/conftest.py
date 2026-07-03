"""
conftest.py — pytest configuration for Blender Pipeline Studio tests.
Adds the project root to sys.path so all imports work without installing.
"""
import sys
import os

# Project root is one directory above this conftest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
