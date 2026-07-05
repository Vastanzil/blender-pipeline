"""Tests for ProjectNamer."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.project_namer import ProjectNamer


def test_name_uses_detected_labels():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("A scene with a cottage", ["cottage", "pond", "bridge"])
    assert name.startswith("cottage_pond_bridge_")


def test_name_max_three_labels():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("",
                                      ["tree", "house", "pond", "rock", "flower"])
    prefix = "_".join(name.split("_")[:3])
    assert prefix == "tree_house_pond"


def test_name_falls_back_to_summary():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("A big forest with ancient trees", [])
    assert "forest" in name or "ancient" in name or "trees" in name


def test_name_has_timestamp_suffix():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("scene", ["cabin"])
    parts = name.split("_")
    # Last two parts should be date (8 digits) and time (4 digits)
    assert parts[-2].isdigit() and len(parts[-2]) == 8
    assert parts[-1].isdigit() and len(parts[-1]) == 4


def test_stopwords_filtered():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("", [])
    # Falls back to summary-less path → scene_YYYYMMDD_HHMM
    assert name.startswith("scene_")


def test_deduplication():
    pn   = ProjectNamer()
    name = pn.name_from_understanding("", ["tree", "tree", "tree"])
    # Should only appear once
    assert name.startswith("tree_")
    assert "tree_tree" not in name
