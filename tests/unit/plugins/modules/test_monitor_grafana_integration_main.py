"""Unit tests for the monitor_grafana_integration write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / update / delete operations mutate an integration store so the
module's post-write ``find`` converges immediately.

Scenario matrix:

* absent on a missing integration (idempotent no-op, by id and by kind)
* absent with a matching integration (check-mode dry run, real delete)
* creation when missing (happy path and check mode)
* no-op when kind / content already match
* content drift triggers an Update
* the ambiguous-kind guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_integration as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INTEGRATION = {
    "IntegrationId": "intg-abc123",
    "Kind": "tencent-cloud-prometheus",
    "Content": '{"prometheusId": "prom-abc123"}',
}


def _integration(**overrides):
    item = copy.deepcopy(INTEGRATION)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "instance_id": "grafana-abc123",
        "kind": "tencent-cloud-prometheus",
        "content": '{"prometheusId": "prom-abc123"}',
    }
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating an integration store."""

    def __init__(self, integrations=None):
        self.integrations = [copy.deepcopy(t) for t in (integrations or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGrafanaIntegrations(self, request):
        self._record("DescribeGrafanaIntegrations", request)
        matched = list(self.integrations)
        iid = getattr(request, "IntegrationId", None)
        if iid:
            matched = [t for t in matched if t.get("IntegrationId") == iid]
        else:
            kind = getattr(request, "Kind", None)
            if kind:
                matched = [t for t in matched if t.get("Kind") == kind]
        return SimpleNamespace(IntegrationSet=[FakeResource(t) for t in matched])

    def CreateGrafanaIntegration(self, request):
        self._record("CreateGrafanaIntegration", request)
        self._next += 1
        item = {
            "IntegrationId": "intg-new-%03d" % self._next,
            "Kind": getattr(request, "Kind", None),
            "Content": getattr(request, "Content", None),
        }
        self.integrations.append(item)
        return SimpleNamespace(IntegrationId=item["IntegrationId"], RequestId="req-fake")

    def UpdateGrafanaIntegration(self, request):
        self._record("UpdateGrafanaIntegration", request)
        for item in self.integrations:
            if item.get("IntegrationId") == getattr(request, "IntegrationId", None):
                item["Kind"] = getattr(request, "Kind", item.get("Kind"))
                item["Content"] = getattr(request, "Content", item.get("Content"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteGrafanaIntegration(self, request):
        self._record("DeleteGrafanaIntegration", request)
        iid = getattr(request, "IntegrationId", None)
        self.integrations = [t for t in self.integrations if t.get("IntegrationId") != iid]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(integrations=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", integration_id="intg-999", content=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["integration"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGrafanaIntegrations"]


def test_absent_missing_by_kind_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(integrations=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", content=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["integration"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(integrations=[_integration()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["integration"]["IntegrationId"] == "intg-abc123"
    assert len(fake.integrations) == 1
    assert "DeleteGrafanaIntegration" not in [c for c, unused in fake.calls]


def test_absent_deletes_integration(monkeypatch):
    fake = FakeMonitorClient(integrations=[_integration()])
    _make_module(monkeypatch, fake)
    _args(state="absent", content=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["integration"] is None
    assert fake.integrations == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteGrafanaIntegration" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_integration(monkeypatch):
    fake = FakeMonitorClient(integrations=[])
    _make_module(monkeypatch, fake)
    _args(state="present", kind="tencent-cloud-tencent-monitor", content="{}")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["integration"]["IntegrationId"].startswith("intg-new-")
    assert result["integration"]["Kind"] == "tencent-cloud-tencent-monitor"
    assert result["integration"]["Content"] == "{}"
    assert len(fake.integrations) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGrafanaIntegrations"
    assert "CreateGrafanaIntegration" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(integrations=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", kind="tencent-cloud-tencent-monitor", content="{}")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["integration"] is None
    assert fake.integrations == []
    assert "CreateGrafanaIntegration" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-integration flows
# ---------------------------------------------------------------------------


def test_existing_integration_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(integrations=[_integration()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["integration"]["IntegrationId"] == "intg-abc123"
    assert "UpdateGrafanaIntegration" not in [c for c, unused in fake.calls]


def test_content_drift_updates_integration(monkeypatch):
    drift = '{"prometheusId": "prom-xyz789"}'
    fake = FakeMonitorClient(integrations=[_integration()])
    _make_module(monkeypatch, fake)
    _args(state="present", content=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["integration"]["Content"] == drift
    assert fake.integrations[0]["Content"] == drift
    ops = [c for c, unused in fake.calls]
    assert "UpdateGrafanaIntegration" in ops


def test_ambiguous_kind_match_fails(monkeypatch):
    fake = FakeMonitorClient(integrations=[_integration(), _integration(IntegrationId="intg-xyz789")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Grafana integrations have the requested kind" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGrafanaIntegrations(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
