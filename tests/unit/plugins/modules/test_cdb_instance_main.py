"""Main-path unit tests for the cdb_instance module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_instance
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "cdb-1",
    "InstanceName": "prod-mysql",
    "Status": 1,
    "TaskStatus": 0,
    "Memory": 8000,
    "Volume": 100,
    "EngineVersion": "8.0",
}


class FakeCdbClient(object):
    def __init__(self, instance=None):
        self.instance = instance
        self.task_statuses = []
        self.UpgradeDBInstance = MagicMock(side_effect=self._upgrade)
        self.DescribeAsyncRequestInfo = MagicMock(side_effect=self._task)
        self.DescribeDBInstances = MagicMock(side_effect=self._describe)
        self.IsolateDBInstance = MagicMock()
        self.ModifyDBInstanceName = MagicMock()

    def _describe(self, request):
        if self.instance is None:
            return SimpleNamespace(Items=[])
        return SimpleNamespace(Items=[FakeResource(self.instance)])

    def _upgrade(self, request):
        self.instance["Memory"] = request.Memory
        self.instance["Volume"] = request.Volume
        return SimpleNamespace(AsyncRequestId="task-resize")

    def _task(self, request):
        status = self.task_statuses.pop(0)
        return SimpleNamespace(Status=status, Info="task %s" % status)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCdbClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cdb_instance, "_load_cdb",
        lambda: (FakeModels(), SimpleNamespace(CdbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# state=present spec resize (UpgradeDBInstance)
# ---------------------------------------------------------------------------


def test_resize_memory_drift_uses_current_volume(client):
    client.instance = dict(INSTANCE)
    client.task_statuses = ["SUCCESS"]
    module_args(
        state="present", instance_id="cdb-1",
        memory=16000, waiter_delay=0,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "CDB instance resized"
    assert result["instance"]["Memory"] == 16000
    client.UpgradeDBInstance.assert_called_once()
    request = client.UpgradeDBInstance.call_args[0][0]
    assert request.InstanceId == "cdb-1"
    assert request.Memory == 16000
    assert request.Volume == 100  # current value fills the unspecified dimension


def test_resize_volume_drift_uses_current_memory(client):
    client.instance = dict(INSTANCE)
    client.task_statuses = ["SUCCESS"]
    module_args(
        state="present", instance_id="cdb-1",
        volume=200, waiter_delay=0,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is True
    request = client.UpgradeDBInstance.call_args[0][0]
    assert request.Volume == 200
    assert request.Memory == 8000  # current value fills the unspecified dimension


def test_resize_both_dimensions_drift(client):
    client.instance = dict(INSTANCE)
    client.task_statuses = ["SUCCESS"]
    module_args(
        state="present", instance_id="cdb-1",
        memory=32000, volume=400, waiter_delay=0,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is True
    request = client.UpgradeDBInstance.call_args[0][0]
    assert request.Memory == 32000
    assert request.Volume == 400


def test_present_matching_spec_is_idempotent(client):
    client.instance = dict(INSTANCE)
    module_args(
        state="present", instance_id="cdb-1",
        memory=8000, volume=100,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is False
    assert result["msg"] == "CDB instance is up to date"
    client.UpgradeDBInstance.assert_not_called()


def test_present_without_spec_params_skips_resize(client):
    client.instance = dict(INSTANCE)
    module_args(state="present", instance_id="cdb-1")
    result = run(cdb_instance.run_module)
    assert result["changed"] is False
    client.UpgradeDBInstance.assert_not_called()


def test_resize_check_mode_reports_changed_without_call(client):
    client.instance = dict(INSTANCE)
    module_args(
        _ansible_check_mode=True,
        state="present", instance_id="cdb-1",
        memory=16000, volume=200,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would resize CDB instance"
    client.UpgradeDBInstance.assert_not_called()


def test_resize_waits_for_async_task_before_returning(client):
    client.instance = dict(INSTANCE)
    client.task_statuses = ["RUNNING", "SUCCESS"]
    module_args(
        state="present", instance_id="cdb-1",
        memory=16000, waiter_delay=0,
    )
    result = run(cdb_instance.run_module)
    assert result["changed"] is True
    assert result["instance"]["Memory"] == 16000
    # UpgradeDBInstance + 2 async-task polls + 1 final describe
    assert client.DescribeAsyncRequestInfo.call_count == 2
    request = client.DescribeAsyncRequestInfo.call_args[0][0]
    assert request.AsyncRequestId == "task-resize"


def test_resize_fails_when_async_task_fails(client):
    client.instance = dict(INSTANCE)
    client.task_statuses = ["FAILED"]
    module_args(
        state="present", instance_id="cdb-1",
        memory=16000, waiter_delay=0,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdb_instance.run_module)
    assert "Asynchronous task failed" in exc.value.args[0]["msg"]
