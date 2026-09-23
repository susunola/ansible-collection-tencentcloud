"""Unit tests for the tdmysql_backup_policy write module (run_module flows).

``run_module()`` reconciles the single TDSQL MySQL backup policy returned for
an instance. It is driven end to end against an in-memory fake client whose
``ModifyDBSBackupPolicy`` operation mutates the policy store, so the
post-write ``DescribeDBSBackupPolicy`` refetch converges immediately.

Scenario matrix:

* idempotent no-op when every supplied field already matches
* drift updates for retention / window / method fields (check mode and real)
* physical-method updates derive ``StorageType=COS``
* explicit API failure (``IsSuccess=False``) and blanket
  ``sdk_error_payload`` failure paths
* argument validation before any SDK call (no fields, bad HH:MM)
* policy-count guard when the describe returns zero policies
* legacy helper regression tests (folded from test_tdmysql_backup_policy.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_backup_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-instance-abc"
POLICY = {
    "BackupStartTime": "00:00",
    "BackupEndTime": "04:00",
    "BackupMethod": "physical",
    "EnableFull": 1,
    "EnableLog": 1,
    "FullRetentionPeriod": 7,
    "LogRetentionPeriod": 7,
    "PeriodTime": "0,1,2,3,4,5,6",
}


def _base(**overrides):
    params = {"instance_id": INSTANCE_ID}
    params.update(overrides)
    return module_args(**params)


class FakeBackupPolicyClient(object):
    """In-memory TDSQL MySQL client holding one instance's backup policy."""

    def __init__(self, policy=None, success=True):
        self.policy = copy.deepcopy(policy) if policy is not None else None
        self.success = success
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBSBackupPolicy(self, request):
        self._record("DescribeDBSBackupPolicy", request)
        assert request.InstanceId == INSTANCE_ID
        items = [FakeResource(self.policy)] if self.policy is not None else []
        return SimpleNamespace(Items=items, RequestId="req-fake")

    def ModifyDBSBackupPolicy(self, request):
        self._record("ModifyDBSBackupPolicy", request)
        self.last_request = request
        if not self.success:
            return SimpleNamespace(IsSuccess=False, Msg="backup window overlaps", RequestId="req-fake")
        payload = json.loads(request.BackupPolicy.to_json_string()) if hasattr(request.BackupPolicy, "to_json_string") else request.BackupPolicy.__dict__
        self.policy = dict(payload)
        return SimpleNamespace(IsSuccess=True, Msg="", RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_converged_policy_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(period_time="0,1,2,3,4,5,6")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_policy"]["PeriodTime"] == "0,1,2,3,4,5,6"
    assert _names(fake) == ["DescribeDBSBackupPolicy"]


def test_converged_single_field_keeps_other_defaults(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(backup_method="physical")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_policy"]["EnableFull"] is True
    assert _names(fake) == ["DescribeDBSBackupPolicy"]


# ---------------------------------------------------------------------------
# drift update flows
# ---------------------------------------------------------------------------


def test_retention_drift_updates_policy(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(full_retention_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_policy"]["FullRetentionPeriod"] == 30
    assert fake.policy["FullRetentionPeriod"] == 30
    assert fake.last_request.InstanceId == INSTANCE_ID
    assert _names(fake) == ["DescribeDBSBackupPolicy", "ModifyDBSBackupPolicy", "DescribeDBSBackupPolicy"]


def test_window_and_method_drift_update(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(backup_start_time="02:00", backup_end_time="06:00", backup_method="snapshot")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_policy"]["BackupStartTime"] == "02:00"
    assert result["backup_policy"]["BackupMethod"] == "snapshot"
    assert fake.policy["BackupStartTime"] == "02:00"
    assert fake.policy["BackupMethod"] == "snapshot"
    assert fake.policy["StorageType"] == "SNAPSHOT"


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(full_retention_days=30, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_policy"]["FullRetentionPeriod"] == 30
    assert "diff" in result
    assert fake.policy["FullRetentionPeriod"] == 7
    assert "ModifyDBSBackupPolicy" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_no_policy_fields_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at least one backup policy field is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_invalid_hhmm_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY))
    _base(backup_start_time="25:99")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must use HH:MM format" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_zero_policies_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient())
    _base(backup_method="physical")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "expected exactly one TDSQL MySQL backup policy" in payload["msg"]
    assert payload["policy_count"] == 0
    assert _names(fake) == ["DescribeDBSBackupPolicy"]


def test_api_reports_failed_update(monkeypatch):
    fake = _make_module(monkeypatch, FakeBackupPolicyClient(policy=POLICY, success=False))
    _base(full_retention_days=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "backup policy update failed" in payload["msg"]
    assert payload["detail"] == "backup window overlaps"
    assert "ModifyDBSBackupPolicy" in _names(fake)


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBSBackupPolicy(self, request):
            raise Boom("tdmysql endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base(backup_method="physical")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tdmysql endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdmysql_backup_policy.py)
# ---------------------------------------------------------------------------


def test_normalize_converts_api_flags_to_booleans():
    assert mod.normalize({"EnableFull": 1, "EnableLog": 0}) == {"EnableFull": True, "EnableLog": False}
    assert mod.normalize({"EnableFull": None}) == {"EnableFull": None}


def test_desired_overlays_only_supplied_fields():
    p = {"backup_method": "snapshot", "enable_log": None}
    value = mod.desired(p, {"BackupMethod": "physical", "EnableLog": True})
    assert value == {"BackupMethod": "snapshot", "EnableLog": True}


def test_modify_request_derives_storage_and_integer_flags():
    p = {"instance_id": "db1"}
    target = {
        "BackupStartTime": "00:00",
        "BackupEndTime": "04:00",
        "BackupMethod": "snapshot",
        "EnableFull": True,
        "EnableLog": False,
        "FullRetentionPeriod": 7,
        "LogRetentionPeriod": 7,
        "PeriodTime": "0,1",
    }
    request = mod.modify_request(FakeModels(), p, target)
    assert request.InstanceId == "db1"
    payload = dict(request.BackupPolicy.__dict__)
    assert payload["StorageType"] == "SNAPSHOT"
    assert payload["EnableFull"] == 1
    assert payload["EnableLog"] == 0
    physical = dict(target, BackupMethod="physical")
    request = mod.modify_request(FakeModels(), p, physical)
    assert request.BackupPolicy.__dict__["StorageType"] == "COS"
