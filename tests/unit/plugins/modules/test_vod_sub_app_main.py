"""Main-path unit tests for the vod_sub_app module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vod_sub_app
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SUB_APP_NAME = "media-prod"


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
    """In-memory stand-in for the VodClient sub-application operations."""

    def __init__(self, apps=None):
        self.apps = list(apps or [])
        self.describe_offsets = []
        self.DescribeSubAppIds = MagicMock(side_effect=self._describe)
        self.CreateSubAppId = MagicMock(side_effect=self._create)
        self.ModifySubAppIdInfo = MagicMock(side_effect=self._modify_info)
        self.ModifySubAppIdStatus = MagicMock(side_effect=self._modify_status)

    def _describe(self, request):
        self.describe_offsets.append(request.Offset)
        start = request.Offset or 0
        end = start + (request.Limit or 200)
        items = [FakeResource(a) for a in self.apps[start:end]]
        return SimpleNamespace(SubAppIdInfoSet=items)

    def _create(self, request):
        self.apps.append({
            "SubAppId": 1400000000,
            "SubAppIdName": request.Name,
            "Description": getattr(request, "Description", None),
            "Status": "On",
        })
        return SimpleNamespace(SubAppId=1400000000)

    def _modify_info(self, request):
        for app in self.apps:
            if app["SubAppId"] == request.SubAppId:
                app["Description"] = request.Description
        return SimpleNamespace()

    def _modify_status(self, request):
        for app in self.apps:
            if app["SubAppId"] == request.SubAppId:
                app["Status"] = request.Status
        return SimpleNamespace()


def make_app(sub_app_id=1400000001, name=SUB_APP_NAME, desc="prod", status="On"):
    return {
        "SubAppId": sub_app_id,
        "SubAppIdName": name,
        "Description": desc,
        "Status": status,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeVodClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        vod_sub_app, "_load_vod",
        lambda: (FakeModels(), SimpleNamespace(VodClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


CREATE_ARGS = dict(
    sub_app_name=SUB_APP_NAME,
    description="production media processing",
)


def test_absent_noop_when_app_missing(client):
    module_args(sub_app_name=SUB_APP_NAME, state="absent")
    result = run(vod_sub_app.run_module)
    assert result["changed"] is False
    client.ModifySubAppIdStatus.assert_not_called()


def test_absent_destroys_existing_app(client):
    client.apps = [make_app()]
    module_args(sub_app_name=SUB_APP_NAME, state="absent")
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    request = client.ModifySubAppIdStatus.call_args[0][0]
    assert request.SubAppId == 1400000001
    assert request.Status == "Destroyed"


def test_absent_noop_when_already_destroyed(client):
    client.apps = [make_app(status="Destroyed")]
    module_args(sub_app_name=SUB_APP_NAME, state="absent")
    result = run(vod_sub_app.run_module)
    assert result["changed"] is False
    client.ModifySubAppIdStatus.assert_not_called()


def test_absent_check_mode_does_not_destroy(client):
    client.apps = [make_app()]
    module_args(sub_app_name=SUB_APP_NAME, state="absent", _ansible_check_mode=True)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.ModifySubAppIdStatus.assert_not_called()


def test_present_noop_when_desc_matches_and_on(client):
    client.apps = [make_app(desc="production media processing")]
    module_args(**CREATE_ARGS)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is False
    assert result["sub_app_id"] == 1400000001
    assert result["status"] == "On"
    client.CreateSubAppId.assert_not_called()
    client.ModifySubAppIdInfo.assert_not_called()
    client.ModifySubAppIdStatus.assert_not_called()


def test_present_updates_description_when_changed(client):
    client.apps = [make_app(desc="old desc")]
    args = dict(CREATE_ARGS)
    args["description"] = "new desc"
    module_args(**args)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    request = client.ModifySubAppIdInfo.call_args[0][0]
    assert request.SubAppId == 1400000001
    assert request.Description == "new desc"
    client.CreateSubAppId.assert_not_called()


def test_present_enables_app_when_off(client):
    client.apps = [make_app(desc="production media processing", status="Off")]
    module_args(**CREATE_ARGS)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    request = client.ModifySubAppIdStatus.call_args[0][0]
    assert request.SubAppId == 1400000001
    assert request.Status == "On"


def test_present_updates_desc_and_enables_together(client):
    client.apps = [make_app(desc="old desc", status="Off")]
    args = dict(CREATE_ARGS)
    args["description"] = "new desc"
    module_args(**args)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    assert client.ModifySubAppIdInfo.call_args[0][0].Description == "new desc"
    assert client.ModifySubAppIdStatus.call_args[0][0].Status == "On"


def test_present_update_check_mode_no_write(client):
    client.apps = [make_app(desc="old desc")]
    args = dict(CREATE_ARGS)
    args["description"] = "new desc"
    module_args(**args, _ansible_check_mode=True)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    client.ModifySubAppIdInfo.assert_not_called()
    client.ModifySubAppIdStatus.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(**CREATE_ARGS)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    assert result["sub_app_id"] == 1400000000
    request = client.CreateSubAppId.call_args[0][0]
    assert request.Name == SUB_APP_NAME
    assert request.Description == "production media processing"


def test_present_optional_create_fields_forwarded(client):
    module_args(**dict(CREATE_ARGS, sub_app_type="Professional", mode="fileid",
                       storage_region="ap-guangzhou", tags=["env=prod"]))
    run(vod_sub_app.run_module)
    request = client.CreateSubAppId.call_args[0][0]
    assert request.Type == "Professional"
    assert request.Mode == "fileid"
    assert request.StorageRegion == "ap-guangzhou"
    assert request.Tags == ["env=prod"]


def test_present_check_mode_does_not_create(client):
    module_args(**CREATE_ARGS, _ansible_check_mode=True)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateSubAppId.assert_not_called()


def test_find_sub_app_scans_beyond_first_page(client):
    first_page = [make_app(sub_app_id=1400000000 + i, name="other-{0}".format(i))
                  for i in range(200)]
    # The paged target must match CREATE_ARGS.description, otherwise the module
    # detects a description difference and triggers an update (changed=True).
    client.apps = first_page + [make_app(sub_app_id=1400000999, name=SUB_APP_NAME,
                                         desc="production media processing")]
    module_args(**CREATE_ARGS)
    result = run(vod_sub_app.run_module)
    assert result["changed"] is False
    assert result["sub_app_id"] == 1400000999
    assert client.describe_offsets == [0, 200]


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(**CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(vod_sub_app.run_module)
    assert exc.value.args[0]["failed"] is True
