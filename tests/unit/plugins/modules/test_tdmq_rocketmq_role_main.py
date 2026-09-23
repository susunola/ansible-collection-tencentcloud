"""Unit tests for the tdmq_rocketmq_role write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a RocketMQ-role store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing role (idempotent no-op)
* absent with a matching role (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the role already matches (name/remark/permission_type)
* remark / permission_type drift updates through ModifyRocketMQRole
* credential fields (Token/AccessKey/SecretKey/SecretName) are stripped
  from every returned role payload
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_role as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ROLE = {
    "RoleName": "order-service",
    "Remark": "Order service identity",
    "PermType": "TopicAndGroup",
    "Token": "secret-token",
    "AccessKey": "ak-123",
    "SecretKey": "sk-456",
    "SecretName": "order-service",
}


def _role(**overrides):
    item = copy.deepcopy(ROLE)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"cluster_id": "rocketmq-abc", "name": "order-service"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small RocketMQ-role store."""

    def __init__(self, roles=None):
        self.roles = [copy.deepcopy(t) for t in (roles or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.roles:
            if item.get("RoleName") == name:
                return item
        return None

    def DescribeRocketMQRoles(self, request):
        self._record("DescribeRocketMQRoles", request)
        return SimpleNamespace(RoleSets=[FakeResource(t) for t in self.roles], TotalCount=len(self.roles))

    def CreateRocketMQRole(self, request):
        self._record("CreateRocketMQRole", request)
        self.roles.append(
            {
                "RoleName": getattr(request, "RoleName", None),
                "Remark": getattr(request, "Remark", None) or "",
                "PermType": getattr(request, "PermType", None),
                "Token": "tok-" + (getattr(request, "RoleName", "") or ""),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQRole(self, request):
        self._record("ModifyRocketMQRole", request)
        item = self._by_name(getattr(request, "RoleName", None))
        if item is not None:
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
            item["PermType"] = getattr(request, "PermType", item.get("PermType"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQRoles(self, request):
        self._record("DeleteRocketMQRoles", request)
        names = list(getattr(request, "RoleNames", None) or [])
        self.roles = [t for t in self.roles if t.get("RoleName") not in names]
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
    fake = FakeTdmqClient(roles=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["role"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRocketMQRoles"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(roles=[_role()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"]["RoleName"] == "order-service"
    assert len(fake.roles) == 1
    assert "DeleteRocketMQRoles" not in [c for c, unused in fake.calls]


def test_absent_deletes_role(monkeypatch):
    fake = FakeTdmqClient(roles=[_role()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"] is None
    assert fake.roles == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRocketMQRoles" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_role(monkeypatch):
    fake = FakeTdmqClient(roles=[])
    _make_module(monkeypatch, fake)
    _config(state="present", permission_type="TopicAndGroup", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"]["RoleName"] == "order-service"
    assert result["role"]["PermType"] == "TopicAndGroup"
    assert len(fake.roles) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRocketMQRoles"
    assert "CreateRocketMQRole" in ops


def test_create_role_strips_credentials_on_refind(monkeypatch):
    fake = FakeTdmqClient(roles=[])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is True
    for field in ("Token", "AccessKey", "SecretKey", "SecretName"):
        assert field not in result["role"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(roles=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", remark="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"] is None
    assert fake.roles == []
    assert "CreateRocketMQRole" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-role flows
# ---------------------------------------------------------------------------


def test_existing_role_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(roles=[_role()])
    _make_module(monkeypatch, fake)
    _config(state="present", permission_type="TopicAndGroup", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["role"]["RoleName"] == "order-service"
    assert "ModifyRocketMQRole" not in [c for c, unused in fake.calls]


def test_remark_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(roles=[_role(Remark="Stale remark")])
    _make_module(monkeypatch, fake)
    _config(state="present", permission_type="TopicAndGroup", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"]["Remark"] == "Order service identity"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQRole" in ops


def test_permission_type_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(roles=[_role(PermType="Cluster")])
    _make_module(monkeypatch, fake)
    _config(state="present", permission_type="TopicAndGroup", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["role"]["PermType"] == "TopicAndGroup"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQRole" in ops


def test_role_payload_never_leaks_credentials(monkeypatch):
    fake = FakeTdmqClient(roles=[_role()])
    _make_module(monkeypatch, fake)
    _config(state="present", permission_type="TopicAndGroup", remark="Order service identity")
    result = run(mod.run_module)
    assert result["changed"] is False
    for field in ("Token", "AccessKey", "SecretKey", "SecretName"):
        assert field not in result["role"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRocketMQRoles(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
