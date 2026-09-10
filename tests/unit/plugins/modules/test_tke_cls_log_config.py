"""Unit tests for the tke_cls_log_config write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TKE client whose
Create/Delete operations mutate a per-name log-config store. DescribeLogConfigs
returns the store as a JSON string, exercising the module's defensive JSON
parsing and name-based idempotency lookup.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the configuration already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* required_if guard (state=present needs log_config and logset_id)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cls_log_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


class FakeTkeClient(object):
    """In-memory TKE client mutating a per-name log-config store."""

    def __init__(self, configs=None):
        # configs: dict name -> config dict
        self.configs = dict(configs or {})
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeLogConfigs(self, request):
        self._record("DescribeLogConfigs", request)
        return SimpleNamespace(
            Total=len(self.configs),
            Message="",
            LogConfigs=json.dumps(list(self.configs.values())),
            RequestId="req-fake",
        )

    def CreateCLSLogConfig(self, request):
        self._record("CreateCLSLogConfig", request)
        created = json.loads(request.LogConfig)
        self.configs[created["name"]] = created
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLogConfigs(self, request):
        self._record("DeleteLogConfigs", request)
        for name in (request.LogConfigNames or []):
            self.configs.pop(name, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tke", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeTkeClient(configs={})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"name": "stdout", "logType": "container_stdout"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "cls-abc123"
    assert result["log_config_name"] == "stdout"
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLogConfigs"
    assert "CreateCLSLogConfig" in ops
    assert "DeleteLogConfigs" not in ops
    assert "stdout" in fake.configs


def test_delete_when_present(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"name": "stdout", "logType": "container_stdout"}})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteLogConfigs" in ops
    assert "CreateCLSLogConfig" not in ops
    assert fake.configs == {}


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"name": "stdout", "logType": "container_stdout"}})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"name": "stdout", "logType": "container_stdout"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeLogConfigs"]
    assert "CreateCLSLogConfig" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeTkeClient(configs={})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is False
    assert "DeleteLogConfigs" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(configs={})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"name": "stdout", "logType": "container_stdout"},
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert "CreateCLSLogConfig" not in [c for c, unused in fake.calls]
    assert fake.configs == {}


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"name": "stdout", "logType": "container_stdout"}})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteLogConfigs" not in [c for c, unused in fake.calls]
    assert "stdout" in fake.configs


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_present_requires_log_config_and_logset_id(monkeypatch):
    fake = FakeTkeClient(configs={})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "log_config" in exc.value.args[0]["msg"]
