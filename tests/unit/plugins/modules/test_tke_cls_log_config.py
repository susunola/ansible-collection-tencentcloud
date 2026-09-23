"""Unit tests for the tke_cls_log_config write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TKE client whose
Create/Delete operations mutate a per-name log-config store. DescribeLogConfigs
returns the documented ItemCount/Items JSON envelope, exercising the module's
metadata.name-based idempotency lookup.

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
            LogConfigs=json.dumps({"ItemCount": len(self.configs), "Items": list(self.configs.values())}),
            RequestId="req-fake",
        )

    def CreateCLSLogConfig(self, request):
        self._record("CreateCLSLogConfig", request)
        created = json.loads(request.LogConfig)
        self.configs[created["metadata"]["name"]] = created
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLogConfigs(self, request):
        self._record("DeleteLogConfigs", request)
        self.configs.pop(request.LogConfigNames, None)
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
                log_config={"metadata": {"name": "stdout"}, "spec": {"inputDetail": {"type": "container_stdout"}}})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "cls-abc123"
    assert result["log_config_name"] == "stdout"
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLogConfigs"
    assert fake.calls[0][1].LogConfigNames == "stdout"
    assert "CreateCLSLogConfig" in ops
    assert "DeleteLogConfigs" not in ops
    assert "stdout" in fake.configs


def test_delete_when_present(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"metadata": {"name": "stdout"}}})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteLogConfigs" in ops
    assert [request.LogConfigNames for op, request in fake.calls if op == "DeleteLogConfigs"] == ["stdout"]
    assert "CreateCLSLogConfig" not in ops
    assert fake.configs == {}


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"metadata": {"name": "stdout"}}})
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"metadata": {"name": "stdout"}})
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
                log_config={"metadata": {"name": "stdout"}},
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert "CreateCLSLogConfig" not in [c for c, unused in fake.calls]
    assert fake.configs == {}


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(configs={"stdout": {"metadata": {"name": "stdout"}}})
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


def test_malformed_describe_fails_closed(monkeypatch):
    fake = FakeTkeClient()
    fake.DescribeLogConfigs = lambda request: SimpleNamespace(LogConfigs="not-json")
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)
    assert "DeleteLogConfigs" not in [name for name, unused in fake.calls]


def test_incomplete_items_page_fails_closed(monkeypatch):
    fake = FakeTkeClient()
    fake.DescribeLogConfigs = lambda request: SimpleNamespace(
        LogConfigs=json.dumps({"ItemCount": 1, "Items": []}), Message="")
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_partial_lookup_error_fails_closed(monkeypatch):
    fake = FakeTkeClient()
    fake.DescribeLogConfigs = lambda request: SimpleNamespace(
        LogConfigs=json.dumps({"ItemCount": 0, "Items": []}), Message="lookup failed")
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", state="absent")
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_mismatched_config_name_is_rejected(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"metadata": {"name": "other"}})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must match" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_create_must_be_visible_after_write(monkeypatch):
    fake = FakeTkeClient()
    fake.CreateCLSLogConfig = lambda request: SimpleNamespace(RequestId="req-fake")
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", log_config_name="stdout", logset_id="ls-1",
                log_config={"metadata": {"name": "stdout"}})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "did not reach" in exc.value.args[0]["msg"]
