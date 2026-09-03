"""Unit tests for the cdb_backup_config write module (helpers + run_module).

Reconciles TencentDB for MySQL automatic-backup configuration. There is no
state parameter and no lookup loop: a single DescribeBackupConfig response
is compared field-by-field against the desired target and, on any drift, a
ModifyBackupConfig call converges it. Optional binlog_expire_days and
backup_time_window compare equal when both sides are unset (None).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "instance_id": "cdb-abc123",
        "expire_days": 30,
        "start_time": "03:00",
        "backup_method": "physical",
        "binlog_expire_days": None,
        "backup_time_window": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(CdbClient=object)


def _backup_config(**overrides):
    """DescribeBackupConfig response attributes the module reads."""
    state = {
        "BackupExpireDays": 30,
        "StartTimeMin": "03:00",
        "BackupMethod": "physical",
        "BinlogExpireDays": None,
        "BackupTimeWindow": None,
        "RequestId": "req-fake",
    }
    state.update(overrides)
    return state


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing one backup configuration."""

    def __init__(self, config=None):
        self.config = _backup_config(**(config or {}))
        self.calls = []

    def DescribeBackupConfig(self, request):
        self.calls.append(("DescribeBackupConfig", request))
        return SimpleNamespace(**self.config)

    def ModifyBackupConfig(self, request):
        self.calls.append(("ModifyBackupConfig", request))
        self.config["BackupExpireDays"] = request.ExpireDays
        self.config["StartTimeMin"] = request.StartTime
        self.config["BackupMethod"] = request.BackupMethod
        self.config["BinlogExpireDays"] = request.BinlogExpireDays
        self.config["BackupTimeWindow"] = request.BackupTimeWindow
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder and mapping helper tests
# ---------------------------------------------------------------------------


def test_build_describe_fields():
    request = mod.build_describe(FakeModels(), "cdb-abc123")
    assert type(request).__name__ == "DescribeBackupConfigRequest"
    assert request.InstanceId == "cdb-abc123"


def test_build_update_full_fields():
    request = mod.build_update(
        FakeModels(),
        _params(expire_days=15, start_time="01:00", backup_method="logical", binlog_expire_days=7, backup_time_window="02:00-06:00"),
    )
    assert type(request).__name__ == "ModifyBackupConfigRequest"
    assert request.InstanceId == "cdb-abc123"
    assert request.ExpireDays == 15
    assert request.StartTime == "01:00"
    assert request.BackupMethod == "logical"
    assert request.BinlogExpireDays == 7
    assert request.BackupTimeWindow == "02:00-06:00"


def test_build_update_optional_fields_none_when_unset():
    request = mod.build_update(FakeModels(), _params())
    assert request.BinlogExpireDays is None
    assert request.BackupTimeWindow is None


def test_target_maps_params_with_optional_none():
    assert mod.target(_params()) == {
        "BackupExpireDays": 30,
        "StartTimeMin": "03:00",
        "BackupMethod": "physical",
        "BinlogExpireDays": None,
        "BackupTimeWindow": None,
    }


def test_target_includes_optional_values():
    assert mod.target(_params(expire_days=15, backup_method="logical", binlog_expire_days=7, backup_time_window="02:00-06:00")) == {
        "BackupExpireDays": 15,
        "StartTimeMin": "03:00",
        "BackupMethod": "logical",
        "BinlogExpireDays": 7,
        "BackupTimeWindow": "02:00-06:00",
    }


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_unchanged_config_is_noop(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["BackupExpireDays"] == 30
    assert [name for name, request in fake.calls] == ["DescribeBackupConfig"]
    assert not any(name == "ModifyBackupConfig" for name, request in fake.calls)


def test_expire_days_drift_modifies(monkeypatch):
    fake = FakeCdbClient({"BackupExpireDays": 7})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupExpireDays"] == 30  # wanted reported
    assert [name for name, request in fake.calls] == ["DescribeBackupConfig", "ModifyBackupConfig"]
    modify = [req for name, req in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.ExpireDays == 30


def test_start_time_drift_modifies(monkeypatch):
    fake = FakeCdbClient({"StartTimeMin": "05:00"})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [req for name, req in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.StartTime == "03:00"


def test_backup_method_drift_modifies(monkeypatch):
    fake = FakeCdbClient({"BackupMethod": "logical"})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [req for name, req in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.BackupMethod == "physical"


def test_binlog_expire_days_drift_modifies(monkeypatch):
    fake = FakeCdbClient({"BinlogExpireDays": 7})
    _make_module(monkeypatch, fake)
    _run_args(binlog_expire_days=15)
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [req for name, req in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.BinlogExpireDays == 15


def test_backup_time_window_drift_modifies(monkeypatch):
    fake = FakeCdbClient({"BackupTimeWindow": "02:00-06:00"})
    _make_module(monkeypatch, fake)
    _run_args(backup_time_window="22:00-02:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [req for name, req in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.BackupTimeWindow == "22:00-02:00"


def test_check_mode_drift_is_dry_run(monkeypatch):
    fake = FakeCdbClient({"BackupExpireDays": 7})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupExpireDays"] == 30  # wanted reported even in check mode
    assert result["diff"]["before"]["BackupExpireDays"] == 7
    assert result["diff"]["after"]["BackupExpireDays"] == 30
    assert not any(name == "ModifyBackupConfig" for name, request in fake.calls)


def test_invalid_backup_method_choice_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeCdbClient())
    _run_args(backup_method="snapshot")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "backup_method" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["StartTimeMin"] == "03:00"
