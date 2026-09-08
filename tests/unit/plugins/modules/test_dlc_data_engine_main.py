"""Unit tests for the dlc_data_engine write module (run_module flows).

Complements ``test_dlc_data_engine.py`` (request-builder level) by driving
``run_module()`` end to end against an in-memory fake DLC client whose write
operations mutate the engine store, so the module's post-write ``find``
refetch and waiters converge immediately.

Scenario matrix:

* absent on a missing engine (idempotent no-op)
* absent with a matching engine (requires ``allow_delete``, check-mode dry
  run, and the real delete path)
* creation when missing (with/without the mandatory creation parameters,
  check mode, waiting and the resulting engine lookup)
* no-op when nothing drifts
* drift updates (mutable fields, description) with and without ``wait``
* the scale-down / image-switch / standby-cluster authorization guards
* state transitions (resume a suspended engine)
* validation guards (description length, cluster bounds, conflicting
  crontab/auto_suspend) and the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_data_engine as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENGINE = {
    "DataEngineId": "engine-8b0a1c2d",
    "DataEngineName": "spark-prod",
    "State": 2,
    "EngineType": "spark",
    "EngineTypeDetail": "SparkSQL",
    "EngineExecType": "SQL",
    "ClusterType": "spark_cu",
    "Mode": 1,
    "PayMode": 0,
    "Message": "production",
    "Size": 16,
    "MinClusters": 1,
    "MaxClusters": 3,
    "AutoResume": True,
    "ImageVersionName": "0.9",
    "ImageVersionId": "img-0",
    "StartStandbyCluster": False,
}

IMAGES = [{"ImageVersion": "1.0", "ImageVersionId": "img-1", "State": 2}]


def _engine(**overrides):
    item = copy.deepcopy(ENGINE)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (engine_type, mode, engine_exec_type,
    # resource_type, engine_generation, crontab_resume_suspend, ...) must not
    # be pre-filled with None -- Ansible validates explicit values against the
    # choices. Pass a concrete value only when a scenario needs it.
    params = {"name": "spark-prod"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a small data-engine store."""

    def __init__(self, engines=None, images=None):
        self.engines = [copy.deepcopy(t) for t in (engines or [])]
        self.images = [copy.deepcopy(t) for t in (images or IMAGES)]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find_engine(self, name):
        for item in self.engines:
            if item.get("DataEngineName") == name:
                return item
        return None

    def DescribeDataEngines(self, request):
        self._record("DescribeDataEngines", request)
        name = request.Filters[0].Values[0]
        matches = [dict(t) for t in self.engines if t.get("DataEngineName") == name and t.get("State") != -2]
        return SimpleNamespace(
            DataEngines=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateDataEngine(self, request):
        self._record("CreateDataEngine", request)
        self._next += 1
        item = {
            "DataEngineId": "engine-new-%03d" % self._next,
            "DataEngineName": getattr(request, "DataEngineName", None),
            "State": 2,
            "Message": getattr(request, "Message", None),
        }
        for attr in (
            "EngineType", "ClusterType", "Mode", "PayMode", "Size", "MinClusters",
            "MaxClusters", "AutoResume", "AutoSuspend", "AutoSuspendTime",
            "MaxConcurrency", "TolerableQueueTime", "CrontabResumeSuspend",
            "CrontabResumeSuspendStrategy", "ElasticSwitch", "ElasticLimit",
            "ScheduleElasticityConf", "EngineExecType", "EngineGeneration",
            "ImageVersionName",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        item.setdefault("StartStandbyCluster", False)
        self.engines.append(item)
        return SimpleNamespace(DataEngineId=item["DataEngineId"], RequestId="req-fake")

    def UpdateDataEngine(self, request):
        self._record("UpdateDataEngine", request)
        item = self._find_engine(getattr(request, "DataEngineName", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in (
            "Size", "MinClusters", "MaxClusters", "AutoResume", "AutoSuspend",
            "AutoSuspendTime", "MaxConcurrency", "TolerableQueueTime",
            "CrontabResumeSuspend", "CrontabResumeSuspendStrategy", "ElasticSwitch",
            "ElasticLimit", "ScheduleElasticityConf",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDataEngineDescription(self, request):
        self._record("ModifyDataEngineDescription", request)
        item = self._find_engine(getattr(request, "DataEngineName", None))
        if item is not None:
            item["Message"] = getattr(request, "Message", None)
        return SimpleNamespace(RequestId="req-fake")

    def SuspendResumeDataEngine(self, request):
        self._record("SuspendResumeDataEngine", request)
        item = self._find_engine(getattr(request, "DataEngineName", None))
        if item is not None:
            item["State"] = 2 if getattr(request, "Operate", None) == "resume" else 1
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDataEngine(self, request):
        self._record("DeleteDataEngine", request)
        names = list(getattr(request, "DataEngineNames", None) or [])
        self.engines = [t for t in self.engines if t.get("DataEngineName") not in names]
        return SimpleNamespace(RequestId="req-fake")

    def DescribeDataEngineImageVersions(self, request):
        self._record("DescribeDataEngineImageVersions", request)
        return SimpleNamespace(ImageParentVersions=[FakeResource(t) for t in self.images])

    def SwitchDataEngineImage(self, request):
        self._record("SwitchDataEngineImage", request)
        for item in self.engines:
            if item.get("DataEngineId") == getattr(request, "DataEngineId", None):
                item["ImageVersionId"] = getattr(request, "NewImageVersionId", None)
                for image in self.images:
                    if image.get("ImageVersionId") == getattr(request, "NewImageVersionId", None):
                        item["ImageVersionName"] = image.get("ImageVersion")
        return SimpleNamespace(RequestId="req-fake")

    def SwitchDataEngine(self, request):
        self._record("SwitchDataEngine", request)
        item = self._find_engine(getattr(request, "DataEngineName", None))
        if item is not None:
            item["StartStandbyCluster"] = getattr(request, "StartStandbyCluster", None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_engine_is_idempotent(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-engine")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["data_engine"] is None
    assert result["data_engine_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDataEngines"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.engines) == 1
    assert "DeleteDataEngine" not in [c for c, unused in fake.calls]


def test_absent_deletes_engine(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"] is None
    assert fake.engines == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteDataEngine" in ops


def test_absent_delete_waits_for_convergence(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.engines == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "creation parameters are required" in exc.value.args[0]["msg"]
    assert exc.value.args[0]["missing"] == ["engine_type", "cluster_type", "mode"]


def test_create_engine(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="spark-prod",
        engine_type="spark",
        cluster_type="spark_cu",
        mode=1,
        size=16,
        min_clusters=1,
        max_clusters=3,
        auto_resume=True,
        description="production",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["DataEngineName"] == "spark-prod"
    assert result["data_engine"]["Size"] == 16
    assert result["data_engine_id"].startswith("engine-new-")
    assert len(fake.engines) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDataEngines"
    assert "CreateDataEngine" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="spark-prod",
        engine_type="spark",
        cluster_type="spark_cu",
        mode=1,
        size=16,
        description="production",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine_id"] is None
    assert result["data_engine"]["Size"] == 16
    assert fake.engines == []
    assert "CreateDataEngine" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-engine flows
# ---------------------------------------------------------------------------


def test_existing_engine_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        engine_type="spark",
        cluster_type="spark_cu",
        mode=1,
        size=16,
        min_clusters=1,
        max_clusters=3,
        auto_resume=True,
        description="production",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["data_engine"]["DataEngineId"] == "engine-8b0a1c2d"


def test_update_drift_changes_mutable_fields(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        engine_type="spark",
        cluster_type="spark_cu",
        mode=1,
        size=32,
        min_clusters=2,
        max_clusters=6,
        auto_resume=True,
        description="production",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["Size"] == 32
    assert result["data_engine"]["MinClusters"] == 2
    ops = [c for c, unused in fake.calls]
    assert "UpdateDataEngine" in ops
    assert "ModifyDataEngineDescription" not in ops


def test_update_description_change(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed description", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["Message"] == "renamed description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDataEngineDescription" in ops
    assert "UpdateDataEngine" not in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", engine_type="presto")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "fields are immutable" in payload["msg"]
    assert "EngineType" in payload["immutable_drift"]


def test_scale_down_requires_allow_scale_down(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", size=8)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_scale_down=true" in exc.value.args[0]["msg"]
    assert "Size" in exc.value.args[0]["capacity_drift"]


def test_scale_down_authorized_applies(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", size=8, allow_scale_down=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["Size"] == 8


def test_image_switch_requires_allow_image_switch(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", image_version_name="1.0")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_image_switch=true" in payload["msg"]
    assert payload["image_target"]["ImageVersionId"] == "img-1"


def test_image_switch_authorized_applies(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", image_version_name="1.0", allow_image_switch=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["ImageVersionName"] == "1.0"
    assert result["data_engine"]["ImageVersionId"] == "img-1"
    ops = [c for c, unused in fake.calls]
    assert "SwitchDataEngineImage" in ops


def test_image_switch_unknown_version_fails(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()], images=[])
    _make_module(monkeypatch, fake)
    _base(state="present", image_version_name="9.9", allow_image_switch=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "online DLC data-engine image version was not found" in exc.value.args[0]["msg"]


def test_standby_switch_requires_allow_standby_switch(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", standby_cluster=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_standby_switch=true" in payload["msg"]
    assert "StartStandbyCluster" in payload["standby_drift"]


def test_standby_switch_authorized_applies(monkeypatch):
    fake = FakeDlcClient(engines=[_engine()])
    _make_module(monkeypatch, fake)
    _base(state="present", standby_cluster=True, allow_standby_switch=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["StartStandbyCluster"] is True
    ops = [c for c, unused in fake.calls]
    assert "SwitchDataEngine" in ops


def test_resume_suspended_engine(monkeypatch):
    fake = FakeDlcClient(engines=[_engine(State=1)])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["State"] == 2
    ops = [c for c, unused in fake.calls]
    assert "SuspendResumeDataEngine" in ops


def test_suspend_running_engine(monkeypatch):
    fake = FakeDlcClient(engines=[_engine(State=2)])
    _make_module(monkeypatch, fake)
    _base(state="suspended", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine"]["State"] == 1


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(engines=[_engine(), _engine(DataEngineId="engine-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC data engines matched" in exc.value.args[0]["msg"]


def test_description_too_long_fails(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", description="x" * 251)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "250 characters" in exc.value.args[0]["msg"]


def test_min_clusters_above_max_fails(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", min_clusters=8, max_clusters=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "min_clusters must not exceed max_clusters" in exc.value.args[0]["msg"]


def test_crontab_and_auto_suspend_conflict_fails(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", crontab_resume_suspend=1, auto_suspend=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot both be enabled" in exc.value.args[0]["msg"]


def test_negative_elastic_limit_fails(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", elastic_limit=-1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "elastic_limit must not be negative" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDataEngines(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="spark-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
