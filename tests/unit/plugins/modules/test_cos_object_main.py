"""Main-path unit tests for the cos_object module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
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
CONTENT = b"hello cos object"
CONTENT_MD5 = hashlib.md5(CONTENT).hexdigest()


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status


class FakeCosClient(object):
    """In-memory object store stand-in for CosS3Client."""

    def __init__(self, objects=None):
        # key -> bytes
        self.objects = dict(objects or {})
        self.upload_file = MagicMock(side_effect=self._upload_file)
        self.download_file = MagicMock(side_effect=self._download_file)
        self.delete_object = MagicMock(side_effect=self._delete_object)
        self.get_presigned_url = MagicMock(side_effect=self._presign)

    def _upload_file(self, Bucket, Key, LocalFilePath, **kwargs):
        with open(LocalFilePath, "rb") as handle:
            self.objects[Key] = handle.read()
        return {"ETag": '"%s"' % hashlib.md5(self.objects[Key]).hexdigest()}

    def _download_file(self, Bucket, Key, DestFilePath, **kwargs):
        if Key not in self.objects:
            raise FakeCosError("NoSuchKey")
        with open(DestFilePath, "wb") as handle:
            handle.write(self.objects[Key])

    def _delete_object(self, Bucket, Key, **kwargs):
        self.objects.pop(Key, None)

    def _presign(self, Bucket, Key, Method, Expired, **kwargs):
        return "https://{0}.cos.ap-guangzhou.myqcloud.com/{1}?q-sign-algorithm=fake&method={2}&expired={3}".format(
            Bucket, Key, Method, Expired
        )

    def head_object(self, Bucket, Key, **kwargs):
        if Key not in self.objects:
            raise FakeCosError("NoSuchKey")
        data = self.objects[Key]
        return {"Content-Length": str(len(data)), "ETag": '"%s"' % hashlib.md5(data).hexdigest()}


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


@pytest.fixture
def src(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)
    return str(path)


def test_upload_new_object_reports_changed(client, src):
    module_args(bucket="mybucket", appid=APPID, key="site/index.html", src=src)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert result["bucket"] == FULL_NAME
    assert result["etag"] == '"%s"' % CONTENT_MD5
    client.upload_file.assert_called_once()
    assert client.objects["site/index.html"] == CONTENT


def test_upload_identical_object_is_idempotent(client, src):
    client.objects["site/index.html"] = CONTENT
    module_args(bucket="mybucket", appid=APPID, key="site/index.html", src=src)
    result = run(cos_object.run_module)
    assert result["changed"] is False
    client.upload_file.assert_not_called()


def test_upload_drifted_object_overwrites(client, src):
    client.objects["site/index.html"] = b"stale"
    module_args(bucket="mybucket", appid=APPID, key="site/index.html", src=src)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.upload_file.assert_called_once()
    assert client.objects["site/index.html"] == CONTENT


def test_upload_requires_existing_src(client, tmp_path):
    module_args(bucket="mybucket", appid=APPID, key="k", src=str(tmp_path / "missing"))
    try:
        run(cos_object.run_module)
        raise AssertionError("expected AnsibleFailJson")
    except AnsibleFailJson as exc:
        assert "src does not exist" in exc.args[0]["msg"]


def test_absent_deletes_existing_object(client):
    client.objects["k"] = CONTENT
    module_args(bucket="mybucket", appid=APPID, key="k", state="absent")
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.delete_object.assert_called_once_with(Bucket=FULL_NAME, Key="k")
    assert client.objects == {}


def test_absent_on_missing_object_is_unchanged(client):
    module_args(bucket="mybucket", appid=APPID, key="k", state="absent")
    result = run(cos_object.run_module)
    assert result["changed"] is False
    client.delete_object.assert_not_called()


def test_download_fetches_object(client, tmp_path):
    client.objects["k"] = CONTENT
    dest = str(tmp_path / "out.txt")
    module_args(bucket="mybucket", appid=APPID, key="k", mode="download", dest=dest)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert result["dest"] == dest
    with open(dest, "rb") as handle:
        assert handle.read() == CONTENT


def test_download_is_idempotent_when_dest_matches(client, tmp_path):
    client.objects["k"] = CONTENT
    dest = tmp_path / "out.txt"
    dest.write_bytes(CONTENT)
    module_args(bucket="mybucket", appid=APPID, key="k", mode="download", dest=str(dest))
    result = run(cos_object.run_module)
    assert result["changed"] is False
    client.download_file.assert_not_called()


def test_download_fails_when_object_missing(client, tmp_path):
    module_args(bucket="mybucket", appid=APPID, key="k", mode="download", dest=str(tmp_path / "out"))
    try:
        run(cos_object.run_module)
        raise AssertionError("expected AnsibleFailJson")
    except AnsibleFailJson as exc:
        assert "does not exist" in exc.args[0]["msg"]


def test_download_requires_dest(client):
    module_args(bucket="mybucket", appid=APPID, key="k", mode="download")
    try:
        run(cos_object.run_module)
        raise AssertionError("expected AnsibleFailJson")
    except AnsibleFailJson as exc:
        assert "dest is required" in exc.args[0]["msg"]


def test_presign_returns_put_url_without_writes(client):
    module_args(bucket="mybucket", appid=APPID, key="k", mode="presign", expires=600)
    result = run(cos_object.run_module)
    assert result["changed"] is False
    assert "method=PUT" in result["url"]
    assert "expired=600" in result["url"]
    client.upload_file.assert_not_called()
    client.download_file.assert_not_called()
    client.delete_object.assert_not_called()


def test_absent_rejects_presign_mode(client):
    module_args(bucket="mybucket", appid=APPID, key="k", state="absent", mode="presign")
    try:
        run(cos_object.run_module)
        raise AssertionError("expected AnsibleFailJson")
    except AnsibleFailJson as exc:
        assert "mode=sync" in exc.args[0]["msg"]


def test_absent_rejects_download_mode(client):
    module_args(bucket="mybucket", appid=APPID, key="k", state="absent", mode="download", dest="/tmp/x")
    try:
        run(cos_object.run_module)
        raise AssertionError("expected AnsibleFailJson")
    except AnsibleFailJson as exc:
        assert "mode=sync" in exc.args[0]["msg"]


def test_check_mode_upload_makes_no_writes(client, src):
    module_args(bucket="mybucket", appid=APPID, key="k", src=src, _ansible_check_mode=True)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.upload_file.assert_not_called()
    assert client.objects == {}


def test_check_mode_absent_makes_no_writes(client):
    client.objects["k"] = CONTENT
    module_args(bucket="mybucket", appid=APPID, key="k", state="absent", _ansible_check_mode=True)
    result = run(cos_object.run_module)
    assert result["changed"] is True
    client.delete_object.assert_not_called()
    assert client.objects["k"] == CONTENT
