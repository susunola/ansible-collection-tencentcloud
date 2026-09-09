"""Unit tests for the monitor_prometheus_scrape_job write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / update / delete operations mutate a scrape-job store so the
module's post-write ``find`` converges immediately.

Scenario matrix:

* absent on a missing job (idempotent no-op, by id and by name)
* absent with a matching job (check-mode dry run, real delete)
* creation when missing (happy path and check mode)
* no-op when the job config already matches
* config drift triggers an Update
* the ambiguous-name guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_scrape_job as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG = (
    "job_name: application\n"
    "static_configs:\n"
    "  - targets: ['10.0.0.8:9100']\n"
)
SCRAPE_JOB = {
    "JobId": "job-abc123",
    "Name": "application",
    "Config": CONFIG,
}


def _job(**overrides):
    item = copy.deepcopy(SCRAPE_JOB)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": "prom-abc123", "agent_id": "agent-abc123", "name": "application", "config": CONFIG}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating a scrape-job store."""

    def __init__(self, jobs=None):
        self.jobs = [copy.deepcopy(t) for t in (jobs or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusScrapeJobs(self, request):
        self._record("DescribePrometheusScrapeJobs", request)
        matched = list(self.jobs)
        ids = list(getattr(request, "JobIds", None) or [])
        if ids:
            matched = [t for t in matched if t.get("JobId") in ids]
        else:
            name = getattr(request, "Name", None)
            if name:
                matched = [t for t in matched if t.get("Name") == name]
        return SimpleNamespace(ScrapeJobSet=[FakeResource(t) for t in matched])

    def CreatePrometheusScrapeJob(self, request):
        self._record("CreatePrometheusScrapeJob", request)
        self._next += 1
        item = {
            "JobId": "job-new-%03d" % self._next,
            "Name": "",
            "Config": getattr(request, "Config", None),
        }
        self.jobs.append(item)
        return SimpleNamespace(JobId=item["JobId"], RequestId="req-fake")

    def UpdatePrometheusScrapeJob(self, request):
        self._record("UpdatePrometheusScrapeJob", request)
        for item in self.jobs:
            if item.get("JobId") == getattr(request, "JobId", None):
                item["Config"] = getattr(request, "Config", item.get("Config"))
        return SimpleNamespace(RequestId="req-fake")

    def DeletePrometheusScrapeJobs(self, request):
        self._record("DeletePrometheusScrapeJobs", request)
        ids = list(getattr(request, "JobIds", None) or [])
        self.jobs = [t for t in self.jobs if t.get("JobId") not in ids]
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
    fake = FakeMonitorClient(jobs=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name=None, job_id="job-999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scrape_job"] is None
    assert [c for c, unused in fake.calls] == ["DescribePrometheusScrapeJobs"]


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(jobs=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-job")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scrape_job"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scrape_job"]["JobId"] == "job-abc123"
    assert len(fake.jobs) == 1
    assert "DeletePrometheusScrapeJobs" not in [c for c, unused in fake.calls]


def test_absent_deletes_job(monkeypatch):
    fake = FakeMonitorClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scrape_job"] is None
    assert fake.jobs == []
    ops = [c for c, unused in fake.calls]
    assert "DeletePrometheusScrapeJobs" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_job(monkeypatch):
    fake = FakeMonitorClient(jobs=[])
    _make_module(monkeypatch, fake)
    _args(state="present", name="application", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scrape_job"]["JobId"].startswith("job-new-")
    assert result["scrape_job"]["Config"] == CONFIG
    assert len(fake.jobs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusScrapeJobs"
    assert "CreatePrometheusScrapeJob" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(jobs=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scrape_job"] is None
    assert fake.jobs == []
    assert "CreatePrometheusScrapeJob" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-job flows
# ---------------------------------------------------------------------------


def test_existing_job_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scrape_job"]["JobId"] == "job-abc123"
    assert "UpdatePrometheusScrapeJob" not in [c for c, unused in fake.calls]


def test_config_drift_updates_job(monkeypatch):
    drift = CONFIG + "  - targets: ['10.0.0.9:9100']\n"
    fake = FakeMonitorClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _args(state="present", config=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scrape_job"]["Config"] == drift
    assert fake.jobs[0]["Config"] == drift
    ops = [c for c, unused in fake.calls]
    assert "UpdatePrometheusScrapeJob" in ops


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeMonitorClient(jobs=[_job(), _job(JobId="job-xyz789")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Prometheus scrape jobs have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusScrapeJobs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
