"""
config/schema.py
Lightweight config validation — no pydantic required.
Uses dataclass + manual type coercion (stdlib only).
"""
from dataclasses import dataclass

_VALID_BACKENDS = {"manifest"}
_VALID_MODES    = {"auto", "mcpo", "direct"}


@dataclass
class AppConfig:
    # MCP connection
    mcp_host:          str   = "localhost"
    mcp_port:          int   = 8000
    connection_mode:   str   = "auto"       # "auto" | "mcpo" | "direct"

    # AI backend (Manifest only)
    ai_backend:        str   = "manifest"

    # Manifest AI router
    manifest_host:     str   = "http://localhost:2099"
    manifest_token:    str   = ""
    manifest_model:    str   = "auto"

    # Pipeline behaviour
    max_retries:       int   = 5
    poll_interval:     float = 2.0
    ai_timeout:        int   = 120          # seconds per AI request

    # Output
    output_dir:        str   = ""

    # UI
    theme:             str   = "dark"
    window_geometry:   str   = "1600x900"
    last_prompt:       str   = ""
    auto_connect:      bool  = True
    stream_ai:         bool  = True
    log_level:         str   = "INFO"


def validate_config(raw: dict) -> tuple:
    """
    Coerce raw dict into AppConfig; return (AppConfig, [warnings]).
    Never raises — always returns a usable config.
    """
    warnings: list = []
    cfg = AppConfig()

    int_fields   = {"mcp_port", "max_retries", "ai_timeout"}
    float_fields = {"poll_interval"}
    bool_fields  = {"auto_connect", "stream_ai"}

    for key, val in raw.items():
        if not hasattr(cfg, key):
            warnings.append(f"Unknown config key ignored: {key!r}")
            continue
        try:
            if key in int_fields:
                val = int(val)
            elif key in float_fields:
                val = float(val)
            elif key in bool_fields:
                val = bool(val) if not isinstance(val, str) else val.lower() == "true"
            setattr(cfg, key, val)
        except (ValueError, TypeError) as e:
            warnings.append(f"Config key {key!r} invalid value {val!r}: {e}")

    # Range checks
    if not (1 <= cfg.mcp_port <= 65535):
        warnings.append(f"mcp_port {cfg.mcp_port} out of range; reset to 8000")
        cfg.mcp_port = 8000
    if cfg.max_retries < 1:
        warnings.append("max_retries < 1; reset to 1")
        cfg.max_retries = 1
    if cfg.ai_timeout < 5:
        warnings.append("ai_timeout < 5; reset to 30")
        cfg.ai_timeout = 30
    if cfg.ai_backend not in _VALID_BACKENDS:
        warnings.append(
            f"Unknown ai_backend {cfg.ai_backend!r}; reset to manifest.")
        cfg.ai_backend = "manifest"
    if cfg.connection_mode not in _VALID_MODES:
        warnings.append(
            f"Unknown connection_mode {cfg.connection_mode!r}; reset to auto.")
        cfg.connection_mode = "auto"

    return cfg, warnings
