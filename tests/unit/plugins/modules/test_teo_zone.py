"""Unit tests for the teo_zone write module (helpers + run_module).

Covers the create / drift-update / pause-enable / destroy flows of
``plugins/modules/teo_zone.py`` with an in-memory fake EdgeOne client
whose write operations mutate the zone store, so the module's post-write
``find_zone`` refetch converges immediately. Zones are matched by
``ZoneId`` or by name; describe filters server-side via an
``AdvancedFilter`` (``zone-id`` / ``zone-name``) and pages over
``response.Zones`` / ``response.TotalCount``. Configuration drift
(ZoneName/Type/Area/AliasZoneName) goes through ModifyZone while pause
state is synced separately through ModifyZoneStatus. In check mode a
would-be create reports ``zone=None`` and a would-be update the
pre-change zone.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_zone as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE = {
    "ZoneId": "zone-abc123",
    "ZoneName": "example.com",
    "Type": "partial",
    "Area": "global",
    "AliasZoneName": "",
    "Paused": False,
}


def _zone(**overrides):
    """API-shaped zone dict isolated from the shared constant."""
    item = copy.deepcopy(ZONE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "zone_id": None,
        "name": "example.com",
        "zone_type": "partial",
        "area": "global",
        "alias_name": None,
        "plan_id": None,
        "enabled": True,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class FakeTeoClient(object):
    """In-memory TeoClient stand-in for zones.

    Stores API-shaped zone dicts keyed by ZoneId. Describe pages over the
    store honouring Offset/Limit, applies the optional zone-id / zone-name
    AdvancedFilter, and reports TotalCount at the top level (mirroring the
    SDK); write operations mutate the store so post-write refetches
    converge.
    """

    def __init__(self, zones=None):
        self.zones = [copy.deepcopy(z) for z in (zones or [])]
        self.calls = []
        self._created = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _filtered(self, request):
        zones = self.zones
        for item in getattr(request, "Filters", None) or []:
            key = "ZoneId" if item.Name == "zone-id" else "ZoneName"
            zones = [z for z in zones if z.get(key) == item.Values[0]]
        return zones

    def DescribeZones(self, request):
        self._record("DescribeZones", request)
        filtered = self._filtered(request)
        page = filtered[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Zones=[FakeResource(dict(z)) for z in page],
            TotalCount=len(filtered),
            RequestId="req-fake",
        )

    def CreateZone(self, request):
        self._record("CreateZone", request)
        self._created += 1
        zone_id = "zone-new%d" % self._created
        self.zones.append(
            {
                "ZoneId": zone_id,
                "ZoneName": request.ZoneName,
                "Type": request.Type,
                "Area": request.Area,
                "AliasZoneName": getattr(request, "AliasZoneName", None) or "",
                "Paused": False,
            }
        )
        return SimpleNamespace(ZoneId=zone_id, RequestId="req-fake")

    def ModifyZone(self, request):
        self._record("ModifyZone", request)
        for stored in self.zones:
            if stored.get("ZoneId") != request.ZoneId:
                continue
            stored["ZoneName"] = request.ZoneName
            stored["Type"] = request.Type
            stored["Area"] = request.Area
            if hasattr(request, "AliasZoneName"):
                stored["AliasZoneName"] = request.AliasZoneName
        return SimpleNamespace(RequestId="req-fake")

    def ModifyZoneStatus(self, request):
        self._record("ModifyZoneStatus", request)
        for stored in self.zones:
            if stored.get("ZoneId") != request.ZoneId:
                continue
            stored["Paused"] = request.Paused
        return SimpleNamespace(RequestId="req-fake")

    def DeleteZone(self, request):
        self._record("DeleteZone", request)
        self.zones = [z for z in self.zones if z.get("ZoneId") != request.ZoneId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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


def test_describe_request_without_filter():
    # neither zone_id nor name set -> no AdvancedFilter is attached
    request = mod.describe_request(FakeModels(), _params(name=None))
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_describe_request_filters_by_zone_id():
    request = mod.describe_request(FakeModels(), _params(zone_id="zone-abc123"))
    assert request.Filters[0].Name == "zone-id"
    assert request.Filters[0].Values == ["zone-abc123"]


def test_describe_request_filters_by_name():
    request = mod.describe_request(FakeModels(), _params(name="example.com"))
    assert request.Filters[0].Name == "zone-name"
    assert request.Filters[0].Values == ["example.com"]


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(plan_id="plan-x", alias_name="alias1"))
    assert request.Type == "partial"
    assert request.ZoneName == "example.com"
    assert request.Area == "global"
    assert request.PlanId == "plan-x"
    assert request.AliasZoneName == "alias1"


def test_create_request_omits_optionals():
    request = mod.create_request(FakeModels(), _params())
    assert not hasattr(request, "PlanId")
    assert not hasattr(request, "AliasZoneName")


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(name="renamed.com", area="mainland"), "zone-abc123")
    assert request.ZoneId == "zone-abc123"
    assert request.ZoneName == "renamed.com"
    assert request.Type == "partial"
    assert request.Area == "mainland"
    assert not hasattr(request, "AliasZoneName")  # alias_name None -> omitted


def test_update_request_sets_alias_when_given():
    request = mod.update_request(FakeModels(), _params(alias_name="alias1"), "zone-abc123")
    assert request.AliasZoneName == "alias1"


def test_status_request_paused_mapping():
    request = mod.status_request(FakeModels(), "zone-abc123", enabled=True)
    assert request.ZoneId == "zone-abc123"
    assert request.Paused is False
    request = mod.status_request(FakeModels(), "zone-abc123", enabled=False)
    assert request.Paused is True


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "zone-abc123")
    assert request.ZoneId == "zone-abc123"


def test_desired_maps_paused_from_enabled():
    assert mod.desired(_params(enabled=True))["Paused"] is False
    assert mod.desired(_params(enabled=False))["Paused"] is True
    assert mod.desired(_params(alias_name="alias1"))["AliasZoneName"] == "alias1"
    assert mod.desired(_params())["AliasZoneName"] == ""


# ---------------------------------------------------------------------------
# find_zone tests
# ---------------------------------------------------------------------------


def test_find_by_zone_id(monkeypatch):
    fake = FakeTeoClient([_zone(), _zone(ZoneId="zone-other", ZoneName="other.com")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(zone_id="zone-other", name=None))
    value = mod.find_zone(module, fake, FakeModels(), module.params)
    assert value["ZoneId"] == "zone-other"


def test_find_by_name(monkeypatch):
    fake = FakeTeoClient([_zone(ZoneName="other.com"), _zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="example.com"))
    value = mod.find_zone(module, fake, FakeModels(), module.params)
    assert value["ZoneId"] == "zone-abc123"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost.com"))
    assert mod.find_zone(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeTeoClient([_zone(), _zone(ZoneId="zone-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="example.com"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_zone(module, fake, FakeModels(), module.params)
    assert "Multiple EdgeOne zones matched" in exc.value.args[0]["msg"]


def test_find_narrowed_by_server_side_filter(monkeypatch):
    # DescribeZones filters by zone-name server-side, so bulk zones with
    # other names never enlarge the page: a single call returns the target.
    zones = [_zone(ZoneId="zone-%04d" % i, ZoneName="bulk-%04d.com" % i) for i in range(101)]
    zones.append(_zone())
    fake = FakeTeoClient(zones)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="example.com"))
    value = mod.find_zone(module, fake, FakeModels(), module.params)
    assert value["ZoneId"] == "zone-abc123"
    list_calls = [c for c in fake.calls if c[0] == "DescribeZones"]
    assert len(list_calls) == 1  # filter narrows before paging
    assert list_calls[0][1].Offset == 0


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args()  # neither zone_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name():
    module_args(zone_id="zone-abc123", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_zone(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    zone = result["zone"]
    assert zone["ZoneId"] == "zone-new1"
    assert zone["ZoneName"] == "example.com"
    assert zone["Paused"] is False
    names = [c[0] for c in fake.calls]
    # find + post-create refetch + unconditional final refetch
    assert names.count("DescribeZones") == 3
    assert names.count("CreateZone") == 1
    assert "ModifyZoneStatus" not in names  # new zone not paused; enabled
    create = [c for c in fake.calls if c[0] == "CreateZone"][0][1]
    assert create.ZoneName == "example.com"


def test_present_creates_paused_zone(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Paused"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyZoneStatus") == 1
    status = [c for c in fake.calls if c[0] == "ModifyZoneStatus"][0][1]
    assert status.ZoneId == "zone-new1"
    assert status.Paused is True


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["zone"]["ZoneId"] == "zone-abc123"
    names = [c[0] for c in fake.calls]
    assert "ModifyZone" not in names
    assert "ModifyZoneStatus" not in names
    assert "CreateZone" not in names


def test_present_rename_by_id_triggers_config_update(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(zone_id="zone-abc123", name="renamed.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["ZoneName"] == "renamed.com"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyZone") == 1
    assert "ModifyZoneStatus" not in names
    modify = [c for c in fake.calls if c[0] == "ModifyZone"][0][1]
    assert modify.ZoneId == "zone-abc123"
    assert modify.ZoneName == "renamed.com"


def test_present_area_drift_triggers_config_update(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(zone_id="zone-abc123", area="mainland")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Area"] == "mainland"
    modify = [c for c in fake.calls if c[0] == "ModifyZone"][0][1]
    assert modify.Area == "mainland"


def test_present_alias_drift_triggers_config_update(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(zone_id="zone-abc123", alias_name="alias1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["AliasZoneName"] == "alias1"
    modify = [c for c in fake.calls if c[0] == "ModifyZone"][0][1]
    assert modify.AliasZoneName == "alias1"


def test_present_pause_drift_triggers_status_only(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(zone_id="zone-abc123", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Paused"] is True
    names = [c[0] for c in fake.calls]
    assert "ModifyZone" not in names  # config unchanged
    assert names.count("ModifyZoneStatus") == 1
    status = [c for c in fake.calls if c[0] == "ModifyZoneStatus"][0][1]
    assert status.ZoneId == "zone-abc123"
    assert status.Paused is True


def test_present_unpause_drift_triggers_status_only(monkeypatch):
    fake = FakeTeoClient([_zone(Paused=True)])
    _make_module(monkeypatch, fake)
    _run_args(zone_id="zone-abc123", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Paused"] is False
    status = [c for c in fake.calls if c[0] == "ModifyZoneStatus"][0][1]
    assert status.Paused is False


def test_present_rename_by_name_uses_current_zone_id(monkeypatch):
    # identified by name only; the status call falls back to current ZoneId
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(name="example.com", enabled=False)  # no zone_id
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["Paused"] is True
    status = [c for c in fake.calls if c[0] == "ModifyZoneStatus"][0][1]
    assert status.ZoneId == "zone-abc123"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeZones"]  # find only
    assert not any("CreateZone" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(zone_id="zone-abc123", enabled=False).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["ZoneId"] == "zone-abc123"  # pre-change zone reported
    assert not any("ModifyZone" == c[0] for c in fake.calls)
    assert not any("ModifyZoneStatus" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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


def test_absent_deletes_zone(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteZone"][0][1]
    assert delete.ZoneId == "zone-abc123"
    assert fake.zones == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["zone"] is None
    assert not any("DeleteZone" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_zone()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["zone"]["ZoneId"] == "zone-abc123"  # pre-change zone reported
    assert not any("DeleteZone" == c[0] for c in fake.calls)
    assert len(fake.zones) == 1
