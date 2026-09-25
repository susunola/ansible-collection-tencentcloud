# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/add_delete_examples.py.

The script writes the example a reader copies to delete something, so the two
ways it can be wrong are the two things it must read from the module: which
option identifies the resource, and what the delete path needs that creation
does not. Both are pinned here against module sources shaped like this
collection's.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "add_delete_examples.py"


def _load_script():
    scripts = str(SCRIPT_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("add_delete_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def deletes():
    return _load_script()


DOC = """DOCUMENTATION = r'''
module: demo
options:
  state:
    description: Desired state.
    type: str
    choices: [present, absent]
  widget_name:
    description: Name of the widget.
    type: str
  widget_id:
    description: ID of an existing widget.
    type: str
  protection:
    description: Whether deletion protection is on.
    type: bool
  description:
    description: Human-readable description.
    type: str
'''

EXAMPLES = r'''
- name: Create a widget
  susunola.tencentcloud.demo:
    widget_name: production
    protection: true
    description: managed by ansible
'''

RETURN = r'''
widget:
  description: The widget.
  type: dict
'''
"""


def module_source(lookup=None, delete_body=None):
    """A module whose lookup and delete paths can be varied."""
    lookup = lookup if lookup is not None else (
        "    return [w for w in widgets if w.WidgetName == name]\n")
    delete_body = delete_body if delete_body is not None else (
        "    if protection:\n"
        "        module.fail_json(msg='set protection=false first')\n"
        "    client.DeleteWidget(WidgetId=current.WidgetId)\n"
        "    return True\n")
    return (
        DOC
        + "def find_widget(module, client, models, name, widget_id):\n"
        "    widgets = client.ListWidgets()\n"
        + lookup
        + "def delete_widget(module, client, current, protection):\n"
        + delete_body
        + "def build_create(p):\n"
        "    return p['description'], p['protection']\n"
        + "def run_module():\n"
        "    module = TencentCloudModule(argument_spec={}, required_one_of=[('widget_id', 'widget_name')])\n"
        "    p = module.params\n"
        "    client = None\n"
        "    current = find_widget(module, client, None, p['widget_name'], p['widget_id'])\n"
        "    if p['state'] == 'absent':\n"
        "        delete_widget(module, client, current, p['protection'])\n"
        "        module.exit_json(changed=True)\n"
        "    build_create(p)\n"
        "    module.exit_json(changed=True)\n")


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_delete_examples_pass(deletes, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["add_delete_examples.py", "--check"])
    assert deletes.main() == 0


def test_no_module_is_still_missing_a_delete_example(deletes):
    assert deletes.candidates() == []


# --------------------------------------------------------------------------
# identity: what the lookup reads
# --------------------------------------------------------------------------

def test_lookup_reads_give_the_identity(deletes):
    reads = deletes.lookup_reads(module_source())
    assert reads == {"widget_name", "widget_id"}


def test_the_create_example_value_is_used_for_the_identity(deletes):
    source = module_source()
    options = deletes.delete_options(source, "demo", deletes.create_example(source))
    assert options["widget_name"] == "production"


def test_a_create_only_payload_is_not_copied_into_the_delete(deletes):
    """The description says nothing about identity and the delete never reads
    it, so it has no place in a delete call."""
    source = module_source()
    options = deletes.delete_options(source, "demo", deletes.create_example(source))
    assert "description" not in options


# --------------------------------------------------------------------------
# a flag the delete path needs, which the create example sets the other way
# --------------------------------------------------------------------------

def test_delete_path_flag_is_taken_from_the_unit_test(deletes, tmp_path, monkeypatch):
    """This is the alb_load_balancer trap: the create example turns deletion
    protection on, and the module refuses to delete while it is on."""
    monkeypatch.setattr(deletes, "UNIT_TESTS", str(tmp_path))
    (tmp_path / "test_demo.py").write_text(
        "def test_delete(monkeypatch):\n"
        "    module_args(state='absent', widget_name='production', protection=False)\n",
        encoding="utf-8")
    source = module_source()
    options = deletes.delete_options(source, "demo", deletes.create_example(source))
    assert options["protection"] is False


def test_a_ghost_delete_call_does_not_supply_values(deletes, tmp_path, monkeypatch):
    """A test that asserts "nothing happened" passes a resource that does not
    exist; its values are not an example."""
    monkeypatch.setattr(deletes, "UNIT_TESTS", str(tmp_path))
    (tmp_path / "test_demo.py").write_text(
        "def test_absent_missing(monkeypatch):\n"
        "    module_args(state='absent', widget_name='ghost-widget', protection=False)\n",
        encoding="utf-8")
    assert deletes.delete_call_values("demo").get("widget_name") is None


def test_delete_path_without_a_test_value_leaves_the_flag_out(deletes, tmp_path, monkeypatch):
    monkeypatch.setattr(deletes, "UNIT_TESTS", str(tmp_path))
    source = module_source()
    options = deletes.delete_options(source, "demo", deletes.create_example(source))
    assert "protection" not in options


# --------------------------------------------------------------------------
# what it refuses to write
# --------------------------------------------------------------------------

def test_a_module_whose_required_option_is_missing_is_skipped(deletes):
    source = module_source().replace(
        "  widget_id:\n    description: ID of an existing widget.\n    type: str\n",
        "  widget_id:\n    description: ID of an existing widget.\n    type: str\n    required: true\n")
    assert deletes.delete_options(source, "demo", deletes.create_example(source)) is None


def test_a_module_that_already_shows_deletion_is_left_alone(deletes):
    source = module_source().replace(
        "    description: managed by ansible\n",
        "    description: managed by ansible\n\n"
        "- name: Delete a widget\n"
        "  susunola.tencentcloud.demo:\n"
        "    state: absent\n"
        "    widget_name: production\n")
    assert deletes.needs_example(source) is False


def test_a_module_without_state_is_left_alone(deletes):
    source = module_source().replace("    choices: [present, absent]\n", "    choices: [enabled, disabled]\n")
    assert deletes.needs_example(source) is False


# --------------------------------------------------------------------------
# the example it writes
# --------------------------------------------------------------------------

def test_example_is_appended_and_names_the_resource(deletes):
    new_source = deletes.enrich(module_source(), "demo")
    assert "- name: Delete the widget" in new_source
    assert "    state: absent" in new_source
    assert "    widget_name: production" in new_source


def test_example_keeps_the_create_example(deletes):
    new_source = deletes.enrich(module_source(), "demo")
    assert "- name: Create a widget" in new_source


def test_enrichment_is_idempotent(deletes):
    once = deletes.enrich(module_source(), "demo")
    assert deletes.enrich(once, "demo") is None
