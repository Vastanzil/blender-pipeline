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
│  14 tools       │                  (active panel)                 │
│                 │                                                  │
│  [tool list]    │                                                  │
│                 │                                                  │
│  [Refresh]      ├────────────────────────────────────────────────┤
│                 │  Log panel (real-time output)              Clear│
├─ Status Bar ────────────────────────────────────────────────────┤
│ ● localhost:9876    Blender 5.1.2    AI: ollama                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Startup Self-Test

Every time you launch, the app runs **13 automated checks** before the main window opens:

| Check | What it verifies |
|---|---|
| Python version | ≥ 3.11 |
| PyQt6 | GUI framework importable |
| requests | HTTP library available |
| platformdirs | Config directory library |
| websockets | Optional — disabled if missing |
| Config | Config file valid, no corrupt values |
| MCP modules | All mcp.* files importable |
| AI modules | All ai.* files importable |
| Pipeline modules | All pipeline.* files importable |
| Blender builders | blender.* bpy code generators |
| Realtime modules | event_bus, data_bridge importable |
| Code validator | AST check functional |
| Output directory | ~/blender_pipeline_output writable |
| **Blender MCP** | Live ping to blender-mcp server |

**Icons:**
- `✓` green — passed
- `⚠` orange — passed with warning (e.g. optional dep missing)
- `✗` red — failed (app may not work correctly)
- `●` grey — not yet run

When all checks pass, **"✓ SYSTEM READY"** appears in green and the app auto-continues in 3 seconds. Click **Continue** to proceed immediately.

If Blender MCP isn't running, click **Skip Blender Check** — you can connect later via **File → Connect / Setup**.

---

## Connecting to Blender

### First Run
On first launch the **Connection Setup** dialog appears automatically after the startup check. Enter:
- **Host** — usually `localhost`
- **Port** — usually `9876` (blender-mcp default)

Click **Test Connection** to verify, then **Save & Connect**.  
Settings are saved permanently — you will never be asked again.

### Subsequent Runs
The app auto-connects using saved settings. The status bar shows:
```
● localhost:9876    Blender 5.1.2    AI: ollama
```

### Reconnect / Change Settings
**File → Connect / Setup** — opens the connection dialog again at any time.

---

## Tool Browser (Left Sidebar)

The sidebar shows **every tool** exposed by blender-mcp, discovered automatically.

**Search** — type to filter tools by name or description in real time.

**Click a tool** — the Tool Runner tab opens automatically with a form for that tool's parameters.

**Refresh** — re-queries blender-mcp for the tool list (useful if you updated the addon).

---

## AI Pipeline Tab

The most powerful feature. Describe what you want in plain English — the AI plans and executes every step automatically.

### How to Use

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
  Execute in Blender via blender-mcp
      ↓
  If error:  AI fix_error()  →  retry  (up to 5×)
      ↓
  Step complete → checkpoint saved → next step
    ↓
Pipeline Done
```

### Example Prompts

```
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
| **ollama** | Local use, privacy, free | Install Ollama + pull models |
| **openai** | GPT-4 quality | `OPENAI_API_KEY` in `.env` |
| **anthropic** | Claude quality | `ANTHROPIC_API_KEY` in `.env` |
| **gemini** | Google AI | `GEMINI_API_KEY` in `.env` |

Switch backends mid-session — the dropdown takes effect on the next pipeline run.

### Pipeline Steps Panel

Shows real-time progress as each step executes:
- `... 1. Create base mesh` — running
- `[OK] 1. Create base mesh` — completed
- `[FAIL] 2. Add modifier` — failed after retries

### Stopping a Pipeline

Click **Stop** — the current step finishes cleanly and the pipeline halts.

---

## Tool Runner Tab

Run any single MCP tool with a dynamically generated form.

### How to Use

1. **Click a tool** in the left sidebar — the form appears automatically
2. Fill in parameters (required fields marked with `*`)
3. Click **Run Tool**
4. Output appears in the Output panel below

### Parameter Types

The form auto-generates the right widget for each parameter type:

| Schema type | Widget |
|---|---|
| `string` | Text field |
| `integer` | Spin box |
| `number` | Double spin box (4 decimal places) |
| `boolean` | Checkbox |
| `object` / `array` | Multi-line text editor |
| field with `enum` | Dropdown (combo box) |
| field named `code` or `script` | Multi-line code editor |

---

## Code Tab — bpy Editor

Write and execute raw Python/bpy code directly.

### How to Use

1. Type (or paste) bpy code in the editor
2. Click **Validate** — checks syntax and warns about unsafe patterns
3. Click **Execute** — sends code to Blender and shows the output

### Validate

The validator checks:
- Python syntax (AST parse)
- Whether `import bpy` is present
- Banned patterns: `subprocess`, `eval(`, `exec(`, `os.system`, `__import__`

Warnings are shown in orange; syntax errors block execution.

### Example Code

```python
import bpy

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Add a sphere
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(0, 0, 1))
obj = bpy.context.active_object
obj.name = "MySphere"

print(f"Created: {obj.name}")
```

---

## Scene Tab — Live Scene Viewer

Shows the Blender scene object hierarchy in real time.

- Updates automatically whenever a change is detected (MD5 polling every 2 seconds)
- Columns: **Name**, **Type** (MESH, LIGHT, CAMERA…), **Visible**
- Click **Refresh** to force an immediate update

---

## Render Tab

Configure rendering and launch renders without touching Blender's UI.

### Settings

| Field | Description |
|---|---|
| **Engine** | CYCLES, EEVEE, or WORKBENCH |
| **Samples** | Number of render samples |
| **Resolution** | Width × Height in pixels |
| **Output Path** | File path for the rendered image/animation |

### Buttons

- **Apply Settings** — sends engine + resolution + samples to Blender
- **Render Still** — renders the current frame to the output path
- **Render Animation** — renders the full frame range

> For long renders, the output panel shows status. You can close the dialog — Blender renders in the background.

---

## Log Panel (Bottom)

The log panel shows all application events in real time with colour coding:

| Colour | Meaning |
|---|---|
| White | General info |
| Green | Success / completed |
| Orange | Warning |
| Red | Error / failure |
| Grey | Debug / scene updates |

Click **Clear** to wipe the log.

The log also writes to a file:
- Windows: `%USERPROFILE%\blender_pipeline_output\pipeline.log`

---

## Menu Bar

### File
- **Connect / Setup…** — open the connection dialog (re-configure host/port, AI backend)
- **Quit** — exit the application

### View
- **Toggle Theme** — switch between dark and light themes (saved permanently)

### Tools
- **Refresh Tool List** — re-discover all tools from blender-mcp
- **Start WebSocket Server (port 8765)** — enable real-time broadcast to external clients

### Help
- **About** — version and feature summary

---

## WebSocket Integration

For advanced users who want to receive real-time data from Blender Pipeline Studio in another application:

1. **Tools → Start WebSocket Server**
2. Connect your client to `ws://localhost:8765`

Messages are JSON:

```json
// Fired when the Blender scene changes
{
  "event": "scene.updated",
  "data": {
    "scene": { "objects": [...] },
    "md5": "a3f4c2..."
  }
}

// Fired after each pipeline step
{
  "event": "pipeline.step.done",
  "data": {
    "index": 2,
    "total": 7,
    "description": "Add material",
    "success": true,
    "attempts": 1,
    "error": ""
  }
}
```

---

## Config Reference

The config file is managed automatically. All keys and their defaults:

| Key | Default | Description |
|---|---|---|
| `mcp_host` | `localhost` | blender-mcp host |
| `mcp_port` | `9876` | blender-mcp port |
| `ai_backend` | `ollama` | Active AI backend |
| `ollama_host` | `http://localhost:11434` | Ollama API URL |
| `coder_model` | `qwen2.5-coder:7b` | Code generation model |
| `planner_model` | `qwen3:8b` | Planning model |
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

## Tips and Tricks

### AI Prompting Tips

- **Be specific about counts:** "30 trees" is better than "some trees"
- **Mention render engine:** "render with Cycles" ensures the right settings
- **Reference Blender objects by name:** "apply to the Cube object"
- **Break complex tasks into stages:** run one AI pipeline for geometry, another for materials

### Performance

- **Ollama model size:** 7B models are the sweet spot (fast + capable). 3B is faster but weaker at code.
- **Pipeline steps:** 5–7 steps is optimal. Very long pipelines (15+) may lose context coherence.
- **Poll interval:** Increase `poll_interval` to 5–10 seconds if the scene viewer causes stuttering.

### Geometry Nodes (Blender 5.x)

The AI is aware of API differences between Blender 4.x and 5.x. When connected, the correct API is automatically injected into every prompt. For Blender 5.x, generated code will use:
```python
ng.interface.new_socket("Value", in_out='INPUT', socket_type='NodeSocketFloat')
```
instead of the old `ng.inputs.new(...)` syntax.

### Checkpoints

Every pipeline run saves a JSON checkpoint after each step to:
```
~/blender_pipeline_output/checkpoints/run_<timestamp>.json
```
Useful for debugging which step failed and what code was generated.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Q` | Quit |
| `Ctrl+T` | Toggle theme |
| Click tool in sidebar | Open Tool Runner |
| Enter in AI prompt | No shortcut — click Run Pipeline |

---

## Frequently Asked Questions

**Q: The startup check says "Blender MCP not found" but Blender is open.**  
A: Click the N panel in Blender → MCP tab → Start MCP Server. Then reconnect via File → Connect / Setup.

**Q: The AI generates code that fails every time.**  
A: Try switching to a larger model (e.g. `qwen2.5-coder:14b` or an OpenAI backend). Also try a more specific prompt.

**Q: The scene viewer is empty.**  
A: Click Refresh in the Scene tab. If still empty, check that blender-mcp's `get_scene_info` tool is available in the Tool Browser.

**Q: Can I run this without an internet connection?**  
A: Yes — use Ollama with local models. No cloud API needed.

**Q: The AI pipeline is slow.**  
A: Speed depends on your AI backend. Ollama with a 7B model on a GPU is fastest locally. OpenAI GPT-4o-mini is fast and cheap via API.

**Q: How do I change the AI models used for planning vs code?**  
A: Edit `coder_model` and `planner_model` in your config file, or set them in `.env` before launch.
