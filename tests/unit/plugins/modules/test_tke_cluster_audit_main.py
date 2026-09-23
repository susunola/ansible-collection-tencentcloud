"""Unit tests for the tke_cluster_audit write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TKE client whose
enable / disable operations mutate an audit-switch store so post-write
describes converge immediately.

The switch is a pure on/off: once the desired state matches, the module
reports unchanged even if CLS destination parameters differ.

Scenario matrix:

* already-disabled and already-enabled runs are idempotent
* enabling supplies logset/topic/region and disabling may delete them
* the required_if guard (logset_id/topic_id when state=enabled)
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_audit as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "cls-1234"

ENABLED = {
    "Enable": True,
    "LogsetId": "logset-1",
    "TopicId": "topic-1",
    "TopicRegion": "ap-guangzhou",
}


def _switch(**overrides):
    item = copy.deepcopy(ENABLED)
    item.update(overrides)
    return item


def _enabled_args(**overrides):
    params = {"state": "enabled", "cluster_id": CLUSTER_ID, "logset_id": "logset-1", "topic_id": "topic-1", "topic_region": "ap-guangzhou"}
    params.update(overrides)
    return module_args(**params)


def _disabled_args(**overrides):
    params = {"state": "disabled", "cluster_id": CLUSTER_ID, "delete_logset_and_topic": False}
    params.update(overrides)
    return module_args(**params)


class FakeTkeClient(object):
    """In-memory TKE client holding one cluster's audit switch."""

    def __init__(self, switch=None):
        self.switch = copy.deepcopy(switch)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeLogSwitches(self, request):
        self._record("DescribeLogSwitches", request)
        items = [FakeResource(self.switch)] if self.switch is not None else []
        return SimpleNamespace(SwitchSet=items)

    def EnableClusterAudit(self, request):
        self._record("EnableClusterAudit", request)
        self.switch = {
            "Enable": True,
            "LogsetId": getattr(request, "LogsetId", None),
            "TopicId": getattr(request, "TopicId", None),
            "TopicRegion": getattr(request, "TopicRegion", None),
        }
        return SimpleNamespace(RequestId="req-fake")

    def DisableClusterAudit(self, request):
        self._record("DisableClusterAudit", request)
        if self.switch is not None:
            self.switch = dict(self.switch, Enable=False)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_already_disabled_is_idempotent(monkeypatch):
    # An empty SwitchSet reads as disabled: {"Enable": False}.
    fake = FakeTkeClient(switch=None)
    _make_module(monkeypatch, fake)
    _disabled_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit"] == {"Enable": False}
    assert [c for c, unused in fake.calls] == ["DescribeLogSwitches"]


def test_disabled_with_existing_switch_is_idempotent(monkeypatch):
    fake = FakeTkeClient(switch=_switch(Enable=False))
    _make_module(monkeypatch, fake)
    _disabled_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit"]["Enable"] is False


def test_already_enabled_is_idempotent(monkeypatch):
    fake = FakeTkeClient(switch=_switch())
    _make_module(monkeypatch, fake)
    _enabled_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit"]["Enable"] is True
    assert not [c for c, unused in fake.calls if c != "DescribeLogSwitches"]


def test_enabled_ignores_destination_drift(monkeypatch):
    # The module is a pure switch: different topic/logset values on an
    # already-enabled cluster do not count as drift.
    fake = FakeTkeClient(switch=_switch())
    _make_module(monkeypatch, fake)
    _enabled_args(topic_id="topic-other")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "EnableClusterAudit" not in [c for c, unused in fake.calls]


def test_enabling_requires_logset_and_topic(monkeypatch):
    fake = FakeTkeClient(switch=None)
    _make_module(monkeypatch, fake)
    module_args(state="enabled", cluster_id=CLUSTER_ID, logset_id="logset-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "topic_id" in exc.value.args[0]["msg"]


def test_enable_cluster_audit(monkeypatch):
    fake = FakeTkeClient(switch=_switch(Enable=False))
    _make_module(monkeypatch, fake)
    _enabled_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["Enable"] is True
    assert result["audit"]["LogsetId"] == "logset-1"
    ops = [c for c, unused in fake.calls]
    assert "EnableClusterAudit" in ops
    enable_call = [r for c, r in fake.calls if c == "EnableClusterAudit"][0]
    assert enable_call.ClusterId == CLUSTER_ID
    assert enable_call.TopicRegion == "ap-guangzhou"


def test_disable_cluster_audit(monkeypatch):
    fake = FakeTkeClient(switch=_switch())
    _make_module(monkeypatch, fake)
    _disabled_args(delete_logset_and_topic=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["Enable"] is False
    ops = [c for c, unused in fake.calls]
    assert "DisableClusterAudit" in ops
    disable_call = [r for c, r in fake.calls if c == "DisableClusterAudit"][0]
    assert disable_call.DeleteLogSetAndTopic is True
    assert disable_call.ClusterId == CLUSTER_ID


def test_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(switch=_switch(Enable=False))
    _make_module(monkeypatch, fake)
    _enabled_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["Enable"] is False
    assert "EnableClusterAudit" not in [c for c, unused in fake.calls]


def test_disable_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(switch=_switch())
    _make_module(monkeypatch, fake)
    _disabled_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["Enable"] is True
    assert "DisableClusterAudit" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeLogSwitches(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _enabled_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
