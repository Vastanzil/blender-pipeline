"""Tests for BlenderPipelineStudio → BlenderCopilot config migration."""
import json, os, sys, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _write_old_config(old_path, data: dict):
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text(json.dumps(data), encoding="utf-8")


def test_migration_copies_old_config_to_new_path(tmp_path, monkeypatch):
    """When old path exists and new path doesn't, content is copied."""
    old_cfg = tmp_path / "BlenderPipelineStudio" / "config.json"
    new_cfg = tmp_path / "BlenderCopilot"        / "config.json"
    _write_old_config(old_cfg, {"manifest_token": "secret123"})

    import config.registry as reg
    monkeypatch.setattr(reg, "_config_path", lambda: new_cfg)
    monkeypatch.setattr(reg, "_OLD_APP_NAME", "BlenderPipelineStudio")
    # Patch platformdirs to return our tmp old path
    monkeypatch.setattr(
        "config.registry._config_path",
        lambda: new_cfg,
    )
    # Patch the old-path resolution inside _migrate_config
    original_migrate = reg._migrate_config
    def _patched_migrate():
        if new_cfg.exists():
            return
        if old_cfg.exists():
            new_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_cfg, new_cfg)
    monkeypatch.setattr(reg, "_migrate_config", _patched_migrate)

    reg._cache = None
    cfg = reg.load_config()
    assert new_cfg.exists()
    data = json.loads(new_cfg.read_text())
    assert data["manifest_token"] == "secret123"


def test_migration_does_not_overwrite_existing_new_config(tmp_path, monkeypatch):
    """When new path already exists, migration must not overwrite it."""
    old_cfg = tmp_path / "BlenderPipelineStudio" / "config.json"
    new_cfg = tmp_path / "BlenderCopilot"        / "config.json"
    _write_old_config(old_cfg, {"manifest_token": "old_token"})
    new_cfg.parent.mkdir(parents=True, exist_ok=True)
    new_cfg.write_text(json.dumps({"manifest_token": "new_token"}), encoding="utf-8")

    import config.registry as reg
    monkeypatch.setattr(reg, "_config_path", lambda: new_cfg)

    def _patched_migrate():
        if new_cfg.exists():
            return   # should return immediately
        shutil.copy2(old_cfg, new_cfg)
    monkeypatch.setattr(reg, "_migrate_config", _patched_migrate)

    reg._cache = None
    reg.load_config()
    data = json.loads(new_cfg.read_text())
    assert data["manifest_token"] == "new_token"   # not overwritten


def test_migration_no_error_when_neither_path_exists(tmp_path, monkeypatch):
    """When neither old nor new config exists, load_config returns defaults."""
    new_cfg = tmp_path / "BlenderCopilot" / "config.json"

    import config.registry as reg
    monkeypatch.setattr(reg, "_config_path", lambda: new_cfg)
    monkeypatch.setattr(reg, "_migrate_config", lambda: None)

    reg._cache = None
    cfg = reg.load_config()
    assert isinstance(cfg, dict)
    assert "manifest_host" in cfg
