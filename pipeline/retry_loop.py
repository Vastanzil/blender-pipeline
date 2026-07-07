"""
pipeline/retry_loop.py
Executes bpy code via the MCP client.
On error: asks AI to fix, retries up to max_retries times.
"""
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success:  bool
    output:   str  = ""
    error:    str  = ""
    attempts: int  = 0
    code:     str  = ""


class RetryLoop:
    def __init__(self, client, ai, max_retries=5):
        self._client      = client
        self._ai          = ai
        self._max_retries = max_retries

    def execute(self, code: str, context: str = "",
                skill_hint: str | None = None,
                visual_context: str = "") -> ExecutionResult:
        current_code = code

        # Syntax pre-validation before sending to Blender
        try:
            compile(current_code, "<generated>", "exec")
        except SyntaxError as e:
            if self._max_retries > 0:
                try:
                    fixed = self._ai.fix_error(
                        current_code,
                        f"SyntaxError at line {e.lineno}: {e.msg}",
                        context,
                    )
                    import re as _re
                    if "```" in fixed:
                        _m = _re.search(r'```(?:python)?\n?(.*?)```', fixed, _re.DOTALL)
                        if _m:
                            fixed = _m.group(1).strip()
                    if fixed:
                        current_code = fixed
                except Exception:
                    pass

        blenderllm_failures = 0
        for attempt in range(1, self._max_retries + 1):
            result = self._client.exec_code(current_code)
            output = str(result.output or "")
            error  = str(result.error  or "")

            # Detect error in output text as well
            is_error = (
                not result.success
                or "ERROR:" in output
                or "Traceback" in output
                or "Error:" in error
            )

            if not is_error:
                return ExecutionResult(
                    success=True, output=output,
                    attempts=attempt, code=current_code,
                )

            if attempt < self._max_retries:
                err_msg = error or output
                # Escalate to Manifest after 2 consecutive BlenderLLM failures
                force_manifest = blenderllm_failures >= 2
                try:
                    fixed = self._ai.fix_error(
                        current_code, err_msg, context,
                        skill_hint=skill_hint,
                        visual_context=visual_context,
                        force_manifest=force_manifest,
                    )
                    # Track whether BlenderLLM was the backend used
                    import logging
                    _log = logging.getLogger(__name__)
                    if not force_manifest and getattr(self._ai, '_blenderllm', None):
                        from config.registry import get as _get
                        if _get("hybrid_mode", False):
                            blenderllm_failures += 1
                        else:
                            blenderllm_failures = 0
                    else:
                        blenderllm_failures = 0

                    # Strip markdown code fences if AI wraps in them
                    if "```" in fixed:
                        import re
                        m = re.search(r'```(?:python)?\n?(.*?)```', fixed, re.DOTALL)
                        if m:
                            fixed = m.group(1).strip()
                    if fixed:
                        current_code = fixed
                except Exception:
                    pass  # keep current code and retry anyway

        return ExecutionResult(
            success=False,
            error=error,
            output=output,
            attempts=self._max_retries,
            code=current_code,
        )
