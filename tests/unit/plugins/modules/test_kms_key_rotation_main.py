"""Unit tests for the kms_key_rotation write module (run_module flows).

``kms_key_rotation`` reconciles the automatic-rotation switch of an
existing KMS key and its period, reading current state with
``GetKeyRotationStatus`` + ``DescribeKey`` and writing through
``EnableKeyRotation`` / ``DisableKeyRotation``.

Note the module's lazy SDK import helper is ``_load_kms`` (not ``_load``);
the fixture monkeypatches that name. The fake KMS client converges on the
first post-write poll so ``wait_for_rotation`` returns immediately.

Scenario matrix:

* rotation_days validation failure
* up-to-date enabled / disabled no-ops
* enabling with a new period, disabling, period drift (real writes)
* check-mode dry run when the desired state differs
* SDK failure envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import kms_key_rotation as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

KEY = {
    "KeyId": "key-abc123",
    "KeyRotationEnabled": True,
    "RotateDays": 90,
    "LastRotateTime": "2026-08-01 00:00:00",
    "NextRotateTime": "2026-10-30 00:00:00",
}


def _key(**overrides):
    item = copy.deepcopy(KEY)
    item.update(overrides)
    return item


def _key_args(**overrides):
    params = {"key_id": "key-abc123"}
    params.update(overrides)
    return module_args(**params)


class FakeKmsClient(object):
    """In-memory KMS client mutating a key rotation store."""

    def __init__(self, keys=None):
        self.keys = [copy.deepcopy(k) for k in (keys or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, key_id):
        return next((k for k in self.keys if k["KeyId"] == key_id), None)

    def GetKeyRotationStatus(self, request):
        self._record("GetKeyRotationStatus", request)
        key = self._find(request.KeyId)
        return SimpleNamespace(KeyRotationEnabled=bool(key["KeyRotationEnabled"]) if key else False)

    def DescribeKey(self, request):
        self._record("DescribeKey", request)
        key = self._find(request.KeyId)
        if not key:
            return SimpleNamespace(KeyMetadata=None)
        return SimpleNamespace(KeyMetadata=FakeResource({
            "RotateDays": key.get("RotateDays"),
            "LastRotateTime": key.get("LastRotateTime"),
            "NextRotateTime": key.get("NextRotateTime"),
        }))

    def EnableKeyRotation(self, request):
        self._record("EnableKeyRotation", request)
        key = self._find(request.KeyId)
        key["KeyRotationEnabled"] = True
        key["RotateDays"] = getattr(request, "RotateDays", None)
        return SimpleNamespace()

    def DisableKeyRotation(self, request):
        self._record("DisableKeyRotation", request)
        key = self._find(request.KeyId)
        key["KeyRotationEnabled"] = False
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_kms", lambda: (FakeModels(), SimpleNamespace(KmsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# validation and no-op flows
# ---------------------------------------------------------------------------


def test_rotation_days_out_of_range_fails(monkeypatch):
    fake = FakeKmsClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _key_args(enabled=True, rotation_days=3)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "between 7 and 365" in exc.value.args[0]["msg"]


def test_enabled_up_to_date_is_idempotent(monkeypatch):
    fake = FakeKmsClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _key_args(enabled=True, rotation_days=90)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rotation"]["enabled"] is True
    assert "KMS key rotation is up to date" in result["msg"]
    ops = [c for c, unused in fake.calls]
    assert "EnableKeyRotation" not in ops


def test_disabled_up_to_date_is_idempotent(monkeypatch):
    fake = FakeKmsClient(keys=[_key(KeyRotationEnabled=False, RotateDays=None)])
    _make_module(monkeypatch, fake)
    _key_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rotation"]["enabled"] is False
    ops = [c for c, unused in fake.calls]
    assert "DisableKeyRotation" not in ops


# ---------------------------------------------------------------------------
# enabling / disabling / period drift
# ---------------------------------------------------------------------------


def test_enable_rotation_with_new_period(monkeypatch):
    fake = FakeKmsClient(keys=[_key(KeyRotationEnabled=False, RotateDays=None)])
    _make_module(monkeypatch, fake)
    _key_args(enabled=True, rotation_days=90)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rotation"]["enabled"] is True
    assert result["rotation"]["rotation_days"] == 90
    assert fake.keys[0]["KeyRotationEnabled"] is True
    assert fake.keys[0]["RotateDays"] == 90
    ops = [c for c, unused in fake.calls]
    assert "EnableKeyRotation" in ops


def test_disable_rotation(monkeypatch):
    fake = FakeKmsClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _key_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rotation"]["enabled"] is False
    assert fake.keys[0]["KeyRotationEnabled"] is False
    ops = [c for c, unused in fake.calls]
    assert "DisableKeyRotation" in ops


def test_rotation_period_drift_updates(monkeypatch):
    fake = FakeKmsClient(keys=[_key(KeyRotationEnabled=True, RotateDays=365)])
    _make_module(monkeypatch, fake)
    _key_args(enabled=True, rotation_days=90)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rotation"]["rotation_days"] == 90
    assert fake.keys[0]["RotateDays"] == 90
    ops = [c for c, unused in fake.calls]
    assert "EnableKeyRotation" in ops


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeKmsClient(keys=[_key(KeyRotationEnabled=False, RotateDays=None)])
    _make_module(monkeypatch, fake)
    _key_args(_ansible_check_mode=True, enabled=True, rotation_days=90)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update KMS key rotation" in result["msg"]
    assert fake.keys[0]["KeyRotationEnabled"] is False
    ops = [c for c, unused in fake.calls]
    assert "EnableKeyRotation" not in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def GetKeyRotationStatus(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _key_args(enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
