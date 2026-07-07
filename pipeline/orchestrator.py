"""
pipeline/orchestrator.py
v4.0: production-grade upgrade — art style system, scene-protection guardrails,
proper checkpoint resume (skips completed steps), ctx refresh every 5 steps,
scene diff injection, 20-40 step plans, NoneType guards, incremental saves.
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path

from .step             import PipelineStep
from .retry_loop       import RetryLoop
from .checkpoint       import Checkpoint
from .validator        import Validator
from .stages           import Stage
from .spatial_reasoner import SpatialReasoner, DetectedObject, detect_scene_scale
from .poly_budget      import PolyBudgetManager
from .pipeline_logger  import PipelineLogger
from .project_namer    import ProjectNamer
from .terrain_builder  import TerrainBuilder, TerrainFeature, TERRAIN_KEYWORDS
from .scene_verifier   import SceneVerifier
from .reference_loop   import ReferenceLoop
from .scene_positions  import ScenePositions
from .scene_validator  import SceneValidator
from .blueprint        import BlueprintManager
from ai.context_builder import ContextBuilder
from config.registry    import get
from utils.logger       import get_logger

log = get_logger("orchestrator")

_TERRAIN_FEATURE_MAP = {
    "hill":   TerrainFeature.HILL,   "valley": TerrainFeature.VALLEY,
    "road":   TerrainFeature.ROAD,   "path":   TerrainFeature.ROAD,
    "pond":   TerrainFeature.POND,   "lake":   TerrainFeature.POND,
    "river":  TerrainFeature.RIVER,  "stream": TerrainFeature.RIVER,
}

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "has", "have",
    "will", "use", "using", "make", "create", "add", "set", "get", "all", "any",
    "not", "you", "your", "its", "can", "may", "but", "yet", "also",
    "stylized", "detailed", "beautiful", "realistic", "simple", "new",
    "render", "rendering", "scene", "object", "objects", "model", "models",
    "blender", "given", "provided", "sample", "reference", "image",
    "understand", "information", "request", "describe", "briefly",
    "bpy", "import", "context", "data", "ops", "types", "mesh", "edit",
    "mode", "material", "node", "nodes", "engine", "cycles", "eevee",
}

# Injected into every code-gen prompt to prevent object deletion
_SCENE_GUARD = (
    "CRITICAL: Do NOT delete, clear, or overwrite existing scene objects. "
    "Do NOT call bpy.ops.object.delete(), select_all(action='SELECT') followed by delete, "
    "or bpy.ops.wm.read_*. Only ADD new objects. Existing objects must remain untouched.\n"
)

# Snapshot Blender object names via print() → captured in exec output
_SNAPSHOT_CODE = (
    "import bpy, json\n"
    "print('__OBJ_SNAPSHOT__:' + json.dumps([o.name for o in bpy.data.objects]))\n"
)

# Art style + domain knowledge blocks, injected based on prompt keywords
_ART_STYLE_BLOCKS: dict[str, str] = {
    "stylized": (
        "ART STYLE — Stylized/Cartoon:\n"
        "- Exaggerated proportions; smooth, rounded geometry with minimal high-frequency detail\n"
        "- Flat or cel-shaded materials (low roughness variation, saturated hues)\n"
        "- Toon shader: Shader to RGB + ColorRamp node in Blender materials\n"
        "- Strong readable silhouettes; Solidify modifier (flip normals) for outlines\n"
    ),
    "realistic": (
        "ART STYLE — Photorealistic/PBR:\n"
        "- True-to-life proportions and real-world scale (metres)\n"
        "- Multi-layer PBR materials: albedo, roughness map, normal map, AO\n"
        "- Micro-surface detail via Bump/Normal nodes from procedural noise\n"
        "- Edge wear: MixRGB blending base+bright material driven by Geometry > Pointiness\n"
        "- Subsurface scattering for organic materials (leaves, skin, wax)\n"
        "- HDRI world lighting + area lights for bounced GI\n"
        "- Camera: focal length 35-85mm, slight DOF for hero shots\n"
    ),
    "low_poly": (
        "ART STYLE — Low-Poly/Flat:\n"
        "- Deliberate low triangle count (50-500 tris per prop)\n"
        "- Flat shading only — no smooth shading, no SubSurf\n"
        "- Single-color materials per object; palette of 4-6 complementary colors\n"
        "- shade_flat=True on all polygons; strong geometric forms as design choice\n"
    ),
    "semi_realistic": (
        "ART STYLE — Semi-Realistic/Game-Ready:\n"
        "- Moderate poly count (500-5000 tris hero prop, 50-500 background)\n"
        "- PBR materials, slightly saturated warm highlights, cool shadows\n"
        "- Modular architectural pieces that tile/snap to a grid\n"
        "- Foliage: alpha-clipped planes with image textures (not geometry)\n"
    ),
    "medieval": (
        "DOMAIN KNOWLEDGE — Medieval Architecture:\n"
        "- Watchtowers: cylindrical or square base, 8-20m tall, battlements on top\n"
        "  (merlons ~0.5m wide, crenels between them, parapet walk at top)\n"
        "- Castle walls: 1.5-3m thick, 6-10m tall, square towers at corners\n"
        "- Gates: pointed arch (Gothic) or round arch (Romanesque), portcullis slot\n"
        "- Roofs: conical (round towers), pyramid (square towers), crenellated flat top\n"
        "- Materials: rough limestone/granite (roughness 0.85-0.95)\n"
        "- Wood: dark oak color (roughness 0.7, subtle grain Noise texture)\n"
        "- Windows: arrow slits (tall narrow rectangles, ~0.2m wide x 1.0m tall)\n"
        "- Stairs: exterior spiral staircases hugging the tower exterior\n"
    ),
    "island": (
        "DOMAIN KNOWLEDGE — Island/Coastal Terrain:\n"
        "- Island base: circular or organic raised mesh, gentle slopes to water level\n"
        "- Shore: gradual slope, sandy color at water edge (tan/beige)\n"
        "- Ocean plane: flat large plane at Z=0, deep blue, roughness 0.05, metallic 0.9\n"
        "- Waves: Displace modifier on ocean plane with cloud texture, strength 0.1-0.3\n"
        "- Coastal rocks: clusters of flattened UV spheres scattered on beach\n"
        "- Vegetation: palm or pine trees on higher ground (keep away from water edge)\n"
    ),
    "sci_fi": (
        "ART STYLE — Science Fiction/Hard Surface:\n"
        "- Sharp machined edges: Bevel modifier (2-3 segments, weight 0.02-0.05)\n"
        "- Panel lines via Boolean cuts or shrinkwrap onto base mesh\n"
        "- Materials: brushed metal (Anisotropic BSDF), dark composite, emissive strips (strength 5-20)\n"
        "- Greebling: small geometric details on flat surfaces (bolts, vents, antenna)\n"
        "- Scale: door 2m, ceiling 3m, corridor 2.5m wide\n"
    ),
    "nature": (
        "DOMAIN KNOWLEDGE — Natural Environments:\n"
        "- Trees: IcoSphere canopy (scale X,Y,Z varied) + cylinder trunk\n"
        "- Rocks: UV Sphere + Decimate modifier (ratio 0.3) + Displace modifier\n"
        "- Water: animated Displace modifier with Wave texture on subdivided plane\n"
        "- Sky: World shader with Sky Texture (Nishita type) for procedural atmosphere\n"
        "- Lighting: Sun lamp angle 45-60°, strength 3-5, warm color temperature\n"
    ),
}

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "stylized":       ["stylized", "cartoon", "toon", "cel", "anime"],
    "realistic":      ["realistic", "photorealistic", "pbr", "hyper-real", "cinematic"],
    "low_poly":       ["low poly", "low-poly", "lowpoly", "flat", "minimalist"],
    "semi_realistic": ["semi-realistic", "game ready", "game-ready", "stylised realistic"],
    "medieval":       ["medieval", "castle", "watchtower", "knight", "fortress", "dungeon",
                       "tower", "battlements", "keep", "citadel"],
    "island":         ["island", "ocean", "beach", "coastal", "archipelago", "tropical"],
    "sci_fi":         ["sci-fi", "scifi", "futuristic", "space", "cyberpunk", "dystopian"],
    "nature":         ["forest", "jungle", "meadow", "mountain", "cave", "nature", "wilderness"],
}


class Orchestrator:
    def __init__(self, client, ai, bus=None):
        self._client     = client
        self._ai         = ai
        self._bus        = bus
        self._retry      = RetryLoop(client, ai, max_retries=get("max_retries", 5))
        self._validator  = Validator(client)
        self._spatial    = SpatialReasoner()
        self._poly       = PolyBudgetManager()
        self._terrain    = TerrainBuilder()
        self._verifier   = SceneVerifier()
        self._namer      = ProjectNamer()
        self._abort_flag = False

    def abort(self):
        self._abort_flag = True

    def _emit(self, event: str, data: dict):
        if self._bus:
            try:
                self._bus.emit(event, data)
            except Exception:
                pass

    def _detect_style_blocks(self, text: str) -> str:
        combined = text.lower()
        blocks = []
        for style, keywords in _STYLE_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                blocks.append(_ART_STYLE_BLOCKS[style])
        return "\n".join(blocks)

    def _snapshot_objects(self) -> set[str]:
        """Return current Blender object names via exec (best-effort)."""
        try:
            snap = self._client.exec_code(_SNAPSHOT_CODE)
            m = re.search(r'__OBJ_SNAPSHOT__:(\[.*?\])', str(snap.output or ""))
            if m:
                return set(json.loads(m.group(1)))
        except Exception:
            pass
        return set()

    # ------------------------------------------------------------------

    def run(self, prompt: str, images: list | None = None,
            skill_hint: str = "") -> list:
        self._abort_flag = False
        t0 = time.perf_counter()
        log.info(f"Pipeline start: {prompt[:70]}")
        self._emit("pipeline.start", {"prompt": prompt})

        output_dir = (get("output_dir", "") or
                      str(Path.home() / "blender_pipeline_output"))
        rag_dir    = (get("rag_corpus_dir", "") or
                      str(Path(output_dir) / "_rag_corpus"))

        spatial_nodes:   list      = []
        completed_steps: list[str] = []
        goal_summary = ""

        def _ctx_snapshot() -> dict:
            return {
                "goal":             goal_summary,
                "project_name":     checkpoint.state.project_name if "checkpoint" in dir() else "",
                "spatial_nodes":    [{"label": n.label, "world_pos": list(n.world_pos)}
                                     for n in spatial_nodes],
                "completed_steps":  list(completed_steps),
                "scene_objects":    [],
                "validation_state": "ok",
            }

        logger     = PipelineLogger(rag_dir, context_snapshot_fn=_ctx_snapshot)
        checkpoint = Checkpoint()

        # ── 1. Blender context ─────────────────────────────────────────
        ver = (5, 1, 0)
        ctx = ""
        try:
            ver = self._client.get_blender_version()
            ctx = ContextBuilder(self._client, ver).build()
        except Exception as e:
            log.warning(f"Context build failed: {e}")

        # ── 2. Goal analysis ───────────────────────────────────────────
        try:
            goal_prompt = (
                f"Briefly describe in 1-3 sentences what Blender actions you will "
                f"perform for this request. Do NOT write code yet.\n\nRequest: {prompt}"
            )
            goal_summary = self._ai.describe(goal_prompt, images=images)
            goal_summary = goal_summary[:300]
            self._emit("pipeline.goal_analysis", {"summary": goal_summary})
            logger.log("goal", "response", goal_summary)
            log.info(f"Goal: {goal_summary[:80]}")
        except Exception:
            pass

        # ── 3. Style detection + scene scale ──────────────────────────
        style_block = self._detect_style_blocks(prompt + " " + goal_summary)
        scene_scale = detect_scene_scale(prompt + " " + goal_summary)
        log.info(f"Scene scale preset: {scene_scale}")

        # ── 4. Object detection + spatial layout ──────────────────────
        detections       = self._detect_objects(prompt, goal_summary)
        terrain_features = [d for d in detections if d.label.lower() in TERRAIN_KEYWORDS]
        prop_detections  = [d for d in detections if d.label.lower() not in TERRAIN_KEYWORDS]

        spatial_nodes = self._spatial.build_layout(prop_detections, scene_scale=scene_scale)
        spatial_block = self._spatial.to_prompt_block(spatial_nodes)
        self._emit("pipeline.spatial_layout",
                   {"nodes": [{"label": n.label, "world_pos": list(n.world_pos)}
                               for n in spatial_nodes]})

        # ── 5. Project naming ──────────────────────────────────────────
        detected_labels = [d.label for d in detections]
        project_name    = self._namer.name_from_understanding(goal_summary, detected_labels)
        checkpoint.set_project_name(project_name)
        self._emit("pipeline.project_named", {"name": project_name})
        logger.log("project_name", "system", project_name)

        # ── 6. Plan (20-40 detailed steps) ────────────────────────────
        ctx_capped    = ctx[:4000]
        skill_section = f"\nSKILL HINTS: {skill_hint}\n" if skill_hint else ""
        plan_prompt = (
            f"{ctx_capped}{skill_section}\n\n"
            f"SCENE GOAL: {goal_summary}\n\n"
            f"{style_block}\n"
            f"{spatial_block}\n\n"
            f"USER REQUEST: {prompt}\n\n"
            "You are a professional 3D scene director and Blender Python expert. "
            "Plan a complete Blender construction sequence.\n"
            "Return a NUMBERED LIST of 20-40 detailed steps.\n"
            "Requirements for each step:\n"
            "  - Specify what object to create, its exact dimensions, and position\n"
            "  - Specify the material (color, roughness, metallic values)\n"
            "  - Reference objects created in earlier steps by their exact name\n"
            "  - Include modifiers needed (Bevel, Subdivision, Solidify, Displace)\n"
            "Build complexity progressively: base geometry first, then detail, "
            "then materials, then lighting.\n"
            "Include: base terrain/ground, main structures, secondary details, "
            "materials, lighting, camera setup as a final step.\n"
            "Good: '5. Build TowerBattlements: extrude 8 merlons (0.3x0.5x0.4m) around "
            "top of TowerWall; Solidify 0.15m; stone material (gray 0.6, rough 0.9)'\n"
            "Bad:  '5. Add details'\n"
            "One step per line: '1. ...', '2. ...', etc. No JSON, no code blocks."
        )
        logger.log("plan", "prompt", plan_prompt[:500])
        try:
            plan = self._ai.plan(plan_prompt, images=images)
        except Exception as e:
            log.error(f"Planning failed: {e}")
            self._emit("pipeline.aborted", {"reason": str(e), "phase": "planning"})
            return []

        if not plan:
            log.warning("Empty plan returned by AI")
            self._emit("pipeline.aborted",
                       {"reason": "AI returned no steps — try rephrasing your prompt",
                        "phase": "planning"})
            return []

        logger.log("plan", "response", str(plan))
        checkpoint.save_plan(plan)   # persist full plan before any step executes
        checkpoint.mark_complete(Stage.SPATIAL_LAYOUT,
                                 [{"label": n.label, "world_pos": list(n.world_pos)}
                                  for n in spatial_nodes])
        self._emit("pipeline.plan", {"total": len(plan), "steps": plan})
        log.info(f"Plan: {len(plan)} steps")

        # ── 6b. Blueprint generation (Layer 0) ─────────────────────────
        blueprint_slots = []
        if get("blueprint_enabled", True):
            try:
                bp = BlueprintManager(self._client)
                blueprint_slots = bp.generate(
                    plan, scene_scale=scene_scale, style_block=style_block
                )
                if blueprint_slots:
                    bp.materialize(blueprint_slots)
                    self._emit("pipeline.blueprint", {
                        "slots": [{"label": s.label, "pos": list(s.pos)}
                                  for s in blueprint_slots]
                    })
                    log.info(f"Blueprint: {len(blueprint_slots)} slots generated")
            except Exception as e:
                log.warning(f"Blueprint generation failed: {e}")

        # Visual context per step (hybrid mode)
        step_visual_contexts: list[str] = []
        if images:
            for desc in plan:
                try:
                    vc = self._ai.describe(
                        f"{desc}\nDescribe visual/spatial requirements in 2-3 sentences. No code.",
                        images=images,
                    )
                except Exception:
                    vc = ""
                step_visual_contexts.append(vc)
        else:
            step_visual_contexts = [""] * len(plan)

        # ── 7. Terrain Step 0 ─────────────────────────────────────────
        has_terrain = bool(terrain_features)
        if has_terrain:
            terrain_code = self._terrain.base_terrain_snippet()
            if not self._retry.execute(terrain_code, ctx).success:
                log.warning("Terrain init failed — continuing without terrain")
                has_terrain = False

        # ── 8. Execute steps ───────────────────────────────────────────
        steps = self._execute_steps(
            plan=plan,
            start_idx=0,
            ctx=ctx,
            ver=ver,
            images=images,
            goal_summary=goal_summary,
            style_block=style_block,
            spatial_block=spatial_block,
            spatial_nodes=spatial_nodes,
            step_visual_contexts=step_visual_contexts,
            checkpoint=checkpoint,
            logger=logger,
            output_dir=output_dir,
            project_name=project_name,
            has_terrain=has_terrain,
            completed_steps=completed_steps,
            scene_scale=scene_scale,
            blueprint_slots=blueprint_slots,
        )

        # ── 9. Scene verification ──────────────────────────────────────
        screenshots:    list[str] = []
        realism_issues: list      = []
        try:
            screenshots = self._verifier.capture_all(self._client, output_dir)
            if screenshots:
                report = self._verifier.verify_realism(
                    self._ai, screenshots, spatial_nodes, project_name
                )
                realism_issues = [
                    {"type": i.type, "objects": i.objects, "fix_hint": i.fix_hint}
                    for i in report.issues
                ]
                self._emit("pipeline.realism_report",
                           {"issues": realism_issues, "screenshots": screenshots})
                logger.log("verify", "response", str(realism_issues))
                for issue in report.issues[:3]:
                    if not issue.fix_hint:
                        continue
                    fix = self._strip_fences(
                        self._ai.generate_code(
                            f"Fix this scene issue in Blender: {issue.fix_hint}\n"
                            "Return ONLY executable Python code.",
                            images=screenshots,
                        )
                    )
                    self._client.exec_code(fix)
        except Exception as e:
            log.warning(f"Scene verification failed: {e}")

        # ── 10. Reference-guided refinement loop ──────────────────────
        if images:
            try:
                ref_loop = ReferenceLoop(
                    self._client, self._ai,
                    max_iterations=int(get("ref_loop_max_iter", 3)),
                    score_threshold=int(get("ref_loop_threshold", 75)),
                )
                loop_results = ref_loop.run(images, output_dir, project_name, ctx)
                self._emit("pipeline.reference_loop_done", {"iterations": loop_results})
                logger.log("reference_loop", "response", str(loop_results))
                log.info(f"Reference loop: {len(loop_results)} iteration(s)")
            except Exception as e:
                log.warning(f"Reference loop failed: {e}")

        # ── 11. Auto-save .blend ───────────────────────────────────────
        try:
            blend_path = Path(output_dir).expanduser() / f"{project_name}.blend"
            blend_path.parent.mkdir(parents=True, exist_ok=True)
            self._client.exec_code(
                f"import bpy\nbpy.ops.wm.save_as_mainfile(filepath=r'{blend_path}')\n"
            )
            checkpoint.mark_complete(Stage.SAVE, str(blend_path))
            self._emit("pipeline.blend_saved", {"path": str(blend_path)})
            log.info(f"Saved .blend → {blend_path}")
        except Exception as e:
            log.warning(f".blend save failed: {e}")

        elapsed  = time.perf_counter() - t0
        ok_count = sum(1 for s in steps if s.success)
        log.info(f"Pipeline done: {ok_count}/{len(steps)} OK in {elapsed:.1f}s")

        # ── 12. Post-run scene validation (Layer 5) ──────────────────────
        validation_issues: list[dict] = []
        confidence_score: int = 100
        try:
            validator = SceneValidator(self._client)
            issues = validator.validate(
                reasoner=self._spatial,
                score_threshold=int(get("min_confidence_threshold", 70)),
            )
            validation_issues = [
                {"type": i.type, "objects": i.objects, "fix_hint": i.fix_hint, "score": i.score}
                for i in issues
            ]
            for i in issues:
                if i.type == "confidence":
                    confidence_score = i.score
                elif i.fix_hint:
                    fix_code = self._strip_fences(
                        self._ai.generate_code(
                            f"Fix this spatial issue: {i.fix_hint}\n"
                            f"Current object positions: {validator._positions.to_prompt_block()}\n"
                            "Return ONLY executable Python code.",
                            images=None,
                        )
                    )
                    self._client.exec_code(fix_code)
        except Exception as e:
            log.warning(f"Scene validation failed: {e}")

        self._emit("pipeline.done", {
            "total_steps":  len(steps),
            "ok":           ok_count,
            "elapsed_s":    round(elapsed, 2),
            "checkpoint":   checkpoint.path,
            "project_name": project_name,
            "screenshots":  screenshots,
            "confidence":   confidence_score,
            "validation_issues": validation_issues,
        })
        return steps

    # ------------------------------------------------------------------
    # Step execution helper — shared by run() and resume()

    def _execute_steps(
        self,
        plan: list[str],
        start_idx: int,
        ctx: str,
        ver: tuple,
        images: list | None,
        goal_summary: str,
        style_block: str,
        spatial_block: str,
        spatial_nodes: list,
        step_visual_contexts: list[str],
        checkpoint,
        logger,
        output_dir: str,
        project_name: str,
        has_terrain: bool,
        completed_steps: list[str],
        scene_scale: str = "default",
        blueprint_slots: list = None,
    ) -> list:
        steps: list[PipelineStep] = []
        ctx_capped = ctx[:3000]
        scene_pos = ScenePositions(self._client)

        # Seed position registry from blueprint slots (Layer 0 → Layer 1)
        if blueprint_slots:
            scene_pos.seed_from_blueprint(blueprint_slots)

        for idx, description in enumerate(plan):
            if idx < start_idx:
                continue

            # NoneType guard
            if not description or not isinstance(description, str):
                continue
            description = description.strip()
            if not description:
                continue
            first_word = (description.split() or ["object"])[0].lower()

            if self._abort_flag:
                log.info("Pipeline aborted by user")
                self._emit("pipeline.aborted", {"at_step": idx})
                break

            self._emit("pipeline.step.start",
                       {"index": idx, "total": len(plan), "description": description})
            log.info(f"Step {idx+1}/{len(plan)}: {description}")

            # Scene diff — snapshot before step
            pre_objects = self._snapshot_objects()

            visual_ctx  = step_visual_contexts[idx] if idx < len(step_visual_contexts) else ""
            node_pos    = self._node_pos_for(description, spatial_nodes)
            obj_label   = self._extract_label_from_description(description)
            rename_hint = (
                f"\nName the created object '{obj_label}' using "
                f"bpy.context.object.name = '{obj_label}'"
            )

            # Estimate footprint for collision check (keyword heuristic)
            approx_dim  = self._estimate_dim(description, scene_scale)

            # Guaranteed position: blueprint slot → spatial_nodes match → free slot
            if node_pos is None or scene_pos.overlaps(node_pos, approx_dim) is not None:
                from .spatial_reasoner import _SCALE_PRESETS
                min_sep, _ = _SCALE_PRESETS.get(scene_scale, _SCALE_PRESETS["default"])
                node_pos = scene_pos.next_free_pos(
                    candidate_dim=approx_dim, min_spacing=min_sep * 2
                )

            pos_hint = (
                f"\nPlace the object's ORIGIN at world position {node_pos}. "
                f"Approximate footprint: {approx_dim[0]:.1f}×{approx_dim[1]:.1f}×{approx_dim[2]:.1f} m. "
                f"Do NOT place at origin. Check PLACED OBJECTS below — "
                f"your bounding box must not intersect any listed object.\n"
            )

            placed_block = scene_pos.to_prompt_block()

            code_prompt = (
                f"{ctx_capped}\n\n"
                f"{_SCENE_GUARD}"
                f"PROJECT GOAL: {goal_summary}\n"
                f"{style_block}\n"
                f"{spatial_block}\n"
                f"{placed_block}\n"
                f"SCENE BUILT SO FAR: {', '.join(completed_steps[-6:]) or 'nothing yet'}\n\n"
                f"CURRENT STEP ({idx+1}/{len(plan)}): {description}\n"
                f"{pos_hint}{rename_hint}\n"
                "Return ONLY executable Python code. No explanation."
            )
            logger.log("codegen", "prompt", code_prompt[:400], meta={"step": idx})

            try:
                code = self._ai.generate_code(
                    code_prompt, images=images,
                    skill_hint=None,
                    visual_context=visual_ctx,
                )
                code = self._strip_fences(code)
            except Exception as e:
                code = f"print('Code generation failed: {e}')"
                log.warning(f"Code gen failed step {idx+1}: {e}")

            logger.log("codegen", "response", code[:400], meta={"step": idx})

            obj_name = self._extract_obj_name(code, description)

            result = self._retry.execute(
                code, ctx_capped,
                skill_hint=None,
                visual_context=visual_ctx,
            )

            step = PipelineStep(
                index            = idx,
                description      = description,
                code             = result.code,
                success          = result.success,
                error            = result.error,
                output           = result.output,
                attempts         = result.attempts,
                bpy_object_name  = obj_name,
                spatial_pos      = node_pos or (),
                poly_tris_target = self._poly.budget_for(first_word),
                visual_context   = visual_ctx,
            )

            # Existence validation
            if result.success and obj_name:
                passed, reason = self._validator.validate_step_result(step)
                if not passed:
                    log.warning(f"Validation fail step {idx+1}: {reason}")
                    fix_prompt = (
                        f"{ctx_capped}\n\n"
                        f"{_SCENE_GUARD}"
                        f"The following code ran without error but the object "
                        f"'{obj_name}' was not visible in the scene:\n\n{code}\n\n"
                        f"Reason: {reason}\n"
                        "Rewrite the code so the object is created and visible. "
                        "Ensure bpy.context.view_layer.update() is called."
                    )
                    fix_code = self._strip_fences(
                        self._ai.generate_code(fix_prompt, images=images,
                                               visual_context=visual_ctx)
                    )
                    fix_result = self._retry.execute(fix_code, ctx_capped,
                                                     visual_context=visual_ctx)
                    if fix_result.success:
                        step.code     = fix_result.code
                        step.success  = True
                        step.error    = ""
                        step.attempts += fix_result.attempts

            # Poly budget decimate
            if result.success and obj_name:
                is_organic = any(kw in description.lower()
                                 for kw in ("tree", "bush", "rock", "terrain", "hill"))
                decimate = self._poly.decimate_snippet(obj_name, first_word, is_organic)
                self._client.exec_code(decimate)

            # Place on terrain
            if has_terrain and result.success and obj_name and node_pos:
                place_code = self._terrain.place_on_terrain_snippet(
                    obj_name, (node_pos[0], node_pos[1])
                )
                self._client.exec_code(place_code)

            # Scene diff — snapshot after, track what was added
            post_objects = self._snapshot_objects()
            added = sorted(post_objects - pre_objects)
            if added:
                completed_steps.append(f"{description} → created: {', '.join(added)}")
                scene_pos.refresh(set(added))
            else:
                completed_steps.append(description)

            steps.append(step)

            self._emit("pipeline.step.done", {
                "index":       idx,
                "total":       len(plan),
                "description": description,
                "success":     step.success,
                "attempts":    step.attempts,
                "error":       step.error or "",
                "code":        step.code  or "",
                "obj_name":    obj_name,
            })

            checkpoint.save(steps)
            checkpoint.mark_complete(Stage.ASSET_GEN, idx)

            if not result.success:
                log.warning(f"Step {idx+1} failed: {result.error[:80]}")

            # End-of-block operations every 5 steps
            if idx % 5 == 4:
                # Refresh scene context so AI sees newly created objects
                try:
                    ctx = ContextBuilder(self._client, ver).build()
                    ctx_capped = ctx[:3000]
                except Exception:
                    pass
                # Full position registry refresh
                scene_pos.refresh()

                # Incremental .blend save
                if step.success:
                    try:
                        interim = (Path(output_dir).expanduser()
                                   / f"{project_name}_step{idx+1:02d}.blend")
                        self._client.exec_code(
                            f"import bpy\n"
                            f"bpy.ops.wm.save_as_mainfile(filepath=r'{interim}')\n"
                        )
                        log.info(f"Incremental save → {interim}")
                    except Exception:
                        pass

                # Liveness probe
                if not self._validator.is_alive():
                    log.error("Blender became unresponsive — aborting")
                    self._emit("pipeline.aborted", {"reason": "blender_unresponsive"})
                    break

        return steps

    # ------------------------------------------------------------------
    # Resume from checkpoint — skips completed steps

    def resume(self, run_id: str, prompt: str = "",
               images: list | None = None) -> list:
        checkpoint = Checkpoint(run_id)
        saved = sorted(checkpoint.state.steps, key=lambda s: s.get("index", 0))

        # Prefer the persisted full plan; fall back to executed-step descriptions
        if checkpoint.state.plan:
            full_plan = checkpoint.state.plan
        elif saved:
            full_plan = [s["description"] for s in saved]
        else:
            return self.run(prompt or "resume", images=images)

        resume_from = next(
            (i for i, s in enumerate(saved) if not s.get("success")),
            len(saved),
        )

        # When all saved steps succeeded and no full plan was persisted (old
        # checkpoint), resume_from == len(full_plan) → nothing to run.
        # Re-plan the continuation instead of silently doing nothing.
        if resume_from >= len(full_plan) and not checkpoint.state.plan:
            continuation_prompt = (
                prompt
                or f"Continue building the scene for: {checkpoint.state.project_name}"
            )
            log.info(
                f"Resuming {run_id}: no remaining steps in checkpoint "
                f"(plan not saved) — re-planning continuation"
            )
            self._emit("pipeline.resume", {
                "run_id":    run_id,
                "skip":      resume_from,
                "remaining": 0,
                "replan":    True,
            })
            return self.run(continuation_prompt, images=images)

        # All steps already completed (plan was saved, nothing left to run)
        if resume_from >= len(full_plan):
            log.info(f"Resuming {run_id}: all {len(full_plan)} steps already complete")
            self._emit("pipeline.done", {
                "total_steps":  0,
                "ok":           0,
                "checkpoint":   checkpoint.path,
                "project_name": checkpoint.state.project_name,
                "screenshots":  [],
                "message":      "All steps already complete — nothing to resume.",
            })
            return []

        goal = prompt or checkpoint.state.project_name or "resume"
        style_block = self._detect_style_blocks(goal)
        scene_scale = detect_scene_scale(goal)

        completed_steps: list[str] = [
            s["description"] for s in saved
            if s.get("success") and s.get("index", 0) < resume_from
        ]

        ver = (5, 1, 0)
        ctx = ""
        try:
            ver = self._client.get_blender_version()
            ctx = ContextBuilder(self._client, ver).build()
        except Exception:
            pass

        output_dir   = (get("output_dir", "") or
                        str(Path.home() / "blender_pipeline_output"))
        rag_dir      = (get("rag_corpus_dir", "") or
                        str(Path(output_dir) / "_rag_corpus"))
        logger       = PipelineLogger(rag_dir)
        project_name = checkpoint.state.project_name or "resumed_project"

        # Rebuild spatial layout from saved plan descriptions for resume
        resume_detections = [
            DetectedObject(label=w, estimated_scale=1.0)
            for desc in full_plan
            for w in re.findall(r'[a-z]{4,}', desc.lower())
            if w not in _STOPWORDS
        ][:40]
        spatial_nodes = self._spatial.build_layout(resume_detections, scene_scale=scene_scale)
        spatial_block = self._spatial.to_prompt_block(spatial_nodes)

        self._emit("pipeline.resume", {
            "run_id":    run_id,
            "skip":      resume_from,
            "remaining": len(full_plan) - resume_from,
        })
        log.info(f"Resuming {run_id} — skipping {resume_from} completed steps, "
                 f"{len(full_plan) - resume_from} remaining")

        steps = self._execute_steps(
            plan=full_plan,
            start_idx=resume_from,
            ctx=ctx,
            ver=ver,
            images=images,
            goal_summary=goal,
            style_block=style_block,
            spatial_block=spatial_block,
            spatial_nodes=spatial_nodes,
            step_visual_contexts=[""] * len(full_plan),
            checkpoint=checkpoint,
            logger=logger,
            output_dir=output_dir,
            project_name=project_name,
            has_terrain=False,
            completed_steps=completed_steps,
            scene_scale=scene_scale,
        )

        try:
            blend_path = (Path(output_dir).expanduser()
                          / f"{project_name}_resumed.blend")
            blend_path.parent.mkdir(parents=True, exist_ok=True)
            self._client.exec_code(
                f"import bpy\nbpy.ops.wm.save_as_mainfile(filepath=r'{blend_path}')\n"
            )
            self._emit("pipeline.blend_saved", {"path": str(blend_path)})
            log.info(f"Saved .blend → {blend_path}")
        except Exception as e:
            log.warning(f"Resume .blend save failed: {e}")

        ok_count = sum(1 for s in steps if s.success)
        self._emit("pipeline.done", {
            "total_steps":  len(steps),
            "ok":           ok_count,
            "checkpoint":   checkpoint.path,
            "project_name": project_name,
            "screenshots":  [],
        })
        return steps

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _detect_objects(prompt: str, goal: str) -> list[DetectedObject]:
        combined = (prompt + " " + goal).lower()
        tokens   = re.findall(r"[a-z]+", combined)
        seen: set[str] = set()
        result: list[DetectedObject] = []
        for tok in tokens:
            if tok in seen or len(tok) < 4 or tok in _STOPWORDS:
                continue
            seen.add(tok)
            scale = 2.0 if tok in TERRAIN_KEYWORDS else 1.0
            result.append(DetectedObject(label=tok, estimated_scale=scale))
        return result[:40]

    _LABEL_VERBS: frozenset = frozenset({
        "create", "build", "add", "place", "set", "make", "generate", "attach",
        "apply", "insert", "put", "construct", "setup", "render", "configure",
        "position", "install", "edit", "up", "a", "an", "the", "using", "with",
        "for", "on", "at", "to", "of", "by", "and",
    })

    @classmethod
    def _extract_label_from_description(cls, description: str) -> str:
        """Extract a clean CamelCase object name from a step description.

        'Build TowerBattlements: extrude 8 merlons...' → 'TowerBattlements'
        '1. Create ChairSeat: add Cube at (0,0)...'    → 'ChairSeat'
        'create chair legs using four cylinders'        → 'ChairLegs'
        """
        # Strip leading step number ("1. ", "15. ")
        text = re.sub(r'^\d+\.\s*', '', description).strip()

        # Priority 1: CamelCase compound word (e.g. ChairSeat, TowerWall, OceanPlane)
        m = re.search(r'\b([A-Z][a-z]+[A-Z][a-zA-Z0-9]+)\b', text)
        if m:
            return m.group(1)[:32]

        # Priority 2: Any CamelCase word that is not a known action verb
        for word_m in re.finditer(r'\b([A-Z][a-zA-Z0-9]{3,})\b', text):
            word = word_m.group(1)
            if word.lower() not in cls._LABEL_VERBS:
                return word[:32]

        # Fallback: skip verb/filler words and title-case the first two nouns
        words = [w for w in re.findall(r'[A-Za-z]+', text)
                 if w.lower() not in cls._LABEL_VERBS]
        name = "".join(w.title() for w in words[:2]) or "Object"
        return name[:32]

    @staticmethod
    def _node_pos_for(description: str, nodes: list) -> tuple | None:
        desc_lower = description.lower()
        for node in nodes:
            if node.label.lower() in desc_lower:
                return node.world_pos
        return None

    @staticmethod
    def _estimate_dim(description: str, scene_scale: str = "default") -> tuple[float, float, float]:
        """Keyword heuristic: estimate approximate object footprint in metres."""
        d = description.lower()
        # Large structural / terrain objects
        if any(k in d for k in ("terrain", "ground", "plane", "ocean", "island", "floor")):
            return (20.0, 20.0, 0.5)
        if any(k in d for k in ("castle", "fortress", "citadel")):
            return (15.0, 15.0, 12.0)
        if any(k in d for k in ("tower", "wall", "keep")):
            return (4.0, 4.0, 12.0)
        if any(k in d for k in ("bridge", "gate", "arch")):
            return (6.0, 2.0, 4.0)
        if any(k in d for k in ("house", "cabin", "building", "hut")):
            return (5.0, 5.0, 4.0)
        # Vegetation / nature
        if any(k in d for k in ("tree", "pine", "palm", "oak")):
            return (3.0, 3.0, 6.0)
        if any(k in d for k in ("bush", "shrub", "grass")):
            return (1.0, 1.0, 0.5)
        if any(k in d for k in ("rock", "boulder", "stone")):
            return (1.5, 1.5, 1.0)
        # Furniture / small props
        if any(k in d for k in ("chair", "stool")):
            return (0.5, 0.5, 0.9)
        if any(k in d for k in ("table", "desk")):
            return (1.2, 0.7, 0.75)
        if any(k in d for k in ("lamp", "light", "candle")):
            return (0.2, 0.2, 1.5)
        if any(k in d for k in ("shelf", "cabinet", "wardrobe")):
            return (0.8, 0.4, 1.8)
        # Lighting / camera (non-physical, very small footprint)
        if any(k in d for k in ("camera", "sun", "hdri", "sky", "render")):
            return (0.1, 0.1, 0.1)
        # Default based on scene scale preset
        defaults = {
            "furniture": (0.6, 0.6, 0.8),
            "architectural": (4.0, 4.0, 5.0),
            "landscape": (3.0, 3.0, 2.0),
            "diorama": (0.3, 0.3, 0.4),
            "default": (1.0, 1.0, 1.0),
        }
        return defaults.get(scene_scale, (1.0, 1.0, 1.0))

    @staticmethod
    def _strip_fences(code: str) -> str:
        if "```" in code:
            m = re.search(r'```(?:python)?\n?(.*?)```', code, re.DOTALL)
            if m:
                return m.group(1).strip()
        return code

    @staticmethod
    def _extract_obj_name(code: str, description: str) -> str:
        m = re.search(r"""bpy\.context\.object\.name\s*=\s*['"]([^'"]+)['"]""", code)
        if m:
            return m.group(1)
        slug = re.sub(r"[^a-zA-Z0-9_]", "_", description[:20]).strip("_")
        return slug if slug else "Object"
