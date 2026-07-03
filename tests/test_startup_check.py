"""Tests for the startup self-test system."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_check_result_dataclass():
    from utils.startup_check import CheckResult
    r = CheckResult(name="Test", ok=True, message="All good", elapsed=0.01)
    assert r.ok is True
    assert r.name == "Test"
    assert r.elapsed == 0.01


def test_report_all_ok():
    from utils.startup_check import StartupReport, CheckResult
    rep = StartupReport()
    rep.add(CheckResult("A", True,  "ok"))
    rep.add(CheckResult("B", True,  "ok"))
    assert rep.all_ok is True
    assert "2/2" in rep.summary()


def test_report_one_failure():
    from utils.startup_check import StartupReport, CheckResult
    rep = StartupReport()
    rep.add(CheckResult("A", True,  "ok"))
    rep.add(CheckResult("B", False, "bad"))
    assert rep.all_ok is False
    assert "1/2" in rep.summary()


def test_check_python_version():
    from utils.startup_check import check_python_version
    r = check_python_version()
    assert r.ok is True   # we're running on 3.11+ (test env)
    assert "Python" in r.message


def test_check_pyqt6():
    from utils.startup_check import check_pyqt6
    r = check_pyqt6()
    assert r.ok is True
    assert "PyQt6" in r.message or "Qt" in r.message


def test_check_requests():
    from utils.startup_check import check_requests
    r = check_requests()
    assert r.ok is True
    assert "requests" in r.message


def test_check_config():
    from utils.startup_check import check_config
    r = check_config()
    assert r.ok is True


def test_check_mcp_modules():
    from utils.startup_check import check_mcp_modules
    r = check_mcp_modules()
    assert r.ok is True


def test_check_ai_modules():
    from utils.startup_check import check_ai_modules
    r = check_ai_modules()
    assert r.ok is True


def test_check_pipeline_modules():
    from utils.startup_check import check_pipeline_modules
    r = check_pipeline_modules()
    assert r.ok is True


def test_check_blender_modules():
    from utils.startup_check import check_blender_modules
    r = check_blender_modules()
    assert r.ok is True


def test_check_realtime_modules():
    from utils.startup_check import check_realtime_modules
    r = check_realtime_modules()
    assert r.ok is True


def test_check_code_validator():
    from utils.startup_check import check_code_validator
    r = check_code_validator()
    assert r.ok is True


def test_check_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("config.registry._config_path",
                        lambda: tmp_path / "config.json")
    from utils.startup_check import check_output_dir
    r = check_output_dir()
    assert r.ok is True


def test_run_environment_checks_all_pass():
    from utils.startup_check import run_environment_checks
    report = run_environment_checks()
    assert report.all_ok is True
    assert len(report.results) == 13   # 13 environment checks
    failures = [r for r in report.results if not r.ok]
    assert failures == [], f"Unexpected failures: {[r.name for r in failures]}"


def test_check_blender_connection_fails_gracefully():
    """Should return ok=False cleanly when no server is running (not raise)."""
    from utils.startup_check import check_blender_connection
    r = check_blender_connection("localhost", 19999)  # nothing running there
    assert r.ok is False
    assert r.name != ""
    assert isinstance(r.message, str)
