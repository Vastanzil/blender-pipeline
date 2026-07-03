# Blender Pipeline Studio

> **Full-authority Blender control from a desktop GUI — powered by AI.**

Blender Pipeline Studio connects to [blender-mcp](https://github.com/ahujasid/blender-mcp) running inside Blender and gives you a complete intelligent interface: natural-language AI pipeline, dynamic tool runner, live bpy code editor, real-time scene viewer, and multi-backend LLM integration — all in one dark-themed PyQt6 desktop app.

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BLENDER PIPELINE STUDIO          ● localhost:9876   Blender 5.1  AI: ollama│
├──────────────┬──────────────────────────────────────────────────────────────┤
│  Tools       │  AI Pipeline │ Tool Runner │ Code │ Scene │ Render           │
│  ──────────  │                                                               │
│  Search...   │  Prompt:                                                      │
│  14 tools    │  ┌─────────────────────────────────────────────────────────┐ │
│              │  │ Create a low-poly pine forest with 30 trees and HDRI   │ │
│  execute_    │  │ lighting, scatter them randomly on a plane              │ │
│  blender_    │  └─────────────────────────────────────────────────────────┘ │
│  code        │                                                               │
│  get_scene_  │  AI Backend: [ollama ✓ ▼]   [Run Pipeline] [Stop]           │
│  info        │                                                               │
│  create_     │  ████████████████████░░░  Step 3/7: Scatter instances        │
│  object      │                                                               │
│  set_        │  Pipeline Steps                                               │
│  material    │  [OK] 1. Create base plane                                   │
│  export_     │  [OK] 2. Create pine tree template                           │
│  scene       │  [OK] 3. Scatter 30 instances                                │
│  render_     │  ... 4. Add HDRI world lighting                              │
│  scene       │                                                               │
├──────────────┴──────────────────────────────────────────────────────────────┤
│  Log                                                                    Clear│
│  [14:23:01] Pipeline: Create a low-poly pine forest...                       │
│  [14:23:02] Plan ready — 7 steps                                            │
│  [14:23:03]   OK   Create base plane                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Features

### Core
| Feature | Description |
|---|---|
| **Startup self-test** | Runs 13 checks on every launch — imports, config, deps, live Blender ping. Shows "SYSTEM READY" before opening. |
| **Auto-connect** | Remembers host/port from first-run wizard — never asks again |
| **Dynamic tool browser** | Discovers every tool blender-mcp exposes at runtime — searchable, schema-driven forms auto-generated |
| **AI Pipeline** | Natural language → AI plan → bpy code per step → retry+self-correction → execute |
| **Code Editor** | Raw bpy editor with AST validation and direct execution |
| **Scene Viewer** | Live Blender object hierarchy — MD5-diff polling (no spam) |
| **Render Panel** | Engine, resolution, samples, output path → apply + render still / animation |
| **Real-time WebSocket** | Broadcasts scene updates and pipeline events on `ws://localhost:8765` |

### AI Backends (runtime-switchable)
| Backend | What you need |
|---|---|
| **Ollama** | Local — free, private, no key required |
| **OpenAI** | `OPENAI_API_KEY` |
| **Anthropic Claude** | `ANTHROPIC_API_KEY` |
| **Google Gemini** | `GEMINI_API_KEY` |

### Blender Version Support
- **Blender 5.x** — `ng.interface.new_socket()`, `BLENDER_EEVEE_NEXT`, new outputs API
- **Blender 4.x** — `ng.inputs.new()`, `BLENDER_EEVEE`
- Version detected automatically at connect time; correct API rules injected into every AI prompt

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start blender-mcp inside Blender
#    (see INSTALLATION.md for full steps)

# 3. Launch
python main.py
```

See **[INSTALLATION.md](INSTALLATION.md)** for the complete Windows setup guide.  
See **[USAGE.md](USAGE.md)** for how to use every feature.

---

## Project Structure

```
BLENDER PIPELINE/
├── main.py                       # Entry point (startup check → main window)
│
├── config/                       # Cross-platform config persistence
│   ├── defaults.py               # All default values
│   ├── registry.py               # load/save/get/set → OS config dir
│   └── schema.py                 # Dataclass + type coercion validator
│
├── mcp/                          # blender-mcp JSON-RPC 2.0 client
│   ├── client.py                 # BlenderMCPClient (connection pooling, retry)
│   ├── models.py                 # ToolParam, Tool, ToolResult dataclasses
│   ├── tool_registry.py          # Discovers + indexes all MCP tools
│   └── tool_executor.py          # Type-coerces params, executes tools
│
├── ai/                           # Multi-backend AI router
│   ├── router.py                 # AIRouter — switch backends at runtime
│   ├── compat_rules.py           # Blender version API rules for prompts
│   ├── context_builder.py        # Fetches scene, builds AI context string
│   ├── ollama_client.py          # Ollama /api/generate
│   ├── openai_client.py          # OpenAI chat completions
│   ├── anthropic_client.py       # Anthropic messages API
│   └── gemini_client.py          # Google Gemini generateContent
│
├── blender/                      # bpy code string builders
│   ├── geometry_nodes.py         # GeoNodesBuilder — create/link nodes, scatter
│   ├── materials.py              # MaterialBuilder — PBR, image textures
│   ├── animation.py              # AnimationBuilder — keyframes, drivers
│   └── render.py                 # RenderBuilder — engine, resolution, output
│
├── pipeline/                     # Intelligent execution pipeline
│   ├── orchestrator.py           # prompt→plan→code→execute→checkpoint loop
│   ├── retry_loop.py             # execute → error → AI fix → retry (×5)
│   ├── step.py                   # PipelineStep dataclass
│   ├── checkpoint.py             # JSON checkpoint after each step
│   └── validator.py              # Ping Blender between steps
│
├── realtime/                     # Live data layer
│   ├── event_bus.py              # Thread-safe pub/sub EventBus
│   ├── data_bridge.py            # Background scene poller (MD5 diff)
│   └── websocket_server.py       # ws://localhost:8765 broadcast server
│
├── gui/                          # PyQt6 desktop application
│   ├── app.py                    # BlenderPipelineStudio (QMainWindow)
│   ├── theme/
│   │   ├── dark.qss              # Dark theme (Blender-inspired)
│   │   └── light.qss             # Light theme
│   ├── panels/
│   │   ├── startup_dialog.py     # Startup self-test dialog (runs on every launch)
│   │   ├── ai_chat.py            # AI Pipeline tab
│   │   ├── tool_runner.py        # Dynamic tool form + run
│   │   ├── tool_browser.py       # Searchable tool list
│   │   ├── code_editor.py        # Raw bpy editor + validate + execute
│   │   ├── scene_tree.py         # Live scene hierarchy viewer
│   │   ├── render_panel.py       # Render settings + launch
│   │   ├── log_panel.py          # Colour-coded real-time log
│   │   └── connection_panel.py   # First-run connection setup dialog
│   └── widgets/
│       ├── param_form.py         # Schema-driven auto-form for any tool
│       └── status_bar.py         # Connection + version + AI status bar
│
├── utils/
│   ├── logger.py                 # stdout + rotating file log
│   ├── code_validator.py         # AST parse + pattern safety checks
│   ├── async_runner.py           # AsyncWorker QThread wrapper
│   └── startup_check.py         # 13 self-test checks + Blender ping
│
└── tests/                        # 94 unit tests — all pass
    ├── conftest.py
    ├── test_startup_check.py
    ├── test_config.py
    ├── test_mcp_models.py
    ├── test_mcp_client.py
    ├── test_tool_registry.py
    ├── test_code_validator.py
    ├── test_event_bus.py
    ├── test_retry_loop.py
    ├── test_pipeline_step.py
    ├── test_pipeline_orchestrator.py
    └── test_compat_rules.py
```

---

## Configuration

Config is stored automatically — never edit by hand.

| OS | Location |
|---|---|
| Windows | `%APPDATA%\BlenderPipelineStudio\config.json` |
| macOS | `~/Library/Application Support/BlenderPipelineStudio/config.json` |
| Linux | `~/.config/BlenderPipelineStudio/config.json` |

All config keys are documented in [`.env.example`](.env.example).

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
// Scene changed
{"event": "scene.updated",      "data": {"scene": {...}, "md5": "a3f..."}}

// Pipeline step finished
{"event": "pipeline.step.done", "data": {"index": 2, "success": true, "description": "..."}}
```

---

## Requirements

- Python **3.11+**
- Blender **4.x or 5.x** with [blender-mcp](https://github.com/ahujasid/blender-mcp) addon
- PyQt6 6.6+
- At least one AI backend (Ollama recommended for local use)

---

## License

MIT — see [LICENSE](LICENSE) if present, otherwise free to use and modify.

---

## Credits

Built by **VASTDEVLAB** using:
- [blender-mcp](https://github.com/ahujasid/blender-mcp) by ahujasid
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [Ollama](https://ollama.ai) / OpenAI / Anthropic / Google AI
