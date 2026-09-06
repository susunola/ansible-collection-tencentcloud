"""Main-path unit tests for the vod_class module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vod_class
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLASS_NAME = "marketing"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeVodClient(object):
    """In-memory stand-in for the VodClient class operations."""

    def __init__(self, classes=None):
        self.classes = list(classes or [])
        self.DescribeAllClass = MagicMock(side_effect=self._describe)
        self.CreateClass = MagicMock(side_effect=self._create)
        self.DeleteClass = MagicMock(side_effect=self._delete)

    def _describe(self, request):
        items = [FakeResource(c) for c in self.classes]
        return SimpleNamespace(ClassInfoSet=items)

    def _create(self, request):
        self.classes.append({
            "ClassId": 2222,
            "ClassName": request.ClassName,
            "ParentId": request.ParentId,
        })
        return SimpleNamespace(ClassId=2222)

    def _delete(self, request):
        self.classes = [c for c in self.classes if c["ClassId"] != request.ClassId]
        return SimpleNamespace()


def make_class(class_id=1111, name=CLASS_NAME, parent_id=-1):
    return {
        "ClassId": class_id,
        "ClassName": name,
        "ParentId": parent_id,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeVodClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        vod_class, "_load_vod",
        lambda: (FakeModels(), SimpleNamespace(VodClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_absent_noop_when_class_missing(client):
    module_args(class_name=CLASS_NAME, state="absent")
    result = run(vod_class.run_module)
    assert result["changed"] is False
    client.DeleteClass.assert_not_called()


def test_absent_deletes_existing_class(client):
    client.classes = [make_class()]
    module_args(class_name=CLASS_NAME, state="absent")
    result = run(vod_class.run_module)
    assert result["changed"] is True
    request = client.DeleteClass.call_args[0][0]
    assert request.ClassId == 1111


def test_absent_check_mode_does_not_delete(client):
    client.classes = [make_class()]
    module_args(class_name=CLASS_NAME, state="absent", _ansible_check_mode=True)
    result = run(vod_class.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.DeleteClass.assert_not_called()


def test_present_noop_when_class_exists(client):
    client.classes = [make_class()]
    module_args(class_name=CLASS_NAME)
    result = run(vod_class.run_module)
    assert result["changed"] is False
    assert result["class_id"] == 1111
    client.CreateClass.assert_not_called()


def test_present_matches_by_name_and_parent(client):
    client.classes = [
        make_class(class_id=1111, name="other", parent_id=-1),
        make_class(class_id=2222, name=CLASS_NAME, parent_id=5),
    ]
    module_args(class_name=CLASS_NAME, parent_id=5)
    result = run(vod_class.run_module)
    assert result["changed"] is False
    assert result["class_id"] == 2222
    client.CreateClass.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(class_name=CLASS_NAME)
    result = run(vod_class.run_module)
    assert result["changed"] is True
    assert result["class_id"] == 2222
    request = client.CreateClass.call_args[0][0]
    assert request.ClassName == CLASS_NAME
    assert request.ParentId == -1


def test_present_nested_class_creates_with_parent(client):
    module_args(class_name=CLASS_NAME, parent_id=5)
    run(vod_class.run_module)
    request = client.CreateClass.call_args[0][0]
    assert request.ClassName == CLASS_NAME
    assert request.ParentId == 5


def test_present_sub_app_id_forwarded(client):
    module_args(class_name=CLASS_NAME, sub_app_id=1400000000)
    run(vod_class.run_module)
    request = client.CreateClass.call_args[0][0]
    assert request.SubAppId == 1400000000


def test_present_check_mode_does_not_create(client):
    module_args(class_name=CLASS_NAME, _ansible_check_mode=True)
    result = run(vod_class.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateClass.assert_not_called()


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(class_name=CLASS_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(vod_class.run_module)
    assert exc.value.args[0]["failed"] is True
