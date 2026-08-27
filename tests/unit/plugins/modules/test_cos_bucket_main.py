"""Main-path unit tests for the cos_bucket module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
FULL_NAME = "mybucket-{0}".format(APPID)


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404, request_id="req-fake"):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status
        self._request_id = request_id

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status

    def get_request_id(self):
        return self._request_id


class FakeCosClient(object):
    """In-memory stand-in for CosS3Client; write ops are MagicMock-wrapped."""

    def __init__(self, buckets=None, delete_error=None):
        # full_name -> {"location", "acl", "versioning", "tags"}
        self.buckets = dict(buckets or {})
        self.delete_error = delete_error
        self.create_bucket = MagicMock(side_effect=self._create_bucket)
        self.delete_bucket = MagicMock(side_effect=self._delete_bucket)
        self.put_bucket_acl = MagicMock(side_effect=self._put_bucket_acl)
        self.put_bucket_versioning = MagicMock(side_effect=self._put_bucket_versioning)
        self.put_bucket_tagging = MagicMock(side_effect=self._put_bucket_tagging)
        self.delete_bucket_tagging = MagicMock(side_effect=self._delete_bucket_tagging)

    def _create_bucket(self, Bucket, **kwargs):
        self.buckets[Bucket] = {
            "location": "ap-guangzhou",
            "acl": kwargs.get("ACL", "private"),
            "versioning": None,
            "tags": {},
        }

    def _delete_bucket(self, Bucket, **kwargs):
        if self.delete_error is not None:
            raise self.delete_error
        self.buckets.pop(Bucket, None)

    def _put_bucket_acl(self, Bucket, **kwargs):
        self.buckets[Bucket]["acl"] = kwargs["ACL"]

    def _put_bucket_versioning(self, Bucket, **kwargs):
        self.buckets[Bucket]["versioning"] = kwargs["Status"]

    def _put_bucket_tagging(self, Bucket, **kwargs):
        tags = kwargs["Tagging"]["TagSet"]["Tag"]
        self.buckets[Bucket]["tags"] = {t["Key"]: t["Value"] for t in tags}

    def _delete_bucket_tagging(self, Bucket, **kwargs):
        self.buckets[Bucket]["tags"] = {}

    def head_bucket(self, Bucket, **kwargs):
        if Bucket not in self.buckets:
            raise FakeCosError("NoSuchBucket")
        return {}

    def get_bucket_location(self, Bucket, **kwargs):
        return {"LocationConstraint": self.buckets[Bucket]["location"]}

    def get_bucket_acl(self, Bucket, **kwargs):
        return {"CannedACL": self.buckets[Bucket]["acl"]}

    def get_bucket_versioning(self, Bucket, **kwargs):
        status = self.buckets[Bucket].get("versioning")
        return {"Status": status} if status else {}

    def get_bucket_tagging(self, Bucket, **kwargs):
        tags = self.buckets[Bucket].get("tags") or {}
        if not tags:
            raise FakeCosError("NoSuchTagSet")
        return {"TagSet": {"Tag": [{"Key": k, "Value": v} for k, v in sorted(tags.items())]}}


def _bucket(acl="private", versioning=None, tags=None):
    return {"location": "ap-guangzhou", "acl": acl, "versioning": versioning, "tags": tags or {}}


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_create_reports_changed(client):
    module_args(state="present", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    assert result["bucket"]["full_name"] == FULL_NAME
    assert result["bucket"]["acl"] == "private"
    client.create_bucket.assert_called_once_with(Bucket=FULL_NAME, ACL="private")
    client.put_bucket_versioning.assert_not_called()
    client.put_bucket_tagging.assert_not_called()
    assert "diff" not in result


def test_create_with_versioning_and_tags(client):
    module_args(
        state="present", name="mybucket", appid=APPID,
        acl="public-read", versioning=True, tags={"env": "prod"},
    )
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.create_bucket.assert_called_once_with(Bucket=FULL_NAME, ACL="public-read")
    client.put_bucket_versioning.assert_called_once_with(Bucket=FULL_NAME, Status="Enabled")
    client.put_bucket_tagging.assert_called_once_with(
        Bucket=FULL_NAME,
        Tagging={"TagSet": {"Tag": [{"Key": "env", "Value": "prod"}]}},
    )
    assert result["bucket"]["versioning"] is True
    assert result["bucket"]["tags"] == {"env": "prod"}


def test_second_run_is_idempotent(client):
    client.buckets[FULL_NAME] = _bucket(tags={"env": "prod"})
    module_args(state="present", name="mybucket", appid=APPID, tags={"env": "prod"})
    result = run(cos_bucket.run_module)
    assert result["changed"] is False
    assert result["bucket"]["full_name"] == FULL_NAME
    client.create_bucket.assert_not_called()
    client.put_bucket_acl.assert_not_called()
    client.put_bucket_versioning.assert_not_called()
    client.put_bucket_tagging.assert_not_called()


def test_update_acl_only(client):
    client.buckets[FULL_NAME] = _bucket()
    module_args(state="present", name="mybucket", appid=APPID, acl="public-read")
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.put_bucket_acl.assert_called_once_with(Bucket=FULL_NAME, ACL="public-read")
    client.put_bucket_versioning.assert_not_called()
    client.put_bucket_tagging.assert_not_called()
    assert result["bucket"]["acl"] == "public-read"


def test_update_versioning(client):
    client.buckets[FULL_NAME] = _bucket()
    module_args(state="present", name="mybucket", appid=APPID, versioning=True)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.put_bucket_versioning.assert_called_once_with(Bucket=FULL_NAME, Status="Enabled")


def test_unmanaged_versioning_is_left_alone(client):
    client.buckets[FULL_NAME] = _bucket(versioning="Enabled")
    module_args(state="present", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is False
    client.put_bucket_versioning.assert_not_called()


def test_tag_reconciliation_removes_unlisted_tags(client):
    client.buckets[FULL_NAME] = _bucket(tags={"env": "prod", "old": "gone"})
    module_args(state="present", name="mybucket", appid=APPID, tags={"env": "prod"})
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.put_bucket_tagging.assert_called_once_with(
        Bucket=FULL_NAME,
        Tagging={"TagSet": {"Tag": [{"Key": "env", "Value": "prod"}]}},
    )


def test_clearing_all_tags_calls_delete_tagging(client):
    client.buckets[FULL_NAME] = _bucket(tags={"env": "prod"})
    module_args(state="present", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.delete_bucket_tagging.assert_called_once_with(Bucket=FULL_NAME)


def test_absent_deletes_existing_bucket(client):
    client.buckets[FULL_NAME] = _bucket()
    module_args(state="absent", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    assert result["bucket"] is None
    client.delete_bucket.assert_called_once_with(Bucket=FULL_NAME)
    assert client.buckets == {}


def test_absent_on_missing_bucket_is_unchanged(client):
    module_args(state="absent", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is False
    client.delete_bucket.assert_not_called()


def test_delete_not_found_is_idempotent_success(client):
    client.buckets[FULL_NAME] = _bucket()
    client.delete_error = FakeCosError("NoSuchBucket")
    module_args(state="absent", name="mybucket", appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True


def test_delete_other_error_fails(client):
    client.buckets[FULL_NAME] = _bucket()
    client.delete_error = FakeCosError("BucketNotEmpty", status=409)
    module_args(state="absent", name="mybucket", appid=APPID)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_bucket.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "BucketNotEmpty"
    assert payload["request_id"] == "req-fake"


def test_check_mode_create_makes_no_writes(client):
    module_args(
        state="present", name="mybucket", appid=APPID,
        _ansible_check_mode=True,
    )
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.create_bucket.assert_not_called()
    client.delete_bucket.assert_not_called()


def test_check_mode_update_makes_no_writes(client):
    client.buckets[FULL_NAME] = _bucket()
    module_args(
        state="present", name="mybucket", appid=APPID, acl="public-read",
        _ansible_check_mode=True,
    )
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["acl"] == "private"
    assert result["diff"]["after"]["acl"] == "public-read"
    client.put_bucket_acl.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(
        state="present", name="mybucket", appid=APPID,
        _ansible_diff=True,
    )
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "mybucket"


def test_appid_resolved_via_sts_when_not_given(client, monkeypatch):
    sts = SimpleNamespace(GetCallerIdentity=MagicMock(
        return_value=SimpleNamespace(AccountId=APPID),
    ))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: sts,
    )
    monkeypatch.setattr(cos, "_load_sts", lambda: (MagicMock(), SimpleNamespace(StsClient=object)))
    module_args(state="present", name="mybucket")
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.create_bucket.assert_called_once_with(Bucket=FULL_NAME, ACL="private")
    sts.GetCallerIdentity.assert_called_once()


def test_full_name_in_name_is_not_double_suffixed(client):
    module_args(state="present", name=FULL_NAME, appid=APPID)
    result = run(cos_bucket.run_module)
    assert result["changed"] is True
    client.create_bucket.assert_called_once_with(Bucket=FULL_NAME, ACL="private")
