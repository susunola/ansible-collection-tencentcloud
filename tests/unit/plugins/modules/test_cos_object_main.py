"""Main-path unit tests for the cos_object module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_object
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
FULL_NAME = "mybucket-{0}".format(APPID)
KEY = "images/logo.png"


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


class FakeBody(object):
    """Stand-in for a COS get_object body with get_stream_to_file."""

    def __init__(self, data):
        self._data = data

    def get_stream_to_file(self, path):
        with open(path, "wb") as handle:
            handle.write(self._data)

    def read(self):
        return self._data


class FakeCosClient(object):
    """In-memory stand-in for CosS3Client object operations."""

    def __init__(self, objects=None, delete_error=None):
        # key -> {"etag", "body", "metadata", "storage_class"}
        self.objects = dict(objects or {})
        self.delete_error = delete_error
        self.put_object = MagicMock(side_effect=self._put_object)
        self.delete_object = MagicMock(side_effect=self._delete_object)

    def _put_object(self, Bucket, Key, Body, Metadata=None, StorageClass="STANDARD", **kwargs):
        body = Body if isinstance(Body, bytes) else str(Body).encode("utf-8")
        self.objects[Key] = {
            "etag": '"{0}"'.format(cos_object.md5_of_bytes(body)),
            "body": body,
            "metadata": dict(Metadata or {}),
            "storage_class": StorageClass,
        }

    def _delete_object(self, Bucket, Key, **kwargs):
        if self.delete_error is not None:
            raise self.delete_error
        self.objects.pop(Key, None)

    def head_object(self, Bucket, Key, **kwargs):
        entry = self.objects.get(Key)
        if entry is None:
            raise FakeCosError("NoSuchKey")
        return {
            "ETag": entry["etag"],
            "Content-Length": str(len(entry["body"])),
            "StorageClass": entry.get("storage_class", "STANDARD"),
            "Metadata": dict(entry.get("metadata") or {}),
        }

    def get_object(self, Bucket, Key, **kwargs):
        entry = self.objects.get(Key)
        if entry is None:
            raise FakeCosError("NoSuchKey")
        return {"Body": FakeBody(entry["body"]), "ETag": entry["etag"]}


def _object(data=b"hello world", metadata=None, storage_class="STANDARD"):
    return {
        "etag": '"{0}"'.format(cos_object.md5_of_bytes(data)),
        "body": data,
        "metadata": metadata or {},
        "storage_class": storage_class,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_upload_new_object_reports_changed(client):
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, content="hello")
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()
    assert result["object"]["key"] == KEY
    assert result["object"]["bucket"] == FULL_NAME
    assert result["object"]["content_length"] == 5


def test_upload_from_src_file(client, tmp_path):
    src = tmp_path / "logo.png"
    src.write_bytes(b"png-bytes")
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, src=str(src))
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert client.objects[KEY]["body"] == b"png-bytes"


def test_second_upload_is_idempotent(client):
    client.objects[KEY] = _object()
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, content="hello world")
    result = run(cos_object.run_module)
    assert result["changed"] is False
    client.put_object.assert_not_called()


def test_changed_content_reuploads(client):
    client.objects[KEY] = _object(b"old content")
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, content="new content")
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()


def test_metadata_drift_reuploads_even_when_body_unchanged(client):
    client.objects[KEY] = _object(b"hello world", metadata={"x-cos-meta-owner": "old"})
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY,
        content="hello world", metadata={"owner": "new"},
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()
    assert result["object"]["metadata"] == {"x-cos-meta-owner": "new"}


def test_storage_class_drift_reuploads(client):
    client.objects[KEY] = _object(b"hello world", storage_class="STANDARD_IA")
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY,
        content="hello world", storage_class="ARCHIVE",
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()


def test_force_reuploads_even_when_matching(client):
    client.objects[KEY] = _object()
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY,
        content="hello world", force=True,
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()


def test_download_creates_local_file(client, tmp_path):
    client.objects[KEY] = _object(b"hello world")
    dest = tmp_path / "out.txt"
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, dest=str(dest))
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert dest.read_bytes() == b"hello world"


def test_download_idempotent_when_local_matches(client, tmp_path):
    client.objects[KEY] = _object(b"hello world")
    dest = tmp_path / "out.txt"
    dest.write_bytes(b"hello world")
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, dest=str(dest))
    result = run(cos_object.run_module)
    assert result["changed"] is False


def test_download_force_overwrites_matching_local(client, tmp_path):
    client.objects[KEY] = _object(b"hello world")
    dest = tmp_path / "out.txt"
    dest.write_bytes(b"hello world")
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY,
        dest=str(dest), force=True,
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True


def test_download_missing_object_fails(client, tmp_path):
    dest = tmp_path / "out.txt"
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY, dest=str(dest))
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object.run_module)
    assert "does not exist" in excinfo.value.args[0]["msg"]


def test_download_without_dest_fails(client):
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object.run_module)
    assert "dest is required" in excinfo.value.args[0]["msg"]


def test_absent_deletes_existing_object(client):
    client.objects[KEY] = _object()
    module_args(state="absent", bucket="mybucket", appid=APPID, object=KEY)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert result["object"] is None
    client.delete_object.assert_called_once_with(Bucket=FULL_NAME, Key=KEY)
    assert client.objects == {}


def test_absent_on_missing_object_is_unchanged(client):
    module_args(state="absent", bucket="mybucket", appid=APPID, object=KEY)
    result = run(cos_object.run_module)
    assert result["changed"] is False
    client.delete_object.assert_not_called()


def test_absent_delete_error_fails(client):
    client.objects[KEY] = _object()
    client.delete_error = FakeCosError("AccessDenied", status=403)
    module_args(state="absent", bucket="mybucket", appid=APPID, object=KEY)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-fake"


def test_check_mode_upload_makes_no_writes(client):
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY, content="hello",
        _ansible_check_mode=True,
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.put_object.assert_not_called()
    client.delete_object.assert_not_called()


def test_check_mode_delete_makes_no_writes(client):
    client.objects[KEY] = _object()
    module_args(
        state="absent", bucket="mybucket", appid=APPID, object=KEY,
        _ansible_check_mode=True,
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.delete_object.assert_not_called()


def test_diff_mode_upload_includes_diff(client):
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY, content="hello",
        _ansible_diff=True,
    )
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["key"] == KEY


def test_src_and_content_mutually_exclusive(client, tmp_path):
    src = tmp_path / "f.txt"
    src.write_text("x")
    module_args(
        state="present", bucket="mybucket", appid=APPID, object=KEY,
        src=str(src), content="y",
    )
    with pytest.raises(AnsibleFailJson):
        run(cos_object.run_module)


def test_upload_uses_full_bucket_name(client):
    module_args(state="present", bucket=FULL_NAME, appid=APPID, object=KEY, content="hi")
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.put_object.assert_called_once()
    assert client.put_object.call_args.kwargs["Bucket"] == FULL_NAME


def test_etag_value_strips_quotes():
    assert cos_object.etag_value('"abc123"') == "abc123"
    assert cos_object.etag_value("abc123") == "abc123"
    assert cos_object.etag_value(None) is None


def test_normalize_metadata_prefixes_keys():
    assert cos_object.normalize_metadata({"Owner": "ops", "Team": "x"}) == {
        "x-cos-meta-Owner": "ops",
        "x-cos-meta-Team": "x",
    }


def test_presign_get_returns_url_without_writes(client):
    client.get_presigned_url = MagicMock(
        return_value="https://{0}.cos.ap-guangzhou.myqcloud.com/{1}?signed".format(FULL_NAME, KEY)
    )
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY,
                presign=True, expires=600)
    result = run(cos_object.run_module)
    assert result["changed"] is False
    assert "signed" in result["url"]
    client.get_presigned_url.assert_called_once_with(
        Bucket=FULL_NAME, Key=KEY, Method="GET", Expired=600,
    )
    client.put_object.assert_not_called()
    client.delete_object.assert_not_called()


def test_presign_put_method(client):
    client.get_presigned_url = MagicMock(return_value="https://example/upload")
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY,
                presign=True, method="PUT")
    result = run(cos_object.run_module)
    assert result["changed"] is False
    assert client.get_presigned_url.call_args.kwargs["Method"] == "PUT"


def test_presign_rejected_when_absent(client):
    module_args(state="absent", bucket="mybucket", appid=APPID, object=KEY, presign=True)
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object.run_module)
    assert "state=present" in excinfo.value.args[0]["msg"]


def test_method_rejected_without_presign(client):
    module_args(state="present", bucket="mybucket", appid=APPID, object=KEY,
                content="hi", method="PUT")
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cos_object.run_module)
    assert "presign" in excinfo.value.args[0]["msg"]
    client.put_object.assert_not_called()
