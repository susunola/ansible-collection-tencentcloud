"""Unit tests for the cynosdb_backup_config write module (run_module flows).

The module reconciles the automatic-backup window and retention duration of a
CynosDB cluster. There is no ``state`` parameter, no creation and no
lookup-by-name loop: one ``DescribeBackupConfig`` singleton response is
compared field-by-field (backup window bounds and reserve duration) against
the desired target and, on drift, a ``ModifyBackupConfig`` call converges it
followed by a fresh describe.

Scenario matrix:

* matching configuration is idempotent
* window/retention drift triggers a modify
* drift in check mode is a dry run (no modify call)
* parameter validation failures are reported
* the instance record may carry SDK noise fields; only the compared keys
  matter
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cynosdb_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG = {
    "ClusterId": "cynosdbmysql-abc123",
    "BackupTimeBeg": 10800,
    "BackupTimeEnd": 14400,
    "ReserveDuration": 604800,
    "RequestId": "req-fake",
}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "cluster_id": "cynosdbmysql-abc123",
        "backup_start": 10800,
        "backup_end": 14400,
        "retention_seconds": 604800,
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class FakeCynosdbClient(object):
    """In-memory CynosDB client holding one per-cluster backup configuration."""

    def __init__(self, config=None):
        self.config = _config(**(config or {}))
        self.calls = []

    def DescribeBackupConfig(self, request):
        self.calls.append(("DescribeBackupConfig", request))
        return FakeResource(self.config)

    def ModifyBackupConfig(self, request):
        self.calls.append(("ModifyBackupConfig", request))
        self.config["BackupTimeBeg"] = request.BackupTimeBeg
        self.config["BackupTimeEnd"] = request.BackupTimeEnd
        self.config["ReserveDuration"] = request.ReserveDuration
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CynosdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching configuration
# ---------------------------------------------------------------------------


def test_matching_config_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["BackupTimeBeg"] == 10800
    assert result["backup_config"]["BackupTimeEnd"] == 14400
    assert result["backup_config"]["ReserveDuration"] == 604800
    assert [name for name, unused in fake.calls] == ["DescribeBackupConfig"]


def test_sdk_noise_fields_do_not_trigger_drift(monkeypatch):
    fake = FakeCynosdbClient({"Status": 2, "InstanceName": "orders"})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["InstanceName"] == "orders"


# ---------------------------------------------------------------------------
# drift handling
# ---------------------------------------------------------------------------


def test_backup_end_drift_modifies(monkeypatch):
    fake = FakeCynosdbClient({"BackupTimeEnd": 17000})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupTimeEnd"] == 14400
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeBackupConfig", "ModifyBackupConfig", "DescribeBackupConfig"]
    modify = [request for name, request in fake.calls if name == "ModifyBackupConfig"][0]
    assert modify.ClusterId == "cynosdbmysql-abc123"
    assert modify.BackupTimeBeg == 10800
    assert modify.BackupTimeEnd == 14400
    assert modify.ReserveDuration == 604800


def test_reserve_duration_drift_modifies(monkeypatch):
    fake = FakeCynosdbClient({"ReserveDuration": 2592000})
    _make_module(monkeypatch, fake)
    _run_args(retention_seconds=864000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["ReserveDuration"] == 864000


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient({"BackupTimeBeg": 3600})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupTimeBeg"] == 3600  # drifted current shown
    assert result["diff"]["after"]["BackupTimeBeg"] == 10800
    assert "ModifyBackupConfig" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation and failure paths
# ---------------------------------------------------------------------------


def test_invalid_window_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeCynosdbClient())
    _run_args(backup_start=14400, backup_end=10800)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "backup window" in exc.value.args[0]["msg"]


def test_invalid_retention_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeCynosdbClient())
    _run_args(retention_seconds=60)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_seconds" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCynosdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["BackupTimeEnd"] == 14400
