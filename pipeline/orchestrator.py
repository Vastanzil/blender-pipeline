"""
pipeline/orchestrator.py
Full pipeline: prompt -> AI plan -> code-per-step -> RetryLoop -> validate -> checkpoint.
Emits EventBus events at every stage so the GUI can react in real-time.
"""
import time
from .step       import PipelineStep
from .retry_loop import RetryLoop
from .checkpoint import Checkpoint
from .validator  import Validator
from ai.context_builder import ContextBuilder
from config.registry    import get
from utils.logger       import get_logger

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(self, client, ai, bus=None):
        self._client    = client
        self._ai        = ai
        self._bus       = bus
        self._retry     = RetryLoop(client, ai, max_retries=get("max_retries", 5))
        self._validator = Validator(client)
        self._abort_flag = False

    def abort(self):
        self._abort_flag = True

    def _emit(self, event: str, data: dict):
        if self._bus:
            try:
                self._bus.emit(event, data)
            except Exception:
                pass

    def run(self, prompt: str, images: list | None = None,
            skill_hint: str = "") -> list:
        self._abort_flag = False
        t0 = time.perf_counter()
        log.info(f"Pipeline start: {prompt[:70]}")
        self._emit("pipeline.start", {"prompt": prompt})

        # 1. Build context
        try:
            ver = self._client.get_blender_version()
            ctx = ContextBuilder(self._client, ver).build()
        except Exception as e:
            ctx = ""
            log.warning(f"Context build failed: {e}")

        # 2. Goal analysis — describe intent before executing
        try:
            goal_prompt = (
                f"Briefly describe in 1-3 sentences what Blender actions you will "
                f"perform for this request. Do NOT write code yet.\n\nRequest: {prompt}"
            )
            goal_summary = self._ai.generate_code(goal_prompt, images=images)
            self._emit("pipeline.goal_analysis", {"summary": goal_summary[:300]})
            log.info(f"Goal: {goal_summary[:80]}")
        except Exception:
            pass

        # 3. Plan
        skill_section = f"\nSKILL HINTS: {skill_hint}\n" if skill_hint else ""
        plan_prompt = (
            f"{ctx}{skill_section}\n\nUSER REQUEST: {prompt}\n\n"
            "Return a JSON array of short step descriptions "
            "(each step is one bpy operation). "
            "Maximum 10 steps. Be concise."
        )
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

        self._emit("pipeline.plan", {"total": len(plan), "steps": plan})
        log.info(f"Plan: {len(plan)} steps")

        steps = []
        checkpoint = Checkpoint()

        # 3. Execute each step
        for idx, description in enumerate(plan):
            if self._abort_flag:
                log.info("Pipeline aborted by user")
                self._emit("pipeline.aborted", {"at_step": idx})
                break

            self._emit("pipeline.step.start",
                       {"index": idx, "total": len(plan), "description": description})
            log.info(f"Step {idx+1}/{len(plan)}: {description}")

            # Generate code for this step
            code_prompt = (
                f"{ctx}\n\n"
                f"TASK: Write bpy Python code to: {description}\n"
                "Return ONLY executable Python code. No explanation."
            )
            try:
                code = self._ai.generate_code(code_prompt, images=images)
                # Strip markdown fences if present
                if "```" in code:
                    import re
                    m = re.search(r'```(?:python)?\n?(.*?)```', code, re.DOTALL)
                    if m:
                        code = m.group(1).strip()
            except Exception as e:
                code = f"print('Code generation failed: {e}')"
                log.warning(f"Code gen failed for step {idx+1}: {e}")

            # Execute with retry
            result = self._retry.execute(code, ctx)

            step = PipelineStep(
                index       = idx,
                description = description,
                code        = result.code,
                success     = result.success,
                error       = result.error,
                output      = result.output,
                attempts    = result.attempts,
            )
            steps.append(step)

            self._emit("pipeline.step.done", {
                "index":       idx,
                "total":       len(plan),
                "description": description,
                "success":     result.success,
                "attempts":    result.attempts,
                "error":       result.error or "",
                "code":        result.code  or "",
            })

            checkpoint.save(steps)

            if not result.success:
                log.warning(f"Step {idx+1} failed after {result.attempts} attempts: {result.error[:80]}")

            # Validate Blender still alive every 3 steps
            if idx % 3 == 2 and not self._validator.is_alive():
                log.error("Blender became unresponsive — aborting pipeline")
                self._emit("pipeline.aborted", {"reason": "blender_unresponsive"})
                break

        elapsed = time.perf_counter() - t0
        ok_count = sum(1 for s in steps if s.success)
        log.info(f"Pipeline done: {ok_count}/{len(steps)} steps OK in {elapsed:.1f}s")
        self._emit("pipeline.done", {
            "total_steps": len(steps),
            "ok":          ok_count,
            "elapsed_s":   round(elapsed, 2),
            "checkpoint":  checkpoint.path,
        })
        return steps
