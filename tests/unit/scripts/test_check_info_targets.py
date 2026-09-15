"""Unit tests for scripts/check_info_targets.py.

The guard proves the curated read-surface targets in
``scripts/info_specs_targets.py`` actually shipped: every target must have
a write module, a generated ``<name>_info`` module, a generated unit test,
and a spec in ``scripts/info_specs_auto.py`` carrying the target
``version_added`` marker -- and the reverse, that no spec carries the
marker without a target declaring it.

Most tests run against a throwaway tree so failures do not depend on the
real collection's shape; one test pins the real table so the guard cannot
go vacuous if the tree ever empties out.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_info_targets.py"
TARGETS_PATH = REPO_ROOT / "scripts" / "info_specs_targets.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load(SCRIPT_PATH, "check_info_targets")


@pytest.fixture(scope="module")
def real_targets():
    return _load(TARGETS_PATH, "info_specs_targets")


def _tree(root, targets, specs):
    """Materialise a throwaway repo: TARGETS + SPECS_AUTO + modules."""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    version = "1.5.0"
    lines = ["TARGET_VERSION_ADDED = %r" % version, "TARGETS = {"]
    for write, action in targets.items():
        lines.append("    %r: %r," % (write, action))
    lines.append("}")
    (scripts / "info_specs_targets.py").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    body = ["SPECS_AUTO = ["]
    for module, added in specs:
        body.append("    {'module': %r, 'version_added': %r}," % (module, added))
    body.append("]")
    (scripts / "info_specs_auto.py").write_text(
        "\n".join(body) + "\n", encoding="utf-8")
    return root


def _ship(root, write):
    """Create the write module, the generated _info and its unit test."""
    modules = root / "plugins" / "modules"
    tests = root / "tests" / "unit" / "plugins" / "modules"
    modules.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (modules / ("%s.py" % write)).write_text("# write\n", encoding="utf-8")
    (modules / ("%s_info.py" % write)).write_text("# info\n", encoding="utf-8")
    (tests / ("test_%s_info.py" % write)).write_text(
        "# test\n", encoding="utf-8")


def test_empty_table_is_a_problem(guard, tmp_path):
    """Anti-vacuity: an empty table must fail, not silently pass."""
    _tree(tmp_path, {}, [])
    assert guard.validate(root=tmp_path) == [
        "scripts/info_specs_targets.py declares no targets"]


def test_complete_tree_passes(guard, tmp_path):
    targets = {"alpha_widget": "DescribeWidgets"}
    _tree(tmp_path, targets, [("alpha_widget_info", "1.5.0")])
    _ship(tmp_path, "alpha_widget")
    assert guard.validate(root=tmp_path) == []


def test_missing_generated_module_is_caught(guard, tmp_path):
    _tree(tmp_path, {"alpha_widget": "DescribeWidgets"},
          [("alpha_widget_info", "1.5.0")])
    _ship(tmp_path, "alpha_widget")
    (tmp_path / "plugins" / "modules" / "alpha_widget_info.py").unlink()
    problems = guard.validate(root=tmp_path)
    assert any("produced no plugins/modules/alpha_widget_info.py" in p
               for p in problems)


def test_missing_unit_test_is_caught(guard, tmp_path):
    _tree(tmp_path, {"alpha_widget": "DescribeWidgets"},
          [("alpha_widget_info", "1.5.0")])
    _ship(tmp_path, "alpha_widget")
    (tmp_path / "tests" / "unit" / "plugins" / "modules"
     / "test_alpha_widget_info.py").unlink()
    problems = guard.validate(root=tmp_path)
    assert any("produced no tests/unit/plugins/modules/"
               "test_alpha_widget_info.py" in p for p in problems)


def test_target_without_write_module_is_caught(guard, tmp_path):
    _tree(tmp_path, {"ghost_widget": "DescribeWidgets"},
          [("ghost_widget_info", "1.5.0")])
    _ship(tmp_path, "ghost_widget")
    (tmp_path / "plugins" / "modules" / "ghost_widget.py").unlink()
    problems = guard.validate(root=tmp_path)
    assert any("has no write module plugins/modules/ghost_widget.py" in p
               for p in problems)


def test_spec_without_target_is_caught(guard, tmp_path):
    """Reverse direction: a marked spec nobody declared."""
    _tree(tmp_path, {"alpha_widget": "DescribeWidgets"},
          [("alpha_widget_info", "1.5.0"), ("orphan_info", "1.5.0")])
    _ship(tmp_path, "alpha_widget")
    problems = guard.validate(root=tmp_path)
    assert any("orphan_info is version_added 1.5.0 but no target declares it"
               in p for p in problems)


def test_target_rejected_by_discovery_is_caught(guard, tmp_path):
    """A target whose action no longer resolves yields no spec."""
    _tree(tmp_path, {"alpha_widget": "DescribeWidgets"}, [])
    _ship(tmp_path, "alpha_widget")
    problems = guard.validate(root=tmp_path)
    assert any("alpha_widget_info is declared as a target but carries no "
               "version_added 1.5.0 spec" in p for p in problems)


def test_unmarked_spec_is_ignored(guard, tmp_path):
    """Specs from plain discovery carry another version and are not ours."""
    _tree(tmp_path, {"alpha_widget": "DescribeWidgets"},
          [("alpha_widget_info", "1.5.0"), ("beta_info", "0.9.0")])
    _ship(tmp_path, "alpha_widget")
    assert guard.validate(root=tmp_path) == []


def test_malformed_target_entry_is_caught(guard, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "info_specs_targets.py").write_text(textwrap.dedent("""\
        TARGET_VERSION_ADDED = "1.5.0"
        TARGETS = {"alpha_widget": 17}
        """), encoding="utf-8")
    (scripts / "info_specs_auto.py").write_text(
        "SPECS_AUTO = []\n", encoding="utf-8")
    problems = guard.validate(root=tmp_path)
    assert any("must be an action string or a mapping" in p for p in problems)


def test_mapping_target_without_action_is_caught(guard, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "info_specs_targets.py").write_text(textwrap.dedent("""\
        TARGET_VERSION_ADDED = "1.5.0"
        TARGETS = {"alpha_widget": {"resource": "widget"}}
        """), encoding="utf-8")
    (scripts / "info_specs_auto.py").write_text(
        "SPECS_AUTO = []\n", encoding="utf-8")
    problems = guard.validate(root=tmp_path)
    assert any("has no non-empty 'action'" in p for p in problems)


def test_target_keyed_on_info_module_is_caught(guard, tmp_path):
    _tree(tmp_path, {"alpha_widget_info": "DescribeWidgets"},
          [("alpha_widget_info_info", "1.5.0")])
    _ship(tmp_path, "alpha_widget_info")
    problems = guard.validate(root=tmp_path)
    assert any("already names an _info module" in p for p in problems)


def test_real_collection_passes(guard):
    """Pin the real table: the shipped targets all resolve."""
    assert guard.validate() == []


def test_real_table_is_not_trivially_small(guard, real_targets):
    """Anti-vacuity: the curated table is a substantial, well-formed set."""
    targets = real_targets.TARGETS
    assert len(targets) >= 50
    for write, value in targets.items():
        assert not write.endswith("_info"), write
        action = value["action"] if isinstance(value, dict) else value
        assert isinstance(action, str) and action.strip(), write
        assert (REPO_ROOT / "plugins" / "modules" / ("%s.py" % write)).is_file()
        assert (REPO_ROOT / "plugins" / "modules"
                / ("%s_info.py" % write)).is_file()


def test_real_targets_stamp_the_marker_version(real_targets):
    """Every target-derived spec carries the marker the guard matches on."""
    specs = _load(REPO_ROOT / "scripts" / "info_specs_auto.py",
                  "info_specs_auto").SPECS_AUTO
    marked = {s["module"] for s in specs
              if s.get("version_added") == real_targets.TARGET_VERSION_ADDED}
    assert marked == {"%s_info" % w for w in real_targets.TARGETS}
