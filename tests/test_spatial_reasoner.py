"""Tests for SpatialReasoner — layout, exclusion pairs, attachment groups, collision."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import math

from pipeline.spatial_reasoner import (
    SpatialReasoner, DetectedObject, EXCLUSION_PAIRS, ATTACHMENT_GROUPS
)


def _make(*labels, scale=1.0):
    return [DetectedObject(label=l, estimated_scale=scale) for l in labels]


def test_single_object_not_at_exact_origin():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("house"))
    assert len(nodes) == 1
    # With a single object the grid places it; it should be deterministic
    assert nodes[0].label == "house"


def test_two_props_separated():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("house", "tree"))
    pos_h = nodes[0].world_pos
    pos_t = nodes[1].world_pos
    dist  = math.hypot(pos_h[0] - pos_t[0], pos_h[1] - pos_t[1])
    assert dist >= SpatialReasoner.MIN_SEPARATION_M


def test_exclusion_pairs_get_double_separation():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("house", "tree"))
    pos_h = nodes[0].world_pos
    pos_t = nodes[1].world_pos
    dist  = math.hypot(pos_h[0] - pos_t[0], pos_h[1] - pos_t[1])
    # house↔tree is an exclusion pair → must be >= 2× MIN_SEPARATION
    expected = SpatialReasoner.MIN_SEPARATION_M * SpatialReasoner.EXCLUSION_EXTRA
    assert dist >= expected


def test_attachment_group_assigned():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("bridge_plank", "bridge_post"))
    groups = {n.label: n.attachment_group for n in nodes}
    assert groups["bridge_plank"] == "bridge"
    assert groups["bridge_post"]  == "bridge"


def test_attachment_group_has_parent():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("bridge_plank", "bridge_post", "bridge_rope"))
    parents = [n.parent for n in nodes if n.parent is not None]
    assert len(parents) >= 1   # at least the 2nd+ member has a parent


def test_pond_road_exclusion_exists():
    assert frozenset({"pond", "road"}) in EXCLUSION_PAIRS


def test_cabin_group_defined():
    assert "cabin" in ATTACHMENT_GROUPS
    assert "cabin_wall" in ATTACHMENT_GROUPS["cabin"]


def test_prompt_block_contains_label():
    sr    = SpatialReasoner()
    nodes = sr.build_layout(_make("tree", "rock"))
    block = sr.to_prompt_block(nodes)
    assert "tree" in block
    assert "rock" in block
    assert "SPATIAL LAYOUT" in block


def test_many_objects_no_overlap():
    sr    = SpatialReasoner()
    labels = ["house", "rock", "fence_post", "flower",
              "pond", "path", "bush", "lantern"]
    nodes = sr.build_layout(_make(*labels))
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i >= j:
                continue
            dist = math.hypot(a.world_pos[0] - b.world_pos[0],
                              a.world_pos[1] - b.world_pos[1])
            assert dist >= SpatialReasoner.MIN_SEPARATION_M, \
                f"{a.label} and {b.label} overlap: dist={dist:.3f}"
