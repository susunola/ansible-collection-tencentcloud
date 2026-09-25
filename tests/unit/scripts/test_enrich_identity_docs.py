# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/enrich_identity_docs.py.

The script tells a reader which of an id and a name to give. Every claim it
makes has to come from the module: the "one of these is required" clause from
``required_one_of``, and the "the id wins" clause from the lookup helper's own
negation. These tests pin both, and pin what the script refuses to touch.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "enrich_identity_docs.py"


def _load_script():
    scripts = str(SCRIPT_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("enrich_identity_docs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def identity_docs():
    return _load_script()


def module_source(required_one_of='[("widget_id", "name")]', lookup=None, name_doc="Widget name.",
                  id_doc="Existing widget ID."):
    """A module in the collection's shape, with a configurable lookup helper."""
    lookup = lookup if lookup is not None else (
        '    matches = [item for item in items\n'
        '               if (widget_id and item["WidgetId"] == widget_id)\n'
        '               or (not widget_id and item["WidgetName"] == name)]\n'
        '    return matches\n')
    return (
        "DOCUMENTATION = r'''\n"
        "module: demo\n"
        "options:\n"
        "  widget_id:\n"
        "    description:\n"
        "      - %s\n"
        "    type: str\n"
        "  name:\n"
        "    description:\n"
        "      - %s\n"
        "    type: str\n"
        "  state:\n"
        "    description: Desired state.\n"
        "    type: str\n"
        "    choices: [present, absent]\n"
        "'''\n"
        "RETURN = r'''widget:\n"
        "  description: The widget.\n"
        "  type: dict\n"
        "'''\n"
        "def find(module, client, models, widget_id, name):\n"
        "%s"
        "def run_module():\n"
        "    module = TencentCloudModule(argument_spec={}, required_one_of=%s)\n"
        "    p = module.params\n"
        # The real shape: run_module hands the two options to the lookup
        # helper, which is what makes the bare ``not widget_id`` in its body a
        # statement about the option rather than about some local.
        "    current = find(module, client, models, p[\"widget_id\"], p[\"name\"])\n"
        % (id_doc, name_doc, lookup, required_one_of))


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_identity_docs_pass(identity_docs, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["enrich_identity_docs.py", "--check"])
    assert identity_docs.main() == 0


def test_no_core_pair_is_still_thin(identity_docs):
    assert identity_docs.candidates() == []


# --------------------------------------------------------------------------
# reading the pair out of the module
# --------------------------------------------------------------------------

def test_pair_is_read_from_required_one_of(identity_docs):
    assert identity_docs.identity_groups(module_source()) == [("widget_id", "name")]


def test_a_three_member_group_is_left_alone(identity_docs):
    """The sentence is about an id and a name; a third option changes it."""
    source = module_source('[("widget_id", "name", "arn")]')
    assert identity_docs.identity_groups(source) == []


def test_a_group_with_no_id_is_left_alone(identity_docs):
    assert identity_docs.identity_groups(module_source('[("name", "arn")]')) == []


def test_a_group_whose_id_is_required_is_left_alone(identity_docs):
    """Saying "one of these is required" about an option that is required
    outright would contradict the documentation next to it."""
    source = module_source().replace(
        "  widget_id:\n    description:\n      - Existing widget ID.\n    type: str\n",
        "  widget_id:\n    description:\n      - Existing widget ID.\n    type: str\n    required: true\n")
    assert identity_docs.identity_groups(source) == []


def test_a_pair_that_is_already_described_is_left_alone(identity_docs):
    long_doc = ("The widget to manage, by id. Give either this or O(name); "
                "the module matches on the id when both are given.")
    assert identity_docs.enrich(module_source(id_doc=long_doc, name_doc=long_doc)) is None


# --------------------------------------------------------------------------
# the precedence clause
# --------------------------------------------------------------------------

def test_id_precedence_is_read_from_the_negation(identity_docs):
    assert identity_docs.id_precedence(module_source(), "widget_id")


def test_no_negation_means_no_precedence_claim(identity_docs):
    """Without the fallback in the code there is nothing to say about which
    one wins, so the sentence stops after the half the spec proves."""
    lookup = '    return [item for item in items if item["WidgetId"] == widget_id]\n'
    source = module_source(lookup=lookup)
    assert not identity_docs.id_precedence(source, "widget_id")
    new_source = identity_docs.enrich(source)
    body = identity_docs.DOC_RE.search(new_source).group("body")
    assert "one of this or O(name) is required." in body
    assert "matches on the id" not in body


def test_both_sides_of_the_pair_get_a_sentence(identity_docs):
    new_source = identity_docs.enrich(module_source())
    body = identity_docs.DOC_RE.search(new_source).group("body")
    identifier = identity_docs.option_span(body, "widget_id")
    name = identity_docs.option_span(body, "name")
    # The value is wrapped over several YAML lines; the sentence is what
    # matters, so collapse the whitespace before asserting on it.
    identifier_text = " ".join(" ".join(
        body.split("\n")[identifier[0]:identifier[1]]).split())
    name_text = " ".join(" ".join(body.split("\n")[name[0]:name[1]]).split())
    assert "one of this or O(name) is required" in identifier_text
    assert "the module matches on the id when it is given" in identifier_text
    assert "one of this or O(widget_id) is required" in name_text
    assert "the name is only used when O(widget_id) is not given" in name_text


def test_the_noun_comes_from_the_return_key(identity_docs):
    new_source = identity_docs.enrich(module_source())
    assert "Identifies the widget to manage" in new_source


# --------------------------------------------------------------------------
# what it leaves untouched
# --------------------------------------------------------------------------

def test_only_the_thin_member_is_rewritten(identity_docs):
    """A description that already explains itself is not improved by this
    sentence, so the pair is written around it."""
    long_doc = "Name of the widget. Immutable after creation, and used as the display label."
    new_source = identity_docs.enrich(module_source(name_doc=long_doc))
    body = identity_docs.DOC_RE.search(new_source).group("body")
    assert long_doc in body
    assert "one of this or O(name) is required, and the module matches on the id" in body


def test_the_rest_of_the_option_is_kept(identity_docs):
    new_source = identity_docs.enrich(module_source())
    body = identity_docs.DOC_RE.search(new_source).group("body")
    assert "      - Widget name.\n" not in body
    assert "    type: str\n" in body


def test_enrichment_is_idempotent(identity_docs):
    once = identity_docs.enrich(module_source())
    # The generator owns the sentence it wrote, so a second pass returns the
    # same text rather than None; that is what candidates() compares.
    assert identity_docs.enrich(once) == once
