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
git clone https://github.com/VASTDEVLAB/blender-pipeline-studio.git
cd "blender-pipeline-studio"
```

**Option B — Download ZIP**
1. Download the ZIP from GitHub
2. Extract to `D:\PROJECTS\BLENDER PIPELINE\` (or any folder you choose)
3. Open a Command Prompt or PowerShell in that folder

---

## Step 3 — Install Python Dependencies

In the project folder run:

```bash
pip install -r requirements.txt
```

This installs:
- `PyQt6` — desktop GUI framework
- `requests` — HTTP client for blender-mcp
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

**blender-mcp** is the Blender addon that exposes Blender's Python API as a local HTTP server. Blender Pipeline Studio talks to it.

### 4a. Download the addon

Go to: https://github.com/ahujasid/blender-mcp  
Click **Code → Download ZIP**.

### 4b. Install in Blender

1. Open **Blender**
2. Go to **Edit → Preferences → Add-ons**
3. Click **Install…**
4. Navigate to the downloaded ZIP and select it
5. Enable the addon by checking its checkbox

### 4c. Start the MCP server

1. In Blender, open the **N panel** (press `N` in the 3D Viewport)
2. Find the **MCP** tab
3. Click **Start MCP Server**
4. Default port is **9876** — leave it unless you have a conflict

> The server must be running every time you use Blender Pipeline Studio.  
> You can make it auto-start by saving Blender's startup file after starting it.

---

## Step 5 — (Optional) Install Ollama for Local AI

Ollama runs AI models locally — no API key, no internet required.

1. Download from https://ollama.ai and install
2. Pull the recommended models:
   ```bash
   ollama pull qwen2.5-coder:7b    # for code generation
   ollama pull qwen3:8b             # for planning
   ```
3. Ollama runs as a background service automatically after install

**Alternative models (lighter weight):**
```bash
ollama pull codellama:7b
ollama pull llama3.2:3b
```

---

## Step 6 — (Optional) Cloud AI API Keys

If you want to use OpenAI, Anthropic, or Gemini instead of (or in addition to) Ollama:

1. Copy `.env.example` to `.env`
2. Fill in your key(s):
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GEMINI_API_KEY=AIza...
   ```
3. The app reads these at startup via `os.environ`

You can also enter keys directly in the app settings later.

---

## Step 7 — Launch

```bash
python main.py
```

### First Launch Sequence

**1. Startup Self-Test Dialog**

The app opens a self-test window and runs 13 checks automatically:

```
● Python version         ✓  Python 3.11.9
● PyQt6                  ✓  PyQt6 OK (Qt 6.6.1)
● requests               ✓  requests 2.31.0
● platformdirs           ✓  platformdirs 4.2.0
● websockets (optional)  ✓  websockets 12.0
● Config                 ✓  Config valid
● MCP modules            ✓  MCP modules importable
● AI modules             ✓  AI modules importable
● Pipeline modules       ✓  Pipeline modules importable
● Blender builders       ✓  Blender builder modules importable
● Realtime modules       ✓  Realtime modules importable
● Code validator         ✓  Code validator functional
● Output directory       ✓  Output dir: C:\Users\You\blender_pipeline_output
● Blender MCP (...)      ✓  Blender 5.1.2 connected — 14 tools

✓  SYSTEM READY   (auto-continues in 3 s)
```

If Blender MCP is not running, the last check shows orange — you can still launch and connect later via **File → Connect / Setup**.

**2. Connection Setup (first run only)**

Enter your blender-mcp host and port (defaults: `localhost` / `9876`), click **Save & Connect**. This is saved permanently — never asked again.

**3. Main Window**

The full GUI opens, connected and ready.

---

## Troubleshooting

### "No module named PyQt6"
```bash
pip install PyQt6
```

### "No response from blender-mcp"
- Make sure Blender is open
- Check the MCP tab in the N panel — click **Start MCP Server**
- Confirm the port matches (default 9876)
- Check Windows Firewall isn't blocking localhost connections

### "python is not recognized"
- Python was not added to PATH during install
- Fix: re-run the Python installer → **Modify** → check **Add Python to environment variables**
- Or add `C:\PythonXX\` and `C:\PythonXX\Scripts\` to PATH manually

### "pip is not recognized"
```bash
python -m pip install -r requirements.txt
```

### Python version too old
```
check_python_version: Python 3.9 — need 3.11+
```
Download and install Python 3.11+ from https://www.python.org/downloads/

### Startup check fails on "AI modules"
The AI modules import their own dependencies only when called — this check just verifies the files are importable. If it fails, run:
```bash
pip install -r requirements.txt --force-reinstall
```

---

## Updating

```bash
git pull
pip install -r requirements.txt --upgrade
```

---

## Uninstall

1. Delete the project folder
2. Delete the config file:
   - Windows: `%APPDATA%\BlenderPipelineStudio\config.json`
3. Uninstall the blender-mcp addon from Blender Preferences
4. (Optional) `pip uninstall PyQt6 requests platformdirs websockets`

---

## Virtual Environment (Recommended for Clean Setup)

```bash
# Create
python -m venv .venv

# Activate (run every time before using the app)
.venv\Scripts\activate

# Install
pip install -r requirements.txt

# Run
python main.py

# Deactivate when done
deactivate
```

Create a shortcut that activates the venv and runs the app:

```bat
@echo off
cd /d "D:\PROJECTS\BLENDER PIPELINE"
call .venv\Scripts\activate
python main.py
```

Save as `launch_studio.bat` and double-click to start.
