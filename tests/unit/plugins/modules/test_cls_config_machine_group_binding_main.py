"""Unit tests for the cls_config_machine_group_binding write module.

``cls_config_machine_group_binding`` idempotently applies (state=present)
or removes (state=absent) a CLS collection configuration on a machine
group. The fake CLS client keeps a set of ``(config_id, group_id)``
bindings and mutates it on Apply/Delete so re-reads converge.

Scenario matrix:

* present on an already bound config (no-op)
* present on an unbound config (real apply, check-mode dry run)
* absent on a missing binding (no-op)
* absent on an existing binding (check-mode dry run, real delete)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_config_machine_group_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BINDING = {"ConfigId": "config-abc123", "GroupId": "group-abc123"}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _b_args(**overrides):
    params = {"config_id": "config-abc123", "group_id": "group-abc123"}
    params.update(overrides)
    return module_args(**params)


class FakeClsClient(object):
    """In-memory CLS client mutating a config/machine-group binding set."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(b) for b in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMachineGroupConfigs(self, request):
        self._record("DescribeMachineGroupConfigs", request)
        configs = [FakeResource({"ConfigId": b["ConfigId"]}) for b in self.bindings if b["GroupId"] == request.GroupId]
        return SimpleNamespace(Configs=configs)

    def ApplyConfigToMachineGroup(self, request):
        self._record("ApplyConfigToMachineGroup", request)
        pair = {"ConfigId": request.ConfigId, "GroupId": request.GroupId}
        if pair not in self.bindings:
            self.bindings.append(pair)
        return SimpleNamespace()

    def DeleteConfigFromMachineGroup(self, request):
        self._record("DeleteConfigFromMachineGroup", request)
        self.bindings = [
            b for b in self.bindings
            if not (b["ConfigId"] == request.ConfigId and b["GroupId"] == request.GroupId)
        ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(ClsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_already_bound_is_idempotent(monkeypatch):
    fake = FakeClsClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] == BINDING
    assert [c for c, unused in fake.calls] == ["DescribeMachineGroupConfigs"]


def test_present_applies_binding(monkeypatch):
    fake = FakeClsClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == BINDING
    assert fake.bindings == [BINDING]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeMachineGroupConfigs"
    assert "ApplyConfigToMachineGroup" in ops


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == BINDING
    assert fake.bindings == []
    assert "ApplyConfigToMachineGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_binding_is_idempotent(monkeypatch):
    fake = FakeClsClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert len(fake.bindings) == 1
    assert "DeleteConfigFromMachineGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_binding(monkeypatch):
    fake = FakeClsClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteConfigFromMachineGroup" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMachineGroupConfigs(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _b_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
