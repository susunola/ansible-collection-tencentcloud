"""Unit tests for the tdmq_rocketmq_namespace write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a RocketMQ-namespace store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing namespace (idempotent no-op)
* absent with a matching namespace (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the namespace already matches (remark)
* remark drift updates through ModifyRocketMQNamespace
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_namespace as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAMESPACE = {
    "NamespaceId": "production",
    "Remark": "Production workloads",
}


def _namespace(**overrides):
    item = copy.deepcopy(NAMESPACE)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"cluster_id": "rocketmq-abc", "name": "production"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small RocketMQ-namespace store."""

    def __init__(self, namespaces=None):
        self.namespaces = [copy.deepcopy(t) for t in (namespaces or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.namespaces:
            if item.get("NamespaceId") == name:
                return item
        return None

    def DescribeRocketMQNamespaces(self, request):
        self._record("DescribeRocketMQNamespaces", request)
        return SimpleNamespace(Namespaces=[FakeResource(t) for t in self.namespaces], TotalCount=len(self.namespaces))

    def CreateRocketMQNamespace(self, request):
        self._record("CreateRocketMQNamespace", request)
        self.namespaces.append(
            {
                "NamespaceId": getattr(request, "NamespaceId", None),
                "Remark": getattr(request, "Remark", None) or "",
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQNamespace(self, request):
        self._record("ModifyRocketMQNamespace", request)
        item = self._by_name(getattr(request, "NamespaceId", None))
        if item is not None:
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQNamespace(self, request):
        self._record("DeleteRocketMQNamespace", request)
        self.namespaces = [t for t in self.namespaces if t.get("NamespaceId") != getattr(request, "NamespaceId", None)]
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
    fake = FakeTdmqClient(namespaces=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRocketMQNamespaces"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceId"] == "production"
    assert len(fake.namespaces) == 1
    assert "DeleteRocketMQNamespace" not in [c for c, unused in fake.calls]


def test_absent_deletes_namespace(monkeypatch):
    fake = FakeTdmqClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    assert fake.namespaces == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRocketMQNamespace" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_namespace(monkeypatch):
    fake = FakeTdmqClient(namespaces=[])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Production workloads")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceId"] == "production"
    assert result["namespace"]["Remark"] == "Production workloads"
    assert len(fake.namespaces) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRocketMQNamespaces"
    assert "CreateRocketMQNamespace" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(namespaces=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", remark="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    assert fake.namespaces == []
    assert "CreateRocketMQNamespace" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-namespace flows
# ---------------------------------------------------------------------------


def test_existing_namespace_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Production workloads")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"]["NamespaceId"] == "production"
    assert "ModifyRocketMQNamespace" not in [c for c, unused in fake.calls]


def test_remark_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(namespaces=[_namespace(Remark="Stale remark")])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Production workloads")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Remark"] == "Production workloads"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQNamespace" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRocketMQNamespaces(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
