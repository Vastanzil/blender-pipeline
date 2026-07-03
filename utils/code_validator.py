"""utils/code_validator.py — Static AST validation for bpy Python code."""
import ast
from dataclasses import dataclass, field

BANNED = {"subprocess", "os.system", "eval(", "exec(", "__import__"}


@dataclass
class ValidationResult:
    ok:       bool
    errors:   list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def validate_bpy_code(code: str) -> ValidationResult:
    if not code or not code.strip():
        return ValidationResult(ok=False, errors=["Code is empty"])

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(ok=False, errors=[f"Syntax error: {e}"])

    warnings = []

    # bpy import check
    if "bpy" in code and "import bpy" not in code:
        warnings.append("bpy used but 'import bpy' not found — may fail in Blender")
    elif "import bpy" not in code:
        warnings.append("No 'import bpy' detected — is this Blender code?")

    # Banned pattern check
    for pattern in BANNED:
        if pattern in code:
            warnings.append(f"Potentially unsafe pattern: {pattern!r}")

    return ValidationResult(ok=True, warnings=warnings)
