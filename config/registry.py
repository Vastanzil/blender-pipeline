"""
config/registry.py
Cross-platform config persistence.

  Windows  → %APPDATA%\\BlenderPipelineStudio\\config.json
  Linux    → ~/.config/BlenderPipelineStudio/config.json
  macOS    → ~/Library/Application Support/BlenderPipelineStudio/config.json

First run: file doesn't exist — DEFAULTS are returned transparently.
save_config() creates the directory automatically.

In-memory cache: load_config() reads from disk once and caches the result.
Subsequent get() calls return from cache — no repeated JSON file I/O during
pipeline execution.  set() keeps both cache and disk in sync.
"""
import json
import sys
from pathlib import Path
from typing import Any

from .defaults import DEFAULTS

APP_NAME = "BlenderPipelineStudio"

# In-memory cache — populated on first load_config() call.
# set() writes through to disk and updates cache.
# reset_to_defaults() clears cache so the next call re-reads from disk.
_cache: dict | None = None


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
    global _cache
    if _cache is not None:
        return _cache
    p = _config_path()
    disk: dict = {}
    if p.exists():
        try:
            disk = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            disk = {}
    _cache = {**DEFAULTS, **disk}
    return _cache


def save_config(data: dict) -> None:
    global _cache
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Merge: defaults < existing disk/cache < new data
    base = _cache if _cache is not None else {**DEFAULTS}
    merged = {**DEFAULTS, **base, **data}
    p.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    _cache = merged


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
    global _cache
    _cache = None
    p = _config_path()
    if p.exists():
        p.unlink()


def config_path_str() -> str:
    return str(_config_path())
