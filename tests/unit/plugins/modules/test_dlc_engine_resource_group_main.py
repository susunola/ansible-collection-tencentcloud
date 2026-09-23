"""Unit tests for the dlc_engine_resource_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the resource-group store (plus a separate
static/dynamic config record store), so the module's post-write ``find`` +
config refetch and ``wait_group`` pollers converge immediately.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent with a matching group (``allow_delete`` guard, check-mode dry run,
  real delete waiting for convergence)
* creation when missing (missing parent engine name, happy path, check mode)
* no-op when nothing drifts
* drift updates (base fields, capacity, network bindings, static config)
* the scale-down and data-engine-name immutability guards
* validation branches (min>max executors, auto_pause_time range)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_engine_resource_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BASE = {
    "AutoLaunch": 0,
    "AutoPause": 0,
    "AutoPauseTime": 15,
    "MaxConcurrency": 8,
}
CAPACITY = {
    "DriverCuSpec": "medium",
    "ExecutorCuSpec": "large",
    "MinExecutorNums": 2,
    "MaxExecutorNums": 10,
}

GROUP = {
    "EngineResourceGroupId": "rg-8b0a1c2d",
    "EngineResourceGroupName": "spark-etl",
    "DataEngineName": "spark-prod",
    "ResourceGroupState": 2,
    "NetworkConfigNames": ["base", "data"],
    "StaticConfig": {},
    "DynamicConfig": {},
    **BASE,
    **CAPACITY,
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "spark-etl"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC standard-engine resource-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.configs = {}  # rg_id -> {"Static": [...], "Dynamic": [...]}
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find_group(self, name):
        for item in self.groups:
            if item.get("EngineResourceGroupName") == name:
                return item
        return None

    def _config_record(self, rg_id, create=True):
        if rg_id not in self.configs and create:
            self.configs[rg_id] = {"Static": [], "Dynamic": []}
        return self.configs.get(rg_id)

    def _config_apply(self, rg_id, request):
        record = self._config_record(rg_id)
        for context in getattr(request, "UpdateConfContext", None) or []:
            target = "Static" if getattr(context, "ConfigType", None) == "StaticConfigType" else "Dynamic"
            store = record.setdefault(target, [])
            for param in getattr(context, "Params", None) or []:
                key = getattr(param, "ConfigItem", None)
                operate = getattr(param, "Operate", None)
                if operate == "DELETE":
                    store[:] = [p for p in store if p.get("ConfigItem") != key]
                else:
                    for entry in store:
                        if entry.get("ConfigItem") == key:
                            entry["ConfigValue"] = getattr(param, "ConfigValue", "")
                            break
                    else:
                        store.append({"ConfigItem": key, "ConfigValue": getattr(param, "ConfigValue", "")})

    def DescribeStandardEngineResourceGroups(self, request):
        self._record("DescribeStandardEngineResourceGroups", request)
        name = request.Filters[0].Values[0]
        matches = [
            dict(t)
            for t in self.groups
            if t.get("EngineResourceGroupName") == name and t.get("ResourceGroupState") != -1
        ]
        return SimpleNamespace(
            UserEngineResourceGroupInfos=[FakeResource(t) for t in matches],
            Total=len(matches),
            RequestId="req-fake",
        )

    def DescribeStandardEngineResourceGroupConfigInfo(self, request):
        self._record("DescribeStandardEngineResourceGroupConfigInfo", request)
        rg_id = request.Filters[0].Values[0]
        record = self._config_record(rg_id, create=False) or {"Static": [], "Dynamic": []}

        def pairs(values):
            return [FakeResource(p) for p in values]

        return SimpleNamespace(
            StandardEngineResourceGroupConfigInfos=[
                FakeResource(
                    {
                        "StaticConfigPairs": pairs(record.get("Static") or []),
                        "DynamicConfigPairs": pairs(record.get("Dynamic") or []),
                    }
                )
            ],
            Total=1,
            RequestId="req-fake",
        )

    def CreateStandardEngineResourceGroup(self, request):
        self._record("CreateStandardEngineResourceGroup", request)
        self._next += 1
        item = {
            "EngineResourceGroupId": "rg-new-%03d" % self._next,
            "EngineResourceGroupName": getattr(request, "EngineResourceGroupName", None),
            "DataEngineName": getattr(request, "DataEngineName", None),
            "ResourceGroupState": 2,
        }
        for attr in (
            "AutoLaunch", "AutoPause", "AutoPauseTime", "MaxConcurrency", "DriverCuSpec",
            "ExecutorCuSpec", "MinExecutorNums", "MaxExecutorNums",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        if getattr(request, "NetworkConfigNames", None) is not None:
            item["NetworkConfigNames"] = list(request.NetworkConfigNames)
        record = {"Static": [], "Dynamic": []}
        for source, target in (("StaticConfigPairs", "Static"), ("DynamicConfigPairs", "Dynamic")):
            pairs = getattr(request, source, None) or []
            record[target] = [{"ConfigItem": p.ConfigItem, "ConfigValue": p.ConfigValue} for p in pairs]
        self.configs[item["EngineResourceGroupId"]] = record
        self.groups.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateStandardEngineResourceGroupBaseInfo(self, request):
        self._record("UpdateStandardEngineResourceGroupBaseInfo", request)
        item = self._find_group(getattr(request, "EngineResourceGroupName", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in ("AutoLaunch", "AutoPause", "AutoPauseTime", "MaxConcurrency"):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def UpdateStandardEngineResourceGroupResourceInfo(self, request):
        self._record("UpdateStandardEngineResourceGroupResourceInfo", request)
        item = self._find_group(getattr(request, "EngineResourceGroupName", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in ("DriverCuSpec", "ExecutorCuSpec", "MinExecutorNums", "MaxExecutorNums"):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def UpdateEngineResourceGroupNetworkConfigInfo(self, request):
        self._record("UpdateEngineResourceGroupNetworkConfigInfo", request)
        for item in self.groups:
            if item.get("EngineResourceGroupId") == getattr(request, "EngineResourceGroupId", None):
                item["NetworkConfigNames"] = list(request.NetworkConfigNames or [])
        return SimpleNamespace(RequestId="req-fake")

    def UpdateStandardEngineResourceGroupConfigInfo(self, request):
        self._record("UpdateStandardEngineResourceGroupConfigInfo", request)
        item = self._find_group(getattr(request, "EngineResourceGroupName", None))
        if item is not None:
            self._config_apply(item["EngineResourceGroupId"], request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteStandardEngineResourceGroup(self, request):
        self._record("DeleteStandardEngineResourceGroup", request)
        name = getattr(request, "EngineResourceGroupName", None)
        self.groups = [t for t in self.groups if t.get("EngineResourceGroupName") != name]
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


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeStandardEngineResourceGroups"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"] is None
    assert len(fake.groups) == 1
    assert "DeleteStandardEngineResourceGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteStandardEngineResourceGroup" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_data_engine_name(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "data_engine_name is required" in exc.value.args[0]["msg"]


def _create_params(**overrides):
    params = {
        "state": "present",
        "name": "spark-etl",
        "data_engine_name": "spark-prod",
        "auto_launch": True,
        "auto_pause": True,
        "auto_pause_time": 15,
        "max_concurrency": 8,
        "driver_cu_spec": "medium",
        "executor_cu_spec": "large",
        "min_executors": 2,
        "max_executors": 10,
        "network_config_names": ["data", "base", "data"],
        "static_config": {"spark.sql.shuffle.partitions": 200},
        "dynamic_config": {"spark.executor.heartbeatInterval": "10s"},
        "wait": True,
    }
    params.update(overrides)
    return params


def test_create_group_happy_path(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(**_create_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["EngineResourceGroupName"] == "spark-etl"
    assert result["resource_group"]["MinExecutorNums"] == 2
    assert result["resource_group"]["NetworkConfigNames"] == ["base", "data"]
    assert result["resource_group"]["StaticConfig"] == {"spark.sql.shuffle.partitions": "200"}
    assert result["resource_group_id"].startswith("rg-new-")
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeStandardEngineResourceGroups"
    assert "CreateStandardEngineResourceGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, **_create_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group_id"] is None
    assert result["resource_group"]["EngineResourceGroupName"] == "spark-etl"
    assert fake.groups == []
    assert "CreateStandardEngineResourceGroup" not in [c for c, unused in fake.calls]


def test_create_wait_false_skips_polling(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(**_create_params(wait=False))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["MinExecutorNums"] == 2
    assert len(fake.groups) == 1


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[])
    seed = _group()
    rg_id = seed["EngineResourceGroupId"]
    fake.groups.append(seed)
    fake.configs[rg_id] = {
        "Static": [{"ConfigItem": "spark.sql.shuffle.partitions", "ConfigValue": "200"}],
        "Dynamic": [{"ConfigItem": "spark.executor.heartbeatInterval", "ConfigValue": "10s"}],
    }
    _make_module(monkeypatch, fake)
    _base(**_create_params())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource_group"]["EngineResourceGroupId"] == rg_id


def test_update_base_fields_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group(AutoPauseTime=30, MaxConcurrency=4)])
    _make_module(monkeypatch, fake)
    _base(**{
        "state": "present",
        "data_engine_name": "spark-prod",
        "auto_launch": True,
        "auto_pause": True,
        "auto_pause_time": 15,
        "max_concurrency": 4,
        "wait": True,
    })
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["AutoPauseTime"] == 15
    ops = [c for c, unused in fake.calls]
    assert "UpdateStandardEngineResourceGroupBaseInfo" in ops
    assert "UpdateStandardEngineResourceGroupResourceInfo" not in ops


def test_update_capacity_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group(MaxExecutorNums=8)])
    _make_module(monkeypatch, fake)
    _base(**{
        "state": "present",
        "data_engine_name": "spark-prod",
        "driver_cu_spec": "medium",
        "executor_cu_spec": "large",
        "min_executors": 2,
        "max_executors": 10,
        "wait": True,
    })
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["MaxExecutorNums"] == 10
    ops = [c for c, unused in fake.calls]
    assert "UpdateStandardEngineResourceGroupResourceInfo" in ops


def test_update_network_bindings_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group(NetworkConfigNames=["base"])])
    _make_module(monkeypatch, fake)
    _base(**{
        "state": "present",
        "data_engine_name": "spark-prod",
        "network_config_names": ["base", "data"],
        "wait": True,
    })
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["NetworkConfigNames"] == ["base", "data"]
    ops = [c for c, unused in fake.calls]
    assert "UpdateEngineResourceGroupNetworkConfigInfo" in ops


def test_update_static_config_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    rg_id = fake.groups[0]["EngineResourceGroupId"]
    fake.configs[rg_id] = {
        "Static": [{"ConfigItem": "spark.sql.shuffle.partitions", "ConfigValue": "200"}],
        "Dynamic": [],
    }
    _make_module(monkeypatch, fake)
    _base(**{
        "state": "present",
        "data_engine_name": "spark-prod",
        "static_config": {"spark.sql.shuffle.partitions": 400, "spark.executor.cores": "2"},
        "wait": True,
    })
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["StaticConfig"] == {
        "spark.sql.shuffle.partitions": "400",
        "spark.executor.cores": "2",
    }
    ops = [c for c, unused in fake.calls]
    assert "UpdateStandardEngineResourceGroupConfigInfo" in ops


def test_update_static_config_check_mode(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    rg_id = fake.groups[0]["EngineResourceGroupId"]
    fake.configs[rg_id] = {
        "Static": [{"ConfigItem": "spark.sql.shuffle.partitions", "ConfigValue": "200"}],
        "Dynamic": [],
    }
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, **{
        "state": "present",
        "data_engine_name": "spark-prod",
        "static_config": {"spark.sql.shuffle.partitions": 400},
    })
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "UpdateStandardEngineResourceGroupConfigInfo" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_data_engine_name_immutable_fails(monkeypatch):
    fake = FakeDlcClient(groups=[_group(DataEngineName="other-engine")])
    _make_module(monkeypatch, fake)
    _base(state="present", data_engine_name="spark-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "data_engine_name is immutable" in payload["msg"]
    assert "DataEngineName" in payload["immutable_drift"]


def test_scale_down_requires_allow_scale_down(monkeypatch):
    fake = FakeDlcClient(groups=[_group(MinExecutorNums=2, MaxExecutorNums=10)])
    _make_module(monkeypatch, fake)
    _base(state="present", data_engine_name="spark-prod", min_executors=1, max_executors=10)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_scale_down=true" in payload["msg"]
    assert "MinExecutorNums" in payload["capacity_drift"]


def test_scale_down_authorized_applies(monkeypatch):
    fake = FakeDlcClient(groups=[_group(MinExecutorNums=2, MaxExecutorNums=10)])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        data_engine_name="spark-prod",
        min_executors=1,
        max_executors=10,
        allow_scale_down=True,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_group"]["MinExecutorNums"] == 1


def test_min_executors_above_max_fails(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="x", min_executors=8, max_executors=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "min_executors must not exceed max_executors" in exc.value.args[0]["msg"]


def test_auto_pause_time_out_of_range_fails(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="x", auto_pause_time=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "auto_pause_time must be between 1 and 999" in exc.value.args[0]["msg"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group(), _group(EngineResourceGroupId="rg-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC engine resource groups matched" in exc.value.args[0]["msg"]


def test_multiple_config_records_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    rg_id = fake.groups[0]["EngineResourceGroupId"]
    fake.configs[rg_id] = {"Static": [], "Dynamic": []}

    def describe_config(request):
        fake._record("DescribeStandardEngineResourceGroupConfigInfo", request)
        return SimpleNamespace(
            StandardEngineResourceGroupConfigInfos=[
                FakeResource({"StaticConfigPairs": [], "DynamicConfigPairs": []}),
                FakeResource({"StaticConfigPairs": [], "DynamicConfigPairs": []}),
            ],
            Total=2,
        )

    fake.DescribeStandardEngineResourceGroupConfigInfo = describe_config
    _make_module(monkeypatch, fake)
    _base(state="present", data_engine_name="spark-prod", static_config={"a": "b"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC configuration records matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class ExplodingClient(object):
        def DescribeStandardEngineResourceGroups(self, request):
            raise RuntimeError("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="spark-etl")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
