# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for the frozen baselines in scripts/check_quality_gates.py.

Two of the census families are stock counts of existing debt: RETURN entries
with no ``sample`` and core-subset write modules with no integration target.
A stock ceiling alone cannot tell "fixed three, broke three" apart from
"fixed nothing", so each family is also frozen as an explicit list. These
tests pin the three properties that make the list useful: a module that is
not on it must not have the finding, a listed module that no longer has the
finding must be delisted, and the committed lists must match the committed
tree.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_quality_gates.py"


def _null():
    """A throwaway stream for the helper calls that report progress."""
    return io.StringIO()


def _load_script():
    spec = importlib.util.spec_from_file_location("check_quality_gates",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gates():
    return _load_script()


@pytest.fixture
def baselines(gates, tmp_path, monkeypatch):
    """Point the baseline directory at a throwaway tree."""
    monkeypatch.setattr(gates, "BASELINES_DIR", str(tmp_path))
    return gates


def test_missing_baseline_is_reported(baselines):
    problems = baselines.baseline_problems("return_samples", ["a", "b"])
    assert len(problems) == 1
    assert "is missing" in problems[0]
    assert "--write-baseline return_samples" in problems[0]


def test_write_then_read_round_trips(baselines):
    assert baselines.write_baseline("return_samples", ["b", "a"],
                                    out=_null()) == 0
    assert baselines.read_baseline("return_samples") == ["a", "b"]


def test_matching_findings_pass(baselines):
    baselines.write_baseline("return_samples", ["a", "b"], out=_null())
    assert baselines.baseline_problems("return_samples", ["a", "b"]) == []


def test_new_finding_is_reported(baselines):
    baselines.write_baseline("return_samples", ["a"], out=_null())
    problems = baselines.baseline_problems("return_samples", ["a", "new_module"])
    assert len(problems) == 1
    assert "new_module" in problems[0]
    assert "not in the return_samples baseline" in problems[0]
    assert "--write-baseline" not in problems[0]


def test_fixed_and_broken_module_is_still_reported(baselines):
    """The loophole a stock ceiling leaves open.

    One module gained a sample and one new module lost one, so the *count* is
    unchanged and a stock ratchet would stay green. The baseline does not:
    the new module is not on the list.
    """
    baselines.write_baseline("return_samples", ["old_a", "old_b"], out=_null())
    problems = baselines.baseline_problems("return_samples",
                                           ["old_a", "new_module"])
    assert any("new_module" in problem and "not in the" in problem
               for problem in problems)
    assert any("old_b" in problem and "no longer have the finding" in problem
               for problem in problems)


def test_stale_entry_is_reported(baselines):
    baselines.write_baseline("return_samples", ["a", "fixed"], out=_null())
    problems = baselines.baseline_problems("return_samples", ["a"])
    assert len(problems) == 1
    assert "fixed" in problems[0]
    assert "only shrinks" in problems[0]


def test_write_baseline_reports_what_moved(baselines):
    baselines.write_baseline("return_samples", ["a", "b"], out=_null())
    out = io.StringIO()
    baselines.write_baseline("return_samples", ["b", "c"], out=out)
    report = out.getvalue()
    assert "+1, -1" in report
    assert "added:   c" in report
    assert "removed: a" in report


def test_baseline_file_explains_itself(baselines):
    baselines.write_baseline("integration_missing", ["a"], out=_null())
    text = Path(baselines.baseline_path("integration_missing")).read_text(
        encoding="utf-8")
    assert text.startswith("#")
    assert "may only shrink" in text


def test_write_baseline_is_reachable_from_the_command_line(baselines):
    """The documented way to freeze a family must exist and work."""
    assert baselines.main(["--write-baseline", "return_samples"]) == 0
    assert baselines.read_baseline("return_samples") == \
        baselines.return_sample_findings()


def test_committed_return_sample_baseline_matches_the_tree(gates):
    frozen = gates.read_baseline(gates.BASELINE_RETURN_SAMPLES)
    assert frozen is not None
    assert frozen == gates.return_sample_findings()


def test_committed_integration_baseline_matches_the_tree(gates):
    frozen = gates.read_baseline(gates.BASELINE_INTEGRATION_MISSING)
    assert frozen is not None
    assert frozen == gates.integration_findings()[1]
