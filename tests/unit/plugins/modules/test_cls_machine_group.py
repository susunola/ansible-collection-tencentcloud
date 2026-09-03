"""Unit tests for the cls_machine_group write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/cls_machine_group.py`` with an in-memory fake CLS
client whose write operations mutate the group store, so the module's
post-write ``find`` refetch converges immediately. Groups are matched by
``GroupId`` or by name via a server-side Filter (``groupId`` /
``groupName``) over DescribeMachineGroups. ``Type`` (ip vs label) is
immutable after creation (require_immutable_unchanged) and ``OSType`` is
create-only. Tags round-trip through a Key/Value model pair. After a
create the module refetches by name (no id is read back); after a modify
it refetches by the existing GroupId. In check mode a would-be create
reports ``machine_group=None`` and a would-be update the pre-change group.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_machine_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "GroupId": "group-abc123",
    "GroupName": "production-web",
    "MachineGroupType": {"Type": "ip", "Values": ["10.0.0.1", "10.0.0.2"]},
    "Tags": [{"Key": "env", "Value": "prod"}],
    "AutoUpdate": False,
    "UpdateStartTime": "00:00:00",
    "UpdateEndTime": "23:59:59",
    "ServiceLogging": False,
    "DelayCleanupTime": 0,
}


def _group(**overrides):
    """API-shaped group dict isolated from the shared constant."""
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "group_id": None,
        "name": "production-web",
        "group_type": "ip",
        "values": ["10.0.0.1", "10.0.0.2"],
        "tags": {"env": "prod"},
        "auto_update": False,
        "update_start_time": "00:00:00",
        "update_end_time": "23:59:59",
        "service_logging": False,
        "delay_cleanup_time": 0,
        "os_type": 0,
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


class FakeClsClient(object):
    """In-memory ClsClient stand-in for machine groups.

    Stores API-shaped group dicts keyed by GroupId. Describe applies the
    optional groupId / groupName Filter and returns the matching items in
    one call; write operations mutate the store so post-write refetches
    converge.
    """

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _filtered(self, request):
        groups = self.groups
        for item in getattr(request, "Filters", None) or []:
            key = "GroupId" if item.Key == "groupId" else "GroupName"
            groups = [g for g in groups if g.get(key) == item.Values[0]]
        return groups

    @staticmethod
    def _store_type(value):
        return {"Type": value.Type, "Values": sorted(value.Values or [])}

    @staticmethod
    def _store_tags(values):
        return [{"Key": t.Key, "Value": t.Value} for t in (values or [])]

    def DescribeMachineGroups(self, request):
        self._record("DescribeMachineGroups", request)
        groups = self._filtered(request)
        return SimpleNamespace(
            MachineGroups=[FakeResource(dict(g)) for g in groups],
            RequestId="req-fake",
        )

    def CreateMachineGroup(self, request):
        self._record("CreateMachineGroup", request)
        group_id = "group-new%d" % self._next_id
        self._next_id += 1
        self.groups.append(
            {
                "GroupId": group_id,
                "GroupName": request.GroupName,
                "MachineGroupType": self._store_type(request.MachineGroupType),
                "Tags": self._store_tags(request.Tags),
                "AutoUpdate": request.AutoUpdate,
                "UpdateStartTime": request.UpdateStartTime,
                "UpdateEndTime": request.UpdateEndTime,
                "ServiceLogging": request.ServiceLogging,
                "DelayCleanupTime": request.DelayCleanupTime,
            }
        )
        return SimpleNamespace(GroupId=group_id, RequestId="req-fake")

    def ModifyMachineGroup(self, request):
        self._record("ModifyMachineGroup", request)
        for stored in self.groups:
            if stored.get("GroupId") != request.GroupId:
                continue
            stored["GroupName"] = request.GroupName
            stored["MachineGroupType"] = self._store_type(request.MachineGroupType)
            stored["Tags"] = self._store_tags(request.Tags)
            stored["AutoUpdate"] = request.AutoUpdate
            stored["UpdateStartTime"] = request.UpdateStartTime
            stored["UpdateEndTime"] = request.UpdateEndTime
            stored["ServiceLogging"] = request.ServiceLogging
            stored["DelayCleanupTime"] = request.DelayCleanupTime
        return SimpleNamespace(RequestId="req-fake")

    def DeleteMachineGroup(self, request):
        self._record("DeleteMachineGroup", request)
        self.groups = [g for g in self.groups if g.get("GroupId") != request.GroupId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ClsClient=object)),
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


def test_group_type_builder():
    value = mod.group_type(FakeModels(), _params(group_type="label", values=["b", "a"]))
    assert value.Type == "label"
    assert value.Values == ["a", "b"]  # sorted


def test_tag_models_sorted_and_stringified():
    items = mod.tag_models(FakeModels(), {"zebra": 1, "alpha": True})
    assert [(i.Key, i.Value) for i in items] == [("alpha", "True"), ("zebra", "1")]
    assert mod.tag_models(FakeModels(), {}) == []


def test_normalize_flattens_nested_shape():
    value = _group(
        MachineGroupType={"Type": "ip", "Values": ["10.0.0.2", "10.0.0.1"]},
        AutoUpdate=True,
        ServiceLogging=True,
        DelayCleanupTime=3,
    )
    norm = mod.normalize(value)
    assert norm["GroupName"] == "production-web"
    assert norm["Type"] == "ip"
    assert norm["Values"] == ["10.0.0.1", "10.0.0.2"]  # sorted
    assert norm["Tags"] == {"env": "prod"}
    assert norm["AutoUpdate"] is True
    assert norm["ServiceLogging"] is True
    assert norm["DelayCleanupTime"] == 3


def test_normalize_defaults():
    norm = mod.normalize({"GroupName": "x"})
    assert norm["Type"] is None
    assert norm["Values"] == []
    assert norm["Tags"] == {}
    assert norm["AutoUpdate"] is False
    assert norm["DelayCleanupTime"] == 0


def test_wanted_maps_fields():
    target = mod.wanted(_params(auto_update=True, delay_cleanup_time=5))
    assert target["GroupName"] == "production-web"
    assert target["Values"] == ["10.0.0.1", "10.0.0.2"]
    assert target["Tags"] == {"env": "prod"}
    assert target["AutoUpdate"] is True
    assert target["DelayCleanupTime"] == 5


def test_apply_create_includes_os_type():
    request = mod.apply(FakeModels().CreateMachineGroupRequest(), FakeModels(), _params(os_type=1), None)
    assert request.GroupName == "production-web"
    assert request.MachineGroupType.Type == "ip"
    assert request.OSType == 1
    assert not hasattr(request, "GroupId")


def test_apply_update_sets_group_id_and_omits_os_type():
    request = mod.apply(FakeModels().ModifyMachineGroupRequest(), FakeModels(), _params(name="renamed"), "group-abc123")
    assert request.GroupId == "group-abc123"
    assert request.GroupName == "renamed"
    assert not hasattr(request, "OSType")


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_group_id(monkeypatch):
    fake = FakeClsClient([_group(), _group(GroupId="group-other", GroupName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(group_id="group-other", name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == "group-other"


def test_find_by_name(monkeypatch):
    fake = FakeClsClient([_group(GroupName="other"), _group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-web"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == "group-abc123"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeClsClient([_group(), _group(GroupId="group-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-web"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple CLS machine groups have the requested name" in payload["msg"]
    assert payload["name"] == "production-web"


def test_find_builds_name_filter_request(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-web"))
    mod.find(module, fake, FakeModels(), module.params)
    describe = [c for c in fake.calls if c[0] == "DescribeMachineGroups"][0][1]
    assert describe.Filters[0].Key == "groupName"
    assert describe.Filters[0].Values == ["production-web"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args()  # neither group_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name():
    module_args(group_id="group-abc123", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_group(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["machine_group"]
    assert group["GroupId"] == "group-new100"
    assert group["GroupName"] == "production-web"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeMachineGroups") == 2  # find + post-create refetch
    assert names.count("CreateMachineGroup") == 1
    create = [c for c in fake.calls if c[0] == "CreateMachineGroup"][0][1]
    assert create.OSType == 0
    assert create.MachineGroupType.Values == ["10.0.0.1", "10.0.0.2"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["machine_group"]["GroupId"] == "group-abc123"
    names = [c[0] for c in fake.calls]
    assert "ModifyMachineGroup" not in names
    assert "CreateMachineGroup" not in names


def test_present_values_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", values=["10.0.0.9"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["MachineGroupType"]["Values"] == ["10.0.0.9"]
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyMachineGroup") == 1
    assert "CreateMachineGroup" not in names
    modify = [c for c in fake.calls if c[0] == "ModifyMachineGroup"][0][1]
    assert modify.GroupId == "group-abc123"
    assert not hasattr(modify, "OSType")  # create-only


def test_present_tags_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", tags={"env": "prod", "tier": "web"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["Tags"] == [{"Key": "env", "Value": "prod"}, {"Key": "tier", "Value": "web"}]


def test_present_auto_update_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", auto_update=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["AutoUpdate"] is True


def test_present_update_window_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", update_start_time="02:00:00", update_end_time="06:00:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["UpdateStartTime"] == "02:00:00"
    modify = [c for c in fake.calls if c[0] == "ModifyMachineGroup"][0][1]
    assert modify.UpdateStartTime == "02:00:00"


def test_present_service_logging_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", service_logging=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["ServiceLogging"] is True


def test_present_type_immutable_fails(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="group-abc123", group_type="label")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"Type": {"before": "ip", "after": "label"}}
    assert not any("ModifyMachineGroup" == c[0] for c in fake.calls)


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeMachineGroups"]  # find only
    assert not any("CreateMachineGroup" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(group_id="group-abc123", values=["10.0.0.9"]).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["GroupId"] == "group-abc123"  # pre-change group reported
    assert not any("ModifyMachineGroup" == c[0] for c in fake.calls)


def test_check_mode_type_drift_still_fails(monkeypatch):
    # the immutable guard runs before the check-mode gate
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(group_id="group-abc123", group_type="label").items() if v is not None})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Immutable fields cannot be changed" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ClsClient=object)),
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


def test_absent_deletes_group(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="production-web")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteMachineGroup"][0][1]
    assert delete.GroupId == "group-abc123"
    assert fake.groups == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["machine_group"] is None
    assert not any("DeleteMachineGroup" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["machine_group"]["GroupId"] == "group-abc123"  # pre-change group reported
    assert not any("DeleteMachineGroup" == c[0] for c in fake.calls)
    assert len(fake.groups) == 1
