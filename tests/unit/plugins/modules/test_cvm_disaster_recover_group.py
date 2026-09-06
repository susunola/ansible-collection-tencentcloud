"""Unit tests for the cvm_disaster_recover_group write module (helpers + run_module).

Creates, updates and deletes CVM placement groups. The zone of the group
is fixed at creation: placement_type is immutable and affinity can never
decrease on an existing group — either drift fails unless force_replace is
set, and replacement is only allowed for an EMPTY group (one carrying
InstanceIds always fails). Replacement runs delete-then-create and never a
Modify. Renames and affinity increases go through ModifyDisasterRecoverGroup
Attribute. name (state=present) and affinity range 1-10 are validated
before the SDK is reached; the affinity range check fires for absent runs
too.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_disaster_recover_group as mod
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


def _group(**overrides):
    """API-shaped stored group; fresh copy per call."""
    item = {
        "group_id": "ps-1001",
        "name": "production-spread",
        "placement_type": "RACK",
        "affinity": 2,
        "instance_ids": [],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "group_id": None,
        "name": "production-spread",
        "placement_type": "RACK",
        "affinity": 2,
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


def _serialize_group(g):
    """Map a stored group dict onto its API response shape."""
    return {
        "DisasterRecoverGroupId": g["group_id"],
        "Name": g["name"],
        "Type": g["placement_type"],
        "Affinity": g["affinity"],
        "InstanceIds": list(g["instance_ids"]),
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


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing group dicts.

    DescribeDisasterRecoverGroups honours DisasterRecoverGroupIds when
    present, otherwise the Name filter; CreateDisasterRecoverGroup
    synthesises sequential ps-NNNN ids; ModifyDisasterRecoverGroupAttribute
    rewrites Name/Affinity by id; DeleteDisasterRecoverGroups removes by id
    list.
    """

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []
        self._seq = 2000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return "ps-%d" % self._seq

    def DescribeDisasterRecoverGroups(self, request):
        self._record("DescribeDisasterRecoverGroups", request)
        ids = getattr(request, "DisasterRecoverGroupIds", None) or []
        result = self.groups
        if ids:
            result = [g for g in self.groups if g["group_id"] in ids]
        elif getattr(request, "Name", None):
            result = [g for g in self.groups if g["name"] == request.Name]
        return SimpleNamespace(
            DisasterRecoverGroupSet=[FakeResource(_serialize_group(g)) for g in result],
            TotalCount=len(result),
            RequestId="req-fake",
        )

    def CreateDisasterRecoverGroup(self, request):
        self._record("CreateDisasterRecoverGroup", request)
        group_id = self._next_id()
        self.groups.append({
            "group_id": group_id,
            "name": request.Name,
            "placement_type": request.Type,
            "affinity": request.Affinity,
            "instance_ids": [],
        })
        return SimpleNamespace(DisasterRecoverGroupId=group_id, RequestId="req-fake")

    def ModifyDisasterRecoverGroupAttribute(self, request):
        self._record("ModifyDisasterRecoverGroupAttribute", request)
        for group in self.groups:
            if group["group_id"] == request.DisasterRecoverGroupId:
                group["name"] = request.Name
                group["affinity"] = request.Affinity
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDisasterRecoverGroups(self, request):
        self._record("DeleteDisasterRecoverGroups", request)
        ids = request.DisasterRecoverGroupIds
        self.groups = [g for g in self.groups if g["group_id"] not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
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


def test_describe_request_sets_ids_when_group_id():
    request = mod.describe_request(FakeModels(), _params(group_id="ps-9"))
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.DisasterRecoverGroupIds == ["ps-9"]
    assert not hasattr(request, "Name")


def test_describe_request_sets_name_filter():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Name == "production-spread"
    assert not hasattr(request, "DisasterRecoverGroupIds")


def test_describe_request_without_identity_sets_nothing():
    request = mod.describe_request(FakeModels(), _params(name=None))
    assert not hasattr(request, "DisasterRecoverGroupIds")
    assert not hasattr(request, "Name")


def test_create_request_sets_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.Name == "production-spread"
    assert request.Type == "RACK"
    assert request.Affinity == 2


def test_update_request_sets_group_and_fields():
    request = mod.update_request(FakeModels(), _params(name="renamed", affinity=3), "ps-7")
    assert request.DisasterRecoverGroupId == "ps-7"
    assert request.Name == "renamed"
    assert request.Affinity == 3


def test_delete_request_wraps_id():
    request = mod.delete_request(FakeModels(), "ps-7")
    assert request.DisasterRecoverGroupIds == ["ps-7"]


def test_comparable_coerces_affinity():
    value = mod.comparable({"Name": "x", "Type": "HOST", "Affinity": "3"})
    assert value == {"Name": "x", "Type": "HOST", "Affinity": 3}


def test_comparable_defaults_affinity_one():
    value = mod.comparable({"Name": "x", "Type": "HOST", "Affinity": None})
    assert value == {"Name": "x", "Type": "HOST", "Affinity": 1}


def test_desired_maps_params():
    value = mod.desired(_params(name="n", placement_type="SW", affinity=4))
    assert value == {"Name": "n", "Type": "SW", "Affinity": 4}


def test_find_matches_by_group_id():
    fake = FakeCvmClient([_group()])
    module = FakeModule(_params(group_id="ps-1001"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["DisasterRecoverGroupId"] == "ps-1001"
    assert value["Name"] == "production-spread"
    request = module.sdk_calls[0][1]
    assert request.DisasterRecoverGroupIds == ["ps-1001"]


def test_find_matches_by_name():
    fake = FakeCvmClient([_group()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["DisasterRecoverGroupId"] == "ps-1001"
    assert module.sdk_calls[0][1].Name == "production-spread"


def test_find_no_match_returns_none():
    fake = FakeCvmClient()
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multi_match_fails():
    fake = FakeCvmClient([_group(), _group(group_id="ps-1002")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple CVM placement groups matched; specify group_id" in payload["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_group_id_or_name(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_present_requires_name(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(group_id="ps-x", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


@pytest.mark.parametrize("affinity", [0, 11])
def test_affinity_out_of_range_fails(monkeypatch, affinity):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(affinity=affinity)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "affinity must be between 1 and 10" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_affinity_range_checked_for_absent_too(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", affinity=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "affinity must be between 1 and 10" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["placement_group"] is None
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["DisasterRecoverGroupId"] == "ps-1001"
    assert result["diff"]["before"]["Name"] == "production-spread"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]
    assert len(fake.groups) == 1


def test_absent_deletes_group(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeDisasterRecoverGroups",
        "DeleteDisasterRecoverGroups",
    ]
    deleted = fake.calls[1][1]
    assert deleted.DisasterRecoverGroupIds == ["ps-1001"]
    assert fake.groups == []


def test_present_noop_when_group_matches(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["placement_group"]["DisasterRecoverGroupId"] == "ps-1001"
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]


def test_present_renames_group(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="ps-1001", name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["Name"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeDisasterRecoverGroups",
        "ModifyDisasterRecoverGroupAttribute",
        "DescribeDisasterRecoverGroups",
    ]
    updated = fake.calls[1][1]
    assert updated.DisasterRecoverGroupId == "ps-1001"
    assert updated.Name == "renamed"
    assert updated.Affinity == 2
    assert fake.groups[0]["name"] == "renamed"


def test_present_affinity_increase_updates(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(affinity=4)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["Affinity"] == 4
    updated = fake.calls[1][1]
    assert updated.Affinity == 4
    assert fake.groups[0]["affinity"] == 4


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="ps-1001", name="renamed", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["Name"] == "production-spread"
    assert result["diff"]["before"]["Name"] == "production-spread"
    assert result["diff"]["after"]["Name"] == "renamed"
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]
    assert fake.groups[0]["name"] == "production-spread"


def test_present_type_drift_requires_force_replace(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(placement_type="HOST")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "set force_replace=true to replace an empty group" in payload["msg"]
    assert payload["current"]["Type"] == "RACK"
    assert payload["desired"]["Type"] == "HOST"
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]


def test_present_affinity_decrease_requires_force_replace(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(affinity=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "set force_replace=true" in exc.value.args[0]["msg"]


def test_present_force_replace_refuses_non_empty_group(monkeypatch):
    fake = FakeCvmClient([_group(instance_ids=["ins-9"])])
    _make_module(monkeypatch, fake)
    _run_args(placement_type="HOST", force_replace=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "cannot replace a non-empty placement group" in payload["msg"]
    assert payload["instance_ids"] == ["ins-9"]
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]


def test_present_force_replace_recreates_group(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(placement_type="HOST", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["DisasterRecoverGroupId"] == "ps-2001"
    assert result["placement_group"]["Type"] == "HOST"
    assert [c[0] for c in fake.calls] == [
        "DescribeDisasterRecoverGroups",
        "DeleteDisasterRecoverGroups",
        "CreateDisasterRecoverGroup",
        "DescribeDisasterRecoverGroups",
    ]
    deleted = fake.calls[1][1]
    assert deleted.DisasterRecoverGroupIds == ["ps-1001"]
    created = fake.calls[2][1]
    assert created.Name == "production-spread"
    assert created.Type == "HOST"
    assert len(fake.groups) == 1
    assert fake.groups[0]["group_id"] == "ps-2001"


def test_present_check_mode_replace_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(placement_type="HOST", force_replace=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["Type"] == "RACK"
    assert result["diff"]["before"]["Type"] == "RACK"
    assert result["diff"]["after"]["Type"] == "HOST"
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]
    assert len(fake.groups) == 1
    assert fake.groups[0]["placement_type"] == "RACK"


def test_present_creates_group(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"]["DisasterRecoverGroupId"] == "ps-2001"
    assert result["placement_group"]["Name"] == "production-spread"
    assert [c[0] for c in fake.calls] == [
        "DescribeDisasterRecoverGroups",
        "CreateDisasterRecoverGroup",
        "DescribeDisasterRecoverGroups",
    ]
    created = fake.calls[1][1]
    assert created.Name == "production-spread"
    assert created.Type == "RACK"
    assert created.Affinity == 2
    assert len(fake.groups) == 1
    assert fake.groups[0]["group_id"] == "ps-2001"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["placement_group"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Name"] == "production-spread"
    assert [c[0] for c in fake.calls] == ["DescribeDisasterRecoverGroups"]
    assert fake.groups == []


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
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["placement_group"] is None
