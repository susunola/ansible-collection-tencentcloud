"""Unit tests for the tdmq_namespace_role write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a Pulsar namespace-role-binding store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing binding (idempotent no-op)
* absent with a matching binding (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the permission set already matches (order-insensitive)
* permission-set drift triggers ModifyEnvironmentRole
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_namespace_role as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BINDING = {
    "EnvironmentId": "production",
    "RoleName": "application",
    "Permissions": ["produce", "consume"],
}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"cluster_id": "pulsar-abc", "namespace": "production", "role_name": "application"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a Pulsar namespace-role store."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(t) for t in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeEnvironmentRoles(self, request):
        self._record("DescribeEnvironmentRoles", request)
        return SimpleNamespace(
            EnvironmentRoleSets=[FakeResource(t) for t in self.bindings], TotalCount=len(self.bindings)
        )

    def _upsert(self, request):
        role = getattr(request, "RoleName", None)
        for item in self.bindings:
            if item.get("RoleName") == role:
                item["Permissions"] = sorted(getattr(request, "Permissions", None) or [])
                item["EnvironmentId"] = getattr(request, "EnvironmentId", item.get("EnvironmentId"))
                return item
        item = {
            "EnvironmentId": getattr(request, "EnvironmentId", None),
            "RoleName": role,
            "Permissions": sorted(getattr(request, "Permissions", None) or []),
        }
        self.bindings.append(item)
        return item

    def CreateEnvironmentRole(self, request):
        self._record("CreateEnvironmentRole", request)
        self._upsert(request)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyEnvironmentRole(self, request):
        self._record("ModifyEnvironmentRole", request)
        self._upsert(request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEnvironmentRoles(self, request):
        self._record("DeleteEnvironmentRoles", request)
        names = list(getattr(request, "RoleNames", None) or [])
        self.bindings = [t for t in self.bindings if t.get("RoleName") not in names]
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
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace_role"] is None
    assert [c for c, unused in fake.calls] == ["DescribeEnvironmentRoles"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace_role"]["RoleName"] == "application"
    assert len(fake.bindings) == 1
    assert "DeleteEnvironmentRoles" not in [c for c, unused in fake.calls]


def test_absent_deletes_binding(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace_role"] is None
    assert fake.bindings == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteEnvironmentRoles" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_binding(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce", "consume"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace_role"]["RoleName"] == "application"
    assert sorted(result["namespace_role"]["Permissions"]) == ["consume", "produce"]
    assert len(fake.bindings) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeEnvironmentRoles"
    assert "CreateEnvironmentRole" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", permissions=["consume"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace_role"] is None
    assert fake.bindings == []
    assert "CreateEnvironmentRole" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-binding flows
# ---------------------------------------------------------------------------


def test_existing_binding_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce", "consume"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace_role"]["RoleName"] == "application"
    assert "ModifyEnvironmentRole" not in [c for c, unused in fake.calls]


def test_unordered_same_set_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["consume", "produce"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ModifyEnvironmentRole" not in [c for c, unused in fake.calls]


def test_permission_set_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="present", permissions=["produce"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(result["namespace_role"]["Permissions"]) == ["produce"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyEnvironmentRole" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeEnvironmentRoles(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
