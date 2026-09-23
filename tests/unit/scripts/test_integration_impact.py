"""Regression tests for scripts/integration_impact.py.

``validate_registry`` walks registry -> directory: every registered target
must have a tasks/main.yml, a valid cost and real, uniquely-mapped modules.
That direction cannot see a target that was written but never registered --
such a target is never selected by anything and silently never runs, which is
exactly what happened to ``cvm_image`` and ``lighthouse`` (G1-d).

``validate_target_dirs`` walks the other way. These tests pin both directions
so neither the registry nor the checker can rot unnoticed again.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Import the script as a module without executing its __main__.
_REPO = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location("integration_impact", _REPO / "scripts" / "integration_impact.py")
_IMPACT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_IMPACT)  # type: ignore[union-attr]


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    """A scratch collection root wired into the script's ROOT/MAP."""
    root = tmp_path
    (root / "plugins" / "modules").mkdir(parents=True)
    integ = root / "tests" / "integration"
    (integ / "targets").mkdir(parents=True)
    monkeypatch.setattr(_IMPACT, "ROOT", root)
    monkeypatch.setattr(_IMPACT, "MAP", integ / "coverage.yml")
    return root


def write_registry(root, body):
    (root / "tests" / "integration" / "coverage.yml").write_text("version: 1\ntargets:\n" + body, encoding="utf-8")


def make_target(root, name):
    (root / "tests" / "integration" / "targets" / name / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "integration" / "targets" / name / "tasks" / "main.yml").write_text("---\n[]\n", encoding="utf-8")


def make_module(root, name):
    (root / "plugins" / "modules" / (name + ".py")).write_text("", encoding="utf-8")


def test_unregistered_target_directory_is_flagged(tree):
    make_target(tree, "ghost_target")
    write_registry(tree, "  real_target: {cost: low, modules: [demo]}\n")
    make_target(tree, "real_target")
    make_module(tree, "demo")

    problems = _IMPACT.validate_target_dirs({"targets": {"real_target": {}}})

    assert any("ghost_target" in p for p in problems), problems
    assert all("real_target" not in p for p in problems), problems


def test_registered_directory_is_not_flagged(tree):
    make_target(tree, "real_target")
    write_registry(tree, "  real_target: {cost: low, modules: [demo]}\n")
    make_module(tree, "demo")

    assert _IMPACT.validate_target_dirs({"targets": {"real_target": {}}}) == []


def test_helper_targets_are_exempt(tree):
    """The cleanup sweeper is invoked by the workflow, never by target selection."""
    make_target(tree, "cleanup")

    assert _IMPACT.validate_target_dirs({"targets": {}}) == []


def test_missing_targets_root_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(_IMPACT, "ROOT", tmp_path / "nonexistent")

    assert _IMPACT.validate_target_dirs({"targets": {}}) == []


def test_check_fails_when_a_directory_is_unregistered(tree, capsys):
    make_target(tree, "ghost_target")
    write_registry(tree, "  real_target: {cost: low, modules: [demo]}\n")
    make_target(tree, "real_target")
    make_module(tree, "demo")

    rc = _IMPACT.main(["--check", "--files"])

    assert rc == 1
    assert "ghost_target" in capsys.readouterr().out


def test_check_passes_on_a_consistent_tree(tree, capsys):
    make_target(tree, "real_target")
    write_registry(tree, "  real_target: {cost: low, modules: [demo]}\n")
    make_module(tree, "demo")

    # --files (empty) keeps main() from shelling out to git in the scratch tree.
    assert _IMPACT.main(["--check", "--files"]) == 0


def test_registry_direction_still_validates_cost_and_modules(tree):
    """Guard the original direction so this change does not quietly replace it."""
    make_target(tree, "real_target")
    make_module(tree, "demo")

    problems = _IMPACT.validate_registry({"targets": {"real_target": {"cost": "free", "modules": ["nope"]}}})

    assert any("missing module nope" in p for p in problems), problems


def test_registry_rejects_a_duplicate_module_mapping(tree):
    make_target(tree, "one")
    make_target(tree, "two")
    make_module(tree, "demo")

    problems = _IMPACT.validate_registry(
        {"targets": {"one": {"cost": "low", "modules": ["demo"]}, "two": {"cost": "low", "modules": ["demo"]}}}
    )

    assert any("mapped by both" in p for p in problems), problems


def test_orphan_and_registry_problems_are_reported_together(tree):
    """--check must surface both directions in one run, not just the first."""
    make_target(tree, "ghost_target")
    make_target(tree, "real_target")

    problems = _IMPACT.validate_registry({"targets": {"real_target": {"cost": "bogus", "modules": []}}})
    problems += _IMPACT.validate_target_dirs({"targets": {"real_target": {}}})

    assert any("ghost_target" in p for p in problems), problems
    assert any("invalid cost" in p for p in problems), problems
