# BlenderCopilot Master Plan
**A single spec for Claude Code to execute: repo rename, hybrid Claude/BlenderLLM router, and wireframe depth-capture verification.**

Source repo (current): `https://github.com/Vastanzil/blender-pipeline` (GPL-3.0, v3.0, 94 passing tests)
LLM to integrate: `https://github.com/FreedomIntelligence/BlenderLLM` (Apache-2.0, Qwen2.5-Coder-7B-Instruct fine-tune)

---

## 0. How to use this document

This is one spec covering four things that were previously separate threads of discussion:

1. Rename `blender-pipeline` → **BlenderCopilot**, and relocate BlenderLLM into a sibling folder.
2. Add a **Hybrid AI mode**: Claude (via Manifest) does planning/vision, local BlenderLLM does codegen + error-fix.
3. Add **wireframe/depth screenshot capture** to the verification loop, alongside the existing rendered-image capture.
4. A test/benchmark plan to get from "it works" to "it's trustworthy in production."

Claude Code should treat Section 11 as the actual task list, and the earlier sections as the reasoning/spec that task list is derived from. Do not skip Section 1 — it flags two places where this plan's assumptions need to be checked against the real, current state of the codebase before writing code.

---

## 1. Grounding — confirmed facts vs. assumptions to verify first

**Confirmed by inspecting the live repos (do not re-derive, just use these):**

- `blender-pipeline` v3.0 structure is: `main.py`, `config/` (`defaults.py`, `registry.py`, `schema.py`), `mcp/` (`client.py`, `mcpo_client.py`, `factory.py`, `models.py`, `tool_registry.py`, `tool_executor.py`), `ai/` (`router.py`, `manifest_client.py`, `image_encoder.py`, `compat_rules.py`, `context_builder.py`), `pipeline/` (`orchestrator.py`, `workflow_catalog.py`, `retry_loop.py`, `step.py`, `checkpoint.py`, `validator.py`), `realtime/`, `gui/`, `utils/`, `tests/` (94 tests).
- AI backend today is **Manifest-only** (`ai_backend` is hardcoded to `manifest` in config; the old Ollama/OpenAI/Anthropic/Gemini clients were deliberately deleted in v3.0 as dead code). This means the hybrid router is not "add a new option to a switch that already exists" — it's **reintroducing a second backend on purpose**, so name it distinctly (`blenderllm`, not a resurrected `local`/`ollama` client) so nobody mistakes it for the old dead code.
- Manifest runs at `http://localhost:2099`, Bearer token auth, `manifest_model: "auto"`. Confirmed as a real MIT-licensed router (`mnfst/manifest`) supporting custom OpenAI-compatible providers and automatic token/cost/duration logging with a dashboard.
- BlenderLLM is a **Qwen2.5-Coder-7B-Instruct** fine-tune, Apache-2.0 licensed (compatible with GPL-3.0 — MIT/Apache → GPL-3.0 is a safe direction). Its own repo ships `chat.py` (text-only chat) and `modeling.py` (generates a script **and** calls a local Blender executable directly to render it) — it is **not** shipped as an inference server. Its documented limitations, confirmed from the model card: text-only input (no images/multimodal), no material/texture/internal-structure support, and no multi-turn memory.
- Config app-data paths are named after the product (`BlenderPipelineStudio`) on all three OSes — a rename has to include a config migration step, or existing users lose their saved Manifest token/host on upgrade.

**Not confirmed — flagged for you to verify against the actual local working tree before writing code, because they weren't visible in the public repo's README/structure (they may be on an uncommitted branch or added since the last push):**

- `pipeline/scene_verifier.py`, its `RealismIssue` class, `verify_realism()`, `capture_all()`, and the `_CAPTURE_CODE` bpy template. This plan is written assuming they exist with those names, doing camera-position rendered-image capture that gets fed to a vision model to catch floating/sunk/merged geometry. **Before starting Section 7, open this file and confirm the actual function signatures** — if names differ, adjust file paths in Section 11 accordingly rather than creating a duplicate module.
- The exact line range in `pipeline/orchestrator.py` (previously located around lines 320–345) where `verify_realism`/`capture_all` are invoked.

---

## 2. Rename & restructure plan

### 2.1 Repo rename
- GitHub: rename `Vastanzil/blender-pipeline` → `Vastanzil/BlenderCopilot` (GitHub auto-creates a redirect from the old URL; update the `go-import` meta is automatic, no action needed there).
- Local clone: `git remote set-url origin https://github.com/Vastanzil/BlenderCopilot.git`.
- Product name string used in `create_shortcut.py`, `_make_shortcut.vbs`, `launch.bat`, `launch.pyw`, window titles in `gui/app.py`, and the startup dialog: change every literal `"Blender Pipeline Studio"` / `"BlenderPipelineStudio"` → `"BlenderCopilot"`.

### 2.2 Config migration (don't skip this)
Config currently lives at, e.g. on Windows, `%LOCALAPPDATA%\BlenderPipelineStudio\BlenderPipelineStudio\config.json`. On first launch after the rename, `config/registry.py` should:
1. Check if the new path (`...\BlenderCopilot\BlenderCopilot\config.json`) exists.
2. If not, check if the old `BlenderPipelineStudio` path exists; if so, copy it to the new location (don't delete the old one — just leave it as a backup).
3. Log a one-line notice either way so a user watching logs sees what happened.

### 2.3 BlenderLLM folder placement
BlenderLLM is **not** nested inside the app repo. It lives as a sibling folder, one level up from `BlenderCopilot/`, so it can be reused by other local projects later and so its multi-GB model weights never end up inside the git-tracked repo:

```
<parent-folder>/
├── BlenderCopilot/                  # renamed from blender-pipeline
│   ├── main.py
│   ├── ai/
│   │   ├── manifest_client.py
│   │   ├── blenderllm_client.py     # NEW — thin HTTP client, see §4/§5
│   │   └── router.py                # UPDATED — per-step routing, see §4
│   ├── pipeline/
│   │   ├── orchestrator.py          # UPDATED
│   │   └── scene_verifier.py        # UPDATED, see §7
│   └── ...
└── blenderllm/                      # NEW, sibling to BlenderCopilot, NOT git-tracked by it
    ├── repo/                        # clone of FreedomIntelligence/BlenderLLM
    │   ├── chat.py
    │   ├── modeling.py
    │   └── requirements.txt
    ├── models/                      # downloaded weights / GGUF conversions land here
    └── server/                      # NEW — our own OpenAI-compatible wrapper, see §5
        └── serve.py
```

`BlenderCopilot`'s config gets one new field: `blenderllm_home`, defaulting to `../blenderllm` relative to the repo root, overridable so it also works if someone points it at an existing install elsewhere.

---

## 3. Hybrid AI architecture

### 3.1 Core split
| Job | Route (Hybrid ON) | Why |
|---|---|---|
| Goal analysis, planning, decomposing a prompt, interpreting reference images | **Manifest → Claude** | Needs broad reasoning + vision; BlenderLLM has neither vision input nor multi-turn planning ability |
| Turning an already-decided step into `bpy` code | **Local BlenderLLM** | Narrow, syntax-heavy, exactly its training target — and free per call once hosted |
| Fixing a traceback on retry | **Local BlenderLLM** | Same reasoning, plus it's the highest-volume call in the pipeline (retry loop fires up to 5×/step) |
| Any step whose `skill_hint` involves materials, textures, or PBR (e.g. the existing "PBR Material from Reference Image" workflow template) | **Manifest → Claude**, even with Hybrid ON | BlenderLLM's own documented limitation is no material/texture/structural support — routing these to it would silently produce worse output with no error to catch |

That last row matters: this is **not** a single global toggle between "everything cloud" and "everything local." It's per-step, and one class of step is hard-pinned to Claude regardless of the toggle. Get this wrong and the toggle becomes a quality regression that only shows up on PBR-material tasks, which won't be caught by generic tests.

### 3.2 The toggle
`HYBRID_MODE: bool` in config, but implemented as a **routing table**, not an if/else in three call sites:

```python
# ai/router.py
ROUTES_HYBRID_ON = {
    "plan":          "manifest",
    "generate_code": "blenderllm",
    "fix_error":     "blenderllm",
}
ROUTES_HYBRID_OFF = {
    "plan": "manifest", "generate_code": "manifest", "fix_error": "manifest",
}

def resolve(step_kind: str, skill_hint: str | None, hybrid_on: bool) -> str:
    if skill_hint and any(k in skill_hint.lower() for k in ("material", "pbr", "texture")):
        return "manifest"                     # hard pin, ignores hybrid_on
    table = ROUTES_HYBRID_ON if hybrid_on else ROUTES_HYBRID_OFF
    return table[step_kind]
```

This gives a free upgrade path to a third mode later ("local for fix only, cloud for plan+codegen") without re-architecting — it's just a different dict.

### 3.3 The vision handoff problem (new — not in the earlier draft)
Current v3.0 behavior forwards reference images into **every** AI call, including `generate_code()` — "vision-aware code gen." BlenderLLM cannot accept images. So when Hybrid is ON and a step routes to BlenderLLM:

- `plan()` (on Claude) must produce a **self-contained textual description** of what that step needs to build — dimensions, colors, relative placement — detailed enough that `generate_code()` never needs to re-look at the image.
- `orchestrator.py`'s per-step payload needs a new field, e.g. `step.visual_context: str`, populated once during planning and reused by every codegen/fix call for that step, instead of re-passing `images=[...]`.
- Add an explicit unit test asserting that when `hybrid_on=True`, `BlenderLLMClient.generate_code()` is never called with a non-empty `images` argument — this is the kind of bug that won't throw an exception, it'll just silently degrade output quality.

---

## 4. `ai/blenderllm_client.py` — what to build

```python
class BlenderLLMClient:
    def __init__(self, base_url: str, timeout: int = 180): ...
    def generate_code(self, plan_text: str, visual_context: str) -> str: ...
    def fix_error(self, code: str, error: str, plan_text: str, visual_context: str) -> str: ...
    def health(self) -> bool: ...
```

Same shape as `ManifestClient` so `ai/router.py` can call either behind one interface. `timeout` defaults higher than Manifest's `ai_timeout` (120s) — CPU inference on a 7B model will be slower than an API call; see §5 for how much slower and what to do about it.

---

## 5. Serving BlenderLLM locally (CPU-aware — this changes the earlier assumption)

The earlier draft assumed "a self-hosted vLLM/TGI/Ollama endpoint." Two problems with that as stated:

1. BlenderLLM's own repo doesn't ship as a server at all — `modeling.py` loads weights and calls a local Blender executable itself in one script. We need to build the server wrapper ourselves; it doesn't exist upstream.
2. vLLM assumes a CUDA GPU. The known hardware for local AI work here is CPU-only for practical purposes (Ryzen 5 3600 / 32GB RAM, RX 5500 XT with limited ROCm support) — vLLM is off the table, and full-precision transformers CPU inference on a 7B model will be painfully slow for an interactive retry loop.

**Plan:**
1. Download `FreedomIntelligence/BlenderLLM` weights from Hugging Face into `blenderllm/models/`.
2. Convert to GGUF and quantize (Q4_K_M is a reasonable starting point — good quality/speed tradeoff for a 7B coder model on CPU) using `llama.cpp`'s `convert_hf_to_gguf.py`.
3. Serve via `llama.cpp`'s built-in OpenAI-compatible server (`llama-server`) or Ollama (`ollama create` with a Modelfile pointing at the GGUF) — either way you end up with a local `/v1/chat/completions`-compatible endpoint, which is exactly what `BlenderLLMClient` should target, and exactly what Manifest's "custom OpenAI-compatible provider" registration expects (see §6).
4. Benchmark actual tokens/sec on the real machine before committing to this as the default path — if Q4 CPU inference turns out too slow for a usable retry loop (this is the first thing to measure, not assume), fall back options in order of preference: (a) try Q4_0 or Q3_K for more speed at more quality cost, (b) keep BlenderLLM but cap it to first-attempt codegen only and route all *fixes* back to Manifest since fixes are more time-sensitive than initial generation, (c) shelve local codegen and keep Hybrid mode Manifest-only (this is the honest fallback if CPU throughput doesn't clear the bar — better to ship a smaller working feature than a slow "hybrid" nobody enables).

This benchmark (step 4) is the single most important unknown in this whole plan and should happen **before** wiring the toggle into the GUI, not after.

---

## 6. Manifest integration & unified logging

- Register the local BlenderLLM server as a **custom OpenAI-compatible provider** in Manifest's config (this is a Manifest config change, not app code) so both Claude calls and local calls flow through the same router and land in the same dashboard — including duration tracking on the "zero-cost" local calls, which is useful data even though $cost is 0.
- `BlenderLLMClient` can either call the local server directly, or call it *through* Manifest's endpoint with the registered model name — prefer routing through Manifest for the free unified logging/dashboard, and only bypass it (call the local server directly) if there's a specific reason to keep local traffic off the router process (there shouldn't be, since it's all localhost).
- No new logging code needs to be written. This section is entirely config + the client pointing at the right URL.

---

## 7. Wireframe / depth-capture verification feature

*(Written against the assumed current state of `pipeline/scene_verifier.py` — confirm against §1 before implementing.)*

### 7.1 Why
`verify_realism()` currently sends solid-shaded screenshots to the vision model to catch floating, sunk, or merged geometry. Those are fundamentally depth-relationship problems, and solid shading is exactly the shading mode that makes depth relationships ambiguous — two objects that are actually separated in depth can look flush in a solid render from the wrong angle.

### 7.2 What to add
Extend the existing `_CAPTURE_CODE` template to render a second pass per camera angle using Blender's **Workbench** engine in wireframe (and optionally x-ray) shading mode, rather than a full Cycles/EEVEE render — Workbench respects display settings even in background rendering and is far cheaper than a full render pass:

```python
def capture_wireframe(camera, output_path):
    original_engine = scene.render.engine
    original_shading = area.spaces[0].shading.type
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
        area.spaces[0].shading.type = 'WIREFRAME'   # or 'X-RAY' as a second variant
        bpy.ops.render.opengl(write_still=True)
    finally:
        scene.render.engine = original_engine
        area.spaces[0].shading.type = original_shading
```

Always restore original engine/shading settings in a `finally` block — this runs inside the same Blender session as the main render, so a crash mid-capture must not leave the scene in wireframe mode for the next step.

### 7.3 Where it hooks in
- `capture_all()` gains a second return list (or a `{camera_name: {"solid": path, "wireframe": path}}` dict) alongside the existing solid captures.
- `verify_realism()` sends **both** images per camera angle to the vision model in the same call, with a short instruction that the wireframe pass is provided specifically to disambiguate depth/occlusion — don't send them as two separate vision-model calls, since the value is in the model comparing them side by side.
- `orchestrator.py`'s call site (previously around lines 320–345) doesn't need new branching logic, just needs to pass through whatever `capture_all()` now returns to `verify_realism()`.
- Make this **toggleable and scoped**, not unconditional: add a `capture_wireframe: bool` config flag (default on, since it's cheap), and skip it for workflow templates where depth ambiguity isn't the concern — e.g. skip for "PBR Material from Reference Image," since that step doesn't change geometry.

### 7.4 What NOT to do here
Don't route wireframe capture through Hybrid mode's local/cloud split — this is a Blender-side rendering feature, unrelated to which LLM is doing planning or codegen. Keep §3–§6 and §7 as orthogonal changes; they'll be developed and tested independently even though they land in the same repo at the same time.

---

## 8. Pros / cons and how each con gets closed out

| Concern | Mitigation | Where it's handled |
|---|---|---|
| BlenderLLM (7B) codegen quality below Claude on edge cases | Escalation lane: if BlenderLLM fails the same step twice in the retry loop, escalate that one step to Manifest/Claude for the remaining retries; log every escalation | `pipeline/retry_loop.py` |
| No multi-turn memory in BlenderLLM | Already the existing pattern — retry loop re-injects full (error + prior code + plan) as one fresh prompt each cycle. No new work, just confirm it stays true when the client changes. | `pipeline/retry_loop.py` |
| No multimodal input in BlenderLLM | Planning stage must emit a self-contained textual `visual_context` per step; codegen/fix never receive raw images under Hybrid mode | §3.3 |
| No material/texture support in BlenderLLM | Hard-pin material/PBR-flavored steps to Manifest regardless of toggle state | §3.1, §3.2 |
| CPU-only hardware → unknown local throughput | Benchmark tokens/sec before wiring the GUI toggle; documented fallback ladder if too slow | §5 |
| Wireframe pass adds render time | Cheap Workbench OpenGL pass, not a full render; toggleable; skipped for workflows where it adds no value | §7.3 |
| License compatibility | Manifest: MIT. BlenderLLM: Apache-2.0. App: GPL-3.0. Both inbound directions are compatible with GPL-3.0. Note the app's own README currently has a contradiction — the license badge says GPL-3.0 but the Credits section footer text says "MIT — free to use and modify"; fix that inconsistency during the doc pass in §10, don't leave it. | §10 |

---

## 9. Testing & benchmark plan

Build on the existing 94-test suite rather than replacing it.

1. **Unit tests, new:**
   - `ai/router.py::resolve()` — every combination of `step_kind` × `hybrid_on` × material-hint-present, including the hard-pin case.
   - `BlenderLLMClient` — mocked HTTP, confirm no `images` payload is ever sent.
   - Config migration — old path exists / new path exists / neither exists, all three branches.
   - Wireframe capture — engine/shading restored correctly even when the render call raises.
2. **Integration/benchmark harness (new script, e.g. `tests/benchmark_hybrid.py`):** run the same task set through Hybrid ON and Hybrid OFF, recording token cost, wall-clock time, and success rate (pass/fail against `verify_realism`). This is the number that decides whether hybrid mode ships as default-on or stays an opt-in toggle — don't decide that ahead of the data.
3. **Wireframe-specific validation:** hand-pick 5–10 known "floating/sunk/merged geometry" failure cases from prior runs (if logged) and confirm the wireframe pass measurably improves `verify_realism` catch rate on that set, not just that it runs without error.
4. **Soak test:** once both features are wired together, run a larger batch (aim for order-of-magnitude more than the 94-test suite — hundreds of prompts, not thousands, is a realistic bar given the CPU serving constraint) to surface intermittent BlenderLLM failures, escalation-lane trigger rate, and timeout tuning needs before calling this production-grade.

---

## 10. Documentation updates checklist

- `README.md` — update repo name, architecture diagram (add BlenderLLM box + wireframe capture note), Project Structure tree, config table (`hybrid_mode`, `blenderllm_home`, `capture_wireframe`), changelog entry for the new version, **fix the GPL-3.0/MIT license contradiction** in the Credits/License sections.
- `INSTALLATION.md` — add BlenderLLM setup: cloning into `../blenderllm/repo`, downloading weights, GGUF conversion, starting the local server, registering it in Manifest.
- `USAGE.md` — document the Hybrid toggle location in the GUI, what it changes, and the material/PBR hard-pin behavior so users aren't confused when a "local mode" run still shows a Claude call in the log for a material step.
- `.env.example` — add `BLENDERLLM_HOME`, `BLENDERLLM_SERVER_URL` if not routed through Manifest.
- Rename all remaining `blender-pipeline` / `Blender Pipeline Studio` references repo-wide (`grep -ri "blender.pipeline" .` after the code changes land, to catch stragglers in comments/docstrings).

---

## 11. Phased execution task list (for Claude Code)

**Phase 0 — Rename & restructure**
- [ ] Rename repo on GitHub, update local remote.
- [ ] Global find/replace of product name strings (`gui/`, shortcut scripts, launch scripts, window titles).
- [ ] Implement config migration in `config/registry.py`.
- [ ] Create sibling `blenderllm/` folder structure (`repo/`, `models/`, `server/`).

**Phase 1 — BlenderLLM standalone, before touching the app**
- [ ] Clone `FreedomIntelligence/BlenderLLM` into `blenderllm/repo/`.
- [ ] Download weights into `blenderllm/models/`.
- [ ] Convert to GGUF, quantize (start with Q4_K_M).
- [ ] Stand up `llama-server`/Ollama serving it as an OpenAI-compatible endpoint.
- [ ] **Benchmark tokens/sec on real hardware. Do not proceed to Phase 2 until this number is known.**

**Phase 2 — Router & client**
- [ ] Write `ai/blenderllm_client.py`.
- [ ] Write the `resolve()` routing table in `ai/router.py`, including the material hard-pin.
- [ ] Add `hybrid_mode`, `blenderllm_home`, `blenderllm_server_url` to `config/defaults.py` / `schema.py`.
- [ ] Add `step.visual_context` field and update `orchestrator.py` to populate it during planning and stop forwarding raw images to codegen/fix calls when `hybrid_mode=True`.
- [ ] Add the escalation-lane logic to `pipeline/retry_loop.py`.

**Phase 3 — Manifest wiring**
- [ ] Register the local BlenderLLM endpoint as a custom provider in Manifest config.
- [ ] Point `BlenderLLMClient` at Manifest (preferred) or the local server directly.
- [ ] Confirm dashboard shows both Claude and local calls.

**Phase 4 — Wireframe capture**
- [ ] Confirm actual current contents of `pipeline/scene_verifier.py` against §1/§7 assumptions; adjust names/paths if they differ.
- [ ] Implement `capture_wireframe()` extension to `_CAPTURE_CODE`.
- [ ] Update `capture_all()` return shape and `verify_realism()` call to send solid+wireframe pairs.
- [ ] Add `capture_wireframe` config flag and the per-workflow skip logic.

**Phase 5 — Tests**
- [ ] Unit tests per §9.1.
- [ ] Benchmark harness script per §9.2, run Hybrid ON vs OFF.
- [ ] Wireframe catch-rate validation per §9.3.
- [ ] Soak test per §9.4.

**Phase 6 — Docs**
- [ ] Everything in §10.
- [ ] Bump version, write changelog entry.

---

## 12. Open questions to confirm before/while building

1. Confirm `pipeline/scene_verifier.py`'s real current API (§1) — this plan's §7 is written against an assumed shape.
2. Confirm whether BlenderLLM should be called *through* Manifest or directly (§6) — direct is simpler to build first; routing through Manifest is better long-term for unified logging. Fine to build direct first and switch once Phase 1's benchmark confirms the feature is worth keeping.
3. Decide the fallback ladder outcome from §5 step 4 *before* committing to Hybrid mode as anything more than an experimental opt-in toggle in the GUI.
