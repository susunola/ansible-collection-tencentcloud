"""Unit tests for the oceanus_resource_config write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Oceanus client
whose write operations mutate the immutable resource-version store, so the
post-write describe refetches (including the waiters) converge on the first
poll without sleeping.

Scenario matrix:

* absent on a missing version (idempotent) / real delete / delete of a
  historical version while a newer one stays / check-mode dry run
* delete blocked while a job configuration references the version, and
  authorized via ``allow_delete_in_use``
* present: publish when no version exists, publish a new immutable version
  on content drift, no-op when the latest version already matches, and
  picking the latest version among several
* check-mode create preview
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_resource_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RESOURCE_ID = "resource-8b0a1c2d"
WORKSPACE_ID = "space-8b0a1c2d"

LOCATION = {
    "StorageType": 1,
    "Param": {"Bucket": "flink-artifacts-1250000000", "Path": "jars/orders-1.1.jar", "Region": "ap-guangzhou"},
}

VERSION = {
    "Version": 3,
    "ResourceId": RESOURCE_ID,
    "WorkSpaceId": WORKSPACE_ID,
    "ResourceLoc": copy.deepcopy(LOCATION),
    "Remark": "release-1.1",
    "Status": 1,
}


def _version(version, **overrides):
    item = copy.deepcopy(VERSION)
    item["Version"] = version
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"resource_id": RESOURCE_ID, "workspace_id": WORKSPACE_ID, "resource_location": copy.deepcopy(LOCATION), "remark": "release-1.1"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating an immutable resource-version store."""

    def __init__(self, configs=None, jobs=None):
        self.configs = [copy.deepcopy(t) for t in (configs or [])]
        self.jobs = [copy.deepcopy(t) for t in (jobs or [])]
        self.calls = []

    def _scope(self, request):
        return getattr(request, "ResourceId", None), getattr(request, "WorkSpaceId", None)

    def _dictify(self, value):
        if isinstance(value, dict):
            return {k: self._dictify(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._dictify(v) for v in value]
        if value is not None and not isinstance(value, (bool, int, float, str)) and hasattr(value, "__dict__"):
            return {k: self._dictify(v) for k, v in vars(value).items() if not k.startswith("_")}
        return value

    def DescribeResourceConfigs(self, request):
        self.calls.append("DescribeResourceConfigs")
        rid, wid = self._scope(request)
        versions = getattr(request, "ResourceConfigVersions", None)
        matched = [
            t for t in self.configs
            if t.get("ResourceId") == rid and t.get("WorkSpaceId") == wid and (versions is None or t.get("Version") in versions)
        ]
        matched = sorted(matched, key=lambda t: t["Version"])
        return SimpleNamespace(ResourceConfigSet=[FakeResource(t) for t in matched], TotalCount=len(matched), RequestId="req-fake")

    def DescribeResourceRelatedJobs(self, request):
        self.calls.append("DescribeResourceRelatedJobs")
        rid = getattr(request, "ResourceId", None)
        version = getattr(request, "ResourceConfigVersion", None)
        matched = [t for t in self.jobs if t.get("ResourceId") == rid and t.get("ResourceConfigVersion") == version]
        return SimpleNamespace(RefJobInfos=[FakeResource(t) for t in matched], TotalCount=len(matched), RequestId="req-fake")

    def CreateResourceConfig(self, request):
        self.calls.append("CreateResourceConfig")
        rid, wid = self._scope(request)
        existing = [t["Version"] for t in self.configs if t.get("ResourceId") == rid and t.get("WorkSpaceId") == wid]
        version = (max(existing) if existing else 0) + 1
        item = self._dictify(request)
        item["Version"] = version
        item["Status"] = 1
        self.configs.append(item)
        return SimpleNamespace(Version=version, RequestId="req-fake")

    def DeleteResourceConfigs(self, request):
        self.calls.append("DeleteResourceConfigs")
        rid, wid = self._scope(request)
        versions = getattr(request, "ResourceConfigVersions", None) or []
        self.configs = [
            t for t in self.configs
            if not (t.get("ResourceId") == rid and t.get("WorkSpaceId") == wid and t.get("Version") in versions)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_version_is_idempotent(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", version=3)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource_config"] is None
    assert list(fake.calls) == ["DescribeResourceConfigs"]


def test_absent_referenced_version_fails_without_authorization(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(3)], jobs=[{"ResourceId": RESOURCE_ID, "ResourceConfigVersion": 3, "JobId": "job-1"}])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=3)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "referenced by job configurations" in payload["msg"]
    assert payload["version"] == 3
    assert payload["references"][0]["JobId"] == "job-1"


def test_absent_delete_authorized_when_referenced(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(3)], jobs=[{"ResourceId": RESOURCE_ID, "ResourceConfigVersion": 3, "JobId": "job-1"}])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=3, allow_delete_in_use=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.configs == []
    assert "DeleteResourceConfigs" in fake.calls


def test_absent_deletes_version(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(3)])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"] is None
    assert fake.configs == []
    ops = list(fake.calls)
    assert "DeleteResourceConfigs" in ops


def test_absent_deletes_historical_version_keeps_newer(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(1, Remark="release-1.0"), _version(3)])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [t["Version"] for t in fake.configs] == [3]
    assert "DeleteResourceConfigs" in fake.calls


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(3)])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", version=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.configs) == 1
    assert "DeleteResourceConfigs" not in fake.calls


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_no_current_publishes_first_version(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] == 1
    assert result["resource_config"]["Version"] == 1
    assert result["resource_config"]["Remark"] == "release-1.1"
    assert len(fake.configs) == 1
    assert "CreateResourceConfig" in fake.calls


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] is None
    assert result["resource_config"]["ResourceLoc"] == LOCATION
    assert fake.configs == []
    assert "CreateResourceConfig" not in fake.calls


def test_present_latest_matches_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(3)])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["version"] == 3
    assert result["resource_config"]["Version"] == 3
    assert "CreateResourceConfig" not in fake.calls


def test_present_picks_latest_version_among_several(monkeypatch):
    fake = FakeOceanusClient(configs=[_version(1, Remark="release-1.0", ResourceLoc=copy.deepcopy(LOCATION)), _version(3)])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["version"] == 3
    assert "CreateResourceConfig" not in fake.calls


def test_present_creates_new_version_on_content_drift(monkeypatch):
    drift = copy.deepcopy(LOCATION)
    drift["Param"]["Path"] = "jars/orders-1.2.jar"
    fake = FakeOceanusClient(configs=[_version(3)])
    _make_module(monkeypatch, fake)
    _base(resource_location=drift, remark="release-1.2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] == 4
    assert result["resource_config"]["Version"] == 4
    assert result["resource_config"]["Remark"] == "release-1.2"
    assert [t["Version"] for t in fake.configs] == [3, 4]
    assert fake.configs[1]["ResourceLoc"]["Param"]["Path"] == "jars/orders-1.2.jar"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeResourceConfigs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_resource_config.py)
# ---------------------------------------------------------------------------


def test_desired_manages_location_and_explicit_remark():
    location = {"StorageType": 1, "Param": {"Bucket": "artifacts", "Path": "jobs/a.jar", "Region": "ap-guangzhou"}}
    assert mod.desired({"resource_location": location, "remark": "release-2"}) == {"ResourceLoc": location, "Remark": "release-2"}


def test_desired_does_not_manage_omitted_remark():
    location = {"StorageType": 1, "Param": {"Bucket": "artifacts", "Path": "jobs/a.jar"}}
    assert mod.desired({"resource_location": location, "remark": None}) == {"ResourceLoc": location}


def test_managed_value_ignores_sdk_noise_inside_resource_location():
    target = {"ResourceLoc": {"StorageType": 1, "Param": {"Bucket": "artifacts", "Path": "jobs/a.jar"}}}
    current = {
        "ResourceLoc": {
            "StorageType": 1,
            "Param": {"Bucket": "artifacts", "Path": "jobs/a.jar", "Region": None},
            "FlinkConnectorJarUri": None,
        },
        "Status": 1,
    }
    assert mod.managed_value(current, target) == target
