# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for scripts/check_integration_defaults.py.

The weekly credentialed run is the only thing in this repo that touches a
real cloud account, and the list of targets it touches was a string typed
twice inside ``.github/workflows/integration.yml``. Nothing compared either
copy with ``tests/integration/coverage.yml``, and nothing compared the two
copies with each other -- so editing one copy was a complete, silent,
successful edit that left the other one authoritative for whichever trigger
happened to fire.

``docs/integration-env.md`` did write the rule down (free/low runs by
default, medium/high stays opt-in) and the rule was still being violated by
two medium targets that had crept into the list. Writing a rule in prose is
how the module registries, the doc figures and the curated info targets all
rotted; the point of these tests is that the rule is now executed.

So both directions are driven here. A target that is dispatched but should
not be is a problem, and a cheap target that is never dispatched is also a
problem -- the second one is the expensive one, because a target nobody
runs is coverage the registry claims but does not have.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
from pathlib import Path

import pytest

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_integration_defaults.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "integration.yml"
MAP = REPO_ROOT / "tests" / "integration" / "coverage.yml"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load(SCRIPT_PATH, "check_integration_defaults")


@pytest.fixture(scope="module")
def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def coverage():
    return yaml.safe_load(MAP.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dispatched(guard, workflow_text):
    return guard.default_lists(workflow_text)[0]


def _workflow(declared, fallback):
    """Build a minimal workflow carrying both copies of the list.

    The guard reads the workflow as text rather than as YAML, so the fixture
    has to reproduce the two lines the regexes anchor on and nothing else --
    anything more risks a second ``default:`` matching first.
    """
    return (
        "on:\n"
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      targets:\n"
        "        default: '%s'\n"
        "jobs:\n"
        "  run:\n"
        "    env:\n"
        "      TARGETS: ${{ inputs.targets || '%s' }}\n" % (declared, fallback)
    )


def _coverage(*pairs):
    return {"targets": {name: {"cost": cost} for name, cost in pairs}}


# ---------------------------------------------------------------------------
# Anti-vacuity: the guard sees a real workflow and a real registry, and both
# of the sets it compares are non-trivial.
# ---------------------------------------------------------------------------


def test_both_copies_of_the_list_are_found(guard, workflow_text):
    lists = guard.default_lists(workflow_text)
    assert lists is not None, "the guard no longer reads the workflow it guards"
    assert lists[0], "the default copy parsed to nothing"


def test_the_default_list_is_not_token_small(guard, dispatched):
    """Two or three targets would make 'agrees with coverage.yml' worthless."""
    assert len(dispatched) > 10


def test_the_registry_has_targets_that_are_not_dispatched(guard, coverage, dispatched):
    """If everything were dispatched, the opt-in half of the rule is untested."""
    opt_in = set(coverage["targets"]) - set(dispatched)
    assert opt_in, "no opt-in targets left; the cost tiers stopped meaning anything"


def test_every_cost_tier_is_present_in_the_registry(guard, coverage):
    costs = {config.get("cost") for config in coverage["targets"].values()}
    assert {"free", "low"} <= costs, "nothing to assert the dispatch rule against"
    assert costs & {"medium", "high"}, "no opt-in tier left to keep out of the list"


def test_the_real_repo_passes(guard, workflow_text, coverage):
    assert guard.audit(workflow_text, coverage) == []


def test_no_target_is_listed_twice(guard, dispatched):
    assert len(dispatched) == len(set(dispatched))


def test_every_vetted_medium_is_actually_medium(guard, coverage):
    for name in guard.VETTED_MEDIUM:
        assert name in coverage["targets"], "%s is vetted but not registered" % name
        assert coverage["targets"][name]["cost"] == "medium"


def test_every_vetted_medium_states_a_reason(guard):
    """A name with no reason is a claim nobody can review."""
    for name, reason in guard.VETTED_MEDIUM.items():
        assert reason.strip(), "%s is vetted without saying why" % name


# ---------------------------------------------------------------------------
# Dispatched but should not be.
# ---------------------------------------------------------------------------


def test_a_high_cost_target_in_the_default_list_is_caught(guard):
    text = _workflow("cvm_instance alpha", "cvm_instance alpha")
    problems = guard.audit(text, _coverage(("cvm_instance", "high"), ("alpha", "free")))
    assert any("cvm_instance" in p and "high" in p for p in problems)


def test_an_unvetted_medium_target_in_the_default_list_is_caught(guard):
    text = _workflow("cos_bucket alpha", "cos_bucket alpha")
    problems = guard.audit(text, _coverage(("cos_bucket", "medium"), ("alpha", "free")))
    assert any("cos_bucket" in p and "not vetted" in p for p in problems)


def test_an_unknown_target_in_the_default_list_is_caught(guard):
    text = _workflow("typo_target alpha", "typo_target alpha")
    problems = guard.audit(text, _coverage(("alpha", "free")))
    assert any("typo_target" in p and "not in" in p for p in problems)


def test_a_duplicate_in_the_default_list_is_caught(guard):
    text = _workflow("alpha alpha", "alpha alpha")
    problems = guard.audit(text, _coverage(("alpha", "free")))
    assert any("listed twice" in p for p in problems)


def test_an_empty_default_list_is_caught(guard):
    text = _workflow("", "")
    problems = guard.audit(text, _coverage(("alpha", "free")))
    assert any("empty" in p for p in problems)


# ---------------------------------------------------------------------------
# Never dispatched but should be.
# ---------------------------------------------------------------------------


def test_a_free_target_missing_from_the_default_list_is_caught(guard):
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free"), ("beta", "free")))
    assert any("beta" in p and "missing from the default list" in p for p in problems)


def test_a_low_cost_target_missing_from_the_default_list_is_caught(guard):
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free"), ("gamma", "low")))
    assert any("gamma" in p and "missing from the default list" in p for p in problems)


def test_a_high_cost_target_left_out_is_not_a_problem(guard):
    """Opt-in is the correct state for an expensive target, not a gap.

    Only the absence of a *complaint about delta* is asserted: the real
    VETTED_MEDIUM table names targets this synthetic registry does not have,
    so the problem list is never empty here.
    """
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free"), ("delta", "high")))
    assert not any("delta" in p for p in problems), problems


# ---------------------------------------------------------------------------
# The two copies drifting apart.
# ---------------------------------------------------------------------------


def test_the_two_copies_disagreeing_is_caught(guard):
    text = _workflow("alpha beta", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free"), ("beta", "free")))
    assert any("disagree" in p for p in problems)
    assert any("beta" in p for p in problems)


def test_an_unreadable_workflow_is_caught_rather_than_passed(guard):
    """If the workflow is restructured, the guard must not go quietly green."""
    problems = guard.audit("jobs:\n  run:\n    steps: []\n", _coverage(("alpha", "free")))
    assert any("could not find both copies" in p for p in problems)


# ---------------------------------------------------------------------------
# The vetting table itself rotting.
# ---------------------------------------------------------------------------


def test_a_vetted_target_that_is_not_registered_is_caught(guard, monkeypatch):
    monkeypatch.setitem(guard.VETTED_MEDIUM, "gone_target", "it used to exist")
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free")))
    assert any("gone_target" in p and "not in the registry" in p for p in problems)


def test_a_vetted_target_whose_cost_changed_is_caught(guard, monkeypatch):
    """Vetting is a claim about a medium target; a free one needs no claim."""
    monkeypatch.setitem(guard.VETTED_MEDIUM, "alpha", "it used to be medium")
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free")))
    assert any("alpha" in p and "only medium targets need vetting" in p for p in problems)


def test_a_vetted_target_that_stopped_being_dispatched_is_caught(guard, monkeypatch):
    monkeypatch.setitem(guard.VETTED_MEDIUM, "beta", "safe enough")
    text = _workflow("alpha", "alpha")
    problems = guard.audit(text, _coverage(("alpha", "free"), ("beta", "medium")))
    assert any("beta" in p and "not in the default list" in p for p in problems)


# ---------------------------------------------------------------------------
# The vetted medium targets really are the ones the registry says they are,
# and the reason really does describe an always-teardown. Each one is a
# standing claim that a weekly unattended run will not leave a bill behind.
# ---------------------------------------------------------------------------


def test_the_vetted_reasons_describe_a_teardown(guard):
    for name, reason in guard.VETTED_MEDIUM.items():
        assert "always" in reason, "%s: the reason must name the teardown block" % name
        assert "leaving no long-lived billable resource" in reason, name
