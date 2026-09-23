"""Unit tests for the dlc_work_group_policy write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake DLC client
whose attach/detach operations mutate the work-group ``PolicySet`` store, so
the post-write ``DescribeWorkGroups`` refetch and the reconciliation waiter
converge immediately. The module reconciles (no create/delete lifecycle): the
work group must already exist and the run converges its attached policy set.

Scenario matrix:

* missing work group fails before any write
* idempotent no-op when policies already match (metadata ignored)
* check-mode dry run for attach / detach
* attach, detach and combined add+remove runs (SDK request fields captured)
* ``allow_empty`` guard for removing every policy
* argument-validation failure (missing required params) before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_dlc_work_group_policy.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_work_group_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = 10042

READ_POLICY = {
    "Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE",
    "Catalog": "DataLakeCatalog", "PolicyId": "p-1001",
}
ADD_POLICY = {"Database": "marketing", "Operation": "SELECT", "PolicyType": "DATABASE"}


def _group(**overrides):
    item = {"WorkGroupId": GROUP_ID, "PolicySet": []}
    item.update(overrides)
    return item


def _policy(value):
    """Build a full SDK-shaped fixture policy the describe path would return."""
    policy = mod.normalize_policy(value)
    policy.update({k: v for k, v in value.items() if k not in policy})
    return policy


def _base(**overrides):
    params = {"work_group_id": GROUP_ID, "policies": [dict(ADD_POLICY)]}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating each work group's PolicySet store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _match_group(self, request):
        for group in self.groups:
            if group.get("WorkGroupId") == getattr(request, "WorkGroupId", None):
                return group
        return None

    def DescribeWorkGroups(self, request):
        self._record("DescribeWorkGroups", request)
        matches = [g for g in self.groups if g.get("WorkGroupId") == getattr(request, "WorkGroupId", None)]
        return SimpleNamespace(WorkGroupSet=[FakeResource(g) for g in matches], RequestId="req-fake")

    @staticmethod
    def _key(value):
        return json.dumps(mod.normalize_policy(value), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _as_dict(policy_model):
        return {k: copy.deepcopy(v) for k, v in vars(policy_model).items() if not k.startswith("_")}

    def AttachWorkGroupPolicy(self, request):
        self._record("AttachWorkGroupPolicy", request)
        group = self._match_group(request)
        store = group.setdefault("PolicySet", [])
        for policy in getattr(request, "PolicySet", None) or []:
            value = self._as_dict(policy)
            if self._key(value) not in {self._key(existing) for existing in store}:
                store.append(value)
        return SimpleNamespace(RequestId="req-fake")

    def DetachWorkGroupPolicy(self, request):
        self._record("DetachWorkGroupPolicy", request)
        group = self._match_group(request)
        if getattr(request, "PolicyIds", None):
            ids = set(request.PolicyIds)
            group["PolicySet"] = [v for v in group.get("PolicySet", []) if str(v.get("PolicyId")) not in ids]
            return SimpleNamespace(RequestId="req-fake")
        removed = {self._key(self._as_dict(policy)) for policy in getattr(request, "PolicySet", None) or []}
        group["PolicySet"] = [v for v in group.get("PolicySet", []) if self._key(v) not in removed]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# precondition failures
# ---------------------------------------------------------------------------


def test_missing_work_group_fails(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "DLC work group not found" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_policies_already_match_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[_group(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[{"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policies"] == [mod.normalize_policy(READ_POLICY)]
    assert result["added"] == []
    assert result["removed"] == []
    assert [name for name, unused in fake.calls] == ["DescribeWorkGroups"]


# ---------------------------------------------------------------------------
# attach flows
# ---------------------------------------------------------------------------


def test_attach_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([ADD_POLICY])
    assert fake.groups[0]["PolicySet"] == []
    assert "AttachWorkGroupPolicy" not in [name for name, unused in fake.calls]


def test_attach_adds_missing_policy(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([ADD_POLICY])
    assert result["added"] == mod.normalize_policies([ADD_POLICY])
    request = _find_call(fake, "AttachWorkGroupPolicy")
    assert request.WorkGroupId == GROUP_ID
    assert vars(request)["PolicySet"][0].Database == "marketing"
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeWorkGroups"
    assert ops[-1] == "DescribeWorkGroups"  # waiter converges, final refetch


# ---------------------------------------------------------------------------
# detach flows
# ---------------------------------------------------------------------------


def test_remove_empty_set_requires_allow_empty(monkeypatch):
    fake = FakeDlcClient(groups=[_group(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]
    assert len(fake.groups[0]["PolicySet"]) == 1


def test_detach_removes_stale_policy(monkeypatch):
    fake = FakeDlcClient(groups=[_group(PolicySet=[_policy(READ_POLICY), _policy(ADD_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[{"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == [mod.normalize_policy(READ_POLICY)]
    assert result["removed"] == [mod.normalize_policy(ADD_POLICY)]
    request = _find_call(fake, "DetachWorkGroupPolicy")
    assert request.WorkGroupId == GROUP_ID
    # The removed marketing policy has no server PolicyId, so detach uses PolicySet.
    assert not hasattr(request, "PolicyIds")
    assert vars(request)["PolicySet"][0].Database == "marketing"


def test_allow_empty_removes_every_policy(monkeypatch):
    fake = FakeDlcClient(groups=[_group(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == []
    assert result["removed"] == [mod.normalize_policy(READ_POLICY)]
    request = _find_call(fake, "DetachWorkGroupPolicy")
    assert request.PolicyIds == ["p-1001"]
    assert fake.groups[0]["PolicySet"] == []


def test_combined_add_and_remove_reconciles(monkeypatch):
    fake = FakeDlcClient(groups=[_group(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    replace = {"Database": "archive", "Operation": "SELECT", "PolicyType": "DATABASE"}
    _base(policies=[replace])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([replace])
    assert result["added"] == mod.normalize_policies([replace])
    assert result["removed"] == [mod.normalize_policy(READ_POLICY)]
    ops = [name for name, unused in fake.calls]
    assert "AttachWorkGroupPolicy" in ops
    assert "DetachWorkGroupPolicy" in ops


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(work_group_id=GROUP_ID)  # policies omitted
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "policies" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWorkGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_work_group_policy.py)
# ---------------------------------------------------------------------------


class _Policy(object):
    def from_json_string(self, value):
        self.value = value


class _Request(object):
    pass


_Models = type("Models", (), {"Policy": _Policy, "DetachWorkGroupPolicyRequest": _Request})


def test_normalize_policy_ignores_server_metadata_and_applies_defaults():
    value = mod.normalize_policy({"Database": "sales", "PolicyType": "DATABASE", "PolicyId": "generated", "Source": "WORKGROUP"})
    assert value["Database"] == "sales"
    assert value["PolicyType"] == "DATABASE"
    assert value["Catalog"] == "DataLakeCatalog"
    assert "PolicyId" not in value


def test_delta_compares_policy_semantics_only():
    current = [{"Database": "sales", "PolicyType": "DATABASE", "PolicyId": "p-1"}]
    assert mod.delta(current, [{"Database": "sales", "PolicyType": "DATABASE"}]) == ([], [])


def test_detach_prefers_deterministic_policy_ids():
    request = mod.detach_request(_Models, 42, [{"PolicyType": "ADMIN"}], ["p-1"])
    assert request.WorkGroupId == 42
    assert request.PolicyIds == ["p-1"]
    assert not hasattr(request, "PolicySet")
