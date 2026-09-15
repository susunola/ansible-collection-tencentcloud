# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for scripts/check_roadmap_status.py.

The panorama's 30-item table carries a hand-maintained ``chip done`` badge
and nothing checked it, so it rotted in both directions. On 2026-09-14 ten
items already met their own written acceptance while the table still listed
them as open, and every one of them had been described in the docs as
outstanding work.

These tests are the guard's non-vacuity proof. The repo really does satisfy
every criterion (so the guard is not trivially green), the badge really does
agree with the measurement in both directions (so a false claim and a stale
claim both fail), and the helpers that read numbers do not match substrings.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_roadmap_status.py"
MODULES_DIR = REPO_ROOT / "plugins" / "modules"
ROLES_DIR = REPO_ROOT / "roles"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load(SCRIPT_PATH, "check_roadmap_status")


@pytest.fixture(scope="module")
def marked(guard):
    return guard.parse_panorama()


@pytest.fixture(scope="module")
def measured(guard):
    return guard.measure()


# ---------------------------------------------------------------------------
# Anti-vacuity: the parser and the criteria both see a real, non-empty repo.
# ---------------------------------------------------------------------------


def test_the_panorama_still_has_thirty_rows(marked):
    assert len(marked) == 30, "the priority table changed size; the parser may be lost"
    assert "P0-01" in marked and "P2-08" in marked


def test_the_table_has_both_done_and_open_items(marked):
    """A parser that marks everything one way has stopped reading the badges."""
    assert any(marked.values()), "no item is badged done"
    assert not all(marked.values()), "every item is badged done"


def test_every_criterion_maps_to_a_real_row(guard, marked):
    assert set(guard.CRITERIA) <= set(marked)


def test_every_criterion_has_a_title(guard):
    assert set(guard.TITLES) == set(guard.CRITERIA)


def test_the_criteria_are_more_than_a_token_few(guard, measured):
    """One or two criteria would make 'all pass' worthless as a signal."""
    assert len(measured) >= 10


def test_every_criterion_explains_itself(measured):
    """A criterion returning an empty detail cannot be acted on."""
    for item, (_satisfied, detail) in measured.items():
        assert detail.strip(), "%s returned an empty detail" % item


# ---------------------------------------------------------------------------
# The measured state of the real repository.
# ---------------------------------------------------------------------------


def test_the_real_repo_passes_every_criterion(measured):
    failures = {item: detail for item, (ok, detail) in measured.items() if not ok}
    assert failures == {}, "unmet acceptance: %s" % failures


def test_the_real_repo_has_no_badge_mismatches(guard):
    assert guard.validate() == []


def test_the_module_count_the_guard_uses_is_real(guard):
    names, write = guard._module_names()
    assert len(names) == len([p for p in MODULES_DIR.glob("*.py") if not p.name.startswith("__")])
    assert len(write) > 400


def test_the_role_discovery_finds_every_role(guard):
    roles = {p.name for p in ROLES_DIR.iterdir() if p.is_dir() and p.name.startswith("tc_")}
    assert len(roles) > 50
    assert len(guard._role_dirs()) == len(roles)


# ---------------------------------------------------------------------------
# Both directions of the comparison.
# ---------------------------------------------------------------------------


def test_a_false_done_claim_is_reported(guard, marked, measured, monkeypatch):
    """Badged done but the acceptance is not met -- the badge is marketing."""
    item = sorted(i for i in guard.CRITERIA if marked.get(i))[0]
    broken = dict(measured)
    broken[item] = (False, "deliberately broken")
    monkeypatch.setattr(guard, "measure", lambda root=None: broken)
    problems = guard.validate()
    assert any(
        p.startswith(item) and "marked done but fails" in p for p in problems
    ), problems


def test_a_stale_open_item_is_reported(guard, marked, monkeypatch):
    """Acceptance met but never badged -- the roadmap advertises a dead gap."""
    item = sorted(guard.CRITERIA)[0]
    unbadged = dict(marked)
    unbadged[item] = False
    monkeypatch.setattr(guard, "parse_panorama", lambda root=None: unbadged)
    problems = guard.validate()
    assert any(
        p.startswith(item) and "not marked done" in p for p in problems
    ), problems


def test_an_empty_panorama_is_a_problem_rather_than_a_pass(guard, monkeypatch):
    """If the table's markup changes, the guard must not go quietly green."""
    monkeypatch.setattr(guard, "parse_panorama", lambda root=None: {})
    problems = guard.validate()
    assert problems and "no priority rows" in problems[0]


def test_a_criterion_without_a_row_is_reported(guard, marked, monkeypatch):
    monkeypatch.setattr(guard, "parse_panorama", lambda root=None: {k: v for k, v in marked.items() if k != "P0-09"})
    problems = guard.validate()
    assert any("P0-09" in p and "no row" in p for p in problems)


# ---------------------------------------------------------------------------
# The failure paths.  A criterion that can only ever return True is the
# failure mode this whole guard exists to prevent, so each one is driven
# against a synthetic tree that violates it.
# ---------------------------------------------------------------------------


def test_a_shallow_module_test_is_caught(guard, tmp_path):
    directory = tmp_path / guard.MODULE_TEST_DIR
    directory.mkdir(parents=True)
    (directory / "test_thin.py").write_text("def test_thin():\n    assert True\n")
    satisfied, detail = guard._p0_09(tmp_path)
    assert not satisfied
    assert "test_thin.py" in detail


def test_a_companion_doc_on_a_stale_figure_is_caught(guard, tmp_path):
    modules = tmp_path / guard.MODULES_DIR
    modules.mkdir(parents=True)
    for index in range(3):
        (modules / ("m%d.py" % index)).write_text("")
    for relative in guard.COMPANION_DOCS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("module count 781\n")
    satisfied, detail = guard._p0_12(tmp_path)
    assert not satisfied
    assert "capability-map" in detail and "3" in detail


def test_an_integration_env_without_alerting_is_caught(guard, tmp_path):
    path = tmp_path / guard.INTEGRATION_ENV
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("| `TENCENTCLOUD_SECRET_ID` | secret |\n\ncleanup runs with if: always()\n")
    satisfied, detail = guard._p0_03(tmp_path)
    assert not satisfied
    assert "failure alerting" in detail


def test_an_unmapped_release_is_caught(guard, tmp_path):
    changelog = tmp_path / guard.CHANGELOG
    changelog.parent.mkdir(parents=True, exist_ok=True)
    changelog.write_text("ancestor: null\nreleases:\n  1.0.0:\n    changes: {}\n  1.1.0:\n    changes: {}\n")
    porting = tmp_path / guard.PORTING
    porting.parent.mkdir(parents=True, exist_ok=True)
    porting.write_text("# Porting guide\n\n## 10. Version map\n\n| Version |\n| --- |\n| `1.0.0` |\n")
    satisfied, detail = guard._p2_07(tmp_path)
    assert not satisfied
    assert "1.1.0" in detail


def test_a_missing_demo_page_is_caught(guard, tmp_path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / guard.README).write_text("# README\n")
    satisfied, _detail = guard._p2_06(tmp_path)
    assert not satisfied


def test_an_unlinked_demo_page_is_caught(guard, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "demo.html").write_text("<html></html>\n")
    (tmp_path / guard.README).write_text("# README\n\nNo link here.\n")
    satisfied, detail = guard._p2_06(tmp_path)
    assert not satisfied
    assert "does not link" in detail


# ---------------------------------------------------------------------------
# Number handling.
# ---------------------------------------------------------------------------


def test_numbers_are_matched_whole(guard):
    """``55`` must not be found inside ``1557`` or ``553``."""
    found = guard._numbers("sanity 1557/1900 and 553 downloads")
    assert 55 not in found
    assert {1557, 553} <= found


def test_numbers_strip_thousands_separators(guard):
    assert 13511 in guard._numbers("13,511 passed")


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------


def test_the_report_names_every_criterion(guard):
    report = guard.report()
    for item in guard.CRITERIA:
        assert item in report


def test_the_report_lists_what_it_cannot_measure(guard):
    """Silence about the unmeasured items is how a reader assumes they pass."""
    report = guard.report()
    assert "not mechanically measurable" in report
    assert "P0-05" in report.split("not mechanically measurable")[1]
