"""Unit tests for the private_dns_zone write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/private_dns_zone.py`` with an in-memory fake Private DNS
client whose write operations mutate the zone store, so the module's
post-write ``wait_for_zone`` refetch converges immediately. Zones are
matched by ``zone_id`` (DescribePrivateZone, not-found swallowed) or by
``Domain`` across the paged DescribePrivateZoneList (Limit 100); VPC
associations converge to the exact desired set and remarks are updated
in place.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import private_dns_zone as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE = {
    "ZoneId": "zone-pdns-1",
    "Domain": "internal.example.com",
    "Remark": "",
    "VpcSet": [],
    "Tags": None,
}


def _zone(**overrides):
    """API-shaped zone dict isolated from the shared constant."""
    item = copy.deepcopy(ZONE)
    item.update(overrides)
    return item


def _vpc(region="ap-guangzhou", vpc_id="vpc-abc123"):
    return {"region": region, "vpc_id": vpc_id}


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "zone_id": None,
        "domain": "internal.example.com",
        "remark": "",
        "vpcs": None,
        "tags": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class _PdnResource(FakeResource):
    """SDK resource that also supports to_json_string like real models."""

    def to_json_string(self):
        return json.dumps(self._data)


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


class _NotFound(RuntimeError):
    """SDK-style not-found exception carrying a get_code()."""

    def get_code(self):
        return "ResourceNotFound.PrivateZoneNotExists"


class FakePrivateDnsClient(object):
    """In-memory PrivatednsClient stand-in.

    Stores API-shaped zone dicts. DescribePrivateZone raises a not-found
    error for missing ids (find_zone swallows it); DescribePrivateZoneList
    pages over the store honouring Offset/Limit; write operations mutate the
    store so post-write refetches converge.
    """

    def __init__(self, zones=None):
        self.zones = [copy.deepcopy(z) for z in (zones or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "zone-pdns-%d" % self._next_id

    @staticmethod
    def _vpc_set(request):
        return [{"Region": v.Region, "UniqVpcId": v.UniqVpcId} for v in (getattr(request, "VpcSet", None) or [])]

    def DescribePrivateZone(self, request):
        self._record("DescribePrivateZone", request)
        for stored in self.zones:
            if stored.get("ZoneId") == request.ZoneId:
                return SimpleNamespace(PrivateZone=_PdnResource(dict(stored)), RequestId="req-fake")
        raise _NotFound("zone not found")

    def DescribePrivateZoneList(self, request):
        self._record("DescribePrivateZoneList", request)
        page = self.zones[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            PrivateZoneSet=[_PdnResource(dict(z)) for z in page],
            TotalCount=len(self.zones),
            RequestId="req-fake",
        )

    def CreatePrivateZone(self, request):
        self._record("CreatePrivateZone", request)
        zone_id = self._new_id()
        entry = {
            "ZoneId": zone_id,
            "Domain": request.Domain,
            "Remark": request.Remark,
            "VpcSet": self._vpc_set(request),
        }
        tags = getattr(request, "TagSet", None)
        if tags:
            entry["Tags"] = [{"TagKey": t.TagKey, "TagValue": t.TagValue} for t in tags]
        self.zones.append(entry)
        return SimpleNamespace(ZoneId=zone_id, RequestId="req-fake")

    def DeletePrivateZone(self, request):
        self._record("DeletePrivateZone", request)
        self.zones = [z for z in self.zones if z.get("ZoneId") != request.ZoneId]
        return SimpleNamespace(RequestId="req-fake")

    def ModifyPrivateZone(self, request):
        self._record("ModifyPrivateZone", request)
        for stored in self.zones:
            if stored.get("ZoneId") == request.ZoneId:
                stored["Remark"] = request.Remark
        return SimpleNamespace(RequestId="req-fake")

    def ModifyPrivateZoneVpc(self, request):
        self._record("ModifyPrivateZoneVpc", request)
        for stored in self.zones:
            if stored.get("ZoneId") == request.ZoneId:
                stored["VpcSet"] = self._vpc_set(request)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_private_dns",
        lambda: (FakeModels(), SimpleNamespace(PrivatednsClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_dict_conversion():
    resource = _PdnResource({"ZoneId": "z", "Domain": "d.example.com"})
    assert mod._dict(resource) == {"ZoneId": "z", "Domain": "d.example.com"}
    assert mod._dict(None) is None


def test_vpcs_normalises_sorted_dedup_shape():
    value = mod._vpcs([{"Region": "ap-shanghai", "UniqVpcId": "vpc-b"}, {"Region": "ap-guangzhou", "UniqVpcId": "vpc-a"}])
    assert value == [
        {"Region": "ap-guangzhou", "UniqVpcId": "vpc-a"},
        {"Region": "ap-shanghai", "UniqVpcId": "vpc-b"},
    ]


def test_vpcs_accepts_lowercase_input_keys():
    value = mod._vpcs([{"region": "ap-guangzhou", "vpc_id": "vpc-a"}])
    assert value == [{"Region": "ap-guangzhou", "UniqVpcId": "vpc-a"}]


def test_vpcs_empty_and_none():
    assert mod._vpcs(None) == []
    assert mod._vpcs([]) == []


def test_build_vpcs_maps_fields():
    items = mod.build_vpcs(FakeModels(), [_vpc(), _vpc("ap-shanghai", "vpc-b")])
    assert [(i.Region, i.UniqVpcId) for i in items] == [
        ("ap-guangzhou", "vpc-abc123"),
        ("ap-shanghai", "vpc-b"),
    ]


def test_build_vpcs_empty_and_none():
    assert mod.build_vpcs(FakeModels(), None) == []
    assert mod.build_vpcs(FakeModels(), []) == []


def test_create_request_fields():
    request = mod.build_create_request(FakeModels(), _params(remark="prod zone", vpcs=[_vpc()]))
    assert request.Domain == "internal.example.com"
    assert request.Remark == "prod zone"
    assert [(v.Region, v.UniqVpcId) for v in request.VpcSet] == [("ap-guangzhou", "vpc-abc123")]


def test_create_request_tags_sorted():
    request = mod.build_create_request(FakeModels(), _params(tags={"z": "2", "a": "1"}))
    assert [(t.TagKey, t.TagValue) for t in request.TagSet] == [("a", "1"), ("z", "2")]


def test_create_request_without_tags_and_vpcs():
    request = mod.build_create_request(FakeModels(), _params())
    assert request.VpcSet == []
    assert not hasattr(request, "TagSet")


# ---------------------------------------------------------------------------
# find_zone tests
# ---------------------------------------------------------------------------


def test_find_zone_by_zone_id(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(zone_id="zone-pdns-1"))
    value = mod.find_zone(module, fake, FakeModels(), "zone-pdns-1", None)
    assert value["ZoneId"] == "zone-pdns-1"
    assert value["Domain"] == "internal.example.com"


def test_find_zone_by_zone_id_not_found_returns_none(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(zone_id="zone-pdns-ghost"))
    assert mod.find_zone(module, fake, FakeModels(), "zone-pdns-ghost", None) is None


def test_find_zone_by_domain(monkeypatch):
    fake = FakePrivateDnsClient([_zone(Domain="other.example.com"), _zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_zone(module, fake, FakeModels(), None, "internal.example.com")
    assert value["ZoneId"] == "zone-pdns-1"


def test_find_zone_no_match_returns_none(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(domain="ghost.example.com"))
    assert mod.find_zone(module, fake, FakeModels(), None, "ghost.example.com") is None


def test_find_zone_multiple_matches_fails(monkeypatch):
    fake = FakePrivateDnsClient([_zone(), _zone(ZoneId="zone-pdns-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_zone(module, fake, FakeModels(), None, "internal.example.com")
    assert "Multiple private zones have the requested domain" in exc.value.args[0]["msg"]


def test_find_zone_paginates_past_100(monkeypatch):
    zones = [_zone(ZoneId="bulk-%04d" % i, Domain="bulk-%04d.example.com" % i) for i in range(101)]
    zones.append(_zone())
    fake = FakePrivateDnsClient(zones)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_zone(module, fake, FakeModels(), None, "internal.example.com")
    assert value["ZoneId"] == "zone-pdns-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribePrivateZoneList"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present", remark="x")  # neither zone_id nor domain
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_zone(monkeypatch):
    fake = FakePrivateDnsClient()
    _make_module(monkeypatch, fake)
    _run_args(remark="prod", vpcs=[_vpc()])
    result = run(mod.run_module)
    assert result["changed"] is True
    zone = result["zone"]
    assert zone["ZoneId"] == "zone-pdns-101"
    assert zone["Domain"] == "internal.example.com"
    assert zone["Remark"] == "prod"
    assert zone["VpcSet"] == [{"Region": "ap-guangzhou", "UniqVpcId": "vpc-abc123"}]
    names = [c[0] for c in fake.calls]
    assert names.count("DescribePrivateZone") == 1  # post-create wait refetch
    assert names.count("DescribePrivateZoneList") == 1  # initial find
    assert names.count("CreatePrivateZone") == 1


def test_present_creates_zone_without_vpcs(monkeypatch):
    fake = FakePrivateDnsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["VpcSet"] == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["zone"]["ZoneId"] == "zone-pdns-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyPrivateZone" not in names
    assert "ModifyPrivateZoneVpc" not in names


def test_present_remark_drift_triggers_update(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(remark="updated-remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Remark"] == "updated-remark"
    modify = [c for c in fake.calls if c[0] == "ModifyPrivateZone"][0][1]
    assert modify.ZoneId == "zone-pdns-1"
    assert modify.Remark == "updated-remark"
    assert not any("ModifyPrivateZoneVpc" == c[0] for c in fake.calls)


def test_present_vpc_drift_triggers_update(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(vpcs=[_vpc()])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["VpcSet"] == [{"Region": "ap-guangzhou", "UniqVpcId": "vpc-abc123"}]
    names = [c[0] for c in fake.calls]
    assert "ModifyPrivateZone" not in names
    assert names.count("ModifyPrivateZoneVpc") == 1


def test_present_vpc_replace_exact_set(monkeypatch):
    fake = FakePrivateDnsClient([_zone(VpcSet=[{"Region": "ap-shanghai", "UniqVpcId": "vpc-old"}])])
    _make_module(monkeypatch, fake)
    _run_args(vpcs=[_vpc()])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["VpcSet"] == [{"Region": "ap-guangzhou", "UniqVpcId": "vpc-abc123"}]
    modify = [c for c in fake.calls if c[0] == "ModifyPrivateZoneVpc"][0][1]
    assert [(v.Region, v.UniqVpcId) for v in modify.VpcSet] == [("ap-guangzhou", "vpc-abc123")]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_private_dns",
        lambda: (FakeModels(), SimpleNamespace(PrivatednsClient=object)),
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


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"] is None
    assert not any("CreatePrivateZone" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(remark="new"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Remark"] == ""  # pre-change state reported
    assert not any("ModifyPrivateZone" == c[0] for c in fake.calls)


def test_absent_removes_zone(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"] is None
    delete = [c for c in fake.calls if c[0] == "DeletePrivateZone"][0][1]
    assert delete.ZoneId == "zone-pdns-1"
    assert fake.zones == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", domain="ghost.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["zone"] is None
    assert not any("DeletePrivateZone" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient([_zone()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"] is not None  # pre-change state reported
    assert not any("DeletePrivateZone" == c[0] for c in fake.calls)
    assert len(fake.zones) == 1
