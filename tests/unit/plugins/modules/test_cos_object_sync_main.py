"""Main-path unit tests for the cos_object_sync module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import os
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_object_sync
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
FULL_NAME = "mybucket-{0}".format(APPID)


def md5_hex(data):
    return hashlib.md5(data).hexdigest()


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
    """In-memory stand-in for CosS3Client object operations."""

    def __init__(self, objects=None, put_error=None):
        # key -> {"etag", "body"}
        self.objects = dict(objects or {})
        self.put_error = put_error
        self.put_object = MagicMock(side_effect=self._put_object)
        self.delete_object = MagicMock(side_effect=self._delete_object)

    def list_objects(self, Bucket, Prefix=None, Marker=None, MaxKeys=1000, **kwargs):
        keys = sorted(k for k in self.objects if k.startswith(Prefix or ""))
        if Marker:
            keys = [k for k in keys if k > Marker]
        page = keys[:MaxKeys]
        truncated = len(keys) > MaxKeys
        contents = [
            {
                "Key": key,
                "ETag": '"{0}"'.format(self.objects[key]["etag"]),
                "Size": len(self.objects[key]["body"]),
                "LastModified": "2026-08-31T12:00:00.000Z",
                "StorageClass": "STANDARD",
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

    def _put_object(self, Bucket, Key, Body, **kwargs):
        if self.put_error is not None:
            raise self.put_error
        body = Body if isinstance(Body, bytes) else str(Body).encode("utf-8")
        self.objects[Key] = {"etag": md5_hex(body), "body": body}

    def _delete_object(self, Bucket, Key, **kwargs):
        self.objects.pop(Key, None)


def write_tree(root, files):
    """Write ``{relative_path: bytes}`` under ``root`` on disk."""
    for rel, data in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_uploads_new_files(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa", "sub/b.txt": b"bbb"})
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path))
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert result["summary"] == {"uploaded": 2, "deleted": 0, "unchanged": 0, "skipped_remote": 0}
    assert sorted(result["uploaded"]) == ["a.txt", "sub/b.txt"]
    assert client.put_object.call_count == 2
    assert client.objects["a.txt"]["etag"] == md5_hex(b"aaa")
    assert client.objects["sub/b.txt"]["etag"] == md5_hex(b"bbb")


def test_skips_unchanged_files(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {"a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"}}
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path))
    result = run(cos_object_sync.run_module)
    assert result["changed"] is False
    assert result["summary"]["unchanged"] == 1
    client.put_object.assert_not_called()


def test_reuploads_changed_content(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"new"})
    client.objects = {"a.txt": {"etag": md5_hex(b"old"), "body": b"old"}}
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path))
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert result["uploaded"] == ["a.txt"]
    assert client.objects["a.txt"]["etag"] == md5_hex(b"new")


def test_force_reuploads_even_when_unchanged(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {"a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"}}
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path), force=True)
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert result["summary"]["uploaded"] == 1
    assert result["summary"]["unchanged"] == 0


def test_delete_removes_extraneous_remote(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {
        "a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"},
        "stale.txt": {"etag": "x", "body": b"x"},
    }
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path), delete=True)
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert result["deleted"] == ["stale.txt"]
    assert "stale.txt" not in client.objects


def test_without_delete_skips_extraneous_remote(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {
        "a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"},
        "stale.txt": {"etag": "x", "body": b"x"},
    }
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path))
    result = run(cos_object_sync.run_module)
    assert result["changed"] is False
    assert result["summary"]["skipped_remote"] == 1
    client.delete_object.assert_not_called()


def test_prefix_constructs_keys(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path), prefix="assets/")
    result = run(cos_object_sync.run_module)
    assert result["uploaded"] == ["assets/a.txt"]
    assert "assets/a.txt" in client.objects


def test_delete_is_scoped_to_prefix(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {
        "assets/a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"},
        "other/keep.txt": {"etag": "x", "body": b"x"},
    }
    module_args(
        bucket="mybucket", appid=APPID,
        src=str(tmp_path), prefix="assets/", delete=True,
    )
    result = run(cos_object_sync.run_module)
    assert result["changed"] is False
    assert "other/keep.txt" in client.objects


def test_empty_local_tree_with_delete_empties_prefix(client, tmp_path):
    client.objects = {
        "a.txt": {"etag": "x", "body": b"x"},
        "b.txt": {"etag": "y", "body": b"y"},
    }
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path), delete=True)
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert sorted(result["deleted"]) == ["a.txt", "b.txt"]
    assert client.objects == {}


def test_check_mode_reports_without_writes(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {"stale.txt": {"etag": "x", "body": b"x"}}
    module_args(
        bucket="mybucket", appid=APPID,
        src=str(tmp_path), delete=True, _ansible_check_mode=True,
    )
    result = run(cos_object_sync.run_module)
    assert result["changed"] is True
    assert "Would upload 1, delete 1" in result["msg"]
    assert result["summary"] == {"uploaded": 1, "deleted": 1, "unchanged": 0, "skipped_remote": 0}
    client.put_object.assert_not_called()
    client.delete_object.assert_not_called()


def test_check_mode_unchanged_reports_false(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.objects = {"a.txt": {"etag": md5_hex(b"aaa"), "body": b"aaa"}}
    module_args(
        bucket="mybucket", appid=APPID,
        src=str(tmp_path), _ansible_check_mode=True,
    )
    result = run(cos_object_sync.run_module)
    assert result["changed"] is False


def test_src_missing_fails(client, tmp_path):
    missing = os.path.join(str(tmp_path), "nope")
    module_args(bucket="mybucket", appid=APPID, src=missing)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object_sync.run_module)
    assert "is not a directory" in excinfo.value.args[0]["msg"]


def test_put_error_fails(client, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    client.put_error = FakeCosError("AccessDenied", status=403)
    module_args(bucket="mybucket", appid=APPID, src=str(tmp_path))
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object_sync.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-fake"


def test_resolves_appid_via_sts(client, monkeypatch, tmp_path):
    write_tree(str(tmp_path), {"a.txt": b"aaa"})
    sts_resolved = []
    monkeypatch.setattr(
        cos, "resolve_appid", lambda module: sts_resolved.append(1) or APPID
    )
    module_args(bucket="mybucket", src=str(tmp_path))
    result = run(cos_object_sync.run_module)
    assert sts_resolved == [1]
    assert result["uploaded"] == ["a.txt"]
