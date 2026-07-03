"""Tests for Blender version-detected compat rules."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_blender5_uses_interface_new_socket():
    from ai.compat_rules import get_compat_block
    block = get_compat_block((5, 1, 2))
    assert "interface.new_socket" in block


def test_blender5_uses_eevee_next():
    from ai.compat_rules import get_compat_block
    block = get_compat_block((5, 0, 0))
    assert "BLENDER_EEVEE_NEXT" in block


def test_blender4_uses_old_inputs_api():
    from ai.compat_rules import get_compat_block
    block = get_compat_block((4, 3, 0))
    assert "ng.inputs.new" in block


def test_blender4_no_eevee_next():
    from ai.compat_rules import get_compat_block
    block = get_compat_block((4, 3, 0))
    assert "BLENDER_EEVEE_NEXT" not in block


def test_blender4_has_plain_eevee():
    from ai.compat_rules import get_compat_block
    block = get_compat_block((4, 3, 0))
    assert "BLENDER_EEVEE" in block


def test_returns_string_always():
    from ai.compat_rules import get_compat_block
    for ver in [(3, 6, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0), ()]:
        block = get_compat_block(ver)
        assert isinstance(block, str)
        assert len(block) > 0


def test_block_contains_bps_prefix():
    from ai.compat_rules import get_compat_block
    for ver in [(4, 0, 0), (5, 0, 0)]:
        assert "BPS_" in get_compat_block(ver)
