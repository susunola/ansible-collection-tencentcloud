"""Main-path unit tests for the cos_object_info module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_object_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
FULL_NAME = "mybucket-{0}".format(APPID)


class FakeCosError(Exception):
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
    """In-memory stand-in for CosS3Client listing operations."""

    def __init__(self, objects=None):
        # key -> {"etag", "size", "last_modified", "storage_class"}
        self.objects = dict(objects or {})

    def list_objects(self, Bucket, Prefix=None, Marker=None, MaxKeys=1000, **kwargs):
        keys = sorted(self.objects)
        if Prefix:
            keys = [k for k in keys if k.startswith(Prefix)]
        if Marker:
            keys = [k for k in keys if k > Marker]
        page = keys[:MaxKeys]
        truncated = len(keys) > MaxKeys
        contents = [
            {
                "Key": key,
                "ETag": '"{0}"'.format(self.objects[key]["etag"]),
                "Size": self.objects[key]["size"],
                "LastModified": self.objects[key]["last_modified"],
                "StorageClass": self.objects[key].get("storage_class", "STANDARD"),
            }
            for key in page
        ]
        result = {
            "Contents": contents,
            "IsTruncated": "true" if truncated else "false",
            "Name": Bucket,
        }
        if truncated and page:
            result["NextMarker"] = page[-1]
        return result


def _obj(etag="abc", size=10, last_modified="2026-08-31T12:00:00.000Z", storage_class="STANDARD"):
    return {"etag": etag, "size": size, "last_modified": last_modified, "storage_class": storage_class}


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_lists_all_objects(client):
    client.objects = {
        "a.txt": _obj(etag="e1"),
        "b.txt": _obj(etag="e2"),
        "images/c.png": _obj(etag="e3"),
    }
    module_args(bucket="mybucket", appid=APPID)
    result = run(cos_object_info.run_module)
    assert result["changed"] is False
    assert result["key_count"] == 3
    assert result["is_truncated"] is False
    keys = [o["key"] for o in result["objects"]]
    assert keys == ["a.txt", "b.txt", "images/c.png"]
    assert result["objects"][0]["etag"] == "e1"
    assert result["objects"][0]["storage_class"] == "STANDARD"


def test_prefix_filters_objects(client):
    client.objects = {
        "a.txt": _obj(),
        "images/c.png": _obj(),
        "images/d.png": _obj(),
    }
    module_args(bucket="mybucket", appid=APPID, prefix="images/")
    result = run(cos_object_info.run_module)
    assert result["key_count"] == 2
    assert all(o["key"].startswith("images/") for o in result["objects"])


def test_max_keys_truncates(client):
    client.objects = {
        "a.txt": _obj(),
        "b.txt": _obj(),
        "c.txt": _obj(),
        "d.txt": _obj(),
    }
    module_args(bucket="mybucket", appid=APPID, max_keys=2)
    result = run(cos_object_info.run_module)
    assert result["key_count"] == 2
    assert result["is_truncated"] is True
    assert result["next_marker"] == "b.txt"


def test_marker_resumes_listing(client):
    client.objects = {
        "a.txt": _obj(),
        "b.txt": _obj(),
        "c.txt": _obj(),
        "d.txt": _obj(),
    }
    module_args(bucket="mybucket", appid=APPID, max_keys=2, marker="b.txt")
    result = run(cos_object_info.run_module)
    keys = [o["key"] for o in result["objects"]]
    assert keys == ["c.txt", "d.txt"]


def test_empty_bucket(client):
    module_args(bucket="mybucket", appid=APPID)
    result = run(cos_object_info.run_module)
    assert result["changed"] is False
    assert result["objects"] == []
    assert result["key_count"] == 0


def test_bucket_resolution_appends_appid(client, monkeypatch):
    client.objects = {"a.txt": _obj()}
    sts_resolved = []
    monkeypatch.setattr(
        cos, "resolve_appid", lambda module: sts_resolved.append(1) or APPID
    )
    module_args(bucket="mybucket")
    run(cos_object_info.run_module)
    assert sts_resolved == [1]


def test_sdk_error_fails(client, monkeypatch):
    def boom(client, bucket, prefix=None, marker=None, max_keys=1000):
        raise FakeCosError("AccessDenied", status=403)

    monkeypatch.setattr(cos, "list_objects", boom)
    module_args(bucket="mybucket", appid=APPID)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object_info.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-fake"


def test_check_mode_is_read_only(client):
    client.objects = {"a.txt": _obj()}
    module_args(
        bucket="mybucket", appid=APPID,
        _ansible_check_mode=True,
    )
    result = run(cos_object_info.run_module)
    assert result["changed"] is False
    assert result["key_count"] == 1
