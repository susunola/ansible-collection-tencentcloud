"""Unit tests for the dlc_user_policy write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake DLC client
whose attach/detach operations mutate the per-user ``PolicySet`` store, so the
post-write ``DescribeUsers`` refetch and the reconciliation waiter converge
immediately. The module reconciles (no create/delete lifecycle): a user must
already exist and the run simply converges the directly attached policy set.

Scenario matrix:

* DLC user missing / duplicate-match failures before any write
* idempotent no-op when the policy set already matches
* check-mode dry run for attach and detach
* attach, detach and combined add+remove reconciliation runs (SDK request
  fields captured)
* ``allow_empty`` guard for removing every direct policy
* ADMIN users cannot carry direct policies
* argument-validation failure (missing required params) before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_dlc_user_policy.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_user_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {
    "UserId": "100012345678",
    "UserType": "COMMON",
    "AccountType": "TencentAccount",
    "PolicySet": [],
}

# A server-shaped policy carries generated metadata (PolicyId) the module must ignore.
READ_POLICY = {
    "Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE",
    "Catalog": "DataLakeCatalog", "PolicyId": "p-1001",
}
ADD_POLICY = {"Database": "marketing", "Operation": "SELECT", "PolicyType": "DATABASE"}


def _user(**overrides):
    item = copy.deepcopy(USER)
    item.update(overrides)
    return item


def _policy(value):
    """Build a full SDK-shaped fixture policy the describe path would return."""
    policy = mod.normalize_policy(value)
    policy.update({k: v for k, v in value.items() if k not in policy})
    return policy


def _base(**overrides):
    params = {"user_id": "100012345678", "policies": [dict(ADD_POLICY)]}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating each user's direct PolicySet store."""

    def __init__(self, users=None):
        self.users = [copy.deepcopy(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _match_user(self, request):
        for user in self.users:
            if user.get("UserId") == getattr(request, "UserId", None):
                return user
        return None

    def DescribeUsers(self, request):
        self._record("DescribeUsers", request)
        matches = [u for u in self.users if u.get("UserId") == getattr(request, "UserId", None)]
        return SimpleNamespace(UserSet=[FakeResource(u) for u in matches], TotalCount=len(matches), RequestId="req-fake")

    @staticmethod
    def _key(value):
        return json.dumps(mod.normalize_policy(value), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _as_dict(policy_model):
        return {k: copy.deepcopy(v) for k, v in vars(policy_model).items() if not k.startswith("_")}

    def AttachUserPolicy(self, request):
        self._record("AttachUserPolicy", request)
        user = self._match_user(request)
        store = user.setdefault("PolicySet", [])
        for policy in getattr(request, "PolicySet", None) or []:
            value = self._as_dict(policy)
            if self._key(value) not in {self._key(existing) for existing in store}:
                store.append(value)
        return SimpleNamespace(RequestId="req-fake")

    def DetachUserPolicy(self, request):
        self._record("DetachUserPolicy", request)
        user = self._match_user(request)
        if getattr(request, "PolicyIds", None):
            ids = set(request.PolicyIds)
            user["PolicySet"] = [v for v in user.get("PolicySet", []) if str(v.get("PolicyId")) not in ids]
            return SimpleNamespace(RequestId="req-fake")
        removed = {self._key(self._as_dict(policy)) for policy in getattr(request, "PolicySet", None) or []}
        user["PolicySet"] = [v for v in user.get("PolicySet", []) if self._key(v) not in removed]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# preconditions: the reconciled user must resolve uniquely
# ---------------------------------------------------------------------------


def test_missing_user_fails(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "DLC user not found" in exc.value.args[0]["msg"]


def test_duplicate_user_match_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base()
    dupes = _user(), _user()
    fake.users = dupes
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC users returned" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_policies_already_match_is_idempotent(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[{"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policies"] == [mod.normalize_policy(READ_POLICY)]
    assert result["added"] == []
    assert result["removed"] == []
    assert [name for name, unused in fake.calls] == ["DescribeUsers"]


# ---------------------------------------------------------------------------
# attach flows (policies the module has to add)
# ---------------------------------------------------------------------------


def test_attach_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([ADD_POLICY])
    assert fake.users[0]["PolicySet"] == []
    assert "AttachUserPolicy" not in [name for name, unused in fake.calls]


def test_attach_adds_missing_policy(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([ADD_POLICY])
    assert result["added"] == mod.normalize_policies([ADD_POLICY])
    request = _find_call(fake, "AttachUserPolicy")
    assert request.UserId == "100012345678"
    assert request.AccountType == "TencentAccount"
    assert request.PolicySet[0].Database == "marketing"
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeUsers"
    assert ops[-1] == "DescribeUsers"  # waiter converges immediately, final refetch


# ---------------------------------------------------------------------------
# detach flows (policies the module has to remove)
# ---------------------------------------------------------------------------


def test_detach_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY), _policy(ADD_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, policies=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]


def test_detach_removes_stale_policy(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY), _policy(ADD_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[{"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == [mod.normalize_policy(READ_POLICY)]
    assert result["removed"] == [mod.normalize_policy(ADD_POLICY)]
    request = _find_call(fake, "DetachUserPolicy")
    assert request.UserId == "100012345678"
    # The removed policy carries no server PolicyId, so detach falls back to PolicySet.
    assert not hasattr(request, "PolicyIds")
    assert vars(request)["PolicySet"][0].Database == "marketing"


def test_combined_add_and_remove_reconciles(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    replace = {"Database": "archive", "Operation": "SELECT", "PolicyType": "DATABASE"}
    _base(policies=[replace])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == mod.normalize_policies([replace])
    assert result["added"] == mod.normalize_policies([replace])
    assert result["removed"] == [mod.normalize_policy(READ_POLICY)]
    ops = [name for name, unused in fake.calls]
    assert "AttachUserPolicy" in ops
    assert "DetachUserPolicy" in ops


def test_remove_every_policy_requires_allow_empty(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]
    assert "AttachUserPolicy" not in [name for name, unused in fake.calls]


def test_allow_empty_removes_every_policy(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[_policy(READ_POLICY)])])
    _make_module(monkeypatch, fake)
    _base(policies=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policies"] == []
    assert result["removed"] == [mod.normalize_policy(READ_POLICY)]
    request = _find_call(fake, "DetachUserPolicy")
    assert request.PolicyIds == ["p-1001"]
    assert fake.users[0]["PolicySet"] == []


def test_admin_user_cannot_declare_policies(monkeypatch):
    fake = FakeDlcClient(users=[_user(UserType="ADMIN")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ADMIN DLC users cannot have direct policies" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    module_args(user_id="100012345678")  # policies omitted
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "policies" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsers(self, request):
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
# legacy helper regression tests (folded from test_dlc_user_policy.py)
# ---------------------------------------------------------------------------


class _Object(object):
    def from_json_string(self, value):
        for key, item in json.loads(value).items():
            setattr(self, key, item)


class _Models(object):
    DescribeUsersRequest = _Object
    AttachUserPolicyRequest = _Object
    DetachUserPolicyRequest = _Object
    Policy = _Object


def test_policy_normalization_ignores_server_metadata():
    base = {"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}
    with_metadata = dict(base)
    with_metadata.update(PolicyId=42, Source="USER")
    assert mod.normalize_policy(with_metadata) == mod.normalize_policy(base)


def test_delta_is_exact_and_stable():
    current = [{"Database": "old", "Operation": "SELECT", "PolicyType": "DATABASE"}]
    target = [{"Database": "new", "Operation": "SELECT", "PolicyType": "DATABASE"}]
    added, removed = mod.delta(current, target)
    assert added[0]["Database"] == "new"
    assert removed[0]["Database"] == "old"


def test_requests_include_user_source_and_prefer_ids():
    values = [{"Database": "sales"}]
    assert mod.describe_request(_Models, "10001", "TencentAccount", 100).Offset == 100
    assert mod.attach_request(_Models, "10001", "TencentAccount", values).AccountType == "TencentAccount"
    detached = mod.detach_request(_Models, "10001", "TencentAccount", values, ["42"])
    assert detached.PolicyIds == ["42"]
    assert not hasattr(detached, "PolicySet")
