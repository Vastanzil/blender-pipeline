"""Tests for bpy code static validator."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_valid_bpy_code():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("import bpy\nbpy.ops.mesh.primitive_cube_add()\nprint('done')")
    assert r.ok
    assert not r.errors


def test_empty_code_fails():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("")
    assert not r.ok
    assert any("empty" in e.lower() for e in r.errors)


def test_whitespace_only_fails():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("   \n\t\n  ")
    assert not r.ok


def test_syntax_error_fails():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("import bpy\ndef broken(\nprint('hi')")
    assert not r.ok
    assert any("syntax" in e.lower() for e in r.errors)


def test_missing_bpy_import_warns_not_fails():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("x = 1 + 1\nprint(x)")
    assert r.ok   # not a hard error
    assert any("bpy" in w for w in r.warnings)


def test_bpy_used_without_import_warns():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("bpy.ops.mesh.primitive_cube_add()")
    assert r.ok
    assert any("import bpy" in w for w in r.warnings)


def test_subprocess_import_warns():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("import bpy\nimport subprocess\nprint('x')")
    assert r.ok
    assert any("subprocess" in w for w in r.warnings)


def test_eval_warns():
    from utils.code_validator import validate_bpy_code
    r = validate_bpy_code("import bpy\neval('1+1')")
    assert r.ok
    assert any("eval" in w for w in r.warnings)


def test_clean_bpy_no_warnings():
    from utils.code_validator import validate_bpy_code
    code = (
        "import bpy\n"
        "obj = bpy.data.objects.new('Cube', bpy.data.meshes.new('CubeMesh'))\n"
        "bpy.context.scene.collection.objects.link(obj)\n"
        "print('Created', obj.name)"
    )
    r = validate_bpy_code(code)
    assert r.ok
    assert r.errors == []
