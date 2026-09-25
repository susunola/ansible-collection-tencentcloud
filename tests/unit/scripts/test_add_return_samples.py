# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for scripts/add_return_samples.py.

The script turns a module's own unit-test payload into the ``sample`` of its
``RETURN`` block, so the two things pinned here are the normalisation (what a
payload becomes) and the insertion (that nothing else in the file moves).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "add_return_samples.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("add_return_samples",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def samples():
    return _load_script()


class _Opaque(object):
    """Stands in for an object a test handed the module directly."""


def test_prune_drops_none_ansible_keys_and_opaque_objects(samples):
    payload = {"changed": True, "invocation": {"x": 1}, "Id": "i-1",
               "Missing": None, "Model": _Opaque(), "Nested": {"a": None, "b": 2}}
    assert samples.prune(payload) == {"Id": "i-1", "Nested": {"b": 2}}


def test_prune_keeps_the_json_scalars(samples):
    payload = {"s": "x", "i": 1, "f": 1.5, "b": False, "l": [1, None, "x"]}
    assert samples.prune(payload) == {"s": "x", "i": 1, "f": 1.5, "b": False,
                                      "l": [1, "x"]}


def test_sample_of_takes_the_first_list_element(samples):
    assert samples.sample_of([{"a": 1}, {"a": 2}]) == [{"a": 1}]
    assert samples.sample_of([]) is None
    assert samples.sample_of([_Opaque()]) is None


def test_choose_sample_is_deterministic_and_prefers_the_richest(samples):
    payloads = [{"k": {"a": 1}}, {"k": {"a": 1, "b": 2}}, {"other": 1}]
    assert samples.choose_sample(payloads, "k") == {"a": 1, "b": 2}
    assert samples.choose_sample(payloads, "other") == 1
    assert samples.choose_sample(payloads, "absent") is None


def test_render_sample_indents_sequences_and_inlines_scalars(samples):
    rendered = samples.render_sample({"a": [{"b": 1}]})
    assert rendered[0] == "  sample:"
    assert rendered[1].strip() == samples.SAMPLE_MARKER
    assert "      - b: 1" in rendered
    assert samples.render_sample(False) == ["  sample: false"]


def test_insert_sample_keeps_everything_else(samples):
    text = ('RETURN = r"""\n'
            'first:\n'
            '  description: One.\n'
            '  type: dict\n'
            'second:\n'
            '  description: Two.\n'
            '  type: str\n'
            '"""\n')
    result = samples.insert_sample(text, "first", {"a": 1})
    assert result.startswith('RETURN = r"""\nfirst:\n  description: One.\n'
                             '  type: dict\n  sample:')
    assert "second:\n  description: Two.\n  type: str\n" in result
    assert "  sample:\n    %s\n    a: 1\n" % samples.SAMPLE_MARKER in result


def test_insert_sample_handles_a_block_that_ends_on_the_last_field(samples):
    """``RETURN = r\"\"\"key:\\n  type: dict\"\"\"`` has no trailing newline."""
    text = 'RETURN = r"""key:\n  description: One.\n  type: dict"""\n'
    result = samples.insert_sample(text, "key", {"a": 1})
    assert result == (
        'RETURN = r"""key:\n  description: One.\n  type: dict\n'
        '  sample:\n    %s\n    a: 1\n"""\n' % samples.SAMPLE_MARKER)


def test_insert_sample_refuses_an_unknown_key(samples):
    text = 'RETURN = r"""\nkey:\n  type: dict\n"""\n'
    with pytest.raises(ValueError):
        samples.insert_sample(text, "absent", {"a": 1})


def test_generated_modules_are_owned_by_the_generator(samples):
    generated = samples.generated_modules()
    assert "alb_listener_info" in generated
    assert "alb_listener" not in generated


def test_documented_entries_reads_the_return_block(samples):
    entries = samples.documented_entries("alb_listener")
    assert "listener" in entries
    assert "sample" in entries["listener"]


def test_marker_distinguishes_captured_from_hand_written_samples(samples):
    """A curated sample may be richer than a unit test's fake response."""
    assert samples.SAMPLE_MARKER in samples.module_text("alb_listener")
    assert samples.SAMPLE_MARKER not in samples.module_text("vpc")


def test_is_subset_compares_shapes(samples):
    assert samples.is_subset({"a": 1}, {"a": 2, "b": 3})
    assert not samples.is_subset({"a": 1}, {"b": 2})
    assert not samples.is_subset({"a": {"b": 1}}, {"a": 2})
    assert samples.is_subset([{"a": 1}], [{"a": 1, "b": 2}])


def test_committed_samples_are_documented_and_marked(samples):
    """The batch this script wrote is visible to the gate that checks it."""
    marked = [name for name in ("alb_listener", "subnet", "vpc")
              if samples.marked_keys(name)]
    assert marked == ["alb_listener"]
    assert samples.marked_keys("vpc") == set()
