"""
config/registry.py
Cross-platform config persistence.

  Windows  → %APPDATA%\\BlenderPipelineStudio\\config.json
  Linux    → ~/.config/BlenderPipelineStudio/config.json
  macOS    → ~/Library/Application Support/BlenderPipelineStudio/config.json

First run: file doesn't exist — DEFAULTS are returned transparently.
save_config() creates the directory automatically.
"""
import json
import sys
from pathlib import Path
from typing import Any

from .defaults import DEFAULTS

APP_NAME = "BlenderPipelineStudio"


def _config_path() -> Path:
    try:
        from platformdirs import user_config_dir
        base = Path(user_config_dir(APP_NAME))
    except ImportError:
        if sys.platform == "win32":
            base = Path.home() / "AppData" / "Roaming" / APP_NAME
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / APP_NAME
        else:
            base = Path.home() / ".config" / APP_NAME
    return base / "config.json"


def load_config() -> dict:
    p = _config_path()
    disk: dict = {}
    if p.exists():
        try:
            disk = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            disk = {}
    return {**DEFAULTS, **disk}


def save_config(data: dict) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **load_config(), **data}
    p.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def get(key: str, default: Any = None) -> Any:
    cfg = load_config()
    if key in cfg:
        return cfg[key]
    return DEFAULTS.get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


def reset_to_defaults() -> None:
    p = _config_path()
    if p.exists():
        p.unlink()


def config_path_str() -> str:
    return str(_config_path())
