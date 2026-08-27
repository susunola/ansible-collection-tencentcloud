"""Unit tests for the cos_bucket_info module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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
    def __init__(self, buckets=None):
        self.buckets = dict(buckets or {})

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

    def list_buckets(self, **kwargs):
        self.list_region = kwargs.get("Region")
        return {
            "Buckets": {
                "Bucket": [
                    {"Name": name, "Location": data["location"], "CreationDate": "2026-08-26T00:00:00Z"}
                    for name, data in sorted(self.buckets.items())
                ]
            }
        }


def _bucket(location="ap-guangzhou", acl="private", versioning=None, tags=None):
    return {"location": location, "acl": acl, "versioning": versioning, "tags": tags or {}}


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient({
        "mybucket-1300000000": _bucket(versioning="Enabled", tags={"env": "prod"}),
        "other-1300000000": _bucket(location="ap-shanghai"),
    })
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_describe_single_bucket(client):
    module_args(name="mybucket", appid="1300000000")
    result = run(cos_bucket_info.run_module)
    assert result["changed"] is False
    assert len(result["buckets"]) == 1
    bucket = result["buckets"][0]
    assert bucket["full_name"] == "mybucket-1300000000"
    assert bucket["location"] == "ap-guangzhou"
    assert bucket["acl"] == "private"
    assert bucket["versioning"] is True
    assert bucket["tags"] == {"env": "prod"}


def test_describe_missing_bucket_fails(client):
    module_args(name="missing", appid="1300000000")
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_bucket_info.run_module)
    assert "missing-1300000000" in excinfo.value.args[0]["msg"]


def test_list_all_buckets(client):
    module_args()
    result = run(cos_bucket_info.run_module)
    assert result["changed"] is False
    assert [b["name"] for b in result["buckets"]] == ["mybucket-1300000000", "other-1300000000"]
    assert client.list_region == "ap-guangzhou"


def test_sdk_error_maps_to_fail_json(client, monkeypatch):
    def broken(**kwargs):
        raise FakeCosError("AccessDenied", status=403)

    monkeypatch.setattr(client, "list_buckets", broken)
    module_args()
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_bucket_info.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-fake"
