"""Unit tests for the tsf_container_deployment_group write module.

Drives ``run_module()`` end to end against an in-memory fake TSF client
whose write operations mutate the deployment-group store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing group (idempotent no-op), rejected-deletion guard and
  the real delete path
* pre-SDK validation (replicas required, rolling-update interval)
* no-drift idempotency, immutable resource-drift failure
* mutable updates (metadata via ModifyContainerGroup, replica counts via
  ModifyContainerReplicas) with check-mode dry runs
* creation when missing and its check-mode dry run
* multiple-match guard and the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_container_deployment_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "GroupId": "group-8b0a1c2d",
    "GroupName": "orders-production",
    "ApplicationId": "application-xxx",
    "NamespaceId": "namespace-xxx",
    "ClusterId": "cluster-xxx",
    "InstanceNum": 3,
    "CpuRequest": "0.5",
    "CpuLimit": "1",
    "MemRequest": "512",
    "MemLimit": "1024",
    "AccessType": 1,
    "UpdateType": 0,
    "UpdateIvl": 0,
    "Alias": "orders",
    "GroupResourceType": "DEF",
    "ProtocolPorts": [{"Protocol": "TCP", "Port": 80, "TargetPort": 8080, "Name": "http"}],
}

PORTS = [{"protocol": "TCP", "port": 80, "target_port": 8080, "name": "http"}]


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeTsfClient(object):
    """In-memory TSF client mutating a container deployment-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, group_id):
        for item in self.groups:
            if item.get("GroupId") == group_id:
                return item
        return None

    def _list_for(self, request):
        group_ids = getattr(request, "GroupIdList", None)
        if group_ids:
            return [item for item in self.groups if item.get("GroupId") in group_ids]
        search = getattr(request, "SearchWord", None)
        namespace = getattr(request, "NamespaceId", None)
        cluster = getattr(request, "ClusterId", None)
        return [item for item in self.groups if item.get("GroupName") == search and item.get("NamespaceId") == namespace and item.get("ClusterId") == cluster]

    def DescribeContainerGroups(self, request):
        self._record("DescribeContainerGroups", request)
        return SimpleNamespace(
            Result=SimpleNamespace(Content=[FakeResource(item) for item in self._list_for(request)], TotalCount=len(self._list_for(request)))
        )

    def DescribeContainerGroupDetail(self, request):
        self._record("DescribeContainerGroupDetail", request)
        group = self._by_id(getattr(request, "GroupId", None))
        return SimpleNamespace(Result=FakeResource(group) if group else None)

    def DeleteContainerGroup(self, request):
        self._record("DeleteContainerGroup", request)
        group_id = getattr(request, "GroupId", None)
        self.groups = [item for item in self.groups if item.get("GroupId") != group_id]
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def CreateContainGroup(self, request):
        self._record("CreateContainGroup", request)
        self._next += 1
        item = {"GroupId": "group-new-%03d" % self._next}
        for key, value in vars(request).items():
            item[key] = _plain(value)
        item.setdefault("GroupComment", None)
        self.groups.append(item)
        return SimpleNamespace(Result=item["GroupId"], RequestId="req-fake")

    def ModifyContainerGroup(self, request):
        self._record("ModifyContainerGroup", request)
        group = self._by_id(getattr(request, "GroupId", None))
        if group is not None:
            for key, value in vars(request).items():
                if key != "GroupId":
                    group[key] = _plain(value)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def ModifyContainerReplicas(self, request):
        self._record("ModifyContainerReplicas", request)
        group = self._by_id(getattr(request, "GroupId", None))
        if group is not None:
            group["InstanceNum"] = getattr(request, "InstanceNum", None)
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _group_args(**overrides):
    params = {
        "name": "orders-production",
        "application_id": "application-xxx",
        "namespace_id": "namespace-xxx",
        "cluster_id": "cluster-xxx",
        "replicas": 3,
        "cpu_request": "0.5",
        "cpu_limit": "1",
        "memory_request": "512",
        "memory_limit": "1024",
        "alias": "orders",
        "protocol_ports": copy.deepcopy(PORTS),
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeTsfClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", application_id="application-xxx", namespace_id="namespace-xxx", cluster_id="cluster-xxx")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment_group"] is None


def test_absent_deletes_group(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="orders-production", application_id="application-xxx",
                namespace_id="namespace-xxx", cluster_id="cluster-xxx")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    assert "DeleteContainerGroup" in [c for c, unused in fake.calls]


def test_absent_deletion_rejected(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteContainerGroup(self, request):
            self._record("DeleteContainerGroup", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="orders-production", application_id="application-xxx",
                namespace_id="namespace-xxx", cluster_id="cluster-xxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF container deployment group deletion" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="orders-production", application_id="application-xxx",
                namespace_id="namespace-xxx", cluster_id="cluster-xxx")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteContainerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_present_requires_replicas(monkeypatch):
    fake = FakeTsfClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(name="orders-production", application_id="application-xxx", namespace_id="namespace-xxx", cluster_id="cluster-xxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "replicas is required when state is present" in exc.value.args[0]["msg"]


def test_rolling_update_requires_interval(monkeypatch):
    fake = FakeTsfClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(name="orders-production", application_id="application-xxx", namespace_id="namespace-xxx",
                cluster_id="cluster-xxx", replicas=3, update_type=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "update_interval is required for rolling updates" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment_group"]["GroupId"] == "group-8b0a1c2d"
    assert "ModifyContainerGroup" not in [c for c, unused in fake.calls]


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _group_args(cpu_request="1.5")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "CpuRequest" in payload["immutable_changes"]


def test_update_mutable_fields(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _group_args(alias="renamed-orders", protocol_ports=[{"protocol": "TCP", "port": 443, "target_port": 8443, "name": "https"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["Alias"] == "renamed-orders"
    ops = [c for c, unused in fake.calls]
    assert "ModifyContainerGroup" in ops
    assert "ModifyContainerReplicas" not in ops


def test_update_replicas_only(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _group_args(replicas=6)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["InstanceNum"] == 6
    ops = [c for c, unused in fake.calls]
    assert "ModifyContainerReplicas" in ops
    assert "ModifyContainerGroup" not in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True, alias="renamed-orders")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["Alias"] == "renamed-orders"
    assert fake.groups[0]["Alias"] == "orders"
    assert "ModifyContainerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_group(monkeypatch):
    fake = FakeTsfClient(groups=[])
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupName"] == "orders-production"
    assert result["deployment_group"]["InstanceNum"] == 3
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateContainGroup" in ops
    assert ops[-1] == "DescribeContainerGroupDetail"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(groups=[])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupName"] == "orders-production"
    assert fake.groups == []
    assert "CreateContainGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTsfClient(groups=[_group(), _group(GroupId="group-dup")])
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF container deployment groups matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeContainerGroups(self, request):
            raise Boom("cluster unreachable")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "cluster unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tsf_container_deployment_group.py)
# ---------------------------------------------------------------------------


def test_container_group_normalizes_port_order():
    ports = [
        {"Protocol": "TCP", "Port": 81, "TargetPort": 8081, "Name": "z"},
        {"Protocol": "TCP", "Port": 80, "TargetPort": 8080, "Name": "a"},
    ]
    assert mod._ports(ports)[0]["Name"] == "a"


def test_container_group_maps_capacity_and_resources():
    p = {
        "name": "orders",
        "application_id": "app-1",
        "namespace_id": "ns-1",
        "cluster_id": "c-1",
        "replicas": 3,
        "cpu_request": "0.5",
        "cpu_limit": "1",
        "memory_request": "512",
        "memory_limit": "1024",
        "access_type": 1,
        "protocol_ports": None,
        "update_type": 0,
        "update_interval": None,
        "subnet_id": None,
        "alias": None,
        "resource_type": "DEF",
    }
    target = mod.desired(p)
    assert target["InstanceNum"] == 3 and target["MemLimit"] == "1024"
    assert mod.comparable(dict(target, Status="Running"), target) == target
