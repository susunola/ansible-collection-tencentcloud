"""Unit tests for the dlc_data_engine_config write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client
whose ``UpdateUserDataEngineConfig`` mutates the per-engine config store, so
the module's post-write ``read`` refetch and waiter converge immediately.

Scenario matrix:

* engine-name resolution (found, missing, ambiguous)
* no-op when the configuration already matches
* creation/update of config pairs and the Spark session resource template
* clearing every pair under the ``allow_empty`` authorization guard
* check-mode dry runs
* validation guards (duplicate config keys, empty set without allow_empty,
  duplicate runtime parameter keys)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_data_engine_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENGINE_ID = "engine-8b0a1c2d"
PAIRS = [{"ConfigItem": "spark.sql.shuffle.partitions", "ConfigValue": "200"}]
TEMPLATE = {"DriverSize": "medium", "ExecutorSize": "large", "ExecutorNums": 2}


def _config(**overrides):
    item = {"DataEngineId": ENGINE_ID, "DataEngineConfigPairs": copy.deepcopy(PAIRS), "SessionResourceTemplate": None}
    item.update(overrides)
    return item


def _pairs_args(*items):
    return [{"key": key, "value": value} for key, value in items]


def _base(**overrides):
    params = {"config_pairs": _pairs_args(("spark.sql.shuffle.partitions", "200"))}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client holding engines and per-engine configuration."""

    def __init__(self, engines=None, configs=None):
        self.engines = [copy.deepcopy(t) for t in (engines or [])]
        self.configs = [copy.deepcopy(t) for t in (configs or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _config_by_id(self, engine_id):
        for record in self.configs:
            if record.get("DataEngineId") == engine_id:
                return record
        return None

    def DescribeDataEngines(self, request):
        self._record("DescribeDataEngines", request)
        name = request.Filters[0].Values[0]
        matches = [dict(t) for t in self.engines if t.get("DataEngineName") == name and t.get("State") != -2]
        return SimpleNamespace(DataEngines=[FakeResource(t) for t in matches], TotalCount=len(matches))

    def DescribeUserDataEngineConfig(self, request):
        self._record("DescribeUserDataEngineConfig", request)
        engine_id = request.Filters[0].Values[0]
        record = self._config_by_id(engine_id)
        page = [dict(record)] if record else []
        return SimpleNamespace(DataEngineConfigInstanceInfos=[FakeResource(t) for t in page], TotalCount=len(page))

    def UpdateUserDataEngineConfig(self, request):
        self._record("UpdateUserDataEngineConfig", request)
        engine_id = getattr(request, "DataEngineId", None)
        record = self._config_by_id(engine_id)
        if record is None:
            record = {"DataEngineId": engine_id, "DataEngineConfigPairs": [], "SessionResourceTemplate": None}
            self.configs.append(record)
        pairs = []
        for item in getattr(request, "DataEngineConfigPairs", None) or []:
            pairs.append({"ConfigItem": item.ConfigItem, "ConfigValue": item.ConfigValue})
        record["DataEngineConfigPairs"] = sorted(pairs, key=lambda value: (value["ConfigItem"], value["ConfigValue"]))
        template = getattr(request, "SessionResourceTemplate", None)
        if template is None:
            record["SessionResourceTemplate"] = None
        else:
            rendered = {}
            for attr in ("DriverSize", "ExecutorSize", "ExecutorNums", "ExecutorMaxNumbers"):
                if getattr(template, attr, None) is not None:
                    rendered[attr] = getattr(template, attr)
            runtime = getattr(template, "RunningTimeParameters", None)
            if runtime is not None:
                rendered["RunningTimeParameters"] = sorted(
                    ({"ConfigItem": x.ConfigItem, "ConfigValue": x.ConfigValue} for x in runtime),
                    key=lambda value: (value["ConfigItem"], value["ConfigValue"]),
                )
            record["SessionResourceTemplate"] = rendered
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# engine resolution
# ---------------------------------------------------------------------------


def _engines():
    return [{"DataEngineId": ENGINE_ID, "DataEngineName": "prod-spark", "State": 2}]


def test_engine_name_resolution_fails_when_absent(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(engine_name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "DLC data engine was not found" in exc.value.args[0]["msg"]


def test_engine_name_resolution_fails_when_ambiguous(monkeypatch):
    engines = [{"DataEngineId": "engine-a", "DataEngineName": "prod-spark", "State": 2},
               {"DataEngineId": "engine-b", "DataEngineName": "prod-spark", "State": 2}]
    fake = FakeDlcClient(engines=engines)
    _make_module(monkeypatch, fake)
    _base(engine_name="prod-spark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC data engines matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# no-drift / drift flows by engine_id
# ---------------------------------------------------------------------------


def test_existing_config_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(engines=[], configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(engine_id=ENGINE_ID)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["data_engine_config"]["DataEngineConfigPairs"] == PAIRS
    assert result["engine_id"] == ENGINE_ID
    assert _ops(fake) == ["DescribeUserDataEngineConfig"]


def test_config_adds_pairs_on_drift(monkeypatch):
    fake = FakeDlcClient(engines=[], configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(
        engine_id=ENGINE_ID,
        config_pairs=_pairs_args(("spark.sql.shuffle.partitions", "200"), ("spark.sql.adaptive.enabled", "true")),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine_config"]["DataEngineConfigPairs"] == [
        {"ConfigItem": "spark.sql.adaptive.enabled", "ConfigValue": "true"},
        {"ConfigItem": "spark.sql.shuffle.partitions", "ConfigValue": "200"},
    ]
    assert "UpdateUserDataEngineConfig" in _ops(fake)


def test_config_update_by_engine_name(monkeypatch):
    fake = FakeDlcClient(engines=_engines(), configs=[])
    _make_module(monkeypatch, fake)
    _base(engine_name="prod-spark", config_pairs=_pairs_args(("spark.sql.adaptive.enabled", "true")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["engine_id"] == ENGINE_ID
    ops = _ops(fake)
    assert "DescribeDataEngines" in ops
    assert "UpdateUserDataEngineConfig" in ops


def test_config_template_updates(monkeypatch):
    fake = FakeDlcClient(engines=[], configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(engine_id=ENGINE_ID, session_resource_template={"driver_size": "medium", "executor_size": "large", "executor_nums": 2})
    result = run(mod.run_module)
    assert result["changed"] is True
    template = result["data_engine_config"]["SessionResourceTemplate"]
    assert template["DriverSize"] == "medium"
    assert template["ExecutorSize"] == "large"
    assert template["ExecutorNums"] == 2
    assert "UpdateUserDataEngineConfig" in _ops(fake)


def test_config_clears_pairs_with_allow_empty(monkeypatch):
    fake = FakeDlcClient(engines=[], configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(engine_id=ENGINE_ID, config_pairs=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_engine_config"]["DataEngineConfigPairs"] == []
    assert "UpdateUserDataEngineConfig" in _ops(fake)


def test_config_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(engines=[], configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        engine_id=ENGINE_ID,
        config_pairs=_pairs_args(("spark.sql.adaptive.enabled", "true")),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.configs[0]["DataEngineConfigPairs"] == PAIRS
    assert "UpdateUserDataEngineConfig" not in _ops(fake)


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_duplicate_config_keys_fail(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(engine_id=ENGINE_ID, config_pairs=_pairs_args(("spark.sql.adaptive.enabled", "true"), ("spark.sql.adaptive.enabled", "false")))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "duplicate keys" in exc.value.args[0]["msg"]


def test_empty_config_requires_allow_empty(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    _base(engine_id=ENGINE_ID, config_pairs=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]


def test_duplicate_runtime_parameter_keys_fail(monkeypatch):
    fake = FakeDlcClient(engines=[])
    _make_module(monkeypatch, fake)
    runtime = [
        {"key": "spark.executor.memory", "value": "4g"},
        {"key": "spark.executor.memory", "value": "8g"},
    ]
    _base(engine_id=ENGINE_ID, session_resource_template={"running_time_parameters": runtime})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "running_time_parameters contains duplicate keys" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDataEngines(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(engine_name="prod-spark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
