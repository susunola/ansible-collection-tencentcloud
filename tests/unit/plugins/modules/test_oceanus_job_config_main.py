"""Unit tests for the oceanus_job_config write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake Oceanus client
whose ``CreateJobConfig`` appends immutable configuration versions and
``DeleteJobConfigs`` removes them, so the module's describe/waiter refetches
converge immediately. Job configuration versions are immutable: drift is
handled by publishing a *new* version, and deletion targets one historical
version explicitly.

Scenario matrix:

* idempotent no-op when the latest version already matches the managed fields
* publish when absent (check-mode dry run and real ``CreateJobConfig`` with
  captured request fields, version numbering)
* drift publishes a new version instead of mutating
* absent flows (missing version no-op, ``allow_delete`` guard, check-mode dry
  run, real deletion)
* argument-validation failures before any SDK call (no managed fields,
  mutually exclusive ref options, absent without version)
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_oceanus_job_config.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_job_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

JOB_ID = "cql-abcdefgh"
WORKSPACE = "space-abcdefgh"
CONFIG = {"Version": 1, "JobId": JOB_ID, "WorkSpaceId": WORKSPACE, "ProgramArgs": "SELECT 1", "DefaultParallelism": 4}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"job_id": JOB_ID, "workspace_id": WORKSPACE, "program_args": "SELECT 1", "default_parallelism": 4}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client appending/removing immutable job config versions."""

    def __init__(self, configs=None):
        self.job_configs = [copy.deepcopy(t) for t in (configs or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeJobConfigs(self, request):
        self._record("DescribeJobConfigs", request)
        values = [
            t for t in self.job_configs
            if t.get("JobId") == getattr(request, "JobId", None) and t.get("WorkSpaceId") == getattr(request, "WorkSpaceId", None)
        ]
        versions = getattr(request, "JobConfigVersions", None)
        if versions:
            values = [t for t in values if t.get("Version") in versions]
        return SimpleNamespace(JobConfigSet=[FakeResource(dict(t)) for t in values], RequestId="req-fake")

    def CreateJobConfig(self, request):
        self._record("CreateJobConfig", request)
        entry = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        entry["Version"] = max([t.get("Version", 0) for t in self.job_configs] or [0]) + 1
        self.job_configs.append(entry)
        return SimpleNamespace(Version=entry["Version"], RequestId="req-fake")

    def DeleteJobConfigs(self, request):
        self._record("DeleteJobConfigs", request)
        versions = list(getattr(request, "JobConfigVersions", None) or [])
        self.job_configs = [t for t in self.job_configs if t.get("Version") not in versions]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_latest_version_already_matches_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job_config"]["Version"] == 1
    assert result["version"] == 1
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeJobConfigs"]


# ---------------------------------------------------------------------------
# publication flows
# ---------------------------------------------------------------------------


def test_publish_requires_a_managed_field(monkeypatch):
    fake = FakeOceanusClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(program_args=None, default_parallelism=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at least one managed configuration field is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_publish_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_config"] == {"ProgramArgs": "SELECT 1", "DefaultParallelism": 4}
    assert result["version"] is None
    assert fake.job_configs == []
    assert "CreateJobConfig" not in [name for name, unused in fake.calls]


def test_publish_new_config_version(monkeypatch):
    fake = FakeOceanusClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(remark="first cut")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_config"]["ProgramArgs"] == "SELECT 1"
    assert result["job_config"]["DefaultParallelism"] == 4
    assert result["job_config"]["Version"] == 1
    assert result["version"] == 1
    request = _find_call(fake, "CreateJobConfig")
    assert request.JobId == JOB_ID
    assert request.WorkSpaceId == WORKSPACE
    assert request.ProgramArgs == "SELECT 1"
    assert request.DefaultParallelism == 4
    assert request.Remark == "first cut"
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeJobConfigs"
    assert ops[-1] == "DescribeJobConfigs"  # post-write version refetch


def test_managed_drift_publishes_new_version(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(program_args="SELECT * FROM orders")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_config"]["Version"] == 2
    assert result["job_config"]["ProgramArgs"] == "SELECT * FROM orders"
    assert result["version"] == 2
    assert len(fake.job_configs) == 2
    request = _find_call(fake, "CreateJobConfig")
    assert request.ProgramArgs == "SELECT * FROM orders"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_version_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=99)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job_config"] is None


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", version=1, allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_config"] is None
    assert len(fake.job_configs) == 1
    assert "DeleteJobConfigs" not in [name for name, unused in fake.calls]


def test_absent_deletes_historical_version(monkeypatch):
    fake = FakeOceanusClient(configs=[_config(), _config(Version=2, ProgramArgs="SELECT 2")])
    _make_module(monkeypatch, fake)
    _base(state="absent", version=1, allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_config"] is None
    assert [t.get("Version") for t in fake.job_configs] == [2]
    request = _find_call(fake, "DeleteJobConfigs")
    assert request.JobConfigVersions == [1]
    assert request.ConfigScope == 0


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_mutually_exclusive_ref_options_fail(monkeypatch):
    fake = FakeOceanusClient(configs=[])
    _make_module(monkeypatch, fake)
    module_args(
        job_id=JOB_ID,
        workspace_id=WORKSPACE,
        program_args="SELECT 1",
        resource_refs=[{"ResourceId": "r-1", "Version": 1, "Type": 1}],
        resource_ref_names=[{"Name": "orders-processor", "Type": 1}],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_requires_version(monkeypatch):
    fake = FakeOceanusClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    module_args(job_id=JOB_ID, workspace_id=WORKSPACE, state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "version" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeJobConfigs(self, request):
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
# legacy helper regression tests (folded from test_oceanus_job_config.py)
# ---------------------------------------------------------------------------

_FIELDS_FOR_TEST = (
    "entrypoint_class", "program_args", "remark", "default_parallelism", "properties", "resource_refs", "cos_bucket",
    "log_collect", "log_collect_type", "cls_logset_id", "cls_topic_id", "log_level", "python_version",
    "job_manager_spec", "task_manager_spec", "clazz_levels", "expert_mode_on", "expert_mode_configuration",
    "trace_mode_on", "trace_mode_configuration", "job_graph", "es_serverless_index", "es_serverless_space",
    "checkpoint_retained", "checkpoint_timeout", "checkpoint_interval", "job_manager_cpu", "job_manager_memory",
    "task_manager_cpu", "task_manager_memory", "flink_version", "jdk_version", "variable_replace_mode",
    "state_cos_bucket",
)


def _empty_params(**overrides):
    params = {key: None for key in _FIELDS_FOR_TEST}
    params.update(overrides)
    return params


def test_desired_only_manages_explicit_fields():
    params = _empty_params(program_args="SELECT 1", default_parallelism=4, auto_recover=None)
    assert mod.desired(params) == {"ProgramArgs": "SELECT 1", "DefaultParallelism": 4}


def test_desired_maps_auto_recovery_switch():
    assert mod.desired(_empty_params(auto_recover=False))["AutoRecover"] == -1
    assert mod.desired(_empty_params(auto_recover=True))["AutoRecover"] == 1


def test_resource_refs_compare_without_response_metadata_or_order():
    values = [
        {"ResourceId": "r-b", "Version": 2, "Type": 0, "Name": "b"},
        {"ResourceId": "r-a", "Version": 1, "Type": 1, "SystemProvide": 0},
    ]
    assert mod.normalize_resource_refs(values) == [
        {"ResourceId": "r-b", "Version": 2, "Type": 0},
        {"ResourceId": "r-a", "Version": 1, "Type": 1},
    ]


def test_named_refs_select_latest_or_explicit_version():
    resources = [{"Name": "processor", "ResourceId": "resource-1", "LatestResourceConfigVersion": 4}]
    assert mod.named_refs(resources, [{"Name": "processor", "Type": 1}]) == [{"ResourceId": "resource-1", "Version": 4, "Type": 1}]
    assert mod.named_refs(resources, [{"Name": "processor", "Version": 2, "Type": 0}]) == [{"ResourceId": "resource-1", "Version": 2, "Type": 0}]


def test_managed_value_ignores_nested_sdk_noise():
    target = {"ExpertModeConfiguration": {"NodeConfig": [{"Id": 1, "Parallelism": 4}]}}
    current = {"ExpertModeConfiguration": {"NodeConfig": [{"Id": 1, "Parallelism": 4, "StateTTL": None}], "EdgeConfig": None}}
    assert mod.managed_value(current, target) == target


def test_observed_decodes_combined_log_destination_status():
    assert mod.observed({"LogCollect": 1}, {"LogCollect": True, "LogCollectType": 2}) == {"LogCollect": True, "LogCollectType": 2}
    assert mod.observed({"LogCollect": 4}, {"LogCollect": True, "LogCollectType": 3}) == {"LogCollect": True, "LogCollectType": 3}
