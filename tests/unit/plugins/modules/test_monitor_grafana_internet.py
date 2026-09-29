"""Tests for the Grafana internet-access writer: monitor_grafana_internet.

The module reads one Grafana instance through ``DescribeGrafanaInstances`` and
decides whether internet access is on from ``InternetUrl``: an empty URL means
off. When the observed state differs from ``enabled`` it calls
``EnableGrafanaInternet`` and then polls until the URL the API reports matches
what was asked for, bounded by ``waiter_timeout``.

The three helper tests came first and stay as they were: the describe answer is
read from the current ``Instances`` field (``InstanceSet`` is the older
spelling), a missing instance fails instead of being reported as "internet
off", and the waiter observes the URL rather than assuming the write worked.
Everything below drives ``run_module()`` through the shared harness against an
in-memory Monitor client whose write mutates the stored instance, so the
idempotent no-op, the drift flows, the check-mode dry run, the not-found
failure and the wait timeout are the module's own behaviour.

The client is resolved through the module's ``_load()`` seam, so the SDK is
never imported; ``TencentCloudModule.create_client`` returns the fake.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import itertools
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_internet as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class Request:
    pass


MODELS = types.SimpleNamespace(DescribeGrafanaInstancesRequest=Request)


class Module:
    params = {"waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_read_uses_current_instances_field_and_exact_id():
    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[
                types.SimpleNamespace(InstanceId="other", InternetUrl="https://other"),
                types.SimpleNamespace(InstanceId="grafana-1", InternetUrl=""),
            ], InstanceSet=None)

    assert mod.read_internet_state(Module(), Client(), MODELS, "grafana-1") is False


def test_read_rejects_missing_instance():
    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[], InstanceSet=[])

    with pytest.raises(ValueError, match="was not found"):
        mod.read_internet_state(Module(), Client(), MODELS, "grafana-1")


def test_waiter_observes_internet_url(monkeypatch):
    responses = iter(["", "https://grafana.example"])

    class Client:
        def DescribeGrafanaInstances(self, request):
            return types.SimpleNamespace(Instances=[
                types.SimpleNamespace(InstanceId="grafana-1", InternetUrl=next(responses)),
            ])

    monkeypatch.setattr(mod.time, "sleep", lambda delay: None)
    assert mod.wait_for_internet_state(Module(), Client(), MODELS, "grafana-1", True) is True


INSTANCE_ID = "grafana-abc123"
INTERNET_URL = "https://grafana-abc123.grafana.tencentcloud.com"

#: One Grafana instance as ``DescribeGrafanaInstances`` returns it.
INSTANCE = {
    "InstanceId": INSTANCE_ID,
    "InstanceName": "production-dashboards",
    "InternetUrl": INTERNET_URL,
}


class FakeMonitorClient(object):
    """In-memory Monitor client toggling ``InternetUrl`` on a Grafana instance.

    ``converge=False`` models the API accepting the write but not reporting the
    new URL yet -- what the waiter exists for; the store then never changes and
    the wait runs into its deadline.
    """

    def __init__(self, instances=None, converge=True, error=None):
        self.instances = [dict(item) for item in (instances or [])]
        self.converge = converge
        self.error = error
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        if self.error is not None:
            raise self.error

    @property
    def operations(self):
        return [name for name, _request in self.calls]

    def DescribeGrafanaInstances(self, request):
        self._record("DescribeGrafanaInstances", request)
        wanted = set(getattr(request, "InstanceIds", None) or [])
        return types.SimpleNamespace(
            Instances=[FakeResource(item) for item in self.instances if item["InstanceId"] in wanted],
            InstanceSet=None,
            RequestId="req-monitor-1",
        )

    def EnableGrafanaInternet(self, request):
        self._record("EnableGrafanaInternet", request)
        if self.converge:
            for item in self.instances:
                if item["InstanceId"] == request.InstanceID:
                    item["InternetUrl"] = INTERNET_URL if request.EnableInternet else ""
        return types.SimpleNamespace(RequestId="req-monitor-1")


def _patch_module(monkeypatch, client):
    """Point ``mod`` at ``client`` through its ``_load``/``create_client`` seams."""
    clients = []
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), types.SimpleNamespace(MonitorClient=object)))

    def create_client(self, client_class, endpoint):
        clients.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return clients


def _args(enabled=False, **extra):
    args = {"instance_id": INSTANCE_ID, "enabled": enabled}
    args.update(extra)
    return module_args(**args)


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------


def test_describe_request_asks_for_exactly_one_instance():
    request = mod.build_describe(FakeModels(), INSTANCE_ID)

    assert request.InstanceIds == [INSTANCE_ID]
    assert (request.Offset, request.Limit) == (0, 1)


def test_update_request_carries_the_instance_and_the_target_state():
    request = mod.build_update(FakeModels(), INSTANCE_ID, True)

    assert (request.InstanceID, request.EnableInternet) == (INSTANCE_ID, True)
    assert not hasattr(request, "Offset")


# ---------------------------------------------------------------------------
# run_module: idempotent flows
# ---------------------------------------------------------------------------


def test_run_module_reports_the_documented_keys_when_nothing_changes(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")])
    _patch_module(monkeypatch, client)
    _args(enabled=False)

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "enabled", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["enabled"] is False
    assert client.operations == ["DescribeGrafanaInstances"]
    assert [request.InstanceIds for _name, request in client.calls] == [[INSTANCE_ID]]


def test_run_module_reports_enabled_true_without_a_write_when_access_is_on(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE)])
    _patch_module(monkeypatch, client)
    _args(enabled=True)

    payload = run(mod.run_module)

    assert payload["changed"] is False
    assert payload["enabled"] is True
    assert client.operations == ["DescribeGrafanaInstances"]


def test_run_module_is_idempotent_after_convergence(monkeypatch):
    """The second run finds the state the first one created and changes nothing."""
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")])
    clients = _patch_module(monkeypatch, client)
    _args(enabled=True)

    first = run(mod.run_module)
    second = run(mod.run_module)

    assert first["changed"] is True
    assert second["changed"] is False
    assert second["enabled"] is True
    assert client.operations == [
        "DescribeGrafanaInstances", "EnableGrafanaInternet", "DescribeGrafanaInstances",
        "DescribeGrafanaInstances",
    ]
    assert clients == [(object, "monitor.tencentcloudapi.com")] * 2


# ---------------------------------------------------------------------------
# run_module: drift flows
# ---------------------------------------------------------------------------


def test_run_module_enables_internet_and_waits_for_the_url(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")])
    clients = _patch_module(monkeypatch, client)
    _args(enabled=True)

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "enabled", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["enabled"] is True
    assert client.instances[0]["InternetUrl"] == INTERNET_URL
    assert client.operations == ["DescribeGrafanaInstances", "EnableGrafanaInternet", "DescribeGrafanaInstances"]
    update_request = [request for name, request in client.calls if name == "EnableGrafanaInternet"][0]
    assert (update_request.InstanceID, update_request.EnableInternet) == (INSTANCE_ID, True)
    assert clients == [(object, "monitor.tencentcloudapi.com")]


def test_run_module_disables_internet(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE)])
    _patch_module(monkeypatch, client)
    _args(enabled=False)

    payload = run(mod.run_module)

    assert payload["changed"] is True
    assert payload["enabled"] is False
    assert client.instances[0]["InternetUrl"] == ""
    update_request = [request for name, request in client.calls if name == "EnableGrafanaInternet"][0]
    assert update_request.EnableInternet is False


def test_run_module_check_mode_predicts_the_change_without_writing(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")])
    _patch_module(monkeypatch, client)
    _args(enabled=True, _ansible_check_mode=True)

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "enabled", "diff", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["enabled"] is True
    # The instance is currently off, so ``before`` is False -- an earlier
    # build_diff folded that into None and this test pinned the folding.
    assert payload["diff"] == {"before": False, "after": True}
    assert client.operations == ["DescribeGrafanaInstances"]
    assert client.instances[0]["InternetUrl"] == ""


# ---------------------------------------------------------------------------
# run_module: failure paths
# ---------------------------------------------------------------------------


def test_run_module_fails_when_the_instance_is_not_found(monkeypatch):
    """An unknown instance is an error, not "internet access is off"."""
    client = FakeMonitorClient(instances=[])
    _patch_module(monkeypatch, client)
    _args(enabled=False)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Grafana instance was not found"
    assert payload["instance_id"] == INSTANCE_ID
    assert client.operations == ["DescribeGrafanaInstances"]


def test_run_module_times_out_when_the_url_never_converges(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")], converge=False)
    _patch_module(monkeypatch, client)
    ticks = itertools.count(1000.0, 500.0)
    monkeypatch.setattr(mod.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(mod.time, "sleep", lambda *args, **kwargs: None)
    _args(enabled=True)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Timed out waiting for Grafana internet access convergence"
    assert payload["instance_id"] == INSTANCE_ID
    assert payload["enabled"] is False
    assert payload["expected"] is True
    assert client.operations == ["DescribeGrafanaInstances", "EnableGrafanaInternet", "DescribeGrafanaInstances"]


def test_run_module_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-monitor-denied"

    client = FakeMonitorClient(error=FakeSdkException("not allowed to read Grafana instances"))
    _patch_module(monkeypatch, client)
    _args(enabled=True)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "not allowed to read Grafana instances"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-monitor-denied"
    assert payload["error_kind"] == "unauthorized"


def test_run_module_maps_an_unexpected_error_to_the_failure_envelope(monkeypatch):
    client = FakeMonitorClient(instances=[dict(INSTANCE, InternetUrl="")], error=RuntimeError("socket closed"))
    _patch_module(monkeypatch, client)
    _args(enabled=True)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "socket closed"
    assert payload["error_kind"] == "other"
