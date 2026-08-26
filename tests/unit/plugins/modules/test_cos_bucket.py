"""Unit tests for the cos_bucket module helper functions."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

from ansible_collections.tencentcloud.cloud.plugins.modules import cos_bucket


def test_normalize_tags_stringifies_values():
    assert cos_bucket.normalize_tags({"env": "prod", "cost": 42}) == {"env": "prod", "cost": "42"}
    assert cos_bucket.normalize_tags(None) == {}


def test_desired_state_omits_versioning_when_unmanaged():
    desired = cos_bucket.desired_state("b", "private", None, {})
    assert "versioning" not in desired
    desired = cos_bucket.desired_state("b", "private", True, {})
    assert desired["versioning"] is True


def test_bucket_changes_detects_each_attribute():
    current = {"acl": "private", "versioning": False, "tags": {"env": "dev"}}
    assert cos_bucket.bucket_changes(current, "private", None, {"env": "dev"}) == []
    assert cos_bucket.bucket_changes(current, "public-read", None, {"env": "dev"}) == ["acl"]
    assert cos_bucket.bucket_changes(current, "private", True, {"env": "dev"}) == ["versioning"]
    assert cos_bucket.bucket_changes(current, "private", None, {"env": "prod"}) == ["tags"]


def test_bucket_changes_ignores_versioning_when_unmanaged():
    current = {"acl": "private", "versioning": True, "tags": {}}
    assert cos_bucket.bucket_changes(current, "private", None, {}) == []


def test_set_bucket_acl_passes_canned_acl_header():
    client = MagicMock()
    cos_bucket.set_bucket_acl(client, "b-1", "public-read")
    client.put_bucket_acl.assert_called_once_with(Bucket="b-1", ACL="public-read")


def test_set_bucket_versioning_maps_bool_to_status():
    client = MagicMock()
    cos_bucket.set_bucket_versioning(client, "b-1", True)
    client.put_bucket_versioning.assert_called_once_with(Bucket="b-1", Status="Enabled")
    client.reset_mock()
    cos_bucket.set_bucket_versioning(client, "b-1", False)
    client.put_bucket_versioning.assert_called_once_with(Bucket="b-1", Status="Suspended")


def test_set_bucket_tags_builds_sorted_tagging_payload():
    client = MagicMock()
    cos_bucket.set_bucket_tags(client, "b-1", {"zeta": "1", "alpha": "2"})
    client.put_bucket_tagging.assert_called_once_with(
        Bucket="b-1",
        Tagging={"TagSet": {"Tag": [{"Key": "alpha", "Value": "2"}, {"Key": "zeta", "Value": "1"}]}},
    )


def test_set_bucket_tags_empty_clears_tags():
    client = MagicMock()
    cos_bucket.set_bucket_tags(client, "b-1", {})
    client.delete_bucket_tagging.assert_called_once_with(Bucket="b-1")
    client.put_bucket_tagging.assert_not_called()


def test_create_bucket_passes_canned_acl_header():
    client = MagicMock()
    cos_bucket.create_bucket(client, "b-1", "private")
    client.create_bucket.assert_called_once_with(Bucket="b-1", ACL="private")
