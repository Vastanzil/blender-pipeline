# Blender Pipeline Studio

### 🎉 v2.0 — First Fully Working Prototype

> **AI-powered 3D generation is live.** Type a natural-language prompt, hit Run Pipeline, and watch Blender build your scene step-by-step — planning, code generation, execution, and self-correcting retries, all fully automated. Five AI backends supported. Zero manual coding required.

> **Full-authority Blender control from a desktop GUI — powered by AI.**

Blender Pipeline Studio connects to [blender-mcp](https://github.com/ahujasid/blender-mcp) (via **mcpo** or direct) running inside Blender and gives you a complete intelligent interface: natural-language AI pipeline, dynamic tool runner, live bpy code editor, real-time scene viewer, and multi-backend LLM integration — all in one dark-themed PyQt6 desktop app.

---

## Screenshots
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/55e422b9-9e52-46bd-aec2-792e8d4f7ba7" />

---

## Features

### Core
| Feature | Description |
|---|---|
| **Startup self-test** | Runs 13 checks on every launch — imports, config, deps, live Blender ping. Shows "SYSTEM READY" before opening. |
| **One-click launch** | Double-click `launch.pyw` or the Desktop shortcut — no terminal needed |
| **Auto-connect** | Remembers host/port/mode from first-run wizard — never asks again |
| **mcpo + direct support** | Connects via mcpo (OpenAPI, port 8000) or direct blender-mcp JSON-RPC (port 9876). Auto-detects which is running. |
| **Dynamic tool browser** | Discovers every tool blender-mcp exposes at runtime — searchable, schema-driven forms auto-generated |
| **AI Pipeline** | Natural language → AI plan → bpy code per step → retry+self-correction → execute |
| **Code Editor** | Raw bpy editor with AST validation and direct execution |
| **Scene Viewer** | Live Blender object hierarchy — MD5-diff polling (no spam) |
| **Render Panel** | Engine, resolution, samples, output path → apply + render still / animation |
| **Real-time WebSocket** | Broadcasts scene updates and pipeline events on `ws://localhost:8765` |
| **Thread-safe UI** | All background threads marshal updates to the GUI thread via Qt queued signals — no crashes |

### AI Backends (runtime-switchable)
| Backend | What you need |
|---|---|
| **Ollama** | Local — free, private, no key required. Model dropdowns auto-populate from `/api/tags`. |
| **OpenAI** | `OPENAI_API_KEY` |
| **Anthropic Claude** | `ANTHROPIC_API_KEY` |
| **Google Gemini** | `GEMINI_API_KEY` |
| **Manifest** | Local LLM router ([github.com/mnfst/manifest](https://github.com/mnfst/manifest)). URL `http://localhost:2099`, Bearer token `mnfst_xxx`. `model: "auto"` lets Manifest route to any backend (Ollama, Claude, GPT-4…). |

### Blender Version Support
- **Blender 5.x** — `ng.interface.new_socket()`, `BLENDER_EEVEE_NEXT`, new outputs API
- **Blender 4.x** — `ng.inputs.new()`, `BLENDER_EEVEE`
- Version detected automatically at connect time; correct API rules injected into every AI prompt

---

## Architecture — How it connects

```
Blender (running)
    └── blender-mcp addon  (port 9876, native MCP protocol)
              │
     ┌────────┴─────────┐
     │      mcpo         │   ← recommended: wraps MCP as OpenAPI REST
     │  port 8000        │       mcpo --port 8000 -- blender-mcp.exe
     └────────┬─────────┘
              │  OR direct JSON-RPC (port 9876, legacy)
              │
   Blender Pipeline Studio
   (this app — PyQt6 desktop GUI)
```

The app auto-detects which mode is running. Configure in **Connection Setup** (File → Connect / Setup).

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start blender-mcp inside Blender
#    (see INSTALLATION.md for full steps)

# 3a. Launch with one click — double-click launch.pyw or Desktop shortcut
# 3b. Or from terminal:
python main.py
```

See **[INSTALLATION.md](INSTALLATION.md)** for the complete Windows setup guide.
See **[USAGE.md](USAGE.md)** for how to use every feature.

---

## Project Structure

```
BLENDER PIPELINE/
├── main.py                       # Entry point (startup check → main window)
├── launch.pyw                    # Double-click launcher (no terminal window)
├── launch.bat                    # Batch fallback launcher
├── create_shortcut.py            # Creates a Desktop shortcut (run once)
│
├── config/                       # Cross-platform config persistence
│   ├── defaults.py               # All default values (port 8000, mode auto)
│   ├── registry.py               # load/save/get/set → OS config dir
│   └── schema.py                 # Dataclass + type coercion validator
│
├── mcp/                          # blender-mcp client layer
│   ├── client.py                 # BlenderMCPClient — direct JSON-RPC 2.0 (port 9876)
│   ├── mcpo_client.py            # MCPOClient — mcpo OpenAPI REST (port 8000) ← NEW
│   ├── factory.py                # make_client() auto-detects mcpo vs direct ← NEW
│   ├── models.py                 # ToolParam, Tool, ToolResult dataclasses
│   ├── tool_registry.py          # Discovers + indexes all MCP tools
│   └── tool_executor.py          # Type-coerces params, executes tools
│
├── ai/                           # Multi-backend AI router
│   ├── router.py                 # AIRouter — switch backends at runtime
│   ├── compat_rules.py           # Blender version API rules for prompts
│   ├── context_builder.py        # Fetches scene, builds AI context string
│   ├── ollama_client.py          # Ollama — auto-detects installed models ← UPDATED
│   ├── openai_client.py          # OpenAI chat completions
│   ├── anthropic_client.py       # Anthropic messages API
│   ├── gemini_client.py          # Google Gemini generateContent
│   └── manifest_client.py        # Manifest AI router (localhost:2099) ← NEW
│
├── blender/                      # bpy code string builders
│   ├── geometry_nodes.py
│   ├── materials.py
│   ├── animation.py
│   └── render.py
│
├── pipeline/                     # Intelligent execution pipeline
│   ├── orchestrator.py           # prompt→plan→code→execute→checkpoint loop
│   ├── retry_loop.py             # execute → error → AI fix → retry (×5)
│   ├── step.py
│   ├── checkpoint.py
│   └── validator.py
│
├── realtime/                     # Live data layer
│   ├── event_bus.py              # Thread-safe pub/sub EventBus
│   ├── qt_bridge.py              # QtBridge: bus→widget thread-safety ← NEW
│   ├── data_bridge.py            # Background scene poller (MD5 diff)
│   └── websocket_server.py       # ws://localhost:8765 broadcast server
│
├── gui/                          # PyQt6 desktop application
│   ├── app.py                    # BlenderPipelineStudio (QMainWindow)
│   ├── theme/
│   │   ├── dark.qss
│   │   └── light.qss
│   ├── panels/
│   │   ├── startup_dialog.py     # Startup self-test dialog
│   │   ├── connection_panel.py   # Connection setup: mcpo/direct/auto mode ← UPDATED
│   │   ├── ai_chat.py            # AI Pipeline tab
│   │   ├── tool_runner.py        # Dynamic tool form + run
│   │   ├── tool_browser.py       # Searchable tool list
│   │   ├── code_editor.py        # Raw bpy editor + validate + execute
│   │   ├── scene_tree.py         # Live scene hierarchy viewer
│   │   ├── log_panel.py          # Colour-coded real-time log
│   │   └── render_panel.py       # Render settings + launch
│   └── widgets/
│       ├── param_form.py         # Schema-driven auto-form for any tool
│       └── status_bar.py         # Connection + version + AI status bar
│
├── utils/
│   ├── logger.py
│   ├── code_validator.py
│   ├── async_runner.py           # AsyncWorker QThread — self-managing lifetime ← UPDATED
│   ├── log_writer.py            # Disk log persistence ← NEW
│   └── startup_check.py         # 13 self-test checks + Blender ping
│
└── tests/                        # 94 unit tests — all pass
    └── ...
```

---

## Configuration

Config is stored automatically — never edit by hand.

| OS | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\BlenderPipelineStudio\BlenderPipelineStudio\config.json` |
| macOS | `~/Library/Application Support/BlenderPipelineStudio/config.json` |
| Linux | `~/.config/BlenderPipelineStudio/config.json` |

**To reset config** (forces first-run wizard again):
```bash
python -c "from config.registry import _config_path; _config_path().unlink(missing_ok=True); print('Config cleared')"
```

### Key config values

| Key | Default | Description |
|---|---|---|
| `mcp_host` | `localhost` | blender-mcp / mcpo host |
| `mcp_port` | `8000` | Port — 8000 for mcpo, 9876 for direct |
| `connection_mode` | `auto` | `auto` \| `mcpo` \| `direct` |
| `ai_backend` | `ollama` | Active AI backend |
| `ollama_host` | `http://localhost:11434` | Ollama API URL |
| `coder_model` | *(auto)* | Code model — auto-detected from installed Ollama models. Selectable in UI. |
| `planner_model` | *(auto)* | Planner model — auto-detected. Selectable in UI. |
| `manifest_host` | `http://localhost:2099` | Manifest AI router URL |
| `manifest_token` | *(empty)* | Bearer token (`mnfst_xxx`) — from Manifest dashboard |
| `manifest_model` | `auto` | Model name to send to Manifest (`auto` = let Manifest decide) |
| `max_retries` | `5` | Retry attempts on code failure |
| `poll_interval` | `2.0` | Scene poll interval (seconds) |
| `theme` | `dark` | UI theme |
| `auto_connect` | `true` | Auto-connect on startup |

---

## Running the Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
# 94 passed
```

---

## WebSocket API

Enable via **Tools → Start WebSocket Server**.
Connect any client to `ws://localhost:8765`:

```json
{"event": "scene.updated",      "data": {"scene": {...}, "md5": "a3f..."}}
{"event": "pipeline.step.done", "data": {"index": 2, "success": true, "description": "..."}}
```

---

## Requirements

- Python **3.11+**
- Blender **4.x or 5.x** with [blender-mcp](https://github.com/ahujasid/blender-mcp) addon
- **mcpo** (recommended) or direct blender-mcp server
- PyQt6 6.6+
- At least one AI backend (Ollama recommended for local use)

---

## Changelog

### v2.0 — 2026-07-04 🎉 First Fully Working Prototype
- **Milestone: fully working AI-powered 3D generation** — end-to-end pipeline proven: natural language → AI plan → bpy code generation → Blender execution → self-correcting retries. Successfully generating complex 3D scenes from text prompts.
- **5 AI backends all operational** — Ollama, OpenAI, Anthropic, Gemini, and Manifest AI router. Runtime-switchable from the AI Pipeline tab or Connection Setup.
- **Connection crash fix** — `self.status` created at top of `_build()` before any background thread starts; model refresh deferred via `QTimer.singleShot(0)`. No more `AttributeError` on File → Connect/Setup.
- **Pipeline abort display** — abort reason shown in red with context-specific hints (Ollama not running, bad token, connection refused). Previously aborts were silent.
- **Token sanitization** — Manifest tokens and API keys stripped of whitespace/newlines on save and on client init. Fixes `Invalid leading whitespace` header errors from corrupted copy-paste.
- **AI health monitoring** — 30-second background health poll updates status bar with green/red dot. Shows `backend / model-name` (e.g. `manifest / auto`).
- **Step detail view** — click any completed pipeline step to see generated bpy code, error output, and retry count in a monospace detail pane.
- **Config in-memory cache** — `registry.py` reads config JSON once; subsequent `get()` calls hit memory. `set()` writes through to disk.
- **Log persistence** — all log lines written to `~/blender_pipeline_output/logs/<timestamp>.log`. 📂 button opens log folder.
- **Pipeline settings UI** — max retries, poll interval, AI timeout, and output directory configurable in Connection Setup.
- **Tool browser filter** — live search with `N of M tools` count.
- **Schema updated** — all `manifest_*`, `connection_mode`, `ai_timeout`, `stream_ai`, `log_level` fields added to `AppConfig`. `ai_backend` validator accepts all 5 backends.
- **94 tests passing** — all unit tests green.

### v1.2 — 2026-07-04
- **Manifest AI backend** — 5th AI backend routing through [Manifest](https://github.com/mnfst/manifest) local LLM proxy (`http://localhost:2099`). Uses OpenAI-compatible `/v1/chat/completions` with Bearer token. `model: "auto"` lets Manifest choose the best provider (Ollama, Claude, GPT-4, etc.). Configure in Connection Setup → AI Backend → manifest.
- **Ollama model picker UI** — Connection Setup now shows live coder + planner model dropdowns populated from `/api/tags`. Refresh button re-queries Ollama. Saves as `coder_model` / `planner_model` config keys. Empty = auto-detect as before.
- **AI backend pages** — stacked widget shows only the relevant config for the active backend (Ollama host + model pickers, API key field, or Manifest URL/token/model).

### v1.1 — 2026-07-04
- **mcpo support** — new `MCPOClient` speaks mcpo's OpenAPI REST API (port 8000). `make_client()` auto-detects mcpo vs direct JSON-RPC. Connection panel redesigned with mode selector (mcpo / direct / auto).
- **One-click launch** — `launch.pyw`, `launch.bat`, `create_shortcut.py` for desktop shortcut. No terminal needed.
- **Thread-safety fix** — `QtBridge` marshals all EventBus→widget calls to the GUI thread via Qt queued signals. Eliminated crash on startup caused by DataBridge background thread touching Qt widgets directly.
- **QThread lifetime fix** — `async_runner._live` keeps every in-flight `AsyncWorker` alive until Qt signals `finished`. Fixed "QThread destroyed while running" fatal crash.
- **Ollama model auto-detect** — queries `/api/tags` on first use, picks best installed model from ranked preference list. No more 404 / pipeline abort when configured model isn't installed.
- **Connection error dialog** — friendly `QMessageBox` with step-by-step fix instructions when ping fails. Retry and Connection Setup buttons.
- **Status bar** — new `set_connecting()` orange state while background ping runs.
- Default port changed from `9876` → `8000` (mcpo).

### v1.0 — 2026-07-03
- Initial release — full AI pipeline, tool browser, code editor, scene viewer, render panel, WebSocket broadcast, startup self-test, 94 unit tests.

---

## License

MIT — free to use and modify.

---

## Credits

Built by **VASTDEVLAB** using:
- [blender-mcp](https://github.com/ahujasid/blender-mcp) by ahujasid
- [mcpo](https://github.com/open-webui/mcpo) by open-webui
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [Ollama](https://ollama.ai) / OpenAI / Anthropic / Google AI
