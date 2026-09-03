"""Unit tests for the teo_origin_group write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/teo_origin_group.py`` with an in-memory fake EdgeOne client
whose write operations mutate the origin-group store, so the module's
post-write ``find_group`` refetch converges immediately. Origin groups are
matched by ``group_id`` or by ``Name`` across the paged
DescribeOriginGroup list (Limit 1000); records converge to the exact desired
set, GENERAL groups only accept IP_DOMAIN records and weights are bounded to
0..100.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_origin_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "GroupId": "origin-group-1",
    "Name": "app-origins",
    "Type": "GENERAL",
    "HostHeader": "",
    "Records": [{"Record": "192.0.2.10", "Type": "IP_DOMAIN"}],
}


def _group(**overrides):
    """API-shaped origin-group dict isolated from the shared constant."""
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _record(record, record_type="IP_DOMAIN", weight=None):
    value = {"record": record, "record_type": record_type}
    if weight is not None:
        value["weight"] = weight
    return value


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "zone_id": "zone-edge1",
        "group_id": None,
        "name": "app-origins",
        "group_type": "GENERAL",
        "host_header": None,
        "records": [_record("192.0.2.10")],
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
    """In-memory TeoClient stand-in.

    Stores API-shaped origin-group dicts. DescribeOriginGroup pages over the
    store honouring Offset/Limit so find_group pagination is exercised; the
    write operations mutate the store so post-write refetches converge.
    """

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 10000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _group_id(self):
        self._next_id += 1
        return "origin-group-%05d" % self._next_id

    def DescribeOriginGroup(self, request):
        self._record("DescribeOriginGroup", request)
        page = self.groups[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            OriginGroups=[FakeResource(dict(g)) for g in page],
            TotalCount=len(self.groups),
            RequestId="req-fake",
        )

    def CreateOriginGroup(self, request):
        self._record("CreateOriginGroup", request)
        group_id = self._group_id()
        self.groups.append(
            {
                "GroupId": group_id,
                "Name": request.Name,
                "Type": request.Type,
                "HostHeader": getattr(request, "HostHeader", None) or "",
                "Records": [
                    {"Record": r.Record, "Type": r.Type, "Weight": getattr(r, "Weight", None)}
                    for r in (request.Records or [])
                    if ({"Record": r.Record, "Type": r.Type, "Weight": getattr(r, "Weight", None)}).get("Record") is not None
                ],
            }
        )
        return SimpleNamespace(OriginGroupId=group_id, RequestId="req-fake")

    def ModifyOriginGroup(self, request):
        self._record("ModifyOriginGroup", request)
        for stored in self.groups:
            if stored.get("GroupId") != request.GroupId:
                continue
            stored["Name"] = request.Name
            stored["Type"] = request.Type
            stored["HostHeader"] = request.HostHeader or ""
            stored["Records"] = [
                {"Record": r.Record, "Type": r.Type, "Weight": getattr(r, "Weight", None)}
                for r in (request.Records or [])
            ]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteOriginGroup(self, request):
        self._record("DeleteOriginGroup", request)
        self.groups = [g for g in self.groups if g.get("GroupId") != request.GroupId]
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


def test_describe_request_base_fields():
    request = mod.describe_request(FakeModels(), _params(group_id=None, name=None), offset=7)
    assert request.ZoneId == "zone-edge1"
    assert request.Offset == 7
    assert request.Limit == 1000
    assert not hasattr(request, "Filters")


def test_describe_request_filters_by_group_id():
    request = mod.describe_request(FakeModels(), _params(group_id="origin-group-9"), offset=0)
    assert request.Filters[0].Name == "origin-group-id"
    assert request.Filters[0].Values == ["origin-group-9"]


def test_describe_request_filters_by_name():
    request = mod.describe_request(FakeModels(), _params(group_id=None, name="app-origins"), offset=0)
    assert request.Filters[0].Name == "origin-group-name"
    assert request.Filters[0].Values == ["app-origins"]


def test_records_builder_maps_fields():
    items = mod._records(FakeModels(), [_record("192.0.2.10", weight=70), _record("obj.cos.cn", "COS")])
    assert len(items) == 2
    assert items[0].Record == "192.0.2.10"
    assert items[0].Type == "IP_DOMAIN"
    assert items[0].Weight == 70
    assert items[1].Record == "obj.cos.cn"
    assert items[1].Type == "COS"
    assert not hasattr(items[1], "Weight")


def test_records_builder_empty():
    assert mod._records(FakeModels(), None) == []
    assert mod._records(FakeModels(), []) == []


def test_create_request_fields():
    request = mod.create_request(FakeModels(),
                                 _params(name="app-origins", group_type="HTTP", host_header="origin.example.com",
                                         records=[_record("192.0.2.10", weight=70)]))
    assert request.ZoneId == "zone-edge1"
    assert request.Name == "app-origins"
    assert request.Type == "HTTP"
    assert request.HostHeader == "origin.example.com"
    assert len(request.Records) == 1
    assert request.Records[0].Weight == 70


def test_create_request_omits_host_header_when_absent():
    request = mod.create_request(FakeModels(), _params(group_type="GENERAL"))
    assert not hasattr(request, "HostHeader")


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(group_type="HTTP", host_header=None), "origin-group-1")
    assert request.ZoneId == "zone-edge1"
    assert request.GroupId == "origin-group-1"
    assert request.Type == "HTTP"
    assert request.HostHeader == ""  # update clears the header when not given
    assert request.Records[0].Record == "192.0.2.10"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), "origin-group-1")
    assert request.ZoneId == "zone-edge1"
    assert request.GroupId == "origin-group-1"


def test_normalized_records_sorts_and_drops_missing_weight():
    value = mod._normalized_records(
        [
            {"record": "b.example.com", "record_type": "IP_DOMAIN", "weight": 30},
            {"record": "a.example.com", "record_type": "IP_DOMAIN"},
            {"record": "obj.cos.cn", "record_type": "COS"},
        ]
    )
    assert value == [
        {"Record": "obj.cos.cn", "Type": "COS"},
        {"Record": "a.example.com", "Type": "IP_DOMAIN"},
        {"Record": "b.example.com", "Type": "IP_DOMAIN", "Weight": 30},
    ]


def test_normalized_records_sdk_shape():
    value = mod._normalized_records([{"Record": "192.0.2.10", "Type": "IP_DOMAIN", "Weight": 70}], sdk=True)
    assert value == [{"Record": "192.0.2.10", "Type": "IP_DOMAIN", "Weight": 70}]


def test_desired_mapping():
    value = mod.desired(_params(name="app-origins", group_type="HTTP", host_header="origin.example.com"))
    assert value == {
        "Name": "app-origins",
        "Type": "HTTP",
        "HostHeader": "origin.example.com",
        "Records": [{"Record": "192.0.2.10", "Type": "IP_DOMAIN"}],
    }


# ---------------------------------------------------------------------------
# find_group tests
# ---------------------------------------------------------------------------


def test_find_group_no_match_returns_none(monkeypatch):
    fake = FakeTeoClient([_group(Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find_group(module, fake, FakeModels(), module.params) is None


def test_find_group_by_name(monkeypatch):
    fake = FakeTeoClient([_group(Name="other"), _group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="app-origins"))
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == "origin-group-1"


def test_find_group_by_group_id(monkeypatch):
    fake = FakeTeoClient([_group(), _group(GroupId="origin-group-2", Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(group_id="origin-group-2", name=None))
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == "origin-group-2"


def test_find_group_multiple_matches_fails(monkeypatch):
    fake = FakeTeoClient([_group(), _group(GroupId="origin-group-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="app-origins"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_group(module, fake, FakeModels(), module.params)
    assert "Multiple EdgeOne origin groups matched" in exc.value.args[0]["msg"]


def test_find_group_paginates_past_1000(monkeypatch):
    groups = [_group(GroupId="origin-group-bulk-%04d" % i, Name="bulk-%04d" % i) for i in range(1001)]
    groups.append(_group(Name="app-origins"))
    fake = FakeTeoClient(groups)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="app-origins"))
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == "origin-group-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribeOriginGroup"]
    assert len(list_calls) == 2  # pages of 1000
    assert [c[1].Offset for c in list_calls] == [0, 1000]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present", zone_id="zone-edge1")  # neither group_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name_and_record():
    module_args(state="present", zone_id="zone-edge1", name="app-origins")  # records empty
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and at least one record are required" in exc.value.args[0]["msg"]


def test_present_record_weight_out_of_range_fails():
    module_args(state="present", zone_id="zone-edge1", name="app-origins", records=[_record("192.0.2.10", weight=101)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "weight must be between 0 and 100" in exc.value.args[0]["msg"]


def test_general_group_rejects_non_ip_domain_record():
    module_args(state="present", zone_id="zone-edge1", name="app-origins", records=[_record("obj.cos.cn", "COS")])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "GENERAL origin groups only support IP_DOMAIN records" in exc.value.args[0]["msg"]


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


def test_present_creates_group(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(name="app-origins", records=[_record("192.0.2.10", weight=70)])
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["origin_group"]
    assert group["GroupId"] == "origin-group-10001"
    assert group["Name"] == "app-origins"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeOriginGroup") == 2  # find + refetch
    assert names.count("CreateOriginGroup") == 1
    create = [c for c in fake.calls if c[0] == "CreateOriginGroup"][0][1]
    assert create.Name == "app-origins"
    assert create.Records[0].Weight == 70


def test_present_creates_http_group_with_host_header(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(name="web-origins", group_type="HTTP", host_header="origin.example.com",
              records=[_record("192.0.2.10", weight=70), _record("192.0.2.11", weight=30)])
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["origin_group"]
    assert group["Type"] == "HTTP"
    assert group["HostHeader"] == "origin.example.com"
    assert len(group["Records"]) == 2
    assert sorted(r["Weight"] for r in group["Records"]) == [30, 70]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(records=[_record("192.0.2.10")])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["origin_group"]["GroupId"] == "origin-group-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyOriginGroup" not in names
    assert "CreateOriginGroup" not in names


def test_present_records_drift_triggers_update(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(records=[_record("192.0.2.10", weight=70), _record("192.0.2.11", weight=30)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(r["Record"] for r in result["origin_group"]["Records"]) == ["192.0.2.10", "192.0.2.11"]
    modify = [c for c in fake.calls if c[0] == "ModifyOriginGroup"][0][1]
    assert modify.GroupId == "origin-group-1"
    assert len(modify.Records) == 2


def test_present_rename_by_group_id(monkeypatch):
    fake = FakeTeoClient([_group(Name="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(group_id="origin-group-1", name="new-name", records=[_record("192.0.2.10")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin_group"]["Name"] == "new-name"
    assert len(fake.groups) == 1  # renamed in place


def test_present_host_header_drift_on_http_group(monkeypatch):
    fake = FakeTeoClient([_group(Type="HTTP", HostHeader="old.example.com")])
    _make_module(monkeypatch, fake)
    _run_args(group_type="HTTP", host_header="new.example.com", records=[_record("192.0.2.10")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin_group"]["HostHeader"] == "new.example.com"
    modify = [c for c in fake.calls if c[0] == "ModifyOriginGroup"][0][1]
    assert modify.HostHeader == "new.example.com"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin_group"] is None  # no real group created in check mode
    assert not any("CreateOriginGroup" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(records=[_record("192.0.2.99")]))
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported group is the pre-change state.
    assert result["origin_group"]["Records"][0]["Record"] == "192.0.2.10"
    assert not any("ModifyOriginGroup" == c[0] for c in fake.calls)


def test_absent_removes_group(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", group_id="origin-group-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin_group"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteOriginGroup"][0][1]
    assert delete.GroupId == "origin-group-1"
    assert fake.groups == []


def test_absent_by_name_removes(monkeypatch):
    fake = FakeTeoClient([_group(), _group(GroupId="origin-group-2", Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="other")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [g["GroupId"] for g in fake.groups] == ["origin-group-1"]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["origin_group"] is None
    assert not any("DeleteOriginGroup" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", name="app-origins"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin_group"] is not None  # pre-change state reported
    assert not any("DeleteOriginGroup" == c[0] for c in fake.calls)
    assert len(fake.groups) == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeTeoClient([_group(), _group(GroupId="origin-group-2")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple EdgeOne origin groups matched" in exc.value.args[0]["msg"]
