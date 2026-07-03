"""
utils/startup_check.py
======================
Self-test suite that runs at application startup (before the main window opens).
Each check is a callable that returns a CheckResult.
The checks are fast (<2 s total) and do NOT require Blender to be running —
they verify the Python environment, dependencies, and config sanity.

The optional `blender_check` is run separately (requires a live MCP server)
and is executed from the StartupCheckDialog after the others pass.
"""
from __future__ import annotations
import importlib
import sys
import time
from dataclasses import dataclass, field


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:    str
    ok:      bool
    message: str = ""
    elapsed: float = 0.0   # seconds


@dataclass
class StartupReport:
    results:  list[CheckResult] = field(default_factory=list)
    all_ok:   bool = True

    def add(self, r: CheckResult):
        self.results.append(r)
        if not r.ok:
            self.all_ok = False

    def summary(self) -> str:
        ok  = sum(1 for r in self.results if r.ok)
        tot = len(self.results)
        return f"{ok}/{tot} checks passed"


# ── Individual checks ─────────────────────────────────────────────────────────

def _check(name: str, fn) -> CheckResult:
    t0 = time.perf_counter()
    try:
        ok, msg = fn()
    except Exception as e:
        ok, msg = False, f"Exception: {e}"
    elapsed = time.perf_counter() - t0
    return CheckResult(name=name, ok=ok, message=msg, elapsed=elapsed)


def check_python_version() -> CheckResult:
    def _():
        major, minor = sys.version_info[:2]
        if (major, minor) >= (3, 11):
            return True, f"Python {major}.{minor} ✓"
        return False, f"Python {major}.{minor} — need 3.11+"
    return _check("Python version", _)


def check_pyqt6() -> CheckResult:
    def _():
        from PyQt6.QtCore import QT_VERSION_STR
        return True, f"PyQt6 OK (Qt {QT_VERSION_STR})"
    return _check("PyQt6", _)


def check_requests() -> CheckResult:
    def _():
        import requests
        return True, f"requests {requests.__version__} ✓"
    return _check("requests", _)


def check_platformdirs() -> CheckResult:
    def _():
        try:
            import platformdirs
            return True, f"platformdirs {platformdirs.__version__} ✓"
        except ImportError:
            return True, "platformdirs not installed — using stdlib fallback ✓"
    return _check("platformdirs", _)


def check_websockets() -> CheckResult:
    def _():
        try:
            import websockets
            return True, f"websockets {websockets.__version__} ✓"
        except ImportError:
            return True, "websockets not installed — WebSocket server disabled (optional)"
    return _check("websockets (optional)", _)


def check_config() -> CheckResult:
    def _():
        from config.registry import load_config
        from config.schema   import validate_config
        cfg_dict = load_config()
        cfg, warnings = validate_config(cfg_dict)
        if warnings:
            return True, f"Config OK with {len(warnings)} warning(s): {warnings[0]}"
        return True, "Config valid ✓"
    return _check("Config", _)


def check_mcp_modules() -> CheckResult:
    def _():
        for mod in ("mcp.client", "mcp.models", "mcp.tool_registry", "mcp.tool_executor"):
            importlib.import_module(mod)
        return True, "MCP modules importable ✓"
    return _check("MCP modules", _)


def check_ai_modules() -> CheckResult:
    def _():
        for mod in ("ai.router", "ai.compat_rules", "ai.context_builder"):
            importlib.import_module(mod)
        return True, "AI modules importable ✓"
    return _check("AI modules", _)


def check_pipeline_modules() -> CheckResult:
    def _():
        for mod in ("pipeline.orchestrator", "pipeline.retry_loop", "pipeline.step"):
            importlib.import_module(mod)
        return True, "Pipeline modules importable ✓"
    return _check("Pipeline modules", _)


def check_blender_modules() -> CheckResult:
    def _():
        for mod in ("blender.geometry_nodes", "blender.materials",
                    "blender.animation", "blender.render"):
            importlib.import_module(mod)
        return True, "Blender builder modules importable ✓"
    return _check("Blender builders", _)


def check_realtime_modules() -> CheckResult:
    def _():
        for mod in ("realtime.event_bus", "realtime.data_bridge"):
            importlib.import_module(mod)
        return True, "Realtime modules importable ✓"
    return _check("Realtime modules", _)


def check_code_validator() -> CheckResult:
    def _():
        from utils.code_validator import validate_bpy_code
        r = validate_bpy_code("import bpy\nbpy.ops.mesh.primitive_cube_add()")
        if r.ok:
            return True, "Code validator functional ✓"
        return False, f"Validator returned errors: {r.errors}"
    return _check("Code validator", _)


def check_output_dir() -> CheckResult:
    def _():
        from pathlib import Path
        from config.registry import get
        out = get("output_dir", "") or str(Path.home() / "blender_pipeline_output")
        p = Path(out)
        p.mkdir(parents=True, exist_ok=True)
        return True, f"Output dir: {out} ✓"
    return _check("Output directory", _)


# ── Optional live Blender check (separate — requires MCP running) ──────────────

def check_blender_connection(host: str, port: int) -> CheckResult:
    def _():
        from mcp.client import BlenderMCPClient
        c = BlenderMCPClient(host, port, timeout=5.0)
        if not c.ping():
            return False, f"No response from blender-mcp at {host}:{port}"
        ver = c.get_blender_version()
        tools = c.list_tools()
        v = ".".join(str(x) for x in ver)
        return True, f"Blender {v} connected — {len(tools)} tools ✓"
    return _check(f"Blender MCP ({host}:{port})", _)


# ── Run all environment checks ─────────────────────────────────────────────────

ENVIRONMENT_CHECKS = [
    check_python_version,
    check_pyqt6,
    check_requests,
    check_platformdirs,
    check_websockets,
    check_config,
    check_mcp_modules,
    check_ai_modules,
    check_pipeline_modules,
    check_blender_modules,
    check_realtime_modules,
    check_code_validator,
    check_output_dir,
]


def run_environment_checks() -> StartupReport:
    report = StartupReport()
    for check_fn in ENVIRONMENT_CHECKS:
        report.add(check_fn())
    return report
