"""Unit tests for the monitor_prometheus_cluster_agent write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / delete operations bind and unbind cluster agents in a store.

Scenario matrix:

* present when the cluster is already bound (idempotent no-op)
* absent when no matching agent exists (idempotent no-op)
* present bind when missing (happy path and check-mode dry run)
* absent unbind when bound (real delete and check-mode dry run)
* the blanket SDK failure path

Note: presence is decided purely on ``cluster_id`` + ``cluster_type``; an
existing binding is never modified, only created or deleted.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_cluster_agent as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

AGENT = {
    "ClusterId": "cls-abc123",
    "ClusterType": "tke",
    "Region": "ap-guangzhou",
    "Status": "running",
}


def _agent(**overrides):
    item = copy.deepcopy(AGENT)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "instance_id": "prom-abc123",
        "cluster_id": "cls-abc123",
        "cluster_type": "tke",
        "region": "ap-guangzhou",
    }
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client binding/unbinding cluster agents."""

    def __init__(self, agents=None):
        self.agents = [copy.deepcopy(t) for t in (agents or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusClusterAgents(self, request):
        self._record("DescribePrometheusClusterAgents", request)
        cluster_ids = list(getattr(request, "ClusterIds", None) or [])
        cluster_types = list(getattr(request, "ClusterTypes", None) or [])
        matched = [
            t for t in self.agents
            if t.get("ClusterId") in cluster_ids and t.get("ClusterType") in cluster_types
        ]
        return SimpleNamespace(Agents=[FakeResource(t) for t in matched])

    def CreatePrometheusClusterAgent(self, request):
        self._record("CreatePrometheusClusterAgent", request)
        for agent in list(getattr(request, "Agents", None) or []):
            self.agents.append({
                "ClusterId": getattr(agent, "ClusterId", None),
                "ClusterType": getattr(agent, "ClusterType", None),
                "Region": getattr(agent, "Region", None),
            })
        return SimpleNamespace(RequestId="req-fake")

    def DeletePrometheusClusterAgent(self, request):
        self._record("DeletePrometheusClusterAgent", request)
        for agent in list(getattr(request, "Agents", None) or []):
            cid = getattr(agent, "ClusterId", None)
            ctype = getattr(agent, "ClusterType", None)
            self.agents = [
                t for t in self.agents
                if not (t.get("ClusterId") == cid and t.get("ClusterType") == ctype)
            ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_present_when_already_bound_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(agents=[_agent()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["agent"]["ClusterId"] == "cls-abc123"
    assert [c for c, unused in fake.calls] == ["DescribePrometheusClusterAgents"]


def test_absent_when_not_bound_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(agents=[])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["agent"] is None
    assert [c for c, unused in fake.calls] == ["DescribePrometheusClusterAgents"]


# ---------------------------------------------------------------------------
# binding flows
# ---------------------------------------------------------------------------


def test_present_binds_cluster_agent(monkeypatch):
    fake = FakeMonitorClient(agents=[])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["agent"] == {"ClusterId": "cls-abc123", "ClusterType": "tke"}
    assert len(fake.agents) == 1
    assert fake.agents[0]["ClusterId"] == "cls-abc123"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusClusterAgents"
    assert "CreatePrometheusClusterAgent" in ops


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(agents=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["agent"]["ClusterId"] == "cls-abc123"
    assert fake.agents == []
    assert "CreatePrometheusClusterAgent" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# unbinding flows
# ---------------------------------------------------------------------------


def test_absent_unbinds_cluster_agent(monkeypatch):
    fake = FakeMonitorClient(agents=[_agent()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["agent"] is None
    assert fake.agents == []
    ops = [c for c, unused in fake.calls]
    assert "DeletePrometheusClusterAgent" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(agents=[_agent()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["agent"] is None
    assert len(fake.agents) == 1
    assert "DeletePrometheusClusterAgent" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusClusterAgents(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
