"""Unit tests for tag conversion and comparison."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
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
