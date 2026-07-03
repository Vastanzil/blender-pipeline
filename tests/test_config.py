"""Tests for config registry and schema validation."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_defaults_all_present():
    from config.defaults import DEFAULTS
    required = ["mcp_host", "mcp_port", "ai_backend", "ollama_host",
                "coder_model", "planner_model", "max_retries", "theme"]
    for k in required:
        assert k in DEFAULTS, f"Missing default: {k}"


def test_defaults_types():
    from config.defaults import DEFAULTS
    assert isinstance(DEFAULTS["mcp_port"],    int)
    assert isinstance(DEFAULTS["mcp_host"],    str)
    assert isinstance(DEFAULTS["max_retries"], int)
    assert isinstance(DEFAULTS["poll_interval"], float)
    assert isinstance(DEFAULTS["auto_connect"], bool)


def test_load_config_returns_defaults_when_no_file(monkeypatch, tmp_path):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("config.registry._config_path", lambda: config_file)
    from config.registry import load_config
    cfg = load_config()
    assert cfg["mcp_host"] == "localhost"
    assert cfg["mcp_port"] == 9876


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("config.registry._config_path", lambda: config_file)
    from config.registry import save_config, load_config
    save_config({"mcp_host": "192.168.1.50", "mcp_port": 9999})
    cfg = load_config()
    assert cfg["mcp_host"] == "192.168.1.50"
    assert cfg["mcp_port"] == 9999


def test_get_set(monkeypatch, tmp_path):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("config.registry._config_path", lambda: config_file)
    import config.registry as reg
    reg.set("theme", "light")
    assert reg.get("theme") == "light"
    reg.set("theme", "dark")
    assert reg.get("theme") == "dark"


def test_get_returns_default_for_unknown_key(monkeypatch, tmp_path):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("config.registry._config_path", lambda: config_file)
    from config.registry import get
    assert get("nonexistent_key_xyz", "fallback") == "fallback"


def test_schema_valid():
    from config.schema import validate_config
    cfg, warnings = validate_config({"mcp_port": 9876, "ai_backend": "ollama"})
    assert cfg.mcp_port == 9876
    assert cfg.ai_backend == "ollama"


def test_schema_invalid_port_resets():
    from config.schema import validate_config
    cfg, warnings = validate_config({"mcp_port": 99999})
    assert cfg.mcp_port == 9876
    assert any("mcp_port" in w for w in warnings)


def test_schema_invalid_port_zero():
    from config.schema import validate_config
    cfg, warnings = validate_config({"mcp_port": 0})
    assert cfg.mcp_port == 9876


def test_schema_invalid_backend_resets():
    from config.schema import validate_config
    cfg, warnings = validate_config({"ai_backend": "unknown_llm"})
    assert cfg.ai_backend == "ollama"
    assert any("ai_backend" in w for w in warnings)


def test_schema_unknown_key_warns():
    from config.schema import validate_config
    cfg, warnings = validate_config({"totally_fake_key": "value"})
    assert any("totally_fake_key" in w for w in warnings)


def test_schema_coerces_string_port():
    from config.schema import validate_config
    cfg, warnings = validate_config({"mcp_port": "9876"})
    assert cfg.mcp_port == 9876
    assert isinstance(cfg.mcp_port, int)


def test_save_creates_directory(monkeypatch, tmp_path):
    nested = tmp_path / "deep" / "nested" / "config.json"
    monkeypatch.setattr("config.registry._config_path", lambda: nested)
    from config.registry import save_config
    save_config({"mcp_host": "test"})
    assert nested.exists()
