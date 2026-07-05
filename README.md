# Blender Pipeline Studio

### v3.0 — Image-to-3D Pipeline · 60% Accuracy from Reference Images

> **v3.0 successfully generates 3D models from image references at ~60% accuracy.** Attach a concept image, hit Run Pipeline, and the AI interprets the visual reference to plan and build a matching 3D scene in Blender — automatically. No manual coding. No backend juggling. One AI, one pipeline, full authority over Blender.

> **Full-authority Blender control from a desktop GUI — powered by AI.**

Blender Pipeline Studio connects to [blender-mcp](https://github.com/ahujasid/blender-mcp) (via **mcpo** or direct) running inside Blender and gives you a complete intelligent interface: natural-language + image-reference AI pipeline, dynamic tool runner, live bpy code editor, real-time scene viewer, and one-click workflow templates — all in one dark-themed PyQt6 desktop app.

---

## What's New in v3.0

### Image Reference Upload — Vision-Aware Pipeline
- **Attach reference images** directly in the prompt box — drag-and-drop or click the 📎 button
- Supports PNG, JPG, JPEG, WEBP, BMP, GIF
- Thumbnail strip shows all attached images with per-image remove (✕) buttons
- Images are base64-encoded and sent to Manifest AI in OpenAI vision format (`image_url` content blocks)
- The AI uses the visual reference throughout planning **and** code generation — every step is vision-aware
- After a successful pipeline run, the image strip auto-clears (like Claude.ai/ChatGPT)
- **Result: ~60% accuracy generating 3D models that match the reference image**

### Manifest-Only Routing — Zero Dead Code
- Removed all non-Manifest AI backends (Ollama, OpenAI, Anthropic, Gemini)
- Single `ManifestClient` instance — no backend switching, no dead combo boxes
- Connection Setup simplified to one section: Manifest URL, token, and model
- Config stripped of all `ollama_host`, `coder_model`, `planner_model`, `openai_api_key`, `anthropic_api_key`, `gemini_api_key` fields

### Workflow Catalog — 7 Named Templates
Quick Workflow picker above the prompt box pre-fills the prompt and injects skill hints into the system prompt, reducing hallucination:

| Workflow | What it does |
|---|---|
| **Import PolyHaven Asset** | Downloads HDRI/texture via PolyHaven MCP tools and applies it to the scene |
| **Generate 3D from Image (Hyper3D Rodin)** | Sends reference image to Hyper3D Rodin, polls job, imports the generated mesh |
| **Export Scene to Godot (glTF)** | Applies transforms, verifies PBR materials, exports as GLB |
| **PBR Material from Reference Image** | Analyzes reference image and creates a matching Principled BSDF material |
| **Hard Surface Modifier Stack** | Adds Mirror + Bevel + Weighted Normal + SubSurf with correct settings |
| **Low-Poly Scene** | Primitive meshes, flat shading, solid-color materials, sun + sky lighting |
| **Animate Object (Keyframes)** | Location/rotation/scale keyframes across frames 1–120 |

### Goal-First Pipeline Intelligence
- Before any step executes, the AI describes its intent in 1–3 sentences
- Displayed as a blue italic **Goal:** line above the step list
- Catches misunderstood prompts before code runs — you can Stop immediately if the goal is wrong

---

## What Was Removed in v3.0

| Removed | Reason |
|---|---|
| `ai/ollama_client.py` | Dead code — Manifest routes to Ollama internally if configured |
| `ai/openai_client.py` | Dead code — Manifest routes to GPT-4 if configured |
| `ai/anthropic_client.py` | Dead code — Manifest routes to Claude if configured |
| `ai/gemini_client.py` | Dead code — Manifest routes to Gemini if configured |
| AI Backend combo in AI Chat panel | No switching needed — always Manifest |
| `_refresh_backends()` / `_switch_backend()` in AI Chat | Removed with combo |
| Ollama page in Connection Setup | Entire stacked backend page removed |
| API key pages in Connection Setup | OpenAI / Anthropic / Gemini config pages removed |
| Config fields: `ollama_host`, `coder_model`, `planner_model`, `openai_api_key`, `anthropic_api_key`, `gemini_api_key` | No longer used |

---

## Screenshots

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  BLENDER PIPELINE STUDIO         ● localhost:8000   Blender 5.1  manifest/auto│
├──────────────┬───────────────────────────────────────────────────────────────┤
│  Tools       │  AI Pipeline │ Tool Runner │ Code │ Scene │ Render            │
│  ──────────  │                                                                │
│  Search...   │  Quick Workflow: [PBR Material from Reference Image    ▼]      │
│  22 tools    │                                                                │
│              │  Prompt:                                                       │
│  get_scene_  │  ┌──────────────────────────────────────────────────────────┐ │
│  info        │  │ Create a PBR Principled BSDF material that visually     │ │
│  get_object_ │  │ matches the attached reference image…                    │ │
│  info        │  └──────────────────────────────────────────────────────────┘ │
│  execute_    │  Optionally attach reference images — the AI will use them    │
│  blender_    │  [📎 Add Image]  [🖼 reference.png ✕]                         │
│  code        │                                                                │
│  create_     │  [Run Pipeline]  [Stop]                                        │
│  object      │                                                                │
│  set_        │  Goal: I will analyze the reference image colors and create    │
│  material    │        a Principled BSDF material matching the texture and     │
│  ...         │        roughness, then assign it to the active object.         │
│              │                                                                │
│              │  ████████████████████░░░  Step 2/3: Create Principled BSDF    │
│              │                                                                │
│              │  Pipeline Steps                                                │
│              │  [✓] 1. Analyze reference image colors                        │
│              │  [✓] 2. Create Principled BSDF with matching values           │
│              │  ... 3. Assign material to active object                       │
├──────────────┴───────────────────────────────────────────────────────────────┤
│  Log                                                                     Clear│
│  [09:14:01] Pipeline: Create a PBR material…                                  │
│  [09:14:02] Goal: I will analyze the reference image…                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

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
| **AI Pipeline** | Natural language + image reference → goal analysis → AI plan → bpy code per step → retry+self-correction → execute |
| **Image reference upload** | Thumbnail strip with drag-drop. Images sent as base64 vision blocks to Manifest AI throughout planning and code generation. |
| **Workflow catalog** | 7 named templates with pre-filled prompts and skill hints. Reduces hallucination by telling the AI exactly which MCP tools and bpy calls to use. |
| **Goal-first intelligence** | AI describes intent before executing — shown as blue italic Goal label. Catch misunderstood prompts before any code runs. |
| **Code Editor** | Raw bpy editor with AST validation and direct execution |
| **Scene Viewer** | Live Blender object hierarchy — MD5-diff polling (no spam) |
| **Render Panel** | Engine, resolution, samples, output path → apply + render still / animation |
| **Real-time WebSocket** | Broadcasts scene updates and pipeline events on `ws://localhost:8765` |
| **Thread-safe UI** | All background threads marshal updates to the GUI thread via Qt queued signals — no crashes |

### AI Backend
| | |
|---|---|
| **Manifest AI Router** | Single backend. Local LLM router at `http://localhost:2099` with Bearer token. `model: "auto"` lets Manifest choose the best provider (Ollama, Claude, GPT-4, Gemini…). Configure once in Connection Setup. |

Manifest routes internally to any model — Ollama, OpenAI, Anthropic, Gemini — without this app managing separate API keys per backend.

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
              │
   Manifest AI Router (localhost:2099)
   (routes to Ollama / Claude / GPT-4 / Gemini internally)
```

---

## v3.0 Pipeline Flow

```
User prompt  +  [📎 reference images]
        │
        ▼
  Workflow Catalog (optional template + skill hint injected into system prompt)
        │
        ▼
  Goal Analysis — AI describes intent in 1-3 sentences (shown in blue)
        │
        ▼
  Orchestrator.run(prompt, images=[...], skill_hint="...")
        │
        ├─ ai.plan(prompt, images)          ← vision-aware planning
        │
        ├─ For each step:
        │   ├─ ai.generate_code(step, images)   ← vision-aware code gen
        │   ├─ execute via MCP → Blender
        │   └─ retry loop on failure (up to 5×, AI self-corrects)
        │
        └─ pipeline.done  →  image strip auto-clears
```

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
│   ├── defaults.py               # All default values (Manifest-only, port 8000)
│   ├── registry.py               # load/save/get/set → OS config dir
│   └── schema.py                 # Dataclass + type coercion validator
│
├── mcp/                          # blender-mcp client layer
│   ├── client.py                 # BlenderMCPClient — direct JSON-RPC 2.0 (port 9876)
│   ├── mcpo_client.py            # MCPOClient — mcpo OpenAPI REST (port 8000)
│   ├── factory.py                # make_client() auto-detects mcpo vs direct
│   ├── models.py                 # ToolParam, Tool, ToolResult dataclasses
│   ├── tool_registry.py          # Discovers + indexes all MCP tools
│   └── tool_executor.py          # Type-coerces params, executes tools
│
├── ai/                           # Manifest-only AI layer
│   ├── router.py                 # AIRouter — thin wrapper over ManifestClient
│   ├── manifest_client.py        # Manifest AI router — vision-aware (images param)
│   ├── image_encoder.py          # base64 encode utility for OpenAI vision format ← NEW
│   ├── compat_rules.py           # Blender version API rules for prompts
│   └── context_builder.py        # Fetches scene, builds AI context string
│
├── pipeline/                     # Intelligent execution pipeline
│   ├── orchestrator.py           # prompt+images+skill_hint → goal → plan → execute
│   ├── workflow_catalog.py       # 7 named workflow templates with skill hints ← NEW
│   ├── retry_loop.py             # execute → error → AI fix → retry (×5)
│   ├── step.py
│   ├── checkpoint.py
│   └── validator.py
│
├── realtime/                     # Live data layer
│   ├── event_bus.py              # Thread-safe pub/sub EventBus
│   ├── qt_bridge.py              # QtBridge: bus→widget thread-safety
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
│   │   ├── connection_panel.py   # Connection setup: Manifest + MCP mode
│   │   ├── ai_chat.py            # AI Pipeline tab — image bar + workflow picker
│   │   ├── tool_runner.py        # Dynamic tool form + run
│   │   ├── tool_browser.py       # Searchable tool list
│   │   ├── code_editor.py        # Raw bpy editor + validate + execute
│   │   ├── scene_tree.py         # Live scene hierarchy viewer
│   │   ├── log_panel.py          # Colour-coded real-time log
│   │   └── render_panel.py       # Render settings + launch
│   └── widgets/
│       ├── image_attachment.py   # Thumbnail strip widget with drag-drop ← NEW
│       ├── param_form.py         # Schema-driven auto-form for any tool
│       └── status_bar.py         # Connection + version + AI status bar
│
├── utils/
│   ├── logger.py
│   ├── code_validator.py
│   ├── async_runner.py           # AsyncWorker QThread
│   ├── log_writer.py             # Disk log persistence
│   └── startup_check.py          # 13 self-test checks + Blender ping
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

### Key config values (v3.0)

| Key | Default | Description |
|---|---|---|
| `mcp_host` | `localhost` | blender-mcp / mcpo host |
| `mcp_port` | `8000` | Port — 8000 for mcpo, 9876 for direct |
| `connection_mode` | `auto` | `auto` \| `mcpo` \| `direct` |
| `ai_backend` | `manifest` | Always manifest in v3.0 |
| `manifest_host` | `http://localhost:2099` | Manifest AI router URL |
| `manifest_token` | *(empty)* | Bearer token (`mnfst_xxx`) |
| `manifest_model` | `auto` | Model name — `auto` lets Manifest choose |
| `max_retries` | `5` | Retry attempts on code failure |
| `poll_interval` | `2.0` | Scene poll interval (seconds) |
| `ai_timeout` | `120` | Seconds per AI request |
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
{"event": "scene.updated",         "data": {"scene": {...}, "md5": "a3f..."}}
{"event": "pipeline.goal_analysis", "data": {"summary": "I will create a PBR material..."}}
{"event": "pipeline.step.done",     "data": {"index": 2, "success": true, "description": "..."}}
```

---

## Requirements

- Python **3.11+**
- Blender **4.x or 5.x** with [blender-mcp](https://github.com/ahujasid/blender-mcp) addon
- **mcpo** (recommended) or direct blender-mcp server
- **Manifest AI Router** running on `http://localhost:2099`
- PyQt6 6.6+

---

## Changelog

### v3.0 — 2026-07-06 — Image-to-3D Pipeline

**Milestone: Successfully generates 3D models from image references at ~60% accuracy.**
Attaching a concept image to the prompt and running the pipeline produces a matching 3D scene in Blender with ~60% visual fidelity to the reference — confirmed across object shape, material color, and structural layout tasks.

**New:**
- **Image reference upload** — `gui/widgets/image_attachment.py`: thumbnail strip with drag-drop, file dialog, per-image remove buttons, `images()` → `list[str]`. Added to AI Chat prompt box.
- **Vision-aware Manifest client** — `ai/manifest_client.py`: `_build_content(text, images)` assembles OpenAI multimodal content arrays. `generate_code`, `plan`, `fix_error` all accept `images=None`. Images forwarded from GUI → orchestrator → every AI call.
- **Image encoder utility** — `ai/image_encoder.py`: `encode_image()` and `to_openai_image_block()` for base64/data-URL conversion.
- **Workflow catalog** — `pipeline/workflow_catalog.py`: 7 named templates (PolyHaven, Hyper3D Rodin, Godot export, PBR from image, hard surface stack, low-poly scene, keyframe animation). Each has `prompt_template` + `skill_hint` injected into system prompt.
- **Quick workflow picker** — `QComboBox` above prompt in AI Chat; selecting a workflow pre-fills the prompt and activates its skill hint.
- **Goal-first intelligence** — orchestrator emits `pipeline.goal_analysis` before any step; AI Chat displays blue italic Goal label.
- **Skill hints in plan prompt** — workflow skill hint injected as `SKILL HINTS:` section in the planning prompt, reducing hallucinated tool names.

**Removed:**
- `ai/ollama_client.py` — deleted
- `ai/openai_client.py` — deleted
- `ai/anthropic_client.py` — deleted
- `ai/gemini_client.py` — deleted
- AI Backend combo box and `_refresh_backends`/`_switch_backend` from `gui/panels/ai_chat.py`
- Ollama page and all API key pages from `gui/panels/connection_panel.py`
- Config fields: `ollama_host`, `coder_model`, `planner_model`, `openai_api_key`, `anthropic_api_key`, `gemini_api_key`

**Tests:** 94 passed.

---

### v2.0 — 2026-07-04 — First Fully Working Prototype
- **Milestone: fully working AI-powered 3D generation** — end-to-end pipeline proven: natural language → AI plan → bpy code generation → Blender execution → self-correcting retries.
- **5 AI backends** — Ollama, OpenAI, Anthropic, Gemini, Manifest. Runtime-switchable.
- **Connection crash fix** — `self.status` created at top of `_build()` before any background thread.
- **Pipeline abort display** — abort reason shown in red with context-specific hints.
- **Token sanitization** — whitespace/newlines stripped on save and on client init.
- **AI health monitoring** — 30-second background poll, green/red dot in status bar.
- **Step detail view** — click any step to see generated bpy code + error + retry count.
- **Config in-memory cache** — `registry.py` reads once, writes through.
- **Log persistence** — all log lines written to `~/blender_pipeline_output/logs/`.
- **94 tests passing.**

### v1.2 — 2026-07-04
- **Manifest AI backend** — 5th AI backend, OpenAI-compatible `/v1/chat/completions`.
- **Ollama model picker UI** — live coder + planner model dropdowns from `/api/tags`.

### v1.1 — 2026-07-04
- **mcpo support** — `MCPOClient` + `make_client()` auto-detects mcpo vs direct.
- **One-click launch** — `launch.pyw`, `launch.bat`, `create_shortcut.py`.
- **Thread-safety fix** — `QtBridge` marshals EventBus→widget calls to GUI thread.
- **QThread lifetime fix** — `async_runner._live` prevents destroyed-while-running crash.

### v1.0 — 2026-07-03
- Initial release.

---

## License

MIT — free to use and modify.

---

## Credits

Built by **VASTDEVLAB** using:
- [blender-mcp](https://github.com/ahujasid/blender-mcp) by ahujasid
- [mcpo](https://github.com/open-webui/mcpo) by open-webui
- [blender-open-mcp](https://github.com/dhakalnirajan/blender-open-mcp) — 16-tool surface reference
- [blender-ai-mcp](https://github.com/PatrykIti/blender-ai-mcp) — goal-first routing patterns
- [ComfyUI-BlenderAI-node](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node) — image-to-3D workflow patterns
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [Manifest AI Router](https://github.com/mnfst/manifest)
