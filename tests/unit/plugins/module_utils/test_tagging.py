"""Unit tests for tag conversion and comparison."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import tagging


class FakeSdkTag(object):
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


class FakeModels(object):
    class Tag(object):
        def __init__(self):
            self.Key = None
            self.Value = None


def test_normalize_tags_from_dict_sorted():
    assert tagging.normalize_tags({"b": "2", "a": "1"}) == {"a": "1", "b": "2"}


def test_normalize_tags_from_list_of_dicts():
    assert tagging.normalize_tags([{"key": "b", "value": "2"}, {"key": "a", "value": "1"}]) == {
        "a": "1",
        "b": "2",
    }


def test_normalize_tags_none_and_empty():
    assert tagging.normalize_tags(None) == {}
    assert tagging.normalize_tags({}) == {}


def test_normalize_tags_skips_empty_key():
    assert tagging.normalize_tags([{"key": "", "value": "x"}, {"key": "a", "value": "1"}]) == {"a": "1"}


def test_tags_from_sdk():
    sdk = [FakeSdkTag("env", "prod"), FakeSdkTag("tier", "web")]
    assert tagging.tags_from_sdk(sdk) == {"env": "prod", "tier": "web"}


def test_tags_from_sdk_empty_and_none():
    assert tagging.tags_from_sdk(None) == {}
    assert tagging.tags_from_sdk([]) == {}


def test_tags_from_sdk_accepts_dict_items():
    """Serialized dicts (not SDK objects) must be accepted too."""
    sdk = [
        {"Key": "env", "Value": "prod"},
        {"Key": "", "Value": "empty-key"},
        {"Value": "no-key"},
    ]
    assert tagging.tags_from_sdk(sdk) == {"env": "prod"}


def test_build_sdk_tags():
    sdk_tags = tagging.build_sdk_tags(FakeModels, {"a": "1", "b": "2"})
    assert [(t.Key, t.Value) for t in sdk_tags] == [("a", "1"), ("b", "2")]


def test_build_sdk_tags_empty():
    assert tagging.build_sdk_tags(FakeModels, {}) is None
    assert tagging.build_sdk_tags(FakeModels, None) is None


def test_compare_tags_equal():
    equal, to_add, to_remove = tagging.compare_tags({"env": "prod"}, [FakeSdkTag("env", "prod")])
    assert equal
    assert to_add == {}
    assert to_remove == []


def test_compare_tags_value_changed():
    equal, to_add, to_remove = tagging.compare_tags({"env": "staging"}, [FakeSdkTag("env", "prod")])
    assert not equal
    assert to_add == {"env": "staging"}
    assert to_remove == []


def test_compare_tags_extra_remote_tag_is_removed():
    equal, to_add, to_remove = tagging.compare_tags({"env": "prod"}, [FakeSdkTag("env", "prod"), FakeSdkTag("old", "x")])
    assert not equal
    assert to_remove == ["old"]


def test_compare_tags_missing_key_is_added():
    equal, to_add, to_remove = tagging.compare_tags({"env": "prod", "new": "1"}, [FakeSdkTag("env", "prod")])
    assert not equal
    assert to_add == {"new": "1"}


def test_merge_tags_later_source_wins():
    assert tagging.merge_tags({"env": "staging", "a": "1"}, {"env": "production"}) == {"a": "1", "env": "production"}


def test_merge_tags_single_source_and_no_source():
    assert tagging.merge_tags({"b": "2", "a": "1"}) == {"a": "1", "b": "2"}
    assert tagging.merge_tags() == {}


def test_merge_tags_sorts_by_key():
    assert list(tagging.merge_tags({"b": "2", "a": "1", "C": "3"})) == ["C", "a", "b"]


def test_merge_tags_accepts_one_api_shaped_tag():
    """A ``{"Key": ..., "Value": ...}`` mapping is one tag, not two."""
    assert tagging.merge_tags({"Key": "env", "Value": "prod"}) == {"env": "prod"}


def test_merge_tags_accepts_one_lowercase_pair():
    assert tagging.merge_tags({"key": "env", "value": "prod"}) == {"env": "prod"}


def test_merge_tags_reads_a_mapping_with_extra_keys_as_a_tag_map():
    """Only the exact pair spellings are a single tag; anything else is a map."""
    assert tagging.merge_tags({"Key": "env", "Value": "prod", "extra": "x"}) == {
        "Key": "env",
        "Value": "prod",
        "extra": "x",
    }


def test_merge_tags_accepts_a_list_of_sdk_objects():
    assert tagging.merge_tags([FakeSdkTag("env", "prod"), FakeSdkTag("tier", "web")]) == {
        "env": "prod",
        "tier": "web",
    }


def test_merge_tags_accepts_a_list_of_api_shaped_dicts():
    assert tagging.merge_tags([{"Key": "env", "Value": "prod"}, {"Key": "tier", "Value": "web"}]) == {
        "env": "prod",
        "tier": "web",
    }


def test_merge_tags_accepts_a_list_of_lowercase_pairs():
    assert tagging.merge_tags([{"key": "env", "value": "prod"}]) == {"env": "prod"}


def test_merge_tags_flattens_nested_lists():
    sources = [{"a": "1"}, [[{"Key": "b", "Value": "2"}], [FakeSdkTag("c", "3")]]]
    assert tagging.merge_tags(sources) == {"a": "1", "b": "2", "c": "3"}


def test_merge_tags_treats_a_list_of_tag_maps_as_sources():
    assert tagging.merge_tags([{"a": "1"}, {"b": "2"}]) == {"a": "1", "b": "2"}


def test_merge_tags_skips_none_and_empty_sources():
    assert tagging.merge_tags(None, {}, [], (), "", {"a": "1"}, None) == {"a": "1"}


def test_merge_tags_drops_a_pair_with_an_empty_key():
    assert tagging.merge_tags({"Key": "", "Value": "orphan"}, {"a": "1"}) == {"a": "1"}


def test_merge_tags_drops_a_tag_object_without_a_key():
    assert tagging.merge_tags([FakeSdkTag(None, "orphan"), FakeSdkTag("a", "1")]) == {"a": "1"}


def test_merge_tags_does_not_mutate_its_sources():
    source = {"a": "1"}
    tagging.merge_tags(source, {"b": "2"})
    assert source == {"a": "1"}


def test_merge_tags_coerces_keys_and_values_to_strings():
    assert tagging.merge_tags({"1": 1, "flag": True}) == {"1": "1", "flag": "True"}


@pytest.mark.parametrize("source", ["oops", 1, 1.5, object()])
def test_merge_tags_rejects_an_unsupported_source(source):
    with pytest.raises(TypeError, match="unsupported tag source"):
        tagging.merge_tags(source)


def test_merge_tags_rejects_a_nested_unsupported_source():
    with pytest.raises(TypeError, match="unsupported tag source"):
        tagging.merge_tags([{"a": "1"}, "oops"])
