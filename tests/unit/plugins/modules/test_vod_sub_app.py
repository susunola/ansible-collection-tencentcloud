"""Unit tests for the vod_sub_app write module (helpers + run_module).

Covers the create / description-status drift / destroy flows of
``plugins/modules/vod_sub_app.py`` with an in-memory fake VOD client whose
write operations mutate the sub-application store, so post-write state
converges. Sub-applications are matched by name across the paged
DescribeSubAppIds list; description (ModifySubAppIdInfo) and status
(ModifySubAppIdStatus) are the only in-place updateable fields — everything
else is create-only, and removal is a destroy-status change since the
platform has no delete API.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vod_sub_app as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SUB_APP = {
    "SubAppId": 1400000001,
    "Name": "media-prod",
    "Description": "",
    "Status": "On",
}


def _sub_app(**overrides):
    """API-shaped sub-application dict isolated from the shared constant."""
    item = copy.deepcopy(SUB_APP)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "sub_app_name": "media-prod",
        "state": "present",
        "description": None,
        "sub_app_type": None,
        "mode": None,
        "storage_region": None,
        "tags": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _clean_params(**overrides):
    """_params() with None-valued keys dropped.

    ``sub_app_type`` is a no-default ``choices`` parameter; Ansible
    validates choices for every explicitly passed key, so a pre-filled None
    must be omitted or the module fails validation before any SDK call.
    """
    return {key: value for key, value in _params(**overrides).items() if value is not None}


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**dict(_clean_params(), **extra))


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeVodClient(object):
    """In-memory VodClient stand-in.

    Stores API-shaped sub-application dicts. DescribeSubAppIds pages over
    the store honouring Offset/Limit so find pagination is exercised; the
    write operations mutate the store so post-write refetches converge.
    """

    def __init__(self, apps=None):
        self.apps = [copy.deepcopy(a) for a in (apps or [])]
        self.calls = []
        self._next_id = 1400001001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSubAppIds(self, request):
        self._record("DescribeSubAppIds", request)
        page = self.apps[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            SubAppIdInfoSet=[FakeResource(dict(a)) for a in page],
            TotalCount=len(self.apps),
            RequestId="req-fake",
        )

    def CreateSubAppId(self, request):
        self._record("CreateSubAppId", request)
        app_id = self._next_id
        self._next_id += 1
        entry = {"SubAppId": app_id, "Name": request.Name, "Description": getattr(request, "Description", "") or "", "Status": "On"}
        self.apps.append(entry)
        return SimpleNamespace(SubAppId=app_id, RequestId="req-fake")

    @staticmethod
    def _find(apps, request):
        for stored in apps:
            if stored.get("SubAppId") == getattr(request, "SubAppId", None):
                return stored
        return None

    def ModifySubAppIdInfo(self, request):
        self._record("ModifySubAppIdInfo", request)
        stored = self._find(self.apps, request)
        if stored is not None:
            stored["Description"] = request.Description or ""
        return SimpleNamespace(RequestId="req-fake")

    def ModifySubAppIdStatus(self, request):
        self._record("ModifySubAppIdStatus", request)
        stored = self._find(self.apps, request)
        if stored is not None:
            stored["Status"] = request.Status
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_vod",
        lambda: (FakeModels(), SimpleNamespace(VodClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_sub_app_matches_by_name(monkeypatch):
    fake = FakeVodClient([_sub_app(Name="other-app"), _sub_app()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sub_app(module, fake, FakeModels(), "media-prod")
    assert value["SubAppId"] == 1400000001


def test_find_sub_app_matches_by_sub_app_id_name_alias(monkeypatch):
    fake = FakeVodClient([_sub_app(Name="x", SubAppIdName="media-prod")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sub_app(module, fake, FakeModels(), "media-prod")
    assert value["SubAppId"] == 1400000001


def test_find_sub_app_no_match_returns_none(monkeypatch):
    fake = FakeVodClient([_sub_app(Name="other-app")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_sub_app(module, fake, FakeModels(), "ghost") is None


def test_find_sub_app_paginates_until_match(monkeypatch):
    apps = [_sub_app(SubAppId=1000000000 + i, Name="bulk-%04d" % i) for i in range(450)]
    apps.append(_sub_app())
    fake = FakeVodClient(apps)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_sub_app(module, fake, FakeModels(), "media-prod")
    assert value["SubAppId"] == 1400000001
    assert len([c for c in fake.calls if c[0] == "DescribeSubAppIds"]) == 3  # pages of 200


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_sub_app_name_required():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sub_app_name" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_vod",
        lambda: (FakeModels(), SimpleNamespace(VodClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_sub_app(monkeypatch):
    fake = FakeVodClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sub_app_id"] == 1400001001
    assert result["sub_app_name"] == "media-prod"
    assert "created" in result["msg"]
    create = [c for c in fake.calls if c[0] == "CreateSubAppId"][0][1]
    assert create.Name == "media-prod"
    assert not hasattr(create, "Description")
    assert not hasattr(create, "Type")


def test_present_creates_with_full_fields(monkeypatch):
    fake = FakeVodClient()
    _make_module(monkeypatch, fake)
    _run_args(description="prod media", sub_app_type="Professional", mode="Standard", storage_region="ap-guangzhou", tags=["env=prod"])
    result = run(mod.run_module)
    assert result["changed"] is True
    create = [c for c in fake.calls if c[0] == "CreateSubAppId"][0][1]
    assert create.Description == "prod media"
    assert create.Type == "Professional"
    assert create.Mode == "Standard"
    assert create.StorageRegion == "ap-guangzhou"
    assert create.Tags == ["env=prod"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeVodClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert not any(c[0] == "CreateSubAppId" for c in fake.calls)


def test_present_noop_is_unchanged(monkeypatch):
    fake = FakeVodClient([_sub_app()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["sub_app_id"] == 1400000001
    assert result["status"] == "On"
    assert "already present" in result["msg"]
    assert not any(c[0] in ("ModifySubAppIdInfo", "ModifySubAppIdStatus") for c in fake.calls)


def test_present_description_drift_triggers_info_update(monkeypatch):
    fake = FakeVodClient([_sub_app()])
    _make_module(monkeypatch, fake)
    _run_args(description="new description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "description" in result["msg"]
    info = [c for c in fake.calls if c[0] == "ModifySubAppIdInfo"][0][1]
    assert info.SubAppId == 1400000001
    assert info.Description == "new description"
    assert fake.apps[0]["Description"] == "new description"


def test_present_status_drift_triggers_status_update(monkeypatch):
    fake = FakeVodClient([_sub_app(Status="Offline")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "status" in result["msg"]
    status = [c for c in fake.calls if c[0] == "ModifySubAppIdStatus"][0][1]
    assert status.SubAppId == 1400000001
    assert status.Status == "On"
    assert fake.apps[0]["Status"] == "On"


def test_present_both_drifts_update_twice(monkeypatch):
    fake = FakeVodClient([_sub_app(Status="Offline")])
    _make_module(monkeypatch, fake)
    _run_args(description="upgraded")
    result = run(mod.run_module)
    assert result["changed"] is True
    names = [c[0] for c in fake.calls]
    assert "ModifySubAppIdInfo" in names
    assert "ModifySubAppIdStatus" in names
    assert fake.apps[0]["Description"] == "upgraded"
    assert fake.apps[0]["Status"] == "On"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeVodClient([_sub_app()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(description="draft")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert not any(c[0] in ("ModifySubAppIdInfo", "ModifySubAppIdStatus") for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeVodClient([_sub_app(Name="other-app")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", sub_app_name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "not present" in result["msg"]
    assert not any(c[0] == "ModifySubAppIdStatus" for c in fake.calls)


def test_absent_already_destroyed_is_noop(monkeypatch):
    fake = FakeVodClient([_sub_app(Status="Destroyed")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["status"] == "Destroyed"
    assert "already destroyed" in result["msg"]
    assert not any(c[0] == "ModifySubAppIdStatus" for c in fake.calls)


def test_absent_destroys_sub_app(monkeypatch):
    fake = FakeVodClient([_sub_app()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Destroy request submitted" in result["msg"]
    status = [c for c in fake.calls if c[0] == "ModifySubAppIdStatus"][0][1]
    assert status.SubAppId == 1400000001
    assert status.Status == "Destroyed"
    assert fake.apps[0]["Status"] == "Destroyed"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVodClient([_sub_app()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would destroy" in result["msg"]
    assert not any(c[0] == "ModifySubAppIdStatus" for c in fake.calls)
    assert fake.apps[0]["Status"] == "On"
