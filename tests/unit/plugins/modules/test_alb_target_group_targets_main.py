"""Unit tests for the alb_target_group_targets write module (run_module flows).

``alb_target_group_targets`` reconciles the backend target set of an ALB
target group: targets that only exist remotely are added, targets whose
weight drifted are modified, and - when ``purge`` is on - targets that are
not desired are removed. There is no ``state`` option; the module always
converges toward the requested set.

The fake ALB client stores the live backend list and every mutating SDK
call updates it, so the post-write ``find`` inside the module converges
immediately.

Scenario matrix:

* empty-to-empty no-op and purge removal
* additive creation (real, check mode)
* no-drift idempotence
* weight drift / combined add-update-remove reconciliation
* purge disabled keeps unmanaged backends
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import alb_target_group_targets as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TARGETS = [
    {"ip": "10.0.1.10", "port": 8080, "weight": 50},
    {"ip": "10.0.1.11", "port": 8080, "weight": 10},
]


class TargetModels(FakeModels):
    """FakeModels whose SDK target classes expose ``Weight``.

    The real SDK models declare ``Weight`` at class level, and
    ``_target()`` only sets the attribute when ``hasattr`` finds it.
    """

    def __getattr__(self, name):
        cls = FakeModels.__getattr__(self, name)
        if name in ("TargetToAdd", "TargetToModify", "TargetToRemove"):
            cls.Weight = None
        return cls


def _target(ip, port, weight=10):
    return {"ip": ip, "port": port, "weight": weight}


def _tg_args(**overrides):
    params = {"target_group_id": "alb-tg-test001"}
    params.update(overrides)
    return module_args(**params)


class FakeAlbClient(object):
    """In-memory ALB client mutating a backend target store."""

    def __init__(self, targets=None):
        self.targets = [copy.deepcopy(t) for t in (targets or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _serialized(self):
        return [FakeResource({"TargetIp": t["ip"], "Port": t["port"], "Weight": t["weight"]}) for t in self.targets]

    def DescribeTargetGroupTargets(self, request):
        self._record("DescribeTargetGroupTargets", request)
        return SimpleNamespace(Targets=self._serialized())

    def AddTargetsToTargetGroup(self, request):
        self._record("AddTargetsToTargetGroup", request)
        for x in request.Targets:
            self.targets.append({"ip": x.TargetIp, "port": x.Port, "weight": x.Weight})
        return SimpleNamespace()

    def ModifyTargetsInTargetGroup(self, request):
        self._record("ModifyTargetsInTargetGroup", request)
        for x in request.Targets:
            for t in self.targets:
                if t["ip"] == x.TargetIp and t["port"] == x.Port:
                    t["weight"] = x.Weight
        return SimpleNamespace()

    def RemoveTargetsFromTargetGroup(self, request):
        self._record("RemoveTargetsFromTargetGroup", request)
        keys = [(x.TargetIp, x.Port) for x in request.Targets]
        self.targets = [t for t in self.targets if (t["ip"], t["port"]) not in keys]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (TargetModels(), SimpleNamespace(AlbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# no-op flows
# ---------------------------------------------------------------------------


def test_empty_to_empty_is_idempotent(monkeypatch):
    fake = FakeAlbClient(targets=[])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["targets"] == []
    assert [c for c, unused in fake.calls] == ["DescribeTargetGroupTargets"]


def test_purge_false_keeps_unmanaged_targets(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10), _target("10.0.1.99", 443, 20)])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[_target("10.0.1.10", 8080, 10)], purge=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["targets"] == [_target("10.0.1.10", 8080, 10), _target("10.0.1.99", 443, 20)]
    assert fake.targets == [_target("10.0.1.10", 8080, 10), _target("10.0.1.99", 443, 20)]
    assert "RemoveTargetsFromTargetGroup" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10)])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[_target("10.0.1.10", 8080)])  # weight defaults to 10
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["targets"] == [_target("10.0.1.10", 8080, 10)]
    ops = [c for c, unused in fake.calls]
    assert "ModifyTargetsInTargetGroup" not in ops
    assert "AddTargetsToTargetGroup" not in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_add_targets_when_missing(monkeypatch):
    fake = FakeAlbClient(targets=[])
    _make_module(monkeypatch, fake)
    _tg_args(targets=TARGETS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["targets"] == TARGETS
    assert fake.targets == TARGETS
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTargetGroupTargets"
    assert "AddTargetsToTargetGroup" in ops


def test_add_targets_check_mode_is_dry_run(monkeypatch):
    fake = FakeAlbClient(targets=[])
    _make_module(monkeypatch, fake)
    _tg_args(_ansible_check_mode=True, targets=[_target("10.0.1.10", 8080, 10)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["targets"] == [_target("10.0.1.10", 8080, 10)]
    assert fake.targets == []
    assert "AddTargetsToTargetGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# update / purge flows
# ---------------------------------------------------------------------------


def test_weight_drift_triggers_modify(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10)])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[_target("10.0.1.10", 8080, 80)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.targets == [_target("10.0.1.10", 8080, 80)]
    assert "ModifyTargetsInTargetGroup" in [c for c, unused in fake.calls]


def test_purge_removes_unlisted_targets(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10), _target("10.0.1.11", 8080, 10)])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[_target("10.0.1.10", 8080, 10)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["targets"] == [_target("10.0.1.10", 8080, 10)]
    assert fake.targets == [_target("10.0.1.10", 8080, 10)]
    assert "RemoveTargetsFromTargetGroup" in [c for c, unused in fake.calls]


def test_purge_all_targets_when_desired_empty(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10), _target("10.0.1.11", 8080, 10)])
    _make_module(monkeypatch, fake)
    _tg_args(targets=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["targets"] == []
    assert fake.targets == []


def test_combined_add_update_remove(monkeypatch):
    fake = FakeAlbClient(targets=[_target("10.0.1.10", 8080, 10), _target("10.0.1.11", 8080, 10)])
    _make_module(monkeypatch, fake)
    _tg_args(
        targets=[
            _target("10.0.1.10", 8080, 60),   # update
            _target("10.0.1.12", 8080, 30),   # add
        ]
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.targets == [_target("10.0.1.10", 8080, 60), _target("10.0.1.12", 8080, 30)]
    ops = [c for c, unused in fake.calls]
    assert "AddTargetsToTargetGroup" in ops
    assert "ModifyTargetsInTargetGroup" in ops
    assert "RemoveTargetsFromTargetGroup" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTargetGroupTargets(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _tg_args(targets=[_target("10.0.1.10", 8080, 10)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
