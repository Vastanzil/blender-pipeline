# Usage Guide — Blender Pipeline Studio

This guide explains every feature of the application, tab by tab.

---

## Overview — The Interface

```
┌─ Menu Bar ──────────────────────────────────────────────────────┐
│ File   View   Tools   Help                                       │
├─ Tool Browser ──┬─ Tab Area ─────────────────────────────────────┤
│                 │ AI Pipeline | Tool Runner | Code | Scene | Render│
│  Search...      ├────────────────────────────────────────────────┤
│  22 tools       │                  (active panel)                 │
│                 │                                                  │
│  [tool list]    │                                                  │
│                 │                                                  │
│  [Refresh]      ├────────────────────────────────────────────────┤
│                 │  Log panel (real-time output)              Clear│
├─ Status Bar ────────────────────────────────────────────────────┤
│ ● localhost:8000    Blender 5.1.2    AI: ollama                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Launching

### One click (recommended)
Double-click **`launch.pyw`** in the project folder, or the **"Blender Pipeline Studio"** Desktop shortcut (created by `python create_shortcut.py`).

No terminal window appears.

### From terminal
```powershell
python main.py
```

---

## Startup Self-Test

Every launch runs **13 automated checks** before the main window opens:

| Check | What it verifies |
|---|---|
| Python version | ≥ 3.11 |
| PyQt6 | GUI framework importable |
| requests | HTTP library available |
| platformdirs | Config directory library |
| websockets | Optional — disabled if missing |
| Config | Config file valid |
| MCP modules | All mcp.* files importable |
| AI modules | All ai.* files importable |
| Pipeline modules | All pipeline.* files importable |
| Blender builders | blender.* bpy code generators |
| Realtime modules | event_bus, data_bridge importable |
| Code validator | AST check functional |
| Output directory | ~/blender_pipeline_output writable |
| **Blender MCP** | Live ping — shows `[mcpo]` or `[direct]` |

**Icons:**
- `✓` green — passed
- `⚠` orange — passed with warning (e.g. Blender not reachable yet)
- `✗` red — failed

When all pass, **"✓ SYSTEM READY"** appears and the app auto-continues in 3 seconds.

If Blender MCP isn't running yet, click **Skip Blender Check** — connect later via **File → Connect / Setup**.

---

## Connecting to Blender

### Connection modes

| Mode | Port | When to use |
|---|---|---|
| **mcpo** | 8000 | You have mcpo running (`mcpo --port 8000 -- blender-mcp.exe`) — recommended |
| **Direct** | 9876 | You start the MCP server from inside Blender (N panel → MCP tab) |
| **Auto** | 8000 | Try mcpo first, fall back to direct — good default |

### First Run
The **Connection Setup** dialog opens automatically. Select your mode, enter host/port, click **Test Connection**, then **Save & Connect**.

Settings are saved permanently — never asked again.

### Subsequent runs
The app auto-connects using saved settings. Status bar shows:
```
● localhost:8000    Blender 5.1.2    AI: ollama
```

### Reconnect / Change settings
**File → Connect / Setup** — opens the connection dialog at any time.

### Connection failed dialog
If Blender MCP is unreachable, a dialog shows the exact fix steps:
- **Retry** — tries again immediately (start mcpo/Blender first)
- **Connection Setup…** — opens the config dialog to change port/mode
- **Cancel** — continue without connecting

---

## Tool Browser (Left Sidebar)

Shows **every tool** exposed by blender-mcp, discovered automatically.

**Search** — type to filter tools by name or description.

**Click a tool** — the Tool Runner tab opens with an auto-generated form.

**Refresh** — re-queries for tools (useful after updating the addon).

---

## AI Pipeline Tab

The most powerful feature. Describe what you want in plain English.

### How to use

1. Type your prompt in the **Prompt** box
2. Select an **AI Backend** from the dropdown
3. Click **Run Pipeline**

### What happens internally

```
Your Prompt
    ↓
AI plan()  →  ["Create base mesh", "Add material", "Set lighting", ...]
    ↓
For each step:
  AI generate_code()  →  bpy Python code
      ↓
  Execute in Blender via mcpo/blender-mcp
      ↓
  If error:  AI fix_error()  →  retry  (up to 5×)
      ↓
  Step complete → checkpoint saved → next step
    ↓
Pipeline Done
```

### Example prompts

```
Generate a box and paint it red

Create a low-poly pine forest with 30 trees scattered randomly on a plane,
add HDRI world lighting, and set up a Cycles render

Add a cloth simulation to the selected plane with wind force

Build a city block using Geometry Nodes with procedural building heights

Animate a bouncing ball from frame 1 to 120 with squash and stretch

Create a PBR stone material and apply it to all mesh objects in the scene

Set up a camera rig that orbits around the origin over 250 frames
```

### AI Backend Selection

| Backend | Best for | Setup required |
|---|---|---|
| **ollama** | Local use, privacy, free | Install Ollama + models auto-detected |
| **openai** | GPT-4 quality | `OPENAI_API_KEY` in `.env` |
| **anthropic** | Claude quality | `ANTHROPIC_API_KEY` in `.env` |
| **gemini** | Google AI | `GEMINI_API_KEY` in `.env` |

**Ollama model auto-detection:** The app queries your Ollama installation and picks the best available model automatically. No manual configuration needed. Run `ollama list` to see what's installed.

Switch backends mid-session — takes effect on the next pipeline run.

### Pipeline Steps Panel

Real-time progress:
- `... 1. Create base mesh` — running
- `[OK] 1. Create base mesh` — completed
- `[FAIL] 2. Add modifier` — failed after retries

### Stopping a pipeline

Click **Stop** — current step finishes cleanly and pipeline halts.

---

## Tool Runner Tab

Run any single MCP tool with a dynamically generated form.

### How to use

1. **Click a tool** in the left sidebar
2. Fill in parameters (required fields marked `*`)
3. Click **Run Tool**
4. Output appears below

### Parameter types

| Schema type | Widget |
|---|---|
| `string` | Text field |
| `integer` | Spin box |
| `number` | Double spin box |
| `boolean` | Checkbox |
| `object` / `array` | Multi-line text editor |
| field with `enum` | Dropdown |
| field named `code` or `script` | Code editor |

---

## Code Tab — bpy Editor

Write and execute raw Python/bpy code directly in Blender.

### How to use

1. Type or paste bpy code
2. Click **Validate** — checks syntax and warns about unsafe patterns
3. Click **Execute** — sends to Blender, shows output

### Validator checks

- Python syntax (AST parse)
- Whether `import bpy` is present
- Banned patterns: `subprocess`, `eval(`, `exec(`, `os.system`

### Example

```python
import bpy

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Add a red cube
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
obj = bpy.context.active_object
mat = bpy.data.materials.new("Red")
mat.diffuse_color = (1, 0, 0, 1)
obj.data.materials.append(mat)
print(f"Created: {obj.name}")
```

---

## Scene Tab — Live Scene Viewer

Shows the Blender scene object hierarchy in real time.

- Updates automatically every 2 seconds when Blender's scene changes (MD5-diff — no spam)
- Columns: **Name**, **Type**, **Visible**
- Click **Refresh** to force an immediate update

---

## Render Tab

Configure and launch renders without touching Blender's UI.

| Field | Description |
|---|---|
| **Engine** | CYCLES, EEVEE, or WORKBENCH |
| **Samples** | Render samples |
| **Resolution** | Width × Height |
| **Output Path** | File path for the rendered image |

- **Apply Settings** — sends engine + resolution + samples to Blender
- **Render Still** — renders the current frame
- **Render Animation** — renders the full frame range

---

## Log Panel (Bottom)

Real-time colour-coded output:

| Colour | Meaning |
|---|---|
| White | General info |
| Green | Success / connected |
| Orange | Warning |
| Red | Error / failure |
| Grey | Debug / scene updates |

Click **Clear** to wipe. Log also writes to:
- Windows: `%USERPROFILE%\blender_pipeline_output\pipeline.log`

---

## Menu Bar

### File
- **Connect / Setup…** — open connection dialog (change host/port/mode/AI backend)
- **Quit**

### View
- **Toggle Theme** — switch dark/light (saved permanently)

### Tools
- **Refresh Tool List** — re-discover tools from blender-mcp
- **Start WebSocket Server (port 8765)** — enable real-time broadcast

### Help
- **About** — version summary

---

## WebSocket Integration

For external clients that want real-time events:

1. **Tools → Start WebSocket Server**
2. Connect to `ws://localhost:8765`

Messages are JSON:

```json
// Scene changed
{
  "event": "scene.updated",
  "data": { "scene": { "objects": [...] }, "md5": "a3f4c2..." }
}

// Pipeline step finished
{
  "event": "pipeline.step.done",
  "data": { "index": 2, "total": 7, "description": "Add material", "success": true }
}
```

---

## Config Reference

| Key | Default | Description |
|---|---|---|
| `mcp_host` | `localhost` | blender-mcp / mcpo host |
| `mcp_port` | `8000` | Port (8000 = mcpo, 9876 = direct) |
| `connection_mode` | `auto` | `auto` \| `mcpo` \| `direct` |
| `ai_backend` | `ollama` | Active AI backend |
| `ollama_host` | `http://localhost:11434` | Ollama API URL |
| `coder_model` | *(auto)* | Auto-detected from installed Ollama models |
| `planner_model` | *(auto)* | Auto-detected from installed Ollama models |
| `openai_api_key` | `""` | OpenAI API key |
| `anthropic_api_key` | `""` | Anthropic API key |
| `gemini_api_key` | `""` | Gemini API key |
| `output_dir` | `~/blender_pipeline_output` | Output + log directory |
| `max_retries` | `5` | Retry attempts on code failure |
| `poll_interval` | `2.0` | Scene poll interval (seconds) |
| `theme` | `dark` | UI theme (`dark` or `light`) |
| `auto_connect` | `true` | Auto-connect on startup |
| `log_level` | `INFO` | Log verbosity |

---

## Tips

### AI Prompting
- **Be specific:** "30 trees" beats "some trees"
- **Name objects:** "apply to the Cube object"
- **Mention render engine:** "render with Cycles"
- **Break up complex tasks** into separate pipeline runs

### Ollama Models
The app auto-selects the best installed model. To improve quality:
```bash
ollama pull qwen2.5-coder:7b    # best for code generation
ollama pull qwen3:8b             # best for planning
```
After pulling, the app picks them up automatically on next run.

### Blender 5.x Geometry Nodes
Generated code uses the new API automatically:
```python
ng.interface.new_socket("Value", in_out='INPUT', socket_type='NodeSocketFloat')
```

### Checkpoints
Every pipeline saves a JSON checkpoint per step to:
```
~/blender_pipeline_output/checkpoints/run_<timestamp>.json
```
Useful for debugging which step failed.

---

## Frequently Asked Questions

**Q: Startup check says "Blender MCP not found" but Blender is open.**
A: Make sure mcpo is running (`mcpo --port 8000 -- blender-mcp.exe`). Or if using direct mode: N panel → MCP tab → Start MCP Server.

**Q: Pipeline aborts instantly.**
A: Check your Ollama models — run `ollama list`. If empty, pull a model: `ollama pull qwen2.5-coder:7b`. The app auto-detects what's available.

**Q: The AI generates code that fails every time.**
A: Try a larger or better model. For Ollama: `ollama pull qwen2.5-coder:14b`. Or switch to OpenAI/Anthropic in the AI Backend dropdown.

**Q: Scene viewer is empty.**
A: Click Refresh. If still empty, check that `get_scene_info` appears in the Tool Browser.

**Q: Can I run without internet?**
A: Yes — use Ollama with local models. No cloud needed.

**Q: How do I change the AI model?**
A: For Ollama — just `ollama pull <model>`. The app picks the best installed model automatically. For other backends, set the API key in `.env`.

**Q: App crashes or freezes on startup.**
A: Reset the config:
```bash
python -c "from config.registry import _config_path; _config_path().unlink(missing_ok=True)"
```
Then relaunch.
