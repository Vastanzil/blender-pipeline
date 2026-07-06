"""
pipeline/reference_loop.py
Reference-guided iterative refinement loop (v3.2).

After initial generation, renders the Blender scene, compares it to the
user's reference image via AI vision, scores similarity 0-100, generates
improvement steps for low-scoring areas, applies them, and repeats up to
max_iterations times or until score >= score_threshold.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class ReferenceLoop:
    def __init__(self, client, ai, max_iterations: int = 3,
                 score_threshold: int = 75):
        self._client    = client
        self._ai        = ai
        self._max_iter  = max_iterations
        self._threshold = score_threshold

    def run(self, reference_images: list[str], output_dir: str,
            project_name: str, ctx: str) -> list[dict]:
        """
        Execute the render → compare → improve cycle.

        Returns a list of iteration records:
            {"iteration": int, "render_path": str | None,
             "score": int, "feedback": str, "steps_applied": list[str]}
        """
        iterations = []
        for i in range(self._max_iter):
            render_path = self._render(output_dir, project_name, i)
            score, feedback = self._compare(reference_images, render_path)

            record: dict = {
                "iteration":    i,
                "render_path":  render_path,
                "score":        score,
                "feedback":     feedback,
                "steps_applied": [],
            }

            if score >= self._threshold:
                iterations.append(record)
                break

            if not render_path:
                iterations.append(record)
                break

            improve_steps = self._generate_improvements(
                feedback, ctx, reference_images, render_path
            )
            for step_desc in improve_steps:
                try:
                    code = self._ai.generate_code(
                        f"{ctx}\n\nIMPROVEMENT TASK: {step_desc}\n"
                        "Return ONLY executable bpy Python code.",
                        images=reference_images,
                    )
                    self._client.exec_code(self._strip_fences(code))
                    record["steps_applied"].append(step_desc)
                except Exception:
                    pass

            iterations.append(record)

        return iterations

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _render(self, output_dir: str, project_name: str,
                iteration: int) -> str | None:
        """Trigger a Blender render and return the PNG path, or None on failure."""
        render_path = str(
            Path(output_dir) / f"{project_name}_iter{iteration}.png"
        )
        code = (
            f"import bpy\n"
            f"bpy.context.scene.render.filepath = r'{render_path}'\n"
            f"bpy.context.scene.render.image_settings.file_format = 'PNG'\n"
            f"bpy.ops.render.render(write_still=True)\n"
        )
        try:
            result = self._client.exec_code(code)
            return render_path if result.success else None
        except Exception:
            return None

    def _compare(self, reference_images: list[str],
                 render_path: str | None) -> tuple[int, str]:
        """
        Ask the AI to score similarity 0-100 and list top differences.
        Returns (score, feedback_text).
        """
        if not render_path:
            return 0, "Render failed — no image to compare."

        all_images = list(reference_images) + [render_path]
        prompt = (
            "Compare the RENDER (last image) against the REFERENCE (first image).\n"
            "Score visual similarity 0-100 (100 = pixel-perfect match).\n"
            "List the top 3 differences as actionable Blender improvement tasks.\n"
            'Respond as JSON only: {"score": int, "differences": [str, str, str]}'
        )
        try:
            resp = self._ai.describe(prompt, images=all_images)
            clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', resp.strip(),
                           flags=re.IGNORECASE | re.MULTILINE)
            data = json.loads(clean)
            score = max(0, min(100, int(data.get("score", 0))))
            diffs = data.get("differences", [])
            feedback = "\n".join(str(d) for d in diffs[:3])
            return score, feedback
        except Exception as e:
            return 0, f"Comparison parse error: {e}"

    def _generate_improvements(self, feedback: str, ctx: str,
                               ref_images: list[str],
                               render_path: str) -> list[str]:
        """Return up to 5 improvement step descriptions from the AI."""
        try:
            steps = self._ai.plan(
                f"{ctx}\n\n"
                f"The current render differs from the reference image. "
                f"Identified differences:\n{feedback}\n\n"
                "Return 3-5 numbered improvement steps to fix these differences "
                "in the Blender scene.",
                images=ref_images + [render_path],
            )
            return steps[:5]
        except Exception:
            return []

    @staticmethod
    def _strip_fences(code: str) -> str:
        if "```" in code:
            m = re.search(r'```(?:python)?\n?(.*?)```', code, re.DOTALL)
            if m:
                return m.group(1).strip()
        return code
