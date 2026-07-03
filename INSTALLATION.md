# Installation Guide — Windows

This guide takes you from zero to a running Blender Pipeline Studio on Windows.
Estimated time: **10–15 minutes**.

---

## Prerequisites

| Requirement | Minimum version | Download |
|---|---|---|
| **Python** | 3.11 | https://www.python.org/downloads/ |
| **Blender** | 4.0 or 5.x | https://www.blender.org/download/ |
| **Git** (optional) | any | https://git-scm.com/ |
| **Ollama** (optional, for local AI) | any | https://ollama.ai |

---

## Step 1 — Install Python

1. Download Python 3.11 or newer from https://www.python.org/downloads/
2. Run the installer
3. ✅ **Check "Add Python to PATH"** on the first screen — this is critical
4. Click **Install Now**
5. Verify:
   ```
   python --version
   ```
   You should see `Python 3.11.x` or higher.

---

## Step 2 — Get the Project

**Option A — Git clone (recommended)**
```bash
git clone https://github.com/Vastanzil/blender-pipeline.git
cd blender-pipeline
```

**Option B — Download ZIP**
1. Go to https://github.com/Vastanzil/blender-pipeline
2. Click **Code → Download ZIP**
3. Extract to a folder, e.g. `D:\PROJECTS\BLENDER PIPELINE\`
4. Open PowerShell in that folder

---

## Step 3 — Install Python Dependencies

In the project folder run:

```bash
pip install -r requirements.txt
```

This installs:
- `PyQt6` — desktop GUI framework
- `requests` — HTTP client
- `platformdirs` — cross-platform config directory
- `websockets` — optional WebSocket broadcast server

> **Tip:** Use a virtual environment to keep dependencies isolated:
> ```bash
> python -m venv .venv
> .venv\Scripts\activate
> pip install -r requirements.txt
> ```

---

## Step 4 — Install blender-mcp Inside Blender

**blender-mcp** is the Blender addon that exposes Blender's Python API as a local server.

### 4a. Download the addon

Go to: https://github.com/ahujasid/blender-mcp
Click **Code → Download ZIP**.

### 4b. Install in Blender

1. Open **Blender**
2. Go to **Edit → Preferences → Add-ons**
3. Click **Install…**
4. Select the downloaded ZIP
5. Enable the addon by checking its checkbox

### 4c. Start the MCP server

1. In Blender, open the **N panel** (press `N` in the 3D Viewport)
2. Find the **MCP** tab
3. Click **Start MCP Server**
4. Note the port shown (default **9876**)

---

## Step 5 — Set Up mcpo (Recommended)

**mcpo** wraps the blender-mcp server as a standard REST API that this app uses on **port 8000**.
This is the recommended connection mode.

### 5a. Install mcpo

```bash
pip install mcpo
```

### 5b. Find your blender-mcp executable

After installing blender-mcp in a virtual environment, the executable is at:
```
<your-venv>\Scripts\blender-mcp.exe
```

Example path: `D:\GAMEDEV\AI\MCP\blender-mcp\.venv\Scripts\blender-mcp.exe`

### 5c. Launch mcpo

```bash
mcpo --port 8000 -- "D:\GAMEDEV\AI\MCP\blender-mcp\.venv\Scripts\blender-mcp.exe"
```

You should see:
```
mcpo launched (PID xxxx)
MCPO confirmed on port 8000
```

> **Tip:** Save this as a `.bat` file so you can launch mcpo with one click:
> ```bat
> @echo off
> mcpo --port 8000 -- "D:\GAMEDEV\AI\MCP\blender-mcp\.venv\Scripts\blender-mcp.exe"
> pause
> ```

### 5d. Verify mcpo is working

Open a browser and go to: http://localhost:8000/openapi.json
You should see a large JSON document listing all available Blender tools.

---

## Step 6 — (Optional) Install Ollama for Local AI

Ollama runs AI models locally — no API key, no internet required.

1. Download from https://ollama.ai and install
2. Pull a model (Ollama will auto-select the best available):
   ```bash
   ollama pull qwen2.5-coder:7b    # recommended for code generation
   ollama pull qwen3:8b             # recommended for planning
   ```
   > **Note:** The app automatically detects which models you have installed and uses the best available one. You do not need to configure model names manually.

**Alternative models if the above are too large:**
```bash
ollama pull codellama:7b
ollama pull llama3.2:3b
```

Ollama runs as a background service automatically after install.

---

## Step 7 — (Optional) Cloud AI API Keys

If you want to use OpenAI, Anthropic, or Gemini:

1. Copy `.env.example` to `.env`
2. Fill in your key(s):
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GEMINI_API_KEY=AIza...
   ```

---

## Step 8 — Launch

### Option A — One click (recommended)

Double-click **`launch.pyw`** in the project folder.
No terminal window appears.

### Option B — Create a Desktop shortcut

Run once:
```bash
python create_shortcut.py
```
This creates **"Blender Pipeline Studio"** on your Desktop.

### Option C — From terminal

```powershell
python main.py
```

---

## First Launch Sequence

**1. Startup Self-Test Dialog**

The app runs 13 automated checks:

```
✓  Python version         Python 3.11.x
✓  PyQt6                  PyQt6 OK (Qt 6.x)
✓  requests               requests 2.x
✓  platformdirs           platformdirs OK
✓  websockets (optional)  websockets OK
✓  Config                 Config valid
✓  MCP modules            importable
✓  AI modules             importable
✓  Pipeline modules       importable
✓  Blender builders       importable
✓  Realtime modules       importable
✓  Code validator         functional
✓  Output directory       writable
✓  Blender MCP (...)      Blender 5.1.2 — 22 tools  [mcpo] ✓

✓  SYSTEM READY   (auto-continues in 3 s)
```

If Blender MCP is not reachable, the last check shows orange — you can still
launch and connect later via **File → Connect / Setup**.

**2. Connection Setup (first run only)**

Choose your connection mode:
- **mcpo (recommended)** — port `8000`
- **Direct blender-mcp** — port `9876`
- **Auto-detect** — tries mcpo first, then direct

Click **Test Connection** to verify, then **Save & Connect**.
Settings are saved permanently — never asked again.

**3. Main Window**

The full GUI opens, connected and ready.

---

## Troubleshooting

### "No module named PyQt6"
```bash
pip install PyQt6
```

### "No response at localhost:8000"
- Make sure Blender is open and the MCP addon is enabled
- Make sure mcpo is running: `mcpo --port 8000 -- blender-mcp.exe`
- Try http://localhost:8000/openapi.json in a browser — if it loads, mcpo is fine
- If using direct mode: check N panel → MCP tab → Start MCP Server (port 9876)

### "Pipeline aborted instantly"
- Ollama model not found — run `ollama list` to see installed models
- If empty: `ollama pull qwen2.5-coder:7b`
- The app auto-detects installed models; no config change needed after pulling

### "python is not recognized"
Python was not added to PATH. Fix:
- Re-run the Python installer → **Modify** → check **Add Python to environment variables**

### "pip is not recognized"
```bash
python -m pip install -r requirements.txt
```

### Config is corrupt / app won't start
Reset the config:
```bash
python -c "from config.registry import _config_path; _config_path().unlink(missing_ok=True); print('Config cleared')"
```
Then relaunch — the first-run wizard will appear.

### Desktop shortcut doesn't work after moving the folder
Re-run `python create_shortcut.py` to rebuild it pointing to the new location.

---

## Startup Order (every session)

For the full pipeline to work, start things in this order:

```
1. Open Blender
2. N panel → MCP tab → Start MCP Server  (port 9876)
3. Run:  mcpo --port 8000 -- blender-mcp.exe
4. Launch Blender Pipeline Studio (double-click launch.pyw)
```

> **Tip:** Save Blender's startup file after starting the MCP server so it starts automatically: File → Defaults → Save Startup File.

---

## Updating

```bash
git pull
pip install -r requirements.txt --upgrade
```

---

## Uninstall

1. Delete the project folder
2. Delete the config:
   ```powershell
   Remove-Item "$env:LOCALAPPDATA\BlenderPipelineStudio" -Recurse
   ```
3. Uninstall the blender-mcp addon from Blender Preferences
4. `pip uninstall PyQt6 requests platformdirs websockets mcpo`

---

## Virtual Environment (Clean Setup)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Shortcut that activates venv and launches:
```bat
@echo off
cd /d "D:\PROJECTS\BLENDER PIPELINE"
call .venv\Scripts\activate
start "" pythonw.exe launch.pyw
```

Save as `run_studio.bat` and double-click to start with no terminal.
