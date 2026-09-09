"""Unit tests for the tdcpg_instance_state write module (run_module flows).

``run_module()`` isolates, recovers or restarts TDSQL-C PostgreSQL cluster
instances and waits for the observed status to converge. It is driven end to
end against an in-memory fake client whose action operations mutate an
instance store, so the post-write ``DescribeClusterInstances`` refetch
converges immediately.

Scenario matrix:

* running when already running / isolated when already isolated (idempotent)
* recovery of isolated instances and isolation of running instances (check
  mode and real actions)
* single-instance restart (always changed; idempotence not applied)
* argument validation before any SDK call (empty/duplicate ids, restart of
  multiple instances, period out of range)
* missing instances and blanket ``sdk_error_payload`` failure paths
* waiter timeout when the action never converges
* legacy helper regression tests (folded from test_tdcpg_instance_state.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdcpg_instance_state as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "tdcpg-cluster-abc"
INSTANCE_1 = "tdcpg-ins-aaa"
INSTANCE_2 = "tdcpg-ins-bbb"


def _base(**overrides):
    params = {
        "cluster_id": CLUSTER_ID,
        "instance_ids": [INSTANCE_1],
        "state": "running",
        "period_months": 1,
    }
    params.update(overrides)
    return module_args(**params)


def _instance(instance_id, status):
    return {"InstanceId": instance_id, "Status": status, "ClusterId": CLUSTER_ID}


class FakeInstanceStateClient(object):
    """In-memory TDSQL-C client holding cluster instance runtime states."""

    def __init__(self, instances=None, stuck=False):
        self.instances = {item["InstanceId"]: dict(item) for item in (instances or [])}
        self.stuck = stuck
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterInstances(self, request):
        self._record("DescribeClusterInstances", request)
        assert request.ClusterId == CLUSTER_ID
        return SimpleNamespace(
            InstanceSet=[FakeResource(item) for item in self.instances.values()],
            RequestId="req-fake",
        )

    def _set_status(self, instance_ids, status):
        for instance_id in instance_ids:
            if instance_id in self.instances:
                self.instances[instance_id]["Status"] = status

    def IsolateClusterInstances(self, request):
        self._record("IsolateClusterInstances", request)
        self.last_request = request
        if not self.stuck:
            self._set_status(request.InstanceIdSet, "isolated")
        return SimpleNamespace(RequestId="req-fake")

    def RecoverClusterInstances(self, request):
        self._record("RecoverClusterInstances", request)
        self.last_request = request
        if not self.stuck:
            self._set_status(request.InstanceIdSet, "running")
        return SimpleNamespace(RequestId="req-fake")

    def RestartClusterInstances(self, request):
        self._record("RestartClusterInstances", request)
        self.last_request = request
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdcpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_running_when_already_running_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instances"][0]["Status"] == "running"
    assert _names(fake) == ["DescribeClusterInstances"]


def test_isolated_when_already_isolated_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "isolated")]))
    _base(state="isolated")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instances"][0]["Status"] == "isolated"
    assert _names(fake) == ["DescribeClusterInstances"]


# ---------------------------------------------------------------------------
# state transition flows
# ---------------------------------------------------------------------------


def test_running_recovers_isolated_instance(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "isolated")]))
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"][0]["Status"] == "running"
    assert fake.instances[INSTANCE_1]["Status"] == "running"
    assert fake.last_request.ClusterId == CLUSTER_ID
    assert fake.last_request.Period == 1
    assert _names(fake) == ["DescribeClusterInstances", "RecoverClusterInstances", "DescribeClusterInstances"]


def test_isolated_isolates_running_instance(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(state="isolated")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instances"][0]["Status"] == "isolated"
    assert fake.instances[INSTANCE_1]["Status"] == "isolated"
    assert _names(fake) == ["DescribeClusterInstances", "IsolateClusterInstances", "DescribeClusterInstances"]


def test_restart_always_changes_single_running_instance(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(state="restarted")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["restarted"] is True
    assert result["instances"][0]["Status"] == "running"
    assert fake.last_request.InstanceIdSet == [INSTANCE_1]
    assert _names(fake) == ["DescribeClusterInstances", "RestartClusterInstances", "DescribeClusterInstances"]


def test_running_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "isolated")]))
    _base(state="running", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["restarted"] is False
    assert "diff" in result
    assert fake.instances[INSTANCE_1]["Status"] == "isolated"
    assert "RecoverClusterInstances" not in _names(fake)


def test_running_recovers_multiple_instances(monkeypatch):
    instances = [_instance(INSTANCE_1, "isolated"), _instance(INSTANCE_2, "isolated")]
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=instances))
    _base(state="running", instance_ids=[INSTANCE_1, INSTANCE_2])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [item["Status"] for item in result["instances"]] == ["running", "running"]
    assert fake.instances[INSTANCE_2]["Status"] == "running"


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_empty_instance_ids_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(instance_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "non-empty unique" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_duplicate_instance_ids_fail_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(instance_ids=[INSTANCE_1, INSTANCE_1])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "non-empty unique" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_restart_requires_single_instance(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient())
    _base(state="restarted", instance_ids=[INSTANCE_1, INSTANCE_2])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "restarting one instance" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_period_months_out_of_range_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient())
    _base(period_months=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "period_months must be between 1 and 60" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_instances_fail(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "running")]))
    _base(state="running", instance_ids=[INSTANCE_1, "tdcpg-ins-ghost"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "instances were not found" in payload["msg"]
    assert payload["missing"] == ["tdcpg-ins-ghost"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusterInstances(self, request):
            raise Boom("tdcpg endpoint unreachable")

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tdcpg endpoint unreachable" in payload["error"]


def test_waiter_times_out_when_state_never_changes(monkeypatch):
    fake = _make_module(monkeypatch, FakeInstanceStateClient(instances=[_instance(INSTANCE_1, "isolated")], stuck=True))
    _base(state="running", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for instance state convergence" in payload["msg"]
    assert payload["expected"] == "running"
    assert payload["instances"][0]["Status"] == "isolated"


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdcpg_instance_state.py)
# ---------------------------------------------------------------------------


def test_instance_action_requests_map_exact_set_and_period():
    p = {"cluster_id": "c1", "instance_ids": ["i1", "i2"], "period_months": 3}
    isolate = mod.action_request(FakeModels().IsolateClusterInstancesRequest, p)
    assert isolate.ClusterId == "c1"
    assert isolate.InstanceIdSet == ["i1", "i2"]
    recover = mod.recover_request(FakeModels(), p)
    assert recover.ClusterId == "c1"
    assert recover.InstanceIdSet == ["i1", "i2"]
    assert recover.Period == 3
