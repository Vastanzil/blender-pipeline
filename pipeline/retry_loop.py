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

    def execute(self, code: str, context: str = "") -> ExecutionResult:
        current_code = code
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
                try:
                    current_code = self._ai.fix_error(current_code, err_msg, context)
                    # Strip markdown code fences if AI wraps in them
                    if "```" in current_code:
                        import re
                        m = re.search(r'```(?:python)?\n?(.*?)```', current_code, re.DOTALL)
                        if m:
                            current_code = m.group(1).strip()
                except Exception:
                    pass  # keep current code and retry anyway

        return ExecutionResult(
            success=False,
            error=error,
            output=output,
            attempts=self._max_retries,
            code=current_code,
        )
