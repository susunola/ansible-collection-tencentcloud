"""Unit tests for the ssm_rotation write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake SSM client
whose ``UpdateRotationStatus`` mutates a rotation-detail store, so the
post-update ``DescribeRotationDetail`` refetch converges immediately.

Scenario matrix:

* idempotent no-op when the current rotation already matches (enabled and
  disabled variants)
* drift update through ``UpdateRotationStatus`` with captured request fields
* optional ``begin_time`` propagation (and omission when unset)
* check-mode update is a dry run that reports the desired target
* ``frequency`` range validation before any SDK call
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_ssm_rotation.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_rotation as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

SECRET = "prod/db-managed"


def _detail(**overrides):
    item = {
        "EnableRotation": True,
        "Frequency": 30,
        "LatestRotateTime": "2026-08-01 02:00:00",
        "NextRotateBeginTime": "2026-09-30 02:00:00",
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"secret_name": SECRET, "enabled": True, "frequency": 30}
    params.update(overrides)
    return module_args(**params)


class FakeSsmClient(object):
    """In-memory SSM client exposing one rotation-detail record per secret."""

    def __init__(self, detail=None):
        self.detail = copy.deepcopy(detail) if detail is not None else _detail()
        self.calls = []
        self.last_update = None

    def DescribeRotationDetail(self, request):
        self.calls.append("DescribeRotationDetail")
        assert request.SecretName == SECRET
        return SimpleNamespace(**dict(self.detail))

    def UpdateRotationStatus(self, request):
        self.calls.append("UpdateRotationStatus")
        self.last_update = request
        self.detail["EnableRotation"] = bool(request.EnableRotation)
        self.detail["Frequency"] = int(request.Frequency)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(SsmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_matching_rotation_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail()))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rotation"]["EnableRotation"] is True
    assert result["rotation"]["Frequency"] == 30
    assert result["rotation"]["NextRotateBeginTime"] == "2026-09-30 02:00:00"
    assert fake.calls == ["DescribeRotationDetail"]


def test_disabled_rotation_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail(EnableRotation=False)))
    _base(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rotation"]["EnableRotation"] is False


# ---------------------------------------------------------------------------
# update flows
# ---------------------------------------------------------------------------


def test_rotation_drift_updates(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail(EnableRotation=False, Frequency=60)))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rotation"]["EnableRotation"] is True
    assert result["rotation"]["Frequency"] == 30
    assert result["rotation"]["LatestRotateTime"] == "2026-08-01 02:00:00"
    request = fake.last_update
    assert request.SecretName == SECRET
    assert request.EnableRotation is True
    assert request.Frequency == 30
    assert fake.calls == ["DescribeRotationDetail", "UpdateRotationStatus", "DescribeRotationDetail"]


def test_update_begin_time_is_propagated(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail(Frequency=60)))
    _base(begin_time="2026-09-01 02:00:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.last_update.RotationBeginTime == "2026-09-01 02:00:00"


def test_update_omits_begin_time_when_unset(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail(Frequency=60)))
    _base()
    run(mod.run_module)
    assert not hasattr(fake.last_update, "RotationBeginTime")


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient(detail=_detail(EnableRotation=False, Frequency=60)))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rotation"] == {"EnableRotation": True, "Frequency": 30}
    assert fake.detail["EnableRotation"] is False
    assert fake.detail["Frequency"] == 60
    assert fake.calls == ["DescribeRotationDetail"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_frequency_out_of_range_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient())
    _base(frequency=366)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "between 30 and 365" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_secret_name_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeSsmClient())
    module_args(enabled=True, frequency=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_name" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRotationDetail(self, request):
            raise Boom("ssm endpoint unreachable")

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "ssm endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_ssm_rotation.py)
# ---------------------------------------------------------------------------


def test_update_request_preserves_service_time_format():
    request = mod.update_request(FakeModels(), {
        "secret_name": "prod-db",
        "enabled": True,
        "frequency": 60,
        "begin_time": "2026-09-01 02:00:00",
    })
    assert request.SecretName == "prod-db"
    assert request.EnableRotation is True
    assert request.Frequency == 60
    assert request.RotationBeginTime == "2026-09-01 02:00:00"


def test_comparable_and_result_exclude_unstable_schedule_from_diff():
    response = SimpleNamespace(
        EnableRotation=True,
        Frequency=60,
        LatestRotateTime="2026-08-01 02:00:00",
        NextRotateBeginTime="2026-09-30 02:00:00",
    )
    assert mod.comparable(response) == {"EnableRotation": True, "Frequency": 60}
    assert mod.result(response)["NextRotateBeginTime"] == "2026-09-30 02:00:00"
    assert mod.describe_request(FakeModels(), "prod-db").SecretName == "prod-db"
