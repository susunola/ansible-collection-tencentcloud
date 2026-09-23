"""Unit tests for the tse_gateway_upstream_node_status write module.

Drives ``run_module()`` against an in-memory fake TSE client whose describe
returns a mutable upstream-target list and whose modify flips the target's
health so the post-modify convergence wait resolves on the first poll.

Scenario matrix:

* target lookup: no-op, not-found guard, ambiguity guard
* drain/restore: HEALTHY -> UNHEALTHY modify, check-mode dry run
* failure paths: unsuccessful modify result, convergence timeout,
  blanket SDK failure
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_upstream_node_status as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_upstream_node_status import (
    describe_request,
    find_node,
    modify_request,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY_ID = "gateway-1001"
SERVICE_NAME = "orders"
HOST = "10.0.0.20"
PORT = 8080


def _target(host=HOST, port=PORT, health="HEALTHY"):
    return {"Host": host, "Port": port, "Health": health}


def _node_args(**overrides):
    params = {
        "gateway_id": GATEWAY_ID,
        "service_name": SERVICE_NAME,
        "host": HOST,
        "port": PORT,
        "status": "UNHEALTHY",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE upstream client backed by a mutable target list."""

    def __init__(self, targets=None, converge=True):
        self.targets = [dict(t) for t in targets or []]
        self.converge = converge
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _targets_by_identity(self, request):
        return [t for t in self.targets if t["Host"] == getattr(request, "Host", None)
                and int(t["Port"]) == int(getattr(request, "Port", None))]

    def DescribeCloudNativeAPIGatewayUpstream(self, request):
        self._record("DescribeCloudNativeAPIGatewayUpstream", request)
        payload = [SimpleNamespace(Target=[FakeResource(dict(t)) for t in self.targets])]
        result = SimpleNamespace(UpstreamList=payload, RequestId="req-fake")
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def ModifyUpstreamNodeStatus(self, request):
        self._record("ModifyUpstreamNodeStatus", request)
        if self.converge:
            for target in self._targets_by_identity(request):
                target["Health"] = getattr(request, "Status", target["Health"])
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# argument guards
# ---------------------------------------------------------------------------


def test_invalid_status_choice_fails():
    _node_args(status="DRAINING")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must be one of" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# lookup and reconcile flows
# ---------------------------------------------------------------------------


def test_target_already_desired_is_idempotent(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="UNHEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args(status="UNHEALTHY")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["node"]["Host"] == HOST
    assert result["node"]["Health"] == "UNHEALTHY"
    assert "ModifyUpstreamNodeStatus" not in _names(fake)


def test_target_not_found_fails(monkeypatch):
    fake = FakeTseClient(targets=[_target(host="10.0.0.99")])
    _make_module(monkeypatch, fake)
    _node_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TSE gateway upstream target was not found" in exc.value.args[0]["msg"]


def test_multiple_matching_targets_fail(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="HEALTHY"), _target(health="HEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway upstream targets matched" in exc.value.args[0]["msg"]


def test_drain_healthy_target_waits_for_convergence(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="HEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args(status="UNHEALTHY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Health"] == "UNHEALTHY"
    ops = _names(fake)
    assert "ModifyUpstreamNodeStatus" in ops
    assert "DescribeCloudNativeAPIGatewayUpstream" in ops
    assert fake.targets[0]["Health"] == "UNHEALTHY"


def test_restore_unhealthy_target_is_draining_direction(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="UNHEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args(status="HEALTHY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Health"] == "HEALTHY"
    assert fake.targets[0]["Health"] == "HEALTHY"


def test_check_mode_reports_change_without_modify(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="HEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args(_ansible_check_mode=True, status="UNHEALTHY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Health"] == "UNHEALTHY"
    assert "ModifyUpstreamNodeStatus" not in _names(fake)
    assert fake.targets[0]["Health"] == "HEALTHY"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_modify_unsuccessful_result_fails(monkeypatch):
    class RejectingClient(FakeTseClient):
        def ModifyUpstreamNodeStatus(self, request):
            self._record("ModifyUpstreamNodeStatus", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(targets=[_target(health="HEALTHY")])
    _make_module(monkeypatch, fake)
    _node_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "returned an unsuccessful result" in exc.value.args[0]["msg"]


def test_convergence_timeout_fails(monkeypatch):
    fake = FakeTseClient(targets=[_target(health="HEALTHY")], converge=False)
    _make_module(monkeypatch, fake)
    _node_args(status="UNHEALTHY", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayUpstream(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _node_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


class _Request(object):
    pass


class _Models(object):
    DescribeCloudNativeAPIGatewayUpstreamRequest = _Request
    ModifyUpstreamNodeStatusRequest = _Request


class _Target(object):
    def _serialize(self, allow_none=False):
        return {"Host": HOST, "Port": PORT, "Health": "HEALTHY"}


class _Upstream(object):
    Target = [_Target()]


class _Result(object):
    UpstreamList = [_Upstream()]


class _Response(object):
    Result = _Result()


class _Client(object):
    def DescribeCloudNativeAPIGatewayUpstream(self, request):
        return _Response()


class _Module(object):
    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


def test_legacy_requests_map_target_identity_and_status():
    params = {"gateway_id": GATEWAY_ID, "service_name": SERVICE_NAME, "host": HOST, "port": PORT, "status": "UNHEALTHY"}
    describe = describe_request(_Models, params)
    modify = modify_request(_Models, params)
    assert (describe.GatewayId, describe.ServiceName) == (GATEWAY_ID, SERVICE_NAME)
    assert (modify.Host, modify.Port, modify.Status) == (HOST, PORT, "UNHEALTHY")


def test_legacy_find_node_matches_host_and_port():
    assert find_node(_Module(), _Client(), _Models, {"gateway_id": GATEWAY_ID, "service_name": SERVICE_NAME, "host": HOST, "port": PORT})["Health"] == "HEALTHY"
