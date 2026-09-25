# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/enrich_state_docs.py.

The script writes a sentence about what ``state`` does, so the tests are about
the two ways that sentence can be wrong: claiming a call the module does not
make, and crediting a phase with a call that belongs to the other one. Both
directions are pinned here with module bodies written in the shapes the
collection actually uses.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "enrich_state_docs.py"


def _load_script():
    scripts = str(SCRIPT_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("enrich_state_docs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def state_docs():
    return _load_script()


def module_source(body, thin=True):
    """A module whose documentation and code agree, in the collection's shape."""
    description = "      - Desired state.\n" if thin else "      - C(present) creates it and C(absent) deletes it.\n"
    return (
        "DOCUMENTATION = r'''\n"
        "module: demo\n"
        "options:\n"
        "  state:\n"
        "    description:\n"
        "%s"
        "    type: str\n"
        "    choices: [present, absent]\n"
        "    default: present\n"
        "'''\n"
        "RETURN = r'''widget:\n"
        "  description: The widget.\n"
        "  type: dict\n"
        "'''\n"
        "def run_module():\n"
        "%s"
        % (description, body))


ABSENT_LAST = """\
    current = find(module, client, models, p)
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False)
        module.sdk_call(client.DeleteWidget, request)
        module.exit_json(changed=True)
    if not current:
        module.sdk_call(client.CreateWidget, request)
    else:
        module.sdk_call(client.ModifyWidget, request)
    module.exit_json(changed=True)
"""

ABSENT_FIRST = """\
    current = find(module, client, models, p)
    if p["state"] == "present":
        if not current:
            module.sdk_call(client.CreateWidget, request)
        else:
            module.sdk_call(client.ModifyWidget, request)
        module.exit_json(changed=True)
    if not current:
        module.exit_json(changed=False)
    module.sdk_call(client.DeleteWidget, request)
    module.exit_json(changed=True)
"""

TERNARY = """\
    present = p["state"] == "present"
    module.sdk_call(
        client.BindWidget if present else client.UnbindWidget,
        request,
    )
"""


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_state_docs_pass_the_check(state_docs, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["enrich_state_docs.py", "--check"])
    assert state_docs.main() == 0


def test_no_core_module_is_still_thin(state_docs):
    assert state_docs.candidates() == []


# --------------------------------------------------------------------------
# which phase a call belongs to
# --------------------------------------------------------------------------

def test_absent_branch_last_is_read_correctly(state_docs):
    operations = state_docs.phase_operations(module_source(ABSENT_LAST))
    assert operations == {"create": ["CreateWidget"], "update": ["ModifyWidget"],
                          "delete": ["DeleteWidget"]}


def test_absent_branch_first_is_read_correctly(state_docs):
    """Half the modules in this collection write the absent branch first."""
    operations = state_docs.phase_operations(module_source(ABSENT_FIRST))
    assert operations == {"create": ["CreateWidget"], "update": ["ModifyWidget"],
                          "delete": ["DeleteWidget"]}


def test_ternary_choice_is_split_by_its_condition(state_docs):
    """``client.A if present else client.B`` puts B on the absent path, which a
    branch-only reading discarded as a rollback."""
    operations = state_docs.phase_operations(module_source(TERNARY))
    assert operations == {"create": ["BindWidget"], "update": [], "delete": ["UnbindWidget"]}


def test_a_delete_on_the_present_path_is_not_reported_as_the_deletion(state_docs):
    """Rollbacks and unbinds happen while reconciling; naming them under
    ``absent`` would send a reader looking for a call that is not there."""
    source = module_source(
        '    current = find(module, client, models, p)\n'
        '    if not current:\n'
        '        module.sdk_call(client.CreateWidget, request)\n'
        '    else:\n'
        '        module.sdk_call(client.DeleteWidget, request)\n'
        '        module.sdk_call(client.CreateWidget, request)\n'
        '    if p["state"] == "absent":\n'
        '        module.sdk_call(client.TerminateWidget, request)\n')
    operations = state_docs.phase_operations(source)
    assert operations["delete"] == ["TerminateWidget"]


def test_read_calls_are_never_named(state_docs):
    operations = state_docs.phase_operations(module_source(ABSENT_LAST))
    assert all(not name.startswith("Describe") for names in operations.values() for name in names)


# --------------------------------------------------------------------------
# what the sentence says
# --------------------------------------------------------------------------

def test_sentence_names_both_phases(state_docs):
    lines = state_docs.build_description(
        "widget", {"create": ["CreateWidget"], "update": ["ModifyWidget"],
                   "delete": ["DeleteWidget"]}, waits=False)
    assert lines == ["C(present) creates the widget with V(CreateWidget) when it does not exist "
                     "and updates it with V(ModifyWidget) when it differs. "
                     "C(absent) deletes it with V(DeleteWidget)."]


def test_alternatives_are_joined_with_or(state_docs):
    """Two calls in one phase are a choice, not a sequence."""
    lines = state_docs.build_description(
        "widget", {"create": ["CreateHourlyWidget", "CreateWidget"], "update": [],
                   "delete": ["DeleteWidget"]}, waits=False)
    assert "V(CreateHourlyWidget) or V(CreateWidget)" in lines[0]


def test_isolate_is_not_called_a_delete(state_docs):
    """``state=absent`` on cynosdb_cluster calls IsolateCluster, which is not
    the same thing as deleting it."""
    lines = state_docs.build_description(
        "cluster", {"create": ["CreateClusters"], "update": [], "delete": ["IsolateCluster"]}, waits=False)
    assert "removes it with V(IsolateCluster)" in lines[0]
    assert "deletes it" not in lines[0]


def test_waiter_sentence_appears_only_when_the_module_waits(state_docs):
    assert len(state_docs.build_description(
        "widget", {"create": ["CreateWidget"], "update": [], "delete": ["DeleteWidget"]}, waits=False)) == 1
    assert len(state_docs.build_description(
        "widget", {"create": ["CreateWidget"], "update": [], "delete": ["DeleteWidget"]}, waits=True)) == 2


def test_waiter_detection_matches_the_module(state_docs):
    assert state_docs.waits_for_change("    wait_for_widget(module, client, 'id')")
    assert state_docs.waits_for_change('    "waiter_timeout": 120,')
    assert not state_docs.waits_for_change("    module.sdk_call(client.CreateWidget, request)")


# --------------------------------------------------------------------------
# what the generator refuses to touch
# --------------------------------------------------------------------------

def test_a_long_description_is_left_alone(state_docs):
    source = module_source(ABSENT_LAST, thin=False)
    assert state_docs.enrich(source) is None


def test_other_choices_are_left_alone(state_docs):
    """``running``/``stopped`` has semantics this shape does not cover."""
    source = module_source(ABSENT_LAST).replace(
        "choices: [present, absent]", "choices: [present, absent, running]")
    assert state_docs.enrich(source) is None


def test_a_module_with_no_delete_path_is_left_alone(state_docs):
    """A description that never mentions deletion is worse than the thin one
    it would replace, so the generator reports nothing rather than writing it."""
    source = module_source(
        '    current = find(module, client, models, p)\n'
        '    if not current:\n'
        '        module.sdk_call(client.CreateWidget, request)\n')
    assert state_docs.enrich(source) is None


def test_the_noun_comes_from_the_return_key(state_docs):
    assert state_docs.resource_noun(module_source(ABSENT_LAST)) == "widget"


def test_enrichment_keeps_the_rest_of_the_option(state_docs):
    new_source = state_docs.enrich(module_source(ABSENT_LAST))
    assert "    type: str\n" in new_source
    assert "    choices: [present, absent]\n" in new_source
    assert "    default: present\n" in new_source


def test_enrichment_is_idempotent(state_docs):
    """Running it twice must not wrap the sentence again."""
    once = state_docs.enrich(module_source(ABSENT_LAST))
    assert state_docs.enrich(once) is None
