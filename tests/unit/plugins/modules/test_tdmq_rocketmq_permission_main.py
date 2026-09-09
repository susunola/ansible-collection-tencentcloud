"""Unit tests for the tdmq_rocketmq_permission write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a RocketMQ namespace-role-permission store
so post-write describes converge immediately.

Scenario matrix:

* absent on a missing permission (idempotent no-op)
* absent with a matching permission (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the permission set already matches
* permission-set drift (exact set semantics, unordered) triggers
  ModifyRocketMQEnvironmentRole
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_permission as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PERMISSION = {
    "EnvironmentId": "production",
    "RoleName": "order-service",
    "Permissions": ["produce", "consume"],
}


def _permission(**overrides):
    item = copy.deepcopy(PERMISSION)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"cluster_id": "rocketmq-abc", "namespace": "production", "role_name": "order-service"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a namespace-role permission store."""

    def __init__(self, permissions=None):
        self.permissions = [copy.deepcopy(t) for t in (permissions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRocketMQEnvironmentRoles(self, request):
        self._record("DescribeRocketMQEnvironmentRoles", request)
        return SimpleNamespace(
            EnvironmentRoleSets=[FakeResource(t) for t in self.permissions], TotalCount=len(self.permissions)
        )

    def _upsert(self, request):
        env = getattr(request, "EnvironmentId", None)
        role = getattr(request, "RoleName", None)
        for item in self.permissions:
            if item.get("EnvironmentId") == env and item.get("RoleName") == role:
                item["Permissions"] = list(getattr(request, "Permissions", None) or [])
                return item
        item = {
            "EnvironmentId": env,
            "RoleName": role,
            "Permissions": list(getattr(request, "Permissions", None) or []),
        }
        self.permissions.append(item)
        return item

    def CreateRocketMQEnvironmentRole(self, request):
        self._record("CreateRocketMQEnvironmentRole", request)
        self._upsert(request)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQEnvironmentRole(self, request):
        self._record("ModifyRocketMQEnvironmentRole", request)
        self._upsert(request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQEnvironmentRoles(self, request):
        self._record("DeleteRocketMQEnvironmentRoles", request)
        env = getattr(request, "EnvironmentId", None)
        names = list(getattr(request, "RoleNames", None) or [])
        self.permissions = [
            t
            for t in self.permissions
            if not (t.get("EnvironmentId") == env and t.get("RoleName") in names)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRocketMQEnvironmentRoles"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["RoleName"] == "order-service"
    assert len(fake.permissions) == 1
    assert "DeleteRocketMQEnvironmentRoles" not in [c for c, unused in fake.calls]


def test_absent_deletes_permission(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"] is None
    assert fake.permissions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRocketMQEnvironmentRoles" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_permission(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce", "consume"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["RoleName"] == "order-service"
    assert sorted(result["permission"]["Permissions"]) == ["consume", "produce"]
    assert len(fake.permissions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRocketMQEnvironmentRoles"
    assert "CreateRocketMQEnvironmentRole" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", permissions=["produce"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"] is None
    assert fake.permissions == []
    assert "CreateRocketMQEnvironmentRole" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-permission flows
# ---------------------------------------------------------------------------


def test_existing_permission_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce", "consume"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"]["RoleName"] == "order-service"
    assert "ModifyRocketMQEnvironmentRole" not in [c for c, unused in fake.calls]


def test_permission_set_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(result["permission"]["Permissions"]) == ["produce"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQEnvironmentRole" in ops


def test_unordered_same_set_is_idempotent(monkeypatch):
    # Exact-set semantics compare sorted permission lists, so argument order
    # does not trigger a change.
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["consume", "produce"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ModifyRocketMQEnvironmentRole" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRocketMQEnvironmentRoles(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
