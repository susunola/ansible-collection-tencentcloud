"""Unit tests for the cfs_auto_snapshot_policy write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cfs_auto_snapshot_policy.py`` with an in-memory fake CFS
client whose write operations mutate the policy store, so the module's
post-write ``find`` refetch converges immediately. Policies are matched by
``AutoSnapshotPolicyId`` or by ``PolicyName`` across the paged
DescribeAutoSnapshotPolicies list; the module reconciles the exact set of
bound file systems (unbind removed ids, bind added ids) and refuses to
delete a bound policy unless ``force_delete`` is set.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_auto_snapshot_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POLICY = {
    "AutoSnapshotPolicyId": "asp-nightly",
    "PolicyName": "nightly",
    "Hour": "00",
    "DayOfWeek": "",
    "DayOfMonth": "",
    "IntervalDays": 0,
    "AliveDays": 0,
    "IsActivated": 1,
    "FileSystems": [],
}


def _policy(**overrides):
    """API-shaped policy dict isolated from the shared constant."""
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _fs(fsid):
    return {"FileSystemId": fsid}


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "policy_id": None,
        "name": "nightly",
        "hour": "00",
        "day_of_week": "",
        "day_of_month": "",
        "interval_days": 0,
        "alive_days": 0,
        "enabled": True,
        "file_system_ids": [],
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


class FakeCfsClient(object):
    """In-memory CfsClient stand-in.

    Stores API-shaped policy dicts. DescribeAutoSnapshotPolicies pages over
    the store honouring Offset/Limit so find pagination is exercised; the
    write operations mutate the store (including the FileSystems bindings)
    so post-write refetches converge.
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
            AutoSnapshotPolicies=[FakeResource(dict(p)) for p in page],
            TotalCount=len(self.policies),
            RequestId="req-fake",
        )

    def CreateAutoSnapshotPolicy(self, request):
        self._record("CreateAutoSnapshotPolicy", request)
        policy_id = self._policy_id()
        self.policies.append(
            {
                "AutoSnapshotPolicyId": policy_id,
                "PolicyName": request.PolicyName,
                "Hour": request.Hour,
                "DayOfWeek": request.DayOfWeek,
                "DayOfMonth": request.DayOfMonth,
                "IntervalDays": request.IntervalDays,
                "AliveDays": request.AliveDays,
                "IsActivated": 1,
                "FileSystems": [],
            }
        )
        return SimpleNamespace(AutoSnapshotPolicyId=policy_id, RequestId="req-fake")

    def UpdateAutoSnapshotPolicy(self, request):
        self._record("UpdateAutoSnapshotPolicy", request)
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") != request.AutoSnapshotPolicyId:
                continue
            stored["PolicyName"] = request.PolicyName
            stored["Hour"] = request.Hour
            stored["DayOfWeek"] = request.DayOfWeek
            stored["DayOfMonth"] = request.DayOfMonth
            stored["IntervalDays"] = request.IntervalDays
            stored["AliveDays"] = request.AliveDays
            stored["IsActivated"] = request.IsActivated
        return SimpleNamespace(RequestId="req-fake")

    @staticmethod
    def _apply_bindings(stored, fsids, bind):
        existing = {item["FileSystemId"] for item in stored.get("FileSystems") or []}
        if bind:
            for fsid in sorted(fsids - existing):
                stored.setdefault("FileSystems", []).append(_fs(fsid))
        else:
            stored["FileSystems"] = [item for item in stored.get("FileSystems") or [] if item["FileSystemId"] not in fsids]

    def BindAutoSnapshotPolicy(self, request):
        self._record("BindAutoSnapshotPolicy", request)
        fsids = {x for x in (request.FileSystemIds or "").split(",") if x}
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") == request.AutoSnapshotPolicyId:
                self._apply_bindings(stored, fsids, bind=True)
        return SimpleNamespace(RequestId="req-fake")

    def UnbindAutoSnapshotPolicy(self, request):
        self._record("UnbindAutoSnapshotPolicy", request)
        fsids = {x for x in (request.FileSystemIds or "").split(",") if x}
        for stored in self.policies:
            if stored.get("AutoSnapshotPolicyId") == request.AutoSnapshotPolicyId:
                self._apply_bindings(stored, fsids, bind=False)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAutoSnapshotPolicy(self, request):
        self._record("DeleteAutoSnapshotPolicy", request)
        self.policies = [p for p in self.policies if p.get("AutoSnapshotPolicyId") != request.AutoSnapshotPolicyId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CfsClient=object)),
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
    request = mod.describe_request(FakeModels(), _params(), offset=7)
    assert request.Offset == 7
    assert request.Limit == 100
    assert not hasattr(request, "AutoSnapshotPolicyId")


def test_describe_request_with_policy_id():
    request = mod.describe_request(FakeModels(), _params(policy_id="asp-xyz"), offset=0)
    assert request.AutoSnapshotPolicyId == "asp-xyz"


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(hour="02", day_of_week="1,2,3", alive_days=30, day_of_month="", interval_days=0))
    assert request.PolicyName == "nightly"
    assert request.Hour == "02"
    assert request.DayOfWeek == "1,2,3"
    assert request.DayOfMonth == ""
    assert request.IntervalDays == 0
    assert request.AliveDays == 30


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(hour="03", enabled=False, alive_days=7), "asp-xyz")
    assert request.AutoSnapshotPolicyId == "asp-xyz"
    assert request.PolicyName == "nightly"
    assert request.Hour == "03"
    assert request.DayOfWeek == ""
    assert request.AliveDays == 7
    assert request.IsActivated == 0
    assert request.IntervalDays == 0


def test_update_request_enabled_true_sets_activated():
    request = mod.update_request(FakeModels(), _params(enabled=True), "asp-xyz")
    assert request.IsActivated == 1


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "asp-xyz")
    assert request.AutoSnapshotPolicyId == "asp-xyz"


def test_bind_request_sorts_and_joins():
    request = mod.bind_request(FakeModels(), "asp-xyz", {"cfs-b", "cfs-a"})
    assert request.AutoSnapshotPolicyId == "asp-xyz"
    assert request.FileSystemIds == "cfs-a,cfs-b"


def test_unbind_request_sorts_and_joins():
    request = mod.unbind_request(FakeModels(), "asp-xyz", {"cfs-b", "cfs-a"})
    assert request.FileSystemIds == "cfs-a,cfs-b"


# ---------------------------------------------------------------------------
# _bound / comparable / desired tests
# ---------------------------------------------------------------------------


def test_bound_sorts_ids():
    value = mod._bound({"FileSystems": [_fs("cfs-b"), _fs("cfs-a"), _fs("cfs-c")]})
    assert value == ["cfs-a", "cfs-b", "cfs-c"]


def test_bound_filters_empty_entries():
    value = mod._bound({"FileSystems": [_fs("cfs-a"), {"FileSystemId": None}, {}]})
    assert value == ["cfs-a"]


def test_bound_empty_when_missing():
    assert mod._bound({"FileSystems": None}) == []
    assert mod._bound({}) == []


def test_comparable_mapping():
    value = mod.comparable(
        _policy(
            Hour="02",
            DayOfWeek="1,2,3,4,5,6,7",
            IntervalDays=0,
            AliveDays=30,
            FileSystems=[_fs("cfs-b"), _fs("cfs-a")],
        )
    )
    assert value == {
        "PolicyName": "nightly",
        "Hour": "02",
        "DayOfWeek": "1,2,3,4,5,6,7",
        "DayOfMonth": "",
        "IntervalDays": 0,
        "AliveDays": 30,
        "IsActivated": 1,
        "FileSystemIds": ["cfs-a", "cfs-b"],
    }


def test_comparable_defaults():
    value = mod.comparable({"PolicyName": "nightly", "FileSystems": []})
    assert value["Hour"] == ""
    assert value["DayOfWeek"] == ""
    assert value["DayOfMonth"] == ""
    assert value["IntervalDays"] == 0
    assert value["AliveDays"] == 0
    assert value["IsActivated"] == 0
    assert value["FileSystemIds"] == []


def test_desired_mapping():
    value = mod.desired(_params(hour="02", alive_days=30, file_system_ids=["cfs-b", "cfs-a"]))
    assert value == {
        "PolicyName": "nightly",
        "Hour": "02",
        "DayOfWeek": "",
        "DayOfMonth": "",
        "IntervalDays": 0,
        "AliveDays": 30,
        "IsActivated": 1,
        "FileSystemIds": ["cfs-a", "cfs-b"],
    }


def test_desired_disabled_policy():
    value = mod.desired(_params(enabled=False))
    assert value["IsActivated"] == 0


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCfsClient([_policy(PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeCfsClient([_policy(PolicyName="other"), _policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["AutoSnapshotPolicyId"] == "asp-nightly"


def test_find_by_policy_id(monkeypatch):
    fake = FakeCfsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-other", PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(policy_id="asp-other", name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["AutoSnapshotPolicyId"] == "asp-other"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeCfsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple CFS auto-snapshot policies matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    policies = [_policy(AutoSnapshotPolicyId="asp-bulk-%04d" % i, PolicyName="bulk-%04d" % i) for i in range(250)]
    policies.append(_policy())
    fake = FakeCfsClient(policies)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly"))
    value = mod.find(module, fake, FakeModels(), module.params)
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
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CfsClient=object)),
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
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _run_args(file_system_ids=["cfs-b", "cfs-a"])
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["policy"]
    assert policy["AutoSnapshotPolicyId"] == "asp-fake-10001"
    assert policy["PolicyName"] == "nightly"
    assert sorted(item["FileSystemId"] for item in policy["FileSystems"]) == ["cfs-a", "cfs-b"]
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAutoSnapshotPolicies") == 2  # find + refetch
    assert names.count("CreateAutoSnapshotPolicy") == 1
    assert names.count("BindAutoSnapshotPolicy") == 1
    assert "UnbindAutoSnapshotPolicy" not in names
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.FileSystemIds == "cfs-a,cfs-b"


def test_present_creates_without_bindings(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "nightly"
    names = [c[0] for c in fake.calls]
    assert "BindAutoSnapshotPolicy" not in names
    assert "UnbindAutoSnapshotPolicy" not in names


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCfsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["AutoSnapshotPolicyId"] == "asp-nightly"
    names = [c[0] for c in fake.calls]
    assert not any(name in names for name in ("UpdateAutoSnapshotPolicy", "BindAutoSnapshotPolicy", "UnbindAutoSnapshotPolicy"))


def test_present_schedule_drift_triggers_update(monkeypatch):
    fake = FakeCfsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(hour="02", alive_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Hour"] == "02"
    assert result["policy"]["AliveDays"] == 30
    update = [c for c in fake.calls if c[0] == "UpdateAutoSnapshotPolicy"][0][1]
    assert update.AutoSnapshotPolicyId == "asp-nightly"
    assert update.Hour == "02"


def test_present_disable_toggle_triggers_update(monkeypatch):
    fake = FakeCfsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["IsActivated"] == 0
    update = [c for c in fake.calls if c[0] == "UpdateAutoSnapshotPolicy"][0][1]
    assert update.IsActivated == 0


def test_present_rename_by_policy_id(monkeypatch):
    fake = FakeCfsClient([_policy(PolicyName="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(name="new-name", policy_id="asp-nightly")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "new-name"
    assert len(fake.policies) == 1  # renamed in place


def test_present_binding_added(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a")])])
    _make_module(monkeypatch, fake)
    _run_args(file_system_ids=["cfs-a", "cfs-b"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(item["FileSystemId"] for item in result["policy"]["FileSystems"]) == ["cfs-a", "cfs-b"]
    names = [c[0] for c in fake.calls]
    assert "BindAutoSnapshotPolicy" in names
    assert "UnbindAutoSnapshotPolicy" not in names
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.FileSystemIds == "cfs-b"


def test_present_binding_removed(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a"), _fs("cfs-b")])])
    _make_module(monkeypatch, fake)
    _run_args(file_system_ids=["cfs-a"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(item["FileSystemId"] for item in result["policy"]["FileSystems"]) == ["cfs-a"]
    names = [c[0] for c in fake.calls]
    assert "UnbindAutoSnapshotPolicy" in names
    assert "BindAutoSnapshotPolicy" not in names
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.FileSystemIds == "cfs-b"


def test_present_binding_swap_unbinds_and_binds(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a")])])
    _make_module(monkeypatch, fake)
    _run_args(file_system_ids=["cfs-c"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(item["FileSystemId"] for item in result["policy"]["FileSystems"]) == ["cfs-c"]
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.FileSystemIds == "cfs-a"
    bind = [c for c in fake.calls if c[0] == "BindAutoSnapshotPolicy"][0][1]
    assert bind.FileSystemIds == "cfs-c"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(file_system_ids=["cfs-a"]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None  # no real policy created in check mode
    assert not any(name in [c[0] for c in fake.calls] for name in ("CreateAutoSnapshotPolicy", "BindAutoSnapshotPolicy"))


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCfsClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(hour="02"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Hour"] == "00"  # pre-change state
    assert not any("UpdateAutoSnapshotPolicy" == c[0] for c in fake.calls)


def test_absent_removes_unbound_policy(monkeypatch):
    fake = FakeCfsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteAutoSnapshotPolicy") == 1
    assert "UnbindAutoSnapshotPolicy" not in names
    assert fake.policies == []


def test_absent_refuses_bound_policy_without_force(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a")])])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "force_delete=true" in payload["msg"]
    assert payload["file_system_ids"] == ["cfs-a"]
    assert not any("DeleteAutoSnapshotPolicy" == c[0] for c in fake.calls)


def test_absent_force_delete_unbinds_then_deletes(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a"), _fs("cfs-b")])])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", force_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteAutoSnapshotPolicy") == 1
    unbind = [c for c in fake.calls if c[0] == "UnbindAutoSnapshotPolicy"][0][1]
    assert unbind.FileSystemIds == "cfs-a,cfs-b"
    assert fake.policies == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCfsClient([_policy(PolicyName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert not any("DeleteAutoSnapshotPolicy" == c[0] for c in fake.calls)


def test_absent_check_mode_force_delete_is_dry_run(monkeypatch):
    fake = FakeCfsClient([_policy(FileSystems=[_fs("cfs-a")])])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", force_delete=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is not None  # pre-change state reported
    assert not any(name in [c[0] for c in fake.calls] for name in ("UnbindAutoSnapshotPolicy", "DeleteAutoSnapshotPolicy"))
    assert len(fake.policies) == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeCfsClient([_policy(), _policy(AutoSnapshotPolicyId="asp-2")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CFS auto-snapshot policies matched" in exc.value.args[0]["msg"]
