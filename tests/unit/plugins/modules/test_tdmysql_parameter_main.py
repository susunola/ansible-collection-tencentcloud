"""Unit tests for the tdmysql_parameter write module (run_module flows).

``run_module()`` reconciles a partial map of TDSQL MySQL instance parameters
and optionally waits on the returned task Flow. It is driven end to end
against an in-memory fake client whose ``ModifyDBParameters`` operation
mutates a parameter store, so the post-write ``DescribeDBParameters``
refetch converges immediately.

Scenario matrix:

* idempotent no-op when every requested value already matches
* value drift updates that wait on the task Flow (and with ``wait=False``)
* check-mode dry run without any SDK write
* a changed parameter that requires restart surfaces ``restart_required``
* argument validation before any SDK call (empty parameters map)
* unknown parameter names are rejected before mutation
* task failures (Flow status failed) and waiter timeouts
* blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tdmysql_parameter.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_parameter as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-instance-abc"
TASK_ID = 77


def _base(**overrides):
    params = {"instance_id": INSTANCE_ID, "parameters": {"max_connections": "2000"}, "wait": True}
    params.update(overrides)
    return module_args(**params)


def _store(values):
    return {name: {"Param": name, "Value": value, "NeedRestart": False} for name, value in values.items()}


class FakeParameterClient(object):
    """In-memory TDSQL MySQL client holding instance parameter values."""

    def __init__(self, instance_id=INSTANCE_ID, params=None, flow_status="success"):
        self.instance_id = instance_id
        self.params = copy.deepcopy(params) if params is not None else {}
        self.flow_status = flow_status
        self.calls = []
        self.last_modify = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBParameters(self, request):
        self._record("DescribeDBParameters", request)
        assert request.InstanceId == self.instance_id
        return SimpleNamespace(
            Params=[FakeResource(dict(item)) for item in self.params.values()],
            RequestId="req-fake",
        )

    def ModifyDBParameters(self, request):
        self._record("ModifyDBParameters", request)
        self.last_modify = request
        for item in request.Params:
            if item.Param in self.params:
                self.params[item.Param]["Value"] = str(item.Value)
        return SimpleNamespace(TaskID=TASK_ID, RequestId="req-fake")

    def DescribeFlow(self, request):
        self._record("DescribeFlow", request)
        assert request.FlowId == TASK_ID
        return SimpleNamespace(Status=self.flow_status, RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_converged_parameters_are_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "2000"})))
    _base(parameters={"max_connections": "2000"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["restart_required"] is False
    assert result["parameters"]["max_connections"]["Value"] == "2000"
    assert _names(fake) == ["DescribeDBParameters"]


def test_converged_ignores_unrelated_parameters(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "2000", "slow_query_log": "OFF"})))
    _base(parameters={"max_connections": "2000"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert _names(fake) == ["DescribeDBParameters"]


# ---------------------------------------------------------------------------
# drift update flows
# ---------------------------------------------------------------------------


def test_parameter_drift_updates_and_waits_on_flow(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"})))
    _base(parameters={"max_connections": "2000"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["restart_required"] is False
    assert result["parameters"]["max_connections"]["Value"] == "2000"
    assert fake.params["max_connections"]["Value"] == "2000"
    assert fake.last_modify.InstanceId == INSTANCE_ID
    assert [(item.Param, item.Value) for item in fake.last_modify.Params] == [("max_connections", "2000")]
    assert _names(fake) == [
        "DescribeDBParameters",
        "ModifyDBParameters",
        "DescribeFlow",
        "DescribeDBParameters",
    ]


def test_parameter_drift_with_wait_disabled_skips_flow(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"})))
    _base(parameters={"max_connections": "2000"}, wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DescribeFlow" not in _names(fake)
    assert _names(fake) == ["DescribeDBParameters", "ModifyDBParameters", "DescribeDBParameters"]


def test_parameter_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"})))
    _base(parameters={"max_connections": "2000"}, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameters"]["max_connections"]["Value"] == "2000"
    assert "diff" in result
    assert fake.params["max_connections"]["Value"] == "1000"
    assert "ModifyDBParameters" not in _names(fake)


def test_restart_required_is_reported_for_changed_restarting_parameter(monkeypatch):
    params = {
        "max_connections": {"Param": "max_connections", "Value": "1000", "NeedRestart": False},
        "slow_query_log": {"Param": "slow_query_log", "Value": "OFF", "NeedRestart": True},
    }
    fake = _make_module(monkeypatch, FakeParameterClient(params=params))
    _base(parameters={"slow_query_log": "ON"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["restart_required"] is True
    assert result["parameters"]["slow_query_log"]["Value"] == "ON"
    assert fake.params["slow_query_log"]["Value"] == "ON"


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_empty_parameters_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient())
    _base(parameters={})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "parameters must not be empty" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_unknown_parameter_names_are_rejected(monkeypatch):
    fake = _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"})))
    _base(parameters={"max_connections": "2000", "bogus_setting": "1"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "unknown TDSQL MySQL parameter names" in payload["msg"]
    assert payload["unknown_parameters"] == ["bogus_setting"]
    assert _names(fake) == ["DescribeDBParameters"]


def test_flow_failure_fails(monkeypatch):
    _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"}), flow_status="failed"))
    _base(parameters={"max_connections": "2000"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "parameter task failed" in payload["msg"]
    assert payload["task_id"] == TASK_ID
    assert payload["status"] == "failed"


def test_flow_wait_times_out(monkeypatch):
    _make_module(monkeypatch, FakeParameterClient(params=_store({"max_connections": "1000"}), flow_status="running"))
    _base(parameters={"max_connections": "2000"}, waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for resource state" in payload["msg"]
    assert payload["expected_states"] == ["success"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBParameters(self, request):
            raise Boom("tdmysql endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base(parameters={"max_connections": "2000"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tdmysql endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdmysql_parameter.py)
# ---------------------------------------------------------------------------


class _StubModule(object):
    def sdk_call(self, operation, request=None):
        return operation(request)


def test_describe_and_flow_requests_map_instance_and_task():
    models = FakeModels()
    describe = mod.parameter_describe_request(models, "db1")
    assert describe.InstanceId == "db1"
    flow = mod.flow_request(models, 42)
    assert flow.FlowId == 42


def test_modify_request_maps_sorted_values_to_strings():
    request = mod.modify_request(FakeModels(), "db1", {"z": 2, "a": True})
    assert request.InstanceId == "db1"
    assert [(item.Param, item.Value) for item in request.Params] == [("a", "True"), ("z", "2")]


def test_read_and_select_parameters_are_name_keyed_and_stable():
    client = FakeParameterClient(instance_id="db1", params=_store({"a": "1", "b": "2"}))
    values = mod.read_parameters(_StubModule(), client, FakeModels(), "db1")
    assert mod.selected(values, ["a"])["a"]["Value"] == "1"
    assert list(mod.selected(values, ["b", "a"])) == ["a", "b"]
