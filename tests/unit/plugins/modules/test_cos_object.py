"""Unit tests for the cos_object module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import hashlib

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules.cos_object import (
    download_matches,
    head_object,
    local_md5,
    object_matches,
)


class FakeCosError(Exception):
    def __init__(self, code, status=404):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status


class FakeClient(object):
    def __init__(self, head=None, exc=None):
        self.head = head
        self.exc = exc

    def head_object(self, Bucket, Key):
        if self.exc:
            raise self.exc
        return self.head


CONTENT = b"hello cos object"
CONTENT_MD5 = hashlib.md5(CONTENT).hexdigest()


@pytest.fixture
def src(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(CONTENT)
    return str(path)


def _head(size, etag):
    return {"Content-Length": str(size), "ETag": etag}


def test_local_md5(src):
    assert local_md5(src) == CONTENT_MD5


def test_object_matches_size_and_etag(src):
    assert object_matches(_head(len(CONTENT), '"%s"' % CONTENT_MD5), src) is True


def test_object_matches_rejects_size_drift(src):
    assert object_matches(_head(len(CONTENT) + 1, '"%s"' % CONTENT_MD5), src) is False


def test_object_matches_rejects_hash_drift(src):
    assert object_matches(_head(len(CONTENT), '"0" * 32'), src) is False


def test_object_matches_multipart_etag_compares_size_only(src):
    # Multipart ETags carry a -N suffix and are not plain MD5s.
    assert object_matches(_head(len(CONTENT), '"abcdef1234567890-3"'), src) is True
    assert object_matches(_head(len(CONTENT) + 1, '"abcdef1234567890-3"'), src) is False


def test_object_matches_none_head(src):
    assert object_matches(None, src) is False


def test_download_matches_requires_existing_dest(src):
    assert download_matches(_head(len(CONTENT), '"%s"' % CONTENT_MD5), src) is True
    assert download_matches(_head(len(CONTENT), '"%s"' % CONTENT_MD5), src + ".missing") is False


def test_head_object_returns_none_on_404():
    client = FakeClient(exc=FakeCosError("NoSuchKey"))
    assert head_object(client, "bucket-123", "k") is None


def test_head_object_raises_other_errors():
    client = FakeClient(exc=FakeCosError("AccessDenied", status=403))
    with pytest.raises(FakeCosError):
        head_object(client, "bucket-123", "k")


def test_head_object_returns_metadata():
    head = _head(5, '"etag"')
    client = FakeClient(head=head)
    assert head_object(client, "bucket-123", "k") is head
