"""Tests for TerrainBuilder snippets."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.terrain_builder import TerrainBuilder, TerrainFeature, TERRAIN_KEYWORDS


def test_terrain_keywords_includes_expected():
    for kw in ("ground", "pond", "hill", "road", "river"):
        assert kw in TERRAIN_KEYWORDS


def test_base_terrain_snippet_creates_terrain_object():
    tb  = TerrainBuilder()
    snp = tb.base_terrain_snippet()
    assert "_terrain.name = 'Terrain'" in snp
    assert "subdivide_edges" in snp
    assert "TerrainMat" in snp


def test_base_terrain_removes_stacked_planes():
    tb  = TerrainBuilder()
    snp = tb.base_terrain_snippet()
    assert "Plane" in snp   # removes existing planes


def test_hill_feature_snippet():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.HILL, (2.0, 3.0, 0.0), 5.0)
    assert "HILL" not in snp  # no leftover enum name
    assert "_v.co.z +=" in snp
    assert "Terrain" in snp


def test_valley_feature_snippet():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.VALLEY, (0.0, 0.0, 0.0), 4.0)
    assert "_v.co.z -=" in snp


def test_pond_feature_snippet():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.POND, (1.0, 1.0, 0.0), 3.0)
    assert "Pond_Water" in snp
    assert "WaterMat" in snp


def test_road_feature_snippet():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.ROAD, (0.0, 0.0, 0.0), 10.0)
    assert "_v.co.z = 0.0" in snp


def test_river_feature_snippet():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.RIVER, (0.0, 0.0, 0.0), 8.0)
    assert "River_Water" in snp
    assert "RiverMat" in snp


def test_place_on_terrain_snippet():
    tb  = TerrainBuilder()
    snp = tb.place_on_terrain_snippet("My_Cabin", (3.5, -2.0))
    assert "My_Cabin" in snp
    assert "ray_cast" in snp
    assert "3.5" in snp and "-2.0" in snp


def test_ground_feature_returns_empty():
    tb  = TerrainBuilder()
    snp = tb.feature_snippet(TerrainFeature.GROUND, (0, 0, 0), 1.0)
    assert snp == ""
