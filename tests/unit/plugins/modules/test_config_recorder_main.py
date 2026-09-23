"""Unit tests for the config_recorder write module (run_module flows).

Drives ``run_module()`` against an in-memory fake Config client whose
open / close / update operations mutate a recorder store so post-write
describes converge immediately.

The recorder has no delete: ``enabled=false`` *disables* recording via
``CloseConfigRecorder`` and ``enabled=true`` reopens it with
``OpenConfigRecorder``, while the monitored resource-type set is
reconciled through ``UpdateConfigRecorder``.

Scenario matrix:

* matching enabled state + resource types is idempotent
* resource-type drift triggers UpdateConfigRecorder only
* enable/disable transitions trigger Open/CloseConfigRecorder
* enabling when disabled with new types calls Update then Open
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_recorder as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RESOURCE_TYPES = ["QCS::CVM::Instance", "QCS::VPC::VPC"]


def _record(status=1, types=None):
    return {"Status": status, "ResourceTypes": [copy.deepcopy(t) for t in (types or [])]}


class FakeConfigClient(object):
    """In-memory Config client mutating a recorder (status + types) store."""

    def __init__(self, status=1, types=None):
        self.status = status
        self.types = [copy.deepcopy(t) for t in (types or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeConfigRecorder(self, request):
        self._record("DescribeConfigRecorder", request)
        data = {
            "Status": self.status,
            "RequestId": "req-fake",
            "Items": [FakeResource({"ResourceType": t}) for t in self.types],
        }
        return FakeResource(data)

    def UpdateConfigRecorder(self, request):
        self._record("UpdateConfigRecorder", request)
        self.types = sorted(set(getattr(request, "ResourceTypes", None) or []))
        return SimpleNamespace(RequestId="req-fake")

    def OpenConfigRecorder(self, request):
        self._record("OpenConfigRecorder", request)
        self.status = 1
        return SimpleNamespace(RequestId="req-fake")

    def CloseConfigRecorder(self, request):
        self._record("CloseConfigRecorder", request)
        self.status = 0
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _enabled_args(enabled=True, resource_types=None, **extra):
    params = {"enabled": enabled, "resource_types": [copy.deepcopy(t) for t in (resource_types or [])]}
    params.update(extra)
    return module_args(**params)


def test_enabled_no_drift_is_idempotent(monkeypatch):
    fake = FakeConfigClient(status=1, types=RESOURCE_TYPES)
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=True, resource_types=RESOURCE_TYPES)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["recorder"]["Status"] == 1
    assert result["recorder"]["ResourceTypes"] == sorted(RESOURCE_TYPES)
    assert [c for c, unused in fake.calls] == ["DescribeConfigRecorder"]


def test_disabled_no_drift_is_idempotent(monkeypatch):
    fake = FakeConfigClient(status=0, types=[])
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=False, resource_types=[])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["recorder"]["Status"] == 0


def test_resource_type_drift_updates_only(monkeypatch):
    fake = FakeConfigClient(status=1, types=RESOURCE_TYPES)
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=True, resource_types=RESOURCE_TYPES + ["QCS::CBS::Disk"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["recorder"]["ResourceTypes"] == sorted(RESOURCE_TYPES + ["QCS::CBS::Disk"])
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeConfigRecorder", "UpdateConfigRecorder", "DescribeConfigRecorder"]
    assert "OpenConfigRecorder" not in ops
    assert "CloseConfigRecorder" not in ops


def test_disabling_closes_recorder(monkeypatch):
    fake = FakeConfigClient(status=1, types=[])
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=False, resource_types=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["recorder"]["Status"] == 0
    ops = [c for c, unused in fake.calls]
    assert "CloseConfigRecorder" in ops
    assert "OpenConfigRecorder" not in ops
    assert "UpdateConfigRecorder" not in ops


def test_enabling_opens_recorder(monkeypatch):
    fake = FakeConfigClient(status=0, types=[])
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=True, resource_types=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["recorder"]["Status"] == 1
    ops = [c for c, unused in fake.calls]
    assert "OpenConfigRecorder" in ops
    assert "CloseConfigRecorder" not in ops


def test_enabling_with_new_types_updates_then_opens(monkeypatch):
    fake = FakeConfigClient(status=0, types=RESOURCE_TYPES)
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=True, resource_types=RESOURCE_TYPES + ["QCS::CBS::Disk"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["recorder"]["Status"] == 1
    ops = [c for c, unused in fake.calls]
    assert ops.index("UpdateConfigRecorder") < ops.index("OpenConfigRecorder")


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(status=1, types=RESOURCE_TYPES)
    _make_module(monkeypatch, fake)
    _enabled_args(_ansible_check_mode=True, enabled=False, resource_types=["QCS::CVM::Instance"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len([c for c, unused in fake.calls]) == 1  # describe only
    assert [c for c, unused in fake.calls] == ["DescribeConfigRecorder"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigRecorder(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _enabled_args(enabled=True, resource_types=RESOURCE_TYPES)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
