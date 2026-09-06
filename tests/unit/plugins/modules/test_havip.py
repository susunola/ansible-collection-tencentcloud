"""Unit tests for the havip write module (helpers + run_module).

Creates, renames and deletes VPC high-availability virtual IPs. Network
placement (VpcId/SubnetId/Vip/CheckAssociate) is immutable after creation:
any placement drift fails unless force_replace is set, in which case the
HAVIP is deleted and recreated (never a Modify). Pure renames go through
ModifyHaVipAttribute. A vip-less run against an allocated HAVIP falls back
to the current Vip (desired()) so it is a no-op, not a replacement.
state=present requires name/vpc_id/subnet_id before the SDK is reached;
required_one_of=(havip_id, name) fires for absent runs too.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import havip as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _havip(**overrides):
    """API-shaped stored HAVIP; fresh copy per call."""
    item = {
        "havip_id": "havip-1001",
        "name": "database-vip",
        "vpc_id": "vpc-abc",
        "subnet_id": "subnet-abc",
        "vip": "10.0.1.100",
        "check_associate": False,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "havip_id": None,
        "name": "database-vip",
        "vpc_id": "vpc-abc",
        "subnet_id": "subnet-abc",
        "vip": "10.0.1.100",
        "check_associate": False,
        "force_replace": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


def _serialize_havip(h):
    """Map a stored HAVIP dict onto its API response shape."""
    return {
        "HaVipId": h["havip_id"],
        "HaVipName": h["name"],
        "VpcId": h["vpc_id"],
        "SubnetId": h["subnet_id"],
        "Vip": h.get("vip"),
        "CheckAssociate": h["check_associate"],
    }


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


class FakeVpcClient(object):
    """In-memory VpcClient stand-in storing HAVIP dicts.

    DescribeHaVips honours HaVipIds when present, otherwise the
    havip-name Filter; CreateHaVip synthesises sequential havip-NNNN ids;
    ModifyHaVipAttribute rewrites the name by id; DeleteHaVip removes by
    id.
    """

    def __init__(self, havips=None):
        self.havips = [dict(h) for h in (havips or [])]
        self.calls = []
        self._seq = 2000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return "havip-%d" % self._seq

    def DescribeHaVips(self, request):
        self._record("DescribeHaVips", request)
        ids = getattr(request, "HaVipIds", None) or []
        result = self.havips
        if ids:
            result = [h for h in self.havips if h["havip_id"] in ids]
        elif getattr(request, "Filters", None):
            name = request.Filters[0].Values[0]
            result = [h for h in self.havips if h["name"] == name]
        return SimpleNamespace(HaVipSet=[FakeResource(_serialize_havip(h)) for h in result], RequestId="req-fake")

    def CreateHaVip(self, request):
        self._record("CreateHaVip", request)
        havip_id = self._next_id()
        self.havips.append({
            "havip_id": havip_id,
            "name": request.HaVipName,
            "vpc_id": request.VpcId,
            "subnet_id": request.SubnetId,
            "vip": getattr(request, "Vip", None),
            "check_associate": bool(getattr(request, "CheckAssociate", False)),
        })
        return SimpleNamespace(HaVipId=havip_id, RequestId="req-fake")

    def ModifyHaVipAttribute(self, request):
        self._record("ModifyHaVipAttribute", request)
        for h in self.havips:
            if h["havip_id"] == request.HaVipId:
                h["name"] = request.HaVipName
        return SimpleNamespace(RequestId="req-fake")

    def DeleteHaVip(self, request):
        self._record("DeleteHaVip", request)
        self.havips = [h for h in self.havips if h["havip_id"] != request.HaVipId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_ids_when_havip_id():
    request = mod.describe_request(FakeModels(), _params(havip_id="havip-9"))
    assert request.Limit == 100
    assert request.HaVipIds == ["havip-9"]
    assert not hasattr(request, "Filters")


def test_describe_request_sets_name_filter():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Limit == 100
    assert request.Filters[0].Name == "havip-name"
    assert request.Filters[0].Values == ["database-vip"]
    assert not hasattr(request, "HaVipIds")


def test_describe_request_without_identity_sets_nothing():
    request = mod.describe_request(FakeModels(), _params(havip_id=None, name=None))
    assert request.Limit == 100
    assert not hasattr(request, "HaVipIds")
    assert not hasattr(request, "Filters")


def test_create_request_sets_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.VpcId == "vpc-abc"
    assert request.HaVipName == "database-vip"
    assert request.SubnetId == "subnet-abc"
    assert request.Vip == "10.0.1.100"
    assert request.CheckAssociate is False


def test_create_request_vip_none_when_unset():
    request = mod.create_request(FakeModels(), _params(vip=None))
    assert request.Vip is None
    assert request.CheckAssociate is False


def test_create_request_check_associate_true():
    request = mod.create_request(FakeModels(), _params(check_associate=True))
    assert request.CheckAssociate is True


def test_update_request_sets_id_and_name():
    request = mod.update_request(FakeModels(), "havip-7", "renamed")
    assert request.HaVipId == "havip-7"
    assert request.HaVipName == "renamed"


def test_delete_request_wraps_id():
    request = mod.delete_request(FakeModels(), "havip-7")
    assert request.HaVipId == "havip-7"


def test_comparable_maps_api_fields():
    value = mod.comparable(_serialize_havip(_havip()))
    assert value == {
        "HaVipName": "database-vip",
        "VpcId": "vpc-abc",
        "SubnetId": "subnet-abc",
        "Vip": "10.0.1.100",
        "CheckAssociate": False,
    }


def test_comparable_coerces_check_associate():
    value = mod.comparable({"HaVipName": "x", "VpcId": "v", "SubnetId": "s", "Vip": None, "CheckAssociate": 1})
    assert value["CheckAssociate"] is True


def test_desired_maps_params():
    value = mod.desired(_params())
    assert value == {
        "HaVipName": "database-vip",
        "VpcId": "vpc-abc",
        "SubnetId": "subnet-abc",
        "Vip": "10.0.1.100",
        "CheckAssociate": False,
    }


def test_desired_falls_back_to_current_vip():
    value = mod.desired(_params(vip=None), current={"Vip": "10.0.0.5"})
    assert value["Vip"] == "10.0.0.5"


def test_desired_vip_none_when_no_current():
    value = mod.desired(_params(vip=None), current=None)
    assert value["Vip"] is None


def test_find_matches_by_havip_id():
    fake = FakeVpcClient([_havip()])
    module = FakeModule(_params(havip_id="havip-1001"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["HaVipId"] == "havip-1001"
    assert value["HaVipName"] == "database-vip"
    request = module.sdk_calls[0][1]
    assert request.HaVipIds == ["havip-1001"]


def test_find_matches_by_name():
    fake = FakeVpcClient([_havip()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["HaVipId"] == "havip-1001"
    assert module.sdk_calls[0][1].Filters[0].Values == ["database-vip"]


def test_find_no_match_returns_none():
    fake = FakeVpcClient()
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multi_match_fails():
    fake = FakeVpcClient([_havip(), _havip(havip_id="havip-1002")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple HAVIPs matched; specify havip_id" in payload["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_havip_id_or_name(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args(havip_id=None, name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


@pytest.mark.parametrize("missing", ["name", "vpc_id", "subnet_id"])
def test_present_requires_identity_fields(monkeypatch, missing):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    extra = {"havip_id": "havip-x"} if missing == "name" else {}
    _run_args(**{missing: None}, **extra)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, vpc_id and subnet_id are required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["havip"] is None
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipId"] == "havip-1001"
    assert result["diff"]["before"]["HaVipName"] == "database-vip"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]
    assert len(fake.havips) == 1


def test_absent_deletes_havip(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeHaVips",
        "DeleteHaVip",
    ]
    deleted = fake.calls[1][1]
    assert deleted.HaVipId == "havip-1001"
    assert fake.havips == []


def test_present_noop_when_havip_matches(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["havip"]["HaVipId"] == "havip-1001"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]


def test_present_noop_when_vip_unset_keeps_allocated(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(vip=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["havip"]["Vip"] == "10.0.1.100"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]


def test_present_renames_havip(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(havip_id="havip-1001", name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipName"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeHaVips",
        "ModifyHaVipAttribute",
        "DescribeHaVips",
    ]
    updated = fake.calls[1][1]
    assert updated.HaVipId == "havip-1001"
    assert updated.HaVipName == "renamed"
    assert fake.havips[0]["name"] == "renamed"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(havip_id="havip-1001", name="renamed", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipName"] == "database-vip"
    assert result["diff"]["before"]["HaVipName"] == "database-vip"
    assert result["diff"]["after"]["HaVipName"] == "renamed"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]
    assert fake.havips[0]["name"] == "database-vip"


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"vpc_id": "vpc-new"}, "VpcId"),
        ({"subnet_id": "subnet-new"}, "SubnetId"),
        ({"vip": "10.0.1.200"}, "Vip"),
        ({"check_associate": True}, "CheckAssociate"),
    ],
)
def test_present_placement_drift_requires_force_replace(monkeypatch, overrides, field):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "HAVIP network placement is immutable; set force_replace=true to recreate it" in payload["msg"]
    assert payload["current"][field] != payload["desired"][field]
    assert payload["current"]["HaVipName"] == "database-vip"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]


def test_present_force_replace_recreates_havip(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(vpc_id="vpc-new", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipId"] == "havip-2001"
    assert result["havip"]["VpcId"] == "vpc-new"
    assert [c[0] for c in fake.calls] == [
        "DescribeHaVips",
        "DeleteHaVip",
        "CreateHaVip",
        "DescribeHaVips",
    ]
    deleted = fake.calls[1][1]
    assert deleted.HaVipId == "havip-1001"
    created = fake.calls[2][1]
    assert created.VpcId == "vpc-new"
    assert created.HaVipName == "database-vip"
    assert len(fake.havips) == 1
    assert fake.havips[0]["havip_id"] == "havip-2001"


def test_present_check_mode_replace_is_dry_run(monkeypatch):
    fake = FakeVpcClient([_havip()])
    _make_module(monkeypatch, fake)
    _run_args(vpc_id="vpc-new", force_replace=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["VpcId"] == "vpc-abc"
    assert result["diff"]["before"]["VpcId"] == "vpc-abc"
    assert result["diff"]["after"]["VpcId"] == "vpc-new"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]
    assert len(fake.havips) == 1
    assert fake.havips[0]["vpc_id"] == "vpc-abc"


def test_present_creates_havip(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipId"] == "havip-2001"
    assert result["havip"]["HaVipName"] == "database-vip"
    assert [c[0] for c in fake.calls] == [
        "DescribeHaVips",
        "CreateHaVip",
        "DescribeHaVips",
    ]
    created = fake.calls[1][1]
    assert created.VpcId == "vpc-abc"
    assert created.HaVipName == "database-vip"
    assert created.SubnetId == "subnet-abc"
    assert created.Vip == "10.0.1.100"
    assert created.CheckAssociate is False
    assert len(fake.havips) == 1
    assert fake.havips[0]["havip_id"] == "havip-2001"


def test_present_creates_havip_without_vip(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args(vip=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"]["HaVipId"] == "havip-2001"
    created = fake.calls[1][1]
    assert created.Vip is None
    assert fake.havips[0]["vip"] is None


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["havip"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["HaVipName"] == "database-vip"
    assert [c[0] for c in fake.calls] == ["DescribeHaVips"]
    assert fake.havips == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["havip"] is None
