"""Unit tests for the tag_merge filter plugin.

The merging itself is tested against its implementation in
``tests/unit/plugins/module_utils/test_tagging.py``. What is tested here is the
part only the plugin can get wrong: the Jinja surface (name, argument order),
the error translation, and the claim that the filter adds no semantics of its
own.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
import yaml

from ansible.errors import AnsibleFilterError

from ansible_collections.susunola.tencentcloud.plugins.filter import tags as filter_mod
from ansible_collections.susunola.tencentcloud.plugins.filter.tags import (
    FilterModule,
    tag_merge,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils import tagging as tagging_mod
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import tags as plugin_tags

DOC = yaml.safe_load(filter_mod.DOCUMENTATION)


class FakeSdkTag(object):
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


def test_the_filter_module_exposes_exactly_tag_merge():
    assert FilterModule().filters() == {"tag_merge": tag_merge}


def test_the_filter_reads_tags_through_the_controller_side_shim():
    """The filter must not carry its own copy of the tag semantics."""
    assert filter_mod.merge_tags is plugin_tags.merge_tags
    assert plugin_tags.merge_tags is tagging_mod.merge_tags


def test_tag_merge_merges_sources_left_to_right():
    assert tag_merge({"env": "staging"}, {"env": "production", "tier": "web"}) == {
        "env": "production",
        "tier": "web",
    }


def test_tag_merge_accepts_the_shapes_a_playbook_produces():
    assert tag_merge([{"Key": "env", "Value": "prod"}], {"owner": "platform"}, None) == {
        "env": "prod",
        "owner": "platform",
    }


def test_tag_merge_accepts_a_list_of_sources_as_its_only_argument():
    assert tag_merge([{"a": "1"}, [FakeSdkTag("b", "2")]]) == {"a": "1", "b": "2"}


def test_tag_merge_returns_a_sorted_string_valued_mapping():
    assert tag_merge({"b": 2, "a": 1}) == {"a": "1", "b": "2"}


def test_tag_merge_rejects_an_unsupported_source_with_a_filter_error():
    with pytest.raises(AnsibleFilterError) as excinfo:
        tag_merge("oops")
    assert "tag_merge: unsupported tag source 'oops'" in str(excinfo.value)


def test_the_documentation_names_the_filter_it_documents():
    assert DOC["name"] == "tag_merge"
    assert DOC["name"] in FilterModule().filters()


def test_the_documentation_declares_the_positional_options_the_filter_accepts():
    """``tag_merge(*sources)`` is documented as ``_input`` plus ``_additional``."""
    assert DOC["positional"] == "_input, _additional"
    assert sorted(DOC["options"]) == ["_additional", "_input"]


def test_the_documentation_declares_a_version_added():
    version = DOC["version_added"]
    assert isinstance(version, str)
    assert version.count(".") == 2
