"""Unit tests for the cbs_auto_snapshot_policy write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cbs_auto_snapshot_policy.py`` with an in-memory fake CBS
client whose write operations mutate the policy store, so the module's
post-write ``find`` refetch converges immediately. Policies are matched by
``AutoSnapshotPolicyId`` or by ``AutoSnapshotPolicyName`` across the paged
DescribeAutoSnapshotPolicies list (Limit 100); schedules are SDK ``Policy``
objects deserialised from the module's raw schedule dicts, and the module
reconciles the exact set of bound cloud disks (unbind removed ids, bind
added ids) and refuses to delete a bound policy unless ``force_delete`` is
set.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cbs_auto_snapshot_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SCHEDULE = {"Hour": [2], "DayOfWeek": [0, 1, 2, 3, 4, 5, 6]}

POLICY = {
    "AutoSnapshotPolicyId": "asp-nightly",
    "AutoSnapshotPolicyName": "nightly",
    "Policy": [dict(SCHEDULE)],
    "IsActivated": 1,
    "IsPermanent": 0,
    "RetentionDays": 7,
    "DiskIdSet": [],
}


def _policy(**overrides):
    """API-shaped policy dict isolated from the shared constant."""
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "policy_id": None,
        "name": "nightly",
        "schedules": [dict(SCHEDULE)],
        "enabled": True,
        "permanent": False,
        "retention_days": 7,
        "disk_ids": [],
        "force_delete": False,
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


class _FakePolicy(object):
    """SDK ``Policy`` model stand-in supporting ``_deserialize``.

    ``plugins/modules/cbs_auto_snapshot_policy.py`` builds schedule objects
    through ``models.Policy()._deserialize(value)``; the plain
    ``FakeModels`` attribute factory returns classes without that method, so
    this model stores the deserialised keys and exposes them as attributes.
    """

    def __init__(self):
        self.__dict__["_data"] = {}

    def _deserialize(self, value):
        for key, val in (value or {}).items():
            self.__dict__["_data"][key] = val
        return self

    def __getattr__(self, name):
        try:
            return self.__dict__["_data"][name]
        except KeyError:
            raise AttributeError(name)


class CbsFakeModels(FakeModels):
    """Models namespace whose ``Policy`` resolves to a deserialisable class."""

    Policy = _FakePolicy


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


def _schedule_dicts(request):
    """Convert request.Policy model objects back into plain schedule dicts."""
    result = []
    for item in request.Policy or []:
        entry = {}
        for key in ("Hour", "DayOfWeek", "DayOfMonth", "IntervalDays"):
            if hasattr(item, key):
                entry[key] = getattr(item, key)
        result.append(entry)
    return result


class FakeCbsClient(object):
    """In-memory CbsClient stand-in.

    Stores API-shaped policy dicts. DescribeAutoSnapshotPolicies pages over
    the store honouring Offset/Limit so find pagination is exercised; the
    write operations mutate the store (including the DiskIdSet bindings) so
    post-write refetches converge.
    """

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []
        self._next_id = 10000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _policy_id(self):
        self._next_id += 1
        return "asp-fake-%05d" % self._next_id

    def DescribeAutoSnapshotPolicies(self, request):
        self._record("DescribeAutoSnapshotPolicies", request)
        page = self.policies[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            AutoSnapshotPolicySet=[FakeResource(dict(p)) for p in page],
            TotalCount=len(self.policies),
            RequestId="req-fake",
        )

    def CreateAutoSnapshotPolicy(self, request):
        self._record("CreateAutoSnapshotPolicy", request)
        policy_id = self._policy_id()
        self.policies.append(
            {
                "AutoSnapshotPolicyId": policy_id,
                "AutoSnapshotPolicyName": request.AutoSnapshotPolicyName,
                "Policy": _schedule_dicts(request),
                "IsActivated": 1 if request.IsActivated else 0,
                "IsPermanent": 1 if request.IsPermanent else 0,
                "RetentionDays": request.RetentionDays,
                "DiskIdSet": [],
            }
        )
        return SimpleNamespace(AutoSnapshotPolicyId=policy_id, RequestId="req-fake")

    def ModifyAutoSnapshotPolicyAttribute(self, request):
        self._record("ModifyAutoSnapshotPolicyAttribute", request)
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") != request.AutoSnapshotPolicyId:
                continue
            stored["AutoSnapshotPolicyName"] = request.AutoSnapshotPolicyName
            stored["Policy"] = _schedule_dicts(request)
            stored["IsActivated"] = 1 if request.IsActivated else 0
            stored["IsPermanent"] = 1 if request.IsPermanent else 0
            stored["RetentionDays"] = request.RetentionDays
        return SimpleNamespace(RequestId="req-fake")

    @staticmethod
    def _apply_bindings(stored, disk_ids, bind):
        existing = set(stored.get("DiskIdSet") or [])
        if bind:
            for disk_id in sorted(disk_ids - existing):
                stored.setdefault("DiskIdSet", []).append(disk_id)
        else:
            stored["DiskIdSet"] = [d for d in stored.get("DiskIdSet") or [] if d not in disk_ids]

    def BindAutoSnapshotPolicy(self, request):
        self._record("BindAutoSnapshotPolicy", request)
        disk_ids = set(request.DiskIds or [])
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") == request.AutoSnapshotPolicyId:
                self._apply_bindings(stored, disk_ids, bind=True)
        return SimpleNamespace(RequestId="req-fake")

    def UnbindAutoSnapshotPolicy(self, request):
        self._record("UnbindAutoSnapshotPolicy", request)
        disk_ids = set(request.DiskIds or [])
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") == request.AutoSnapshotPolicyId:
                self._apply_bindings(stored, disk_ids, bind=False)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAutoSnapshotPolicies(self, request):
        self._record("DeleteAutoSnapshotPolicies", request)
        self.policies = [p for p in self.policies if p.get("AutoSnapshotPolicyId") not in (request.AutoSnapshotPolicyIds or [])]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (CbsFakeModels(), SimpleNamespace(CbsClient=object)),
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
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_describe_request_without_policy_id():
    request = mod.describe_request(CbsFakeModels(), _params(), offset=7)
    assert request.Offset == 7
    assert request.Limit == 100
    assert not hasattr(request, "AutoSnapshotPolicyIds")


def test_describe_request_with_policy_id():
    request = mod.describe_request(CbsFakeModels(), _params(policy_id="asp-xyz"), offset=0)
    assert request.AutoSnapshotPolicyIds == ["asp-xyz"]


def test_policies_deserialise_schedule_dicts():
    items = mod._policies(CbsFakeModels(), [dict(SCHEDULE), {"Hour": [3], "DayOfMonth": [1, 15], "IntervalDays": 0}])
    assert len(items) == 2
    assert items[0].Hour == [2]
    assert items[0].DayOfWeek == [0, 1, 2, 3, 4, 5, 6]
    assert items[1].DayOfMonth == [1, 15]


def test_policies_empty_input():
    assert mod._policies(CbsFakeModels(), []) == []


def test_create_request_fields():
    request = mod.create_request(CbsFakeModels(), _params(permanent=True, retention_days=30))
    assert request.AutoSnapshotPolicyName == "nightly"
    assert request.IsActivated is True
    assert request.IsPermanent is True
    assert request.RetentionDays == 30
    assert len(request.Policy) == 1
    assert request.Policy[0].Hour == [2]


def test_update_request_fields():
    request = mod.update_request(CbsFakeModels(), _params(enabled=False, retention_days=3), "asp-xyz")
    assert request.AutoSnapshotPolicyId == "asp-xyz"
    assert request.AutoSnapshotPolicyName == "nightly"
    assert request.IsActivated is False
    assert request.IsPermanent is False
    assert request.RetentionDays == 3
    assert len(request.Policy) == 1


def test_delete_request_fields():
    request = mod.delete_request(CbsFakeModels(), "asp-xyz")
    assert request.AutoSnapshotPolicyIds == ["asp-xyz"]


def test_bind_request_sorts_ids():
    request = mod.bind_request(CbsFakeModels(), "asp-xyz", {"disk-b", "disk-a"})
    assert request.AutoSnapshotPolicyId == "asp-xyz"
    assert request.DiskIds == ["disk-a", "disk-b"]


def test_unbind_request_sorts_ids():
    request = mod.unbind_request(CbsFakeModels(), "asp-xyz", {"disk-b", "disk-a"})
    assert request.DiskIds == ["disk-a", "disk-b"]


# ---------------------------------------------------------------------------
# _schedule_key / _schedules / comparable / desired tests
# ---------------------------------------------------------------------------


def test_schedule_key_orders_by_components():
    assert mod._schedule_key({"Hour": [2], "DayOfWeek": [1, 2]}) < mod._schedule_key({"Hour": [2], "DayOfWeek": [1, 3]})
    assert mod._schedule_key({"Hour": [1]}) < mod._schedule_key({"Hour": [2]})


def test_schedule_key_missing_components_default_empty():
    assert mod._schedule_key({}) == ((), (), (), 0)
    assert mod._schedule_key({"IntervalDays": 3}) == ((), (), (), 3)


def test_schedules_sorts_by_key():
    later = {"Hour": [6]}
    earlier = {"Hour": [2]}
    assert mod._schedules([later, earlier]) == [earlier, later]


def test_schedules_empty_input():
    assert mod._schedules(None) == []
    assert mod._schedules([]) == []


def test_comparable_mapping():
    value = mod.comparable(_policy(DiskIdSet=["disk-b", "disk-a"], Policy=[dict(SCHEDULE)]))
    assert value == {
        "AutoSnapshotPolicyName": "nightly",
        "Policy": [dict(SCHEDULE)],
        "IsActivated": True,
        "IsPermanent": False,
        "RetentionDays": 7,
        "DiskIds": ["disk-a", "disk-b"],
    }


def test_comparable_defaults():
    value = mod.comparable({"AutoSnapshotPolicyName": "nightly", "Policy": None})
    assert value["IsActivated"] is False
    assert value["IsPermanent"] is False
    assert value["RetentionDays"] == 0
    assert value["DiskIds"] == []
    assert value["Policy"] == []


def test_comparable_sorts_policy_schedules():
    value = mod.comparable({"AutoSnapshotPolicyName": "nightly", "Policy": [{"Hour": [6]}, {"Hour": [2]}]})
    assert [entry["Hour"] for entry in value["Policy"]] == [[2], [6]]


def test_desired_mapping():
    value = mod.desired(_params(permanent=True, retention_days=30, disk_ids=["disk-b", "disk-a"]))
    assert value == {
        "AutoSnapshotPolicyName": "nightly",
        "Policy": [dict(SCHEDULE)],
        "IsActivated": True,
        "IsPermanent": True,
        "RetentionDays": 30,
        "DiskIds": ["disk-a", "disk-b"],
    }


def test_desired_disabled_policy():
    value = mod.desired(_params(enabled=False))
    assert value["IsActivated"] is False


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCbsClient([_policy(AutoSnapshotPolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, CbsFakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeCbsClient([_policy(AutoSnapshotPolicyName="other"), _policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    value = mod.find(module, fake, CbsFakeModels(), module.params)
    assert value["AutoSnapshotPolicyId"] == "asp-nightly"


def test_find_by_policy_id(monkeypatch):
    fake = FakeCbsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-other", AutoSnapshotPolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(policy_id="asp-other", name=None))
    value = mod.find(module, fake, CbsFakeModels(), module.params)
    assert value["AutoSnapshotPolicyId"] == "asp-other"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeCbsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, CbsFakeModels(), module.params)
    assert "Multiple CBS automatic snapshot policies matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    policies = [_policy(AutoSnapshotPolicyId="asp-bulk-%04d" % i, AutoSnapshotPolicyName="bulk-%04d" % i) for i in range(250)]
    policies.append(_policy())
    fake = FakeCbsClient(policies)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    value = mod.find(module, fake, CbsFakeModels(), module.params)
    assert value["AutoSnapshotPolicyId"] == "asp-nightly"
    list_calls = [c for c in fake.calls if c[0] == "DescribeAutoSnapshotPolicies"]
    assert len(list_calls) == 3  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100, 200]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_policy_id_or_name():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "policy_id" in exc.value.args[0]["msg"]
    assert "name" in exc.value.args[0]["msg"]


def test_present_requires_name():
    module_args(state="present", policy_id="asp-xyz")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name and schedules are required when state=present"


def test_present_requires_schedules():
    module_args(state="present", name="nightly", schedules=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name and schedules are required when state=present"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (CbsFakeModels(), SimpleNamespace(CbsClient=object)),
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


def test_present_creates_and_binds(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _run_args(disk_ids=["disk-b", "disk-a"])
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["policy"]
    assert policy["AutoSnapshotPolicyId"] == "asp-fake-10001"
    assert policy["AutoSnapshotPolicyName"] == "nightly"
    assert policy["DiskIdSet"] == ["disk-a", "disk-b"]
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAutoSnapshotPolicies") == 2  # find + refetch
    assert names.count("CreateAutoSnapshotPolicy") == 1
    assert names.count("BindAutoSnapshotPolicy") == 1
    assert "UnbindAutoSnapshotPolicy" not in names
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.DiskIds == ["disk-a", "disk-b"]


def test_present_creates_without_bindings(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["AutoSnapshotPolicyName"] == "nightly"
    names = [c[0] for c in fake.calls]
    assert "BindAutoSnapshotPolicy" not in names
    assert "UnbindAutoSnapshotPolicy" not in names


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["AutoSnapshotPolicyId"] == "asp-nightly"
    names = [c[0] for c in fake.calls]
    assert not any(name in names for name in ("ModifyAutoSnapshotPolicyAttribute", "BindAutoSnapshotPolicy", "UnbindAutoSnapshotPolicy"))


def test_present_rename_by_policy_id(monkeypatch):
    fake = FakeCbsClient([_policy(AutoSnapshotPolicyName="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(name="new-name", policy_id="asp-nightly")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["AutoSnapshotPolicyName"] == "new-name"
    assert len(fake.policies) == 1  # renamed in place


def test_present_schedule_drift_triggers_update(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(schedules=[{"Hour": [3]}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Policy"] == [{"Hour": [3]}]
    update = [c for c in fake.calls if c[0] == "ModifyAutoSnapshotPolicyAttribute"][0][1]
    assert update.AutoSnapshotPolicyId == "asp-nightly"
    assert update.Policy[0].Hour == [3]


def test_present_enable_toggle_triggers_update(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["IsActivated"] == 0
    update = [c for c in fake.calls if c[0] == "ModifyAutoSnapshotPolicyAttribute"][0][1]
    assert update.IsActivated is False


def test_present_retention_drift_triggers_update(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(retention_days=30, permanent=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["RetentionDays"] == 30
    assert result["policy"]["IsPermanent"] == 1


def test_present_binding_added(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a"])])
    _make_module(monkeypatch, fake)
    _run_args(disk_ids=["disk-a", "disk-b"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["DiskIdSet"] == ["disk-a", "disk-b"]
    names = [c[0] for c in fake.calls]
    assert "BindAutoSnapshotPolicy" in names
    assert "UnbindAutoSnapshotPolicy" not in names
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.DiskIds == ["disk-b"]


def test_present_binding_removed(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a", "disk-b"])])
    _make_module(monkeypatch, fake)
    _run_args(disk_ids=["disk-a"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["DiskIdSet"] == ["disk-a"]
    names = [c[0] for c in fake.calls]
    assert "UnbindAutoSnapshotPolicy" in names
    assert "BindAutoSnapshotPolicy" not in names
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.DiskIds == ["disk-b"]


def test_present_binding_swap_unbinds_and_binds(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a"])])
    _make_module(monkeypatch, fake)
    _run_args(disk_ids=["disk-c"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["DiskIdSet"] == ["disk-c"]
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.DiskIds == ["disk-a"]
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.DiskIds == ["disk-c"]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(disk_ids=["disk-a"]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None  # no real policy created in check mode
    assert not any(name in [c[0] for c in fake.calls] for name in ("CreateAutoSnapshotPolicy", "BindAutoSnapshotPolicy"))


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(schedules=[{"Hour": [3]}]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Policy"] == [dict(SCHEDULE)]  # pre-change state
    assert not any("ModifyAutoSnapshotPolicyAttribute" == c[0] for c in fake.calls)


def test_absent_removes_unbound_policy(monkeypatch):
    fake = FakeCbsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteAutoSnapshotPolicies") == 1
    assert "UnbindAutoSnapshotPolicy" not in names
    assert fake.policies == []


def test_absent_refuses_bound_policy_without_force(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a"])])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "force_delete=true" in payload["msg"]
    assert payload["disk_ids"] == ["disk-a"]
    assert not any("DeleteAutoSnapshotPolicies" == c[0] for c in fake.calls)


def test_absent_force_delete_unbinds_then_deletes(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a", "disk-b"])])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", force_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteAutoSnapshotPolicies") == 1
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.DiskIds == ["disk-a", "disk-b"]
    assert fake.policies == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCbsClient([_policy(AutoSnapshotPolicyName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert not any("DeleteAutoSnapshotPolicies" == c[0] for c in fake.calls)


def test_absent_check_mode_force_delete_is_dry_run(monkeypatch):
    fake = FakeCbsClient([_policy(DiskIdSet=["disk-a"])])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", force_delete=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is not None  # pre-change state reported
    assert not any(name in [c[0] for c in fake.calls] for name in ("UnbindAutoSnapshotPolicy", "DeleteAutoSnapshotPolicies"))
    assert len(fake.policies) == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeCbsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-2")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CBS automatic snapshot policies matched" in exc.value.args[0]["msg"]
