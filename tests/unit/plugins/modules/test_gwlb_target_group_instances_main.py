"""Unit tests for the gwlb_target_group_instances write module.

Drives ``run_module()`` against an in-memory fake GWLB client whose
register / weight / deregister operations mutate a target-group instance
store so the post-write describe converges immediately.

Scenario matrix:

* exact-set no-op when current matches desired (order and purge semantics)
* additive registration of missing endpoints
* weight-only updates via ModifyTargetGroupInstancesWeight
* purge removing unlisted endpoints (exact-set reconcile)
* purge=false keeping unlisted endpoints while still registering additions
* check-mode dry runs and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gwlb_target_group_instances as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

TARGET_GROUP_ID = "lbtg-cccc"
A = {"ip": "10.0.1.10", "port": 6081, "weight": 50}
B = {"ip": "10.0.1.11", "port": 6081, "weight": 50}


def _args(**overrides):
    params = {"target_group_id": TARGET_GROUP_ID, "instances": [], "purge": True}
    params.update(overrides)
    return module_args(**params)


class FakeGwlbClient(object):
    """In-memory GWLB client mutating a target-group instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, ip, port):
        for item in self.instances:
            if item["ip"] == ip and item["port"] == port:
                return item
        return None

    def DescribeTargetGroupInstances(self, request):
        self._record("DescribeTargetGroupInstances", request)
        # Single-target-group store; filters are accepted but not enforced.
        return SimpleNamespace(
            TargetGroupInstanceSet=[SimpleNamespace(BindIP=i["ip"], Port=i["port"], Weight=i["weight"]) for i in self.instances]
        )

    def RegisterTargetGroupInstances(self, request):
        self._record("RegisterTargetGroupInstances", request)
        for item in getattr(request, "TargetGroupInstances", None) or []:
            self._find(item.BindIP, item.Port) or self.instances.append({"ip": item.BindIP, "port": item.Port, "weight": item.Weight})
        return SimpleNamespace(RequestId="req-fake")

    def ModifyTargetGroupInstancesWeight(self, request):
        self._record("ModifyTargetGroupInstancesWeight", request)
        for item in getattr(request, "TargetGroupInstances", None) or []:
            existing = self._find(item.BindIP, item.Port)
            if existing is not None:
                existing["weight"] = item.Weight
        return SimpleNamespace(RequestId="req-fake")

    def DeregisterTargetGroupInstances(self, request):
        self._record("DeregisterTargetGroupInstances", request)
        keys = [(item.BindIP, item.Port) for item in (getattr(request, "TargetGroupInstances", None) or [])]
        self.instances = [i for i in self.instances if (i["ip"], i["port"]) not in keys]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(GwlbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_exact_set_is_idempotent(monkeypatch):
    fake = FakeGwlbClient(instances=[A, B])
    _make_module(monkeypatch, fake)
    _args(instances=[B, A])  # opposite order: module sorts before comparing
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instances"] == sorted([A, B], key=lambda x: (x["ip"], x["port"]))
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeTargetGroupInstances"]


def test_empty_desired_with_purge_is_idempotent(monkeypatch):
    fake = FakeGwlbClient(instances=[])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instances"] == []
    assert [c for c, unused in fake.calls] == ["DescribeTargetGroupInstances"]


def test_default_weight_normalization_is_idempotent(monkeypatch):
    # Desired omits port/weight (defaults 6081/10); remote matches those.
    remote = {"ip": "10.0.9.1", "port": 6081, "weight": 10}
    fake = FakeGwlbClient(instances=[remote])
    _make_module(monkeypatch, fake)
    _args(instances=[{"ip": "10.0.9.1"}])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instances"] == [remote]


# ---------------------------------------------------------------------------
# reconcile flows
# ---------------------------------------------------------------------------


def test_purge_deregisters_unlisted_instances(monkeypatch):
    fake = FakeGwlbClient(instances=[copy.deepcopy(A), copy.deepcopy(B)])
    _make_module(monkeypatch, fake)
    _args(instances=[B])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"] == [B]
    assert fake.instances == [B]
    ops = [c for c, unused in fake.calls]
    assert "DeregisterTargetGroupInstances" in ops


def test_addition_registers_missing_instance(monkeypatch):
    fake = FakeGwlbClient(instances=[copy.deepcopy(A)])
    _make_module(monkeypatch, fake)
    _args(instances=[A, B])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"] == sorted([A, B], key=lambda x: (x["ip"], x["port"]))
    ops = [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" in ops


def test_weight_drift_updates_weight(monkeypatch):
    fake = FakeGwlbClient(instances=[dict(A, weight=10)])
    _make_module(monkeypatch, fake)
    _args(instances=[A])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"] == [A]
    assert fake.instances == [A]
    ops = [c for c, unused in fake.calls]
    assert "ModifyTargetGroupInstancesWeight" in ops


def test_mixed_reconcile(monkeypatch):
    C = {"ip": "10.0.1.12", "port": 6081, "weight": 10}
    fake = FakeGwlbClient(instances=[dict(A, weight=10), copy.deepcopy(B)])
    _make_module(monkeypatch, fake)
    _args(instances=[A, C])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"] == sorted([A, C], key=lambda x: (x["ip"], x["port"]))
    assert fake.instances == sorted([A, C], key=lambda x: (x["ip"], x["port"]))
    ops = [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" in ops
    assert "ModifyTargetGroupInstancesWeight" in ops
    assert "DeregisterTargetGroupInstances" in ops


def test_purge_false_keeps_unlisted_but_registers_additions(monkeypatch):
    fake = FakeGwlbClient(instances=[copy.deepcopy(B)])
    _make_module(monkeypatch, fake)
    _args(purge=False, instances=[A])
    result = run(mod.run_module)
    assert result["changed"] is True
    # B was not listed but purge=false keeps it in the effective set.
    assert result["instances"] == sorted([A, B], key=lambda x: (x["ip"], x["port"]))
    assert sorted(fake.instances, key=lambda x: (x["ip"], x["port"])) == sorted([A, B], key=lambda x: (x["ip"], x["port"]))
    ops = [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" in ops
    assert "DeregisterTargetGroupInstances" not in ops


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeGwlbClient(instances=[dict(A, weight=10), copy.deepcopy(B)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, instances=[A])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert fake.instances == [dict(A, weight=10), B]
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeTargetGroupInstances"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTargetGroupInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(instances=[A])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_register_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTargetGroupInstances(self, request):
            return SimpleNamespace(TargetGroupInstanceSet=[])

        def RegisterTargetGroupInstances(self, request):
            raise Boom("register refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(instances=[A])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "register refused" in payload["error"]
