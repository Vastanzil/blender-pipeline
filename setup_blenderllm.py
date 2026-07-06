"""
setup_blenderllm.py - one-shot installer for the local BlenderLLM server.

Usage:
    python setup_blenderllm.py

What it does (no compilation, no GPU required):
  0. Preflight checks (Python, disk space >=6 GB, internet)
  1. Choose install directory  (default: <this folder>/blenderllm)
  2. Download llama-server binaries from llama.cpp GitHub release (~17 MB zip)
  3. Download BlenderLLM-Q4_K_M.gguf from Hugging Face (~4.68 GB)
  4. Write start_blenderllm.bat / .sh launch scripts
  5. Start server and health-check
  6. Persist blenderllm_home + blenderllm_server_url to app config
"""

import sys
import shutil
import subprocess
import time
import json
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT       = Path(__file__).parent.resolve()
DEFAULT_INSTALL = REPO_ROOT / "blenderllm"

LLAMA_RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
LLAMA_ASSET_NAME  = "win-cpu-x64.zip"   # substring matched against asset names

HF_GGUF_URL = (
    "https://huggingface.co/mradermacher/BlenderLLM-GGUF"
    "/resolve/main/BlenderLLM.Q4_K_M.gguf"
)
GGUF_SIZE_HINT = "~4.68 GB"

SERVER_HOST    = "127.0.0.1"
SERVER_PORT    = 8080
SERVER_URL     = f"http://{SERVER_HOST}:{SERVER_PORT}"
MIN_FREE_GB    = 6
HEALTH_RETRIES = 18   # x 5 s = 90 s max wait

# DLLs required at runtime by llama-server
_KEEP = {
    "llama-server.exe",
    "llama-server-impl.dll",
    "llama.dll",
    "llama-common.dll",
    "ggml-base.dll",
    "ggml.dll",
    "mtmd.dll",
    "libomp140.x86_64.dll",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _step(n, msg):
    print(f"\n[{n}/6] {msg}")


def _ok(msg):
    print(f"  OK   {msg}")


def _warn(msg):
    print(f"  WARN {msg}", file=sys.stderr)


def _die(msg, hint=""):
    print(f"\n[ERROR] {msg}", file=sys.stderr)
    if hint:
        print(f"        {hint}", file=sys.stderr)
    sys.exit(1)


def _confirm(prompt):
    ans = input(f"{prompt} [y/N] ").strip().lower()
    return ans in ("y", "yes")


def _download(url, dst, label):
    """Download url -> dst with a simple progress printout."""
    dst = Path(dst)
    prev = [0]

    def _hook(count, block, total):
        done = count * block
        pct  = int(done / total * 100) if total > 0 else 0
        if pct // 10 != prev[0] // 10:
            prev[0] = pct
            print(f"    {pct}%  ({done/1e9:.2f} GB)")

    print(f"  Downloading {label} ...")
    urllib.request.urlretrieve(url, dst, reporthook=_hook)
    _ok(f"Saved to {dst}  ({dst.stat().st_size/1e9:.2f} GB)")


# ---------------------------------------------------------------------------
# Step 0 - Preflight
# ---------------------------------------------------------------------------
def step0_preflight():
    _step(0, "Preflight checks")

    if sys.version_info < (3, 11):
        _die(f"Python >= 3.11 required; found {sys.version}")
    _ok(f"Python {sys.version.split()[0]}")

    try:
        urllib.request.urlopen("https://huggingface.co", timeout=10)
        _ok("Internet reachable")
    except Exception:
        _warn("Cannot reach huggingface.co - downloads will likely fail.")


# ---------------------------------------------------------------------------
# Step 1 - Resolve install directory
# ---------------------------------------------------------------------------
def step1_install_dir():
    _step(1, "Choose install directory")
    raw = input(f"  Install to [{DEFAULT_INSTALL}]: ").strip()
    install_dir = Path(raw).resolve() if raw else DEFAULT_INSTALL

    usage = shutil.disk_usage(install_dir.anchor)
    free_gb = usage.free / (1024 ** 3)
    if free_gb < MIN_FREE_GB:
        _warn(f"Only {free_gb:.1f} GB free on {install_dir.anchor} (need >= {MIN_FREE_GB} GB)")
        if not _confirm("  Continue anyway?"):
            _die("Aborted - free up disk space and rerun.")
    else:
        _ok(f"{free_gb:.1f} GB free on {install_dir.anchor}")

    (install_dir / "models").mkdir(parents=True, exist_ok=True)
    (install_dir / "server").mkdir(parents=True, exist_ok=True)
    _ok(f"Install directory: {install_dir}")
    return install_dir


# ---------------------------------------------------------------------------
# Step 2 - Download llama-server binaries
# ---------------------------------------------------------------------------
def step2_download_server(install_dir):
    _step(2, "Download llama-server binaries (llama.cpp prebuilt release)")

    server_dir  = install_dir / "server"
    server_exe  = server_dir / "llama-server.exe"

    # Skip only when every required file is already present
    if server_exe.exists() and server_exe.stat().st_size > 1000:
        missing = [f for f in _KEEP if not (server_dir / f).exists()]
        if not missing:
            _ok("llama-server binaries already present - skipping.")
            return
        _warn(f"Missing runtime files: {', '.join(missing)} - re-downloading.")

    # Fetch the latest release metadata
    print("  Looking up latest llama.cpp release ...")
    try:
        req  = urllib.request.Request(LLAMA_RELEASE_API,
                                      headers={"User-Agent": "BlenderCopilot-Setup"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        _die(f"Could not fetch llama.cpp release info: {exc}",
             "Check your internet connection and try again.")

    tag  = data.get("tag_name", "unknown")
    url  = None
    for asset in data.get("assets", []):
        if LLAMA_ASSET_NAME in asset["name"]:
            url = asset["browser_download_url"]
            name = asset["name"]
            break

    if not url:
        _die(f"Could not find '{LLAMA_ASSET_NAME}' in release {tag}",
             "Check https://github.com/ggml-org/llama.cpp/releases")

    print(f"  Release: {tag}  asset: {name}")
    zip_path = server_dir / "llama-prebuilt.zip"
    _download(url, zip_path, name)

    # Extract only what is needed at runtime
    print("  Extracting runtime files ...")
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            fname = Path(info.filename).name
            if not fname:
                continue
            keep = fname in _KEEP or fname.startswith("ggml-cpu-")
            if keep:
                (server_dir / fname).write_bytes(zf.read(info.filename))

    zip_path.unlink()
    _ok(f"Server binaries installed to {server_dir}")


# ---------------------------------------------------------------------------
# Step 3 - Download GGUF model
# ---------------------------------------------------------------------------
def step3_download_gguf(install_dir):
    _step(3, f"Download BlenderLLM-Q4_K_M.gguf ({GGUF_SIZE_HINT})")

    gguf = install_dir / "models" / "BlenderLLM-Q4_K_M.gguf"
    if gguf.exists() and gguf.stat().st_size > 1_000_000_000:
        _ok(f"Model already present ({gguf.stat().st_size/1e9:.2f} GB) - skipping.")
        return gguf

    if not _confirm(f"  Download {GGUF_SIZE_HINT} model from Hugging Face?"):
        _die("Aborted - rerun when ready to download.")

    _download(HF_GGUF_URL, gguf, "BlenderLLM-Q4_K_M.gguf")
    return gguf


# ---------------------------------------------------------------------------
# Step 4 - Write launch scripts
# ---------------------------------------------------------------------------
def step4_write_scripts(install_dir, gguf_path):
    _step(4, "Write launch scripts")

    rel_gguf  = gguf_path.relative_to(install_dir)
    rel_posix = rel_gguf.as_posix()

    bat = install_dir / "start_blenderllm.bat"
    bat.write_text(
        "@echo off\r\n"
        "REM BlenderCopilot - local BlenderLLM server\r\n"
        f"REM Serves model at http://{SERVER_HOST}:{SERVER_PORT}\r\n"
        'cd /d "%~dp0"\r\n'
        f'server\\llama-server.exe -m "{rel_gguf}" ^\r\n'
        f"  --host {SERVER_HOST} --port {SERVER_PORT} ^\r\n"
        "  --ctx-size 4096 --n-predict 1024 ^\r\n"
        "  --threads 6\r\n"
        "pause\r\n",
        encoding="utf-8",
    )
    _ok(f"Wrote {bat.name}")

    sh = install_dir / "start_blenderllm.sh"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        "# BlenderCopilot - local BlenderLLM server\n"
        'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        f'"$DIR/server/llama-server" -m "$DIR/{rel_posix}" \\\n'
        f"  --host {SERVER_HOST} --port {SERVER_PORT} \\\n"
        "  --ctx-size 4096 --n-predict 1024 \\\n"
        "  --threads 6\n",
        encoding="utf-8",
    )
    _ok(f"Wrote {sh.name}")


# ---------------------------------------------------------------------------
# Step 5 - Start server + health-check
# ---------------------------------------------------------------------------
def step5_start_and_verify(install_dir, gguf_path):
    _step(5, "Start llama-server and verify")

    if not _confirm(f"  Start server at {SERVER_URL}?"):
        _warn("Skipping server start - run start_blenderllm.bat manually later.")
        return False

    server_exe = install_dir / "server" / "llama-server.exe"
    if not server_exe.exists():
        _warn(f"llama-server.exe not found at {server_exe} - skipping start.")
        return False

    proc = subprocess.Popen([
        str(server_exe),
        "-m", str(gguf_path),
        "--host", SERVER_HOST,
        "--port", str(SERVER_PORT),
        "--ctx-size", "4096",
        "--threads", "6",
    ])

    print(f"  Waiting for server (up to {HEALTH_RETRIES * 5} s) ...")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from ai.blenderllm_client import BlenderLLMClient  # type: ignore[import]
        client = BlenderLLMClient(SERVER_URL, timeout=10)
    except ImportError:
        _warn("BlenderLLMClient not importable - skipping health-check.")
        return True

    for _ in range(HEALTH_RETRIES):
        time.sleep(5)
        if client.health():
            _ok(f"Server is up at {SERVER_URL}")
            return True

    _warn(f"Server did not respond after {HEALTH_RETRIES * 5} s.")
    _warn("Run start_blenderllm.bat manually and check for errors.")
    proc.terminate()
    return False


# ---------------------------------------------------------------------------
# Step 6 - Persist config
# ---------------------------------------------------------------------------
def step6_persist_config(install_dir):
    _step(6, "Persist app config")
    try:
        from config.registry import set as reg_set
        reg_set("blenderllm_home",       str(install_dir))
        reg_set("blenderllm_server_url", SERVER_URL)
        reg_set("blenderllm_timeout",    180)
        _ok("Config saved (blenderllm_home, blenderllm_server_url, blenderllm_timeout)")
        _ok("Enable Hybrid Mode in BlenderCopilot Connection Settings to use it.")
    except Exception as exc:
        _warn(f"Could not write app config: {exc}")
        _warn("Set these manually in BlenderCopilot Connection Settings:")
        _warn(f"  blenderllm_home       = {install_dir}")
        _warn(f"  blenderllm_server_url = {SERVER_URL}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  BlenderCopilot - BlenderLLM Setup")
    print("  No compilation or GPU required.")
    print("=" * 60)

    step0_preflight()
    install_dir = step1_install_dir()
    step2_download_server(install_dir)
    gguf_path   = step3_download_gguf(install_dir)
    step4_write_scripts(install_dir, gguf_path)
    step5_start_and_verify(install_dir, gguf_path)
    step6_persist_config(install_dir)

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print(f"  Model:      {gguf_path}")
    print(f"  Server:     {SERVER_URL}")
    print("  Next: open BlenderCopilot -> Connection Settings")
    print("        set Coder Backend = BlenderLLM (local)")
    print("=" * 60)


if __name__ == "__main__":
    main()
