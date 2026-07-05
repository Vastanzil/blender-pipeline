"""
pipeline/orchestrator.py
Full v3.1 pipeline: unlimited steps, spatial reasoning, terrain, poly budget,
logging, checkpoint resume, existence validation, and realism verification.
"""
from __future__ import annotations
import re
import time
from pathlib import Path

from .step            import PipelineStep
from .retry_loop      import RetryLoop
from .checkpoint      import Checkpoint
from .validator       import Validator
from .stages          import Stage
from .spatial_reasoner import SpatialReasoner, DetectedObject
from .poly_budget     import PolyBudgetManager
from .pipeline_logger import PipelineLogger
from .project_namer   import ProjectNamer
from .terrain_builder import TerrainBuilder, TerrainFeature, TERRAIN_KEYWORDS
from .scene_verifier  import SceneVerifier
from ai.context_builder import ContextBuilder
from config.registry    import get
from utils.logger       import get_logger

log = get_logger("orchestrator")

_TERRAIN_FEATURE_MAP = {
    "hill": TerrainFeature.HILL, "valley": TerrainFeature.VALLEY,
    "road": TerrainFeature.ROAD, "path":   TerrainFeature.ROAD,
    "pond": TerrainFeature.POND, "lake":   TerrainFeature.POND,
    "river": TerrainFeature.RIVER, "stream": TerrainFeature.RIVER,
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

        # ── Subsystem wiring: logger context snapshot ─────────────────
        spatial_nodes: list = []
        completed_steps: list[str] = []
        goal_summary = ""

        def _ctx_snapshot() -> dict:
            return {
                "goal":            goal_summary,
                "project_name":    checkpoint.state.project_name if 'checkpoint' in dir() else "",
                "spatial_nodes":   [{"label": n.label, "world_pos": list(n.world_pos)}
                                    for n in spatial_nodes],
                "completed_steps": list(completed_steps),
                "scene_objects":   [],   # populated lazily
                "validation_state": "ok",
            }

        logger     = PipelineLogger(rag_dir, context_snapshot_fn=_ctx_snapshot)
        checkpoint = Checkpoint()

        # ── 1. Blender context ────────────────────────────────────────
        try:
            ver = self._client.get_blender_version()
            ctx = ContextBuilder(self._client, ver).build()
        except Exception as e:
            ctx = ""
            log.warning(f"Context build failed: {e}")

        # ── 2. Goal analysis ──────────────────────────────────────────
        try:
            goal_prompt = (
                f"Briefly describe in 1-3 sentences what Blender actions you will "
                f"perform for this request. Do NOT write code yet.\n\nRequest: {prompt}"
            )
            goal_summary = self._ai.generate_code(goal_prompt, images=images)
            goal_summary = goal_summary[:300]
            self._emit("pipeline.goal_analysis", {"summary": goal_summary})
            logger.log("goal", "response", goal_summary)
            log.info(f"Goal: {goal_summary[:80]}")
        except Exception:
            pass

        # ── 3. Object detection + spatial layout ─────────────────────
        detections = self._detect_objects(prompt, goal_summary)
        terrain_features = [d for d in detections
                            if d.label.lower() in TERRAIN_KEYWORDS]
        prop_detections  = [d for d in detections
                            if d.label.lower() not in TERRAIN_KEYWORDS]

        spatial_nodes = self._spatial.build_layout(prop_detections)
        spatial_block = self._spatial.to_prompt_block(spatial_nodes)
        self._emit("pipeline.spatial_layout",
                   {"nodes": [{"label": n.label, "world_pos": list(n.world_pos)}
                               for n in spatial_nodes]})

        # ── 4. Project naming ─────────────────────────────────────────
        detected_labels = [d.label for d in detections]
        project_name    = self._namer.name_from_understanding(goal_summary, detected_labels)
        checkpoint.set_project_name(project_name)
        self._emit("pipeline.project_named", {"name": project_name})
        logger.log("project_name", "system", project_name)

        # ── 5. Plan ───────────────────────────────────────────────────
        skill_section = f"\nSKILL HINTS: {skill_hint}\n" if skill_hint else ""
        plan_prompt = (
            f"{ctx}{skill_section}\n\n"
            f"{spatial_block}\n\n"
            f"USER REQUEST: {prompt}\n\n"
            "Return a JSON array of short step descriptions.\n"
            "Each step must be ONE atomic bpy operation.\n"
            "Plan as many steps as needed — there is NO step limit.\n"
            "Use human-like reasoning:\n"
            "- Structural components attach TO their parent object\n"
            "- Independent objects maintain at least 0.75m separation\n"
            "- Never merge geometrically distinct objects (tree != house)\n"
            "- Name every object descriptively (e.g. 'Cabin_Wall_North')\n"
            "- Include polish steps last: UV unwrap, smooth shading, materials, lighting"
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
        checkpoint.mark_complete(Stage.SPATIAL_LAYOUT,
                                 [{"label": n.label, "world_pos": list(n.world_pos)}
                                  for n in spatial_nodes])
        self._emit("pipeline.plan", {"total": len(plan), "steps": plan})
        log.info(f"Plan: {len(plan)} steps (no cap)")

        # ── 6. Terrain Step 0 (injected before AI plan) ──────────────
        has_terrain = bool(terrain_features)
        if has_terrain:
            terrain_code = self._terrain.base_terrain_snippet()
            t_result     = self._retry.execute(terrain_code, ctx)
            t_step       = PipelineStep(
                index=0, description="Initialize Terrain mesh",
                code=terrain_code, success=t_result.success,
                error=t_result.error, output=t_result.output,
                attempts=t_result.attempts, bpy_object_name="Terrain",
            )
            if not t_result.success:
                log.warning("Terrain init failed — continuing without terrain")

        steps: list[PipelineStep] = []

        # ── 7. Execute steps (unlimited) ─────────────────────────────
        for idx, description in enumerate(plan):
            if self._abort_flag:
                log.info("Pipeline aborted by user")
                self._emit("pipeline.aborted", {"at_step": idx})
                break

            self._emit("pipeline.step.start",
                       {"index": idx, "total": len(plan), "description": description})
            log.info(f"Step {idx+1}/{len(plan)}: {description}")

            # Determine spatial position for this step's object
            node_pos    = self._node_pos_for(description, spatial_nodes)
            rename_hint = (
                f"\nName the created object '{description[:30]}' using "
                f"bpy.context.object.name = '...'"
            )
            pos_hint = (
                f"\nPlace the object at world position {node_pos} "
                f"(not at origin)." if node_pos else ""
            )

            code_prompt = (
                f"{ctx}\n\n"
                f"TASK: Write bpy Python code to: {description}\n"
                f"{pos_hint}{rename_hint}\n"
                "Return ONLY executable Python code. No explanation."
            )
            logger.log("codegen", "prompt", code_prompt[:400],
                       meta={"step": idx})

            try:
                code = self._ai.generate_code(code_prompt, images=images)
                code = self._strip_fences(code)
            except Exception as e:
                code = f"print('Code generation failed: {e}')"
                log.warning(f"Code gen failed step {idx+1}: {e}")

            logger.log("codegen", "response", code[:400], meta={"step": idx})

            # Extract bpy_object_name from generated code
            obj_name = self._extract_obj_name(code, description)

            result = self._retry.execute(code, ctx)

            step = PipelineStep(
                index           = idx,
                description     = description,
                code            = result.code,
                success         = result.success,
                error           = result.error,
                output          = result.output,
                attempts        = result.attempts,
                bpy_object_name = obj_name,
                spatial_pos     = node_pos or (),
                poly_tris_target= self._poly.budget_for(description.split()[0].lower()),
            )

            # Layer A existence validation
            if result.success and obj_name:
                passed, reason = self._validator.validate_step_result(step)
                if not passed:
                    log.warning(f"Validation fail step {idx+1}: {reason}")
                    # Retry with existence hint
                    fix_prompt = (
                        f"{ctx}\n\nThe following code ran without error but the object "
                        f"'{obj_name}' was not visible in the scene:\n\n{code}\n\n"
                        f"Reason: {reason}\n"
                        "Rewrite the code so the object is created and visible. "
                        "Ensure bpy.context.view_layer.update() is called."
                    )
                    fix_code = self._strip_fences(
                        self._ai.generate_code(fix_prompt, images=images)
                    )
                    fix_result = self._retry.execute(fix_code, ctx)
                    if fix_result.success:
                        step.code     = fix_result.code
                        step.success  = True
                        step.error    = ""
                        step.attempts += fix_result.attempts

            # Poly budget decimate
            if result.success and obj_name:
                is_organic = any(kw in description.lower()
                                 for kw in ("tree", "bush", "rock", "terrain", "hill"))
                decimate   = self._poly.decimate_snippet(
                    obj_name, description.split()[0].lower(), is_organic
                )
                self._client.exec_code(decimate)

            # Place on terrain if terrain exists
            if has_terrain and result.success and obj_name and node_pos:
                place_code = self._terrain.place_on_terrain_snippet(
                    obj_name, (node_pos[0], node_pos[1])
                )
                self._client.exec_code(place_code)

            steps.append(step)
            completed_steps.append(description)

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

            # Liveness probe every 5 steps
            if idx % 5 == 4 and not self._validator.is_alive():
                log.error("Blender became unresponsive — aborting")
                self._emit("pipeline.aborted", {"reason": "blender_unresponsive"})
                break

        # ── 8. Scene verification (4 screenshots + 1 AI call) ─────────
        screenshots: list[str] = []
        realism_issues: list   = []
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

                # Auto-fix pass (max 1 round)
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

        # ── 9. Auto-save .blend ────────────────────────────────────────
        try:
            blend_path = (Path(output_dir).expanduser()
                          / f"{project_name}.blend")
            blend_path.parent.mkdir(parents=True, exist_ok=True)
            save_code = (
                f"import bpy\n"
                f"bpy.ops.wm.save_as_mainfile(filepath=r'{blend_path}')\n"
            )
            self._client.exec_code(save_code)
            checkpoint.mark_complete(Stage.SAVE, str(blend_path))
            self._emit("pipeline.blend_saved", {"path": str(blend_path)})
            log.info(f"Saved .blend → {blend_path}")
        except Exception as e:
            log.warning(f".blend save failed: {e}")

        elapsed   = time.perf_counter() - t0
        ok_count  = sum(1 for s in steps if s.success)
        log.info(f"Pipeline done: {ok_count}/{len(steps)} OK in {elapsed:.1f}s")
        self._emit("pipeline.done", {
            "total_steps":   len(steps),
            "ok":            ok_count,
            "elapsed_s":     round(elapsed, 2),
            "checkpoint":    checkpoint.path,
            "project_name":  project_name,
            "screenshots":   screenshots,
        })
        return steps

    # ------------------------------------------------------------------
    # Resume from checkpoint

    def resume(self, run_id: str, prompt: str = "",
               images: list | None = None) -> list:
        checkpoint = Checkpoint(run_id)
        output_dir = (get("output_dir", "") or
                      str(Path.home() / "blender_pipeline_output"))
        rag_dir    = (get("rag_corpus_dir", "") or
                      str(Path(output_dir) / "_rag_corpus"))
        logger     = PipelineLogger(rag_dir)
        resume_ctx = checkpoint.load_resume_context(logger)
        log.info(f"Resuming {run_id} — completed stages: "
                 f"{resume_ctx.get('completed_stages', [])}")
        # Re-run from next incomplete stage
        return self.run(
            prompt or resume_ctx.get("goal", "resume"),
            images=images,
        )

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _detect_objects(prompt: str, goal: str) -> list[DetectedObject]:
        """Rough keyword extraction from prompt + goal to seed spatial layout."""
        combined = (prompt + " " + goal).lower()
        tokens   = re.findall(r"[a-z]+", combined)
        seen: set[str] = set()
        result: list[DetectedObject] = []
        for tok in tokens:
            if tok in seen or len(tok) < 3:
                continue
            seen.add(tok)
            scale = 2.0 if tok in TERRAIN_KEYWORDS else 1.0
            result.append(DetectedObject(label=tok, estimated_scale=scale))
        return result[:20]   # cap at 20 to avoid noise

    @staticmethod
    def _node_pos_for(description: str,
                      nodes: list) -> tuple | None:
        desc_lower = description.lower()
        for node in nodes:
            if node.label.lower() in desc_lower:
                return node.world_pos
        return None

    @staticmethod
    def _strip_fences(code: str) -> str:
        if "```" in code:
            m = re.search(r'```(?:python)?\n?(.*?)```', code, re.DOTALL)
            if m:
                return m.group(1).strip()
        return code

    @staticmethod
    def _extract_obj_name(code: str, description: str) -> str:
        """Pull the bpy.context.object.name = '...' assignment from code."""
        m = re.search(r"""bpy\.context\.object\.name\s*=\s*['"]([^'"]+)['"]""", code)
        if m:
            return m.group(1)
        # Fallback: use the first word of description as slug
        slug = re.sub(r"[^a-zA-Z0-9_]", "_", description[:20]).strip("_")
        return slug if slug else "Object"
