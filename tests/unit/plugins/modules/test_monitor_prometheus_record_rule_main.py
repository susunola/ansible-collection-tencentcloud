"""Unit tests for the monitor_prometheus_record_rule write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / modify / delete operations mutate a record-rule store so the
module's post-write ``find`` converges immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run, real delete)
* creation when missing (happy path and check mode)
* no-op when the YAML content already matches
* content drift triggers a Modify
* the ambiguous-name guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_record_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONTENT = (
    "groups:\n"
    "  - name: application\n"
    "    rules:\n"
    "      - record: job:http_requests:rate5m\n"
    "        expr: sum by (job) (rate(http_requests_total[5m]))\n"
)
RECORD_RULE = {"Name": "application-rollups", "Content": CONTENT}


def _rule(**overrides):
    item = copy.deepcopy(RECORD_RULE)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": "prom-abc123", "name": "application-rollups", "content": CONTENT}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating a record-rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(t) for t in (rules or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusRecordRules(self, request):
        self._record("DescribePrometheusRecordRules", request)
        return SimpleNamespace(Records=[FakeResource(t) for t in self.rules])

    def CreatePrometheusRecordRuleYaml(self, request):
        self._record("CreatePrometheusRecordRuleYaml", request)
        self._next += 1
        self.rules.append({
            "Name": getattr(request, "Name", None),
            "Content": getattr(request, "Content", None),
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyPrometheusRecordRuleYaml(self, request):
        self._record("ModifyPrometheusRecordRuleYaml", request)
        for item in self.rules:
            if item.get("Name") == getattr(request, "Name", None):
                item["Content"] = getattr(request, "Content", item.get("Content"))
        return SimpleNamespace(RequestId="req-fake")

    def DeletePrometheusRecordRuleYaml(self, request):
        self._record("DeletePrometheusRecordRuleYaml", request)
        names = list(getattr(request, "Names", None) or [])
        self.rules = [t for t in self.rules if t.get("Name") not in names]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(rules=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-rule", content=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record_rule"] is None
    assert [c for c, unused in fake.calls] == ["DescribePrometheusRecordRules"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent", content=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record_rule"]["Name"] == "application-rollups"
    assert len(fake.rules) == 1
    assert "DeletePrometheusRecordRuleYaml" not in [c for c, unused in fake.calls]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeMonitorClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _args(state="absent", content=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record_rule"] is None
    assert fake.rules == []
    ops = [c for c, unused in fake.calls]
    assert "DeletePrometheusRecordRuleYaml" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_rule(monkeypatch):
    fake = FakeMonitorClient(rules=[])
    _make_module(monkeypatch, fake)
    _args(state="present", name="application-rollups", content=CONTENT)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record_rule"]["Name"] == "application-rollups"
    assert result["record_rule"]["Content"] == CONTENT
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusRecordRules"
    assert "CreatePrometheusRecordRuleYaml" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(rules=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", content=CONTENT)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record_rule"] is None
    assert fake.rules == []
    assert "CreatePrometheusRecordRuleYaml" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record_rule"]["Name"] == "application-rollups"
    assert "ModifyPrometheusRecordRuleYaml" not in [c for c, unused in fake.calls]


def test_content_drift_modifies_rule(monkeypatch):
    drift = CONTENT + "      - record: job:http_requests:rate1m\n        expr: rate(http_requests_total[1m])\n"
    fake = FakeMonitorClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _args(state="present", content=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record_rule"]["Content"] == drift
    assert fake.rules[0]["Content"] == drift
    ops = [c for c, unused in fake.calls]
    assert "ModifyPrometheusRecordRuleYaml" in ops


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeMonitorClient(rules=[_rule(), _rule(Name="application-rollups")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Prometheus record rules have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusRecordRules(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
