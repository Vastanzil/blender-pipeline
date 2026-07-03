"""
config/schema.py
Lightweight config validation — no pydantic required.
Uses dataclass + manual type coercion (stdlib only).
"""
from dataclasses import dataclass


@dataclass
class AppConfig:
    mcp_host:          str   = "localhost"
    mcp_port:          int   = 9876
    ai_backend:        str   = "ollama"
    ollama_host:       str   = "http://localhost:11434"
    coder_model:       str   = "qwen2.5-coder:7b"
    planner_model:     str   = "qwen3:8b"
    openai_api_key:    str   = ""
    anthropic_api_key: str   = ""
    gemini_api_key:    str   = ""
    output_dir:        str   = ""
    max_retries:       int   = 5
    poll_interval:     float = 2.0
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

    int_fields   = {"mcp_port", "max_retries"}
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

    if not (1 <= cfg.mcp_port <= 65535):
        warnings.append(f"mcp_port {cfg.mcp_port} out of range; reset to 9876")
        cfg.mcp_port = 9876
    if cfg.max_retries < 1:
        warnings.append("max_retries < 1; reset to 1")
        cfg.max_retries = 1
    if cfg.ai_backend not in ("ollama", "openai", "anthropic", "gemini"):
        warnings.append(f"Unknown ai_backend {cfg.ai_backend!r}; reset to ollama")
        cfg.ai_backend = "ollama"

    return cfg, warnings
