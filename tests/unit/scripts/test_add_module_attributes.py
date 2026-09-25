# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "add_module_attributes.py"


def _load_script():
    # The script imports its sibling normalize_module_docs for the house YAML
    # style, which works when it is run as a script and not when it is loaded
    # from a file path.
    scripts = str(SCRIPT_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("add_module_attributes", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def attributes():
    return _load_script()


def module_text(state_choices=("present", "absent"), extra=""):
    """A minimal module source with an argument spec and a doc block."""
    choices = ", ".join('"%s"' % choice for choice in state_choices)
    return (
        "DOCUMENTATION = r'''\n"
        "module: demo\n"
        "options:\n"
        "  state:\n"
        "    description: Desired state.\n"
        "    type: str\n"
        "    choices: [%s]\n"
        "author: test\n"
        "'''\n"
        "def run_module():\n"
        "    module = TencentCloudModule(\n"
        "        argument_spec={\"state\": {\"choices\": [%s]}},\n"
        "        supports_check_mode=True,\n"
        "    )\n"
        "%s" % (choices, choices, extra))


def with_block(text, block):
    """Return *text* with *block* inserted as its attributes block."""
    return text.replace("author: test", block.rstrip("\n") + "\nauthor: test")


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_attributes_pass_the_check(attributes, monkeypatch):
    """No shipped module may claim more support than its code has."""
    monkeypatch.setattr(sys, "argv", ["add_module_attributes.py", "--check"])
    assert attributes.main() == 0


def test_every_module_has_an_attributes_block(attributes):
    from glob import glob
    assert len(glob(str(REPO_ROOT / "plugins" / "modules" / "*.py"))) == 1027


# --------------------------------------------------------------------------
# support levels
# --------------------------------------------------------------------------

def test_full_claim_on_a_one_shot_module_is_reported(attributes):
    """tat_invocation claimed idempotent: full while every exit path passes
    changed=True and its own description says a start creates a new
    invocation."""
    text = with_block(module_text(("started", "cancelled")), """\
attributes:
  check_mode:
    description: placeholder
    support: full
  idempotent:
    description: placeholder
    support: full""")
    problems = attributes.overclaimed(text, "plugins/modules/tat_invocation.py")
    assert problems == ["idempotent: claims support=full, the module's code supports partial"]


def test_weaker_claim_than_the_rules_allow_is_accepted(attributes):
    """alb_listener says partial for diff_mode and idempotent and explains
    why. That is more useful than the boilerplate, and it is not a
    false claim."""
    text = with_block(module_text(), """\
attributes:
  check_mode:
    description: placeholder
    support: full
  diff_mode:
    description: placeholder
    support: partial
    details: API-assigned fields are not part of the diff.
  idempotent:
    description: placeholder
    support: partial
    details: Waits for observable settings to converge after writes.""")
    assert attributes.overclaimed(text, "plugins/modules/alb_listener.py") == []


def test_no_attributes_block_is_not_an_overclaim(attributes):
    assert attributes.overclaimed(module_text(), "plugins/modules/demo.py") == []


def test_missing_attribute_is_not_an_overclaim(attributes):
    """An attribute a module does not document makes no claim at all."""
    text = with_block(module_text(), """\
attributes:
  check_mode:
    description: placeholder
    support: full""")
    assert attributes.overclaimed(text, "plugins/modules/demo.py") == []


def test_committed_supports_reads_every_attribute(attributes):
    text = module_text()
    body = attributes._DOC_RE.search(with_block(text, """\
attributes:
  check_mode:
    description: placeholder
    support: full
  diff_mode:
    description: placeholder
    support: partial
  idempotent:
    description: placeholder
    support: none""")).group("body")
    assert attributes._committed_supports(body) == {
        "check_mode": "full", "diff_mode": "partial", "idempotent": "none"}


# --------------------------------------------------------------------------
# one-shot states
# --------------------------------------------------------------------------

def test_one_shot_states_honours_the_module_override(attributes):
    """``started`` converges for lighthouse_instance and creates a new record
    for tat_invocation, so the word alone cannot decide it."""
    text = module_text(("started", "stopped"))
    assert attributes._one_shot_states(text, "lighthouse_instance") == []
    assert attributes._one_shot_states(text, "tat_invocation") == ["cancelled", "started"]


def test_one_shot_states_keeps_the_global_list(attributes):
    text = module_text(("present", "rebooted"))
    assert attributes._one_shot_states(text, "cvm_instance") == ["rebooted"]


def test_all_states_one_shot_is_worded_differently(attributes):
    """A module where nothing converges must not say "most C(state) values
    converge"."""
    block = "\n".join(attributes.build_block(
        module_text(("started", "cancelled")), "plugins/modules/tat_invocation.py"))
    assert "Most C(state) values converge" not in block
    assert "Every C(state) value" in block
    assert "support: partial" in block
    assert "details:" in block


def test_partly_one_shot_keeps_the_most_wording(attributes):
    block = "\n".join(attributes.build_block(
        module_text(("present", "absent", "rebooted")), "plugins/modules/cvm_instance.py"))
    assert "Most C(state) values converge and are idempotent" in block
    assert "C(state=rebooted)" in block


def test_state_choices_reads_the_argument_spec(attributes):
    assert attributes._state_choices(module_text(("present", "absent"))) == ["absent", "present"]


# --------------------------------------------------------------------------
# insertion
# --------------------------------------------------------------------------

def test_insert_does_not_touch_an_existing_block(attributes):
    """The generator inserts once. Verify is what keeps an existing claim
    honest, because the generator never rewrites it."""
    text = with_block(module_text(), """\
attributes:
  check_mode:
    description: placeholder
    support: none""")
    new_source, changed = attributes.add_attributes(text, "plugins/modules/demo.py")
    assert changed is False
    assert new_source == text
