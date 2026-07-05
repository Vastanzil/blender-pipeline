"""Tests for PolyBudgetManager."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.poly_budget import PolyBudgetManager, ObjectClass


def test_hero_classification():
    pm = PolyBudgetManager()
    assert pm.classify("house")    == ObjectClass.HERO
    assert pm.classify("tree")     == ObjectClass.HERO
    assert pm.classify("cabin")    == ObjectClass.HERO
    assert pm.classify("character") == ObjectClass.HERO


def test_prop_classification():
    pm = PolyBudgetManager()
    assert pm.classify("flower") == ObjectClass.PROP
    assert pm.classify("rock")   == ObjectClass.PROP
    assert pm.classify("pebble") == ObjectClass.PROP


def test_mid_fallback():
    pm = PolyBudgetManager()
    assert pm.classify("bridge") == ObjectClass.MID
    assert pm.classify("wall")   == ObjectClass.MID


def test_budget_for_hero():
    pm = PolyBudgetManager()
    assert pm.budget_for("house") == 8_000


def test_budget_for_prop():
    pm = PolyBudgetManager()
    assert pm.budget_for("rock") == 400


def test_decimate_snippet_contains_obj_name():
    pm  = PolyBudgetManager()
    snp = pm.decimate_snippet("My_Tree", "tree", is_organic=True)
    assert "My_Tree" in snp
    assert "COLLAPSE" in snp
    assert "8000" in snp


def test_decimate_snippet_planar_for_arch():
    pm  = PolyBudgetManager()
    snp = pm.decimate_snippet("Cabin_Wall", "cabin", is_organic=False)
    assert "PLANAR" in snp
