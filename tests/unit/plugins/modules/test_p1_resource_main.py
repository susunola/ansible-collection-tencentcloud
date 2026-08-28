"""Run-module tests for the independently managed P1 resources."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import (
    cam_group_membership,
    kms_key_rotation,
    private_dns_record,
    private_dns_zone,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


@pytest.fixture(autouse=True)
def no_real_sdk(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)


def wire_module(monkeypatch, module, loader_name, client_name, client):
    models = FakeModels()
    client_module = SimpleNamespace(**{client_name: object})
    monkeypatch.setattr(module, loader_name, lambda: (models, client_module))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    return models


def test_cam_membership_adds_missing_user(monkeypatch):
    client = SimpleNamespace(AddUserToGroup=MagicMock(), RemoveUserFromGroup=MagicMock())
    wire_module(monkeypatch, cam_group_membership, "_load_cam", "CamClient", client)
    monkeypatch.setattr(cam_group_membership, "is_member", lambda *args: False)
    waiter = MagicMock(return_value=True)
    monkeypatch.setattr(cam_group_membership, "wait_for_membership", waiter)

    module_args(group_id=42, sub_uin=10001, state="present")
    result = run(cam_group_membership.run_module)

    assert result["changed"] is True
    assert result["membership"]["present"] is True
    client.AddUserToGroup.assert_called_once()
    waiter.assert_called_once()


def test_cam_membership_check_mode_does_not_write(monkeypatch):
    client = SimpleNamespace(AddUserToGroup=MagicMock(), RemoveUserFromGroup=MagicMock())
    wire_module(monkeypatch, cam_group_membership, "_load_cam", "CamClient", client)
    monkeypatch.setattr(cam_group_membership, "is_member", lambda *args: False)

    module_args(group_id=42, sub_uin=10001, state="present", _ansible_check_mode=True)
    result = run(cam_group_membership.run_module)

    assert result["changed"] is True
    assert "diff" in result
    client.AddUserToGroup.assert_not_called()


def test_kms_rotation_updates_period(monkeypatch):
    client = SimpleNamespace(EnableKeyRotation=MagicMock(), DisableKeyRotation=MagicMock())
    wire_module(monkeypatch, kms_key_rotation, "_load_kms", "KmsClient", client)
    current = {"enabled": True, "rotation_days": 365, "last_rotation_time": None, "next_rotation_time": None}
    expected = dict(current, rotation_days=90)
    monkeypatch.setattr(kms_key_rotation, "get_rotation", lambda *args: current)
    waiter = MagicMock(return_value=expected)
    monkeypatch.setattr(kms_key_rotation, "wait_for_rotation", waiter)

    module_args(key_id="key-1", enabled=True, rotation_days=90)
    result = run(kms_key_rotation.run_module)

    assert result["changed"] is True
    assert result["rotation"]["rotation_days"] == 90
    client.EnableKeyRotation.assert_called_once()
    waiter.assert_called_once()


def test_kms_rotation_is_idempotent(monkeypatch):
    client = SimpleNamespace(EnableKeyRotation=MagicMock(), DisableKeyRotation=MagicMock())
    wire_module(monkeypatch, kms_key_rotation, "_load_kms", "KmsClient", client)
    current = {"enabled": True, "rotation_days": 90, "last_rotation_time": None, "next_rotation_time": None}
    monkeypatch.setattr(kms_key_rotation, "get_rotation", lambda *args: current)

    module_args(key_id="key-1", enabled=True, rotation_days=90)
    result = run(kms_key_rotation.run_module)

    assert result["changed"] is False
    client.EnableKeyRotation.assert_not_called()


def test_private_dns_zone_creates(monkeypatch):
    client = SimpleNamespace(CreatePrivateZone=MagicMock(return_value=SimpleNamespace(ZoneId="zone-1")))
    wire_module(monkeypatch, private_dns_zone, "_load_private_dns", "PrivatednsClient", client)
    monkeypatch.setattr(private_dns_zone, "find_zone", lambda *args: None)
    zone = {"ZoneId": "zone-1", "Domain": "internal.example.com", "Remark": "managed"}
    monkeypatch.setattr(private_dns_zone, "wait_for_zone", MagicMock(return_value=zone))

    module_args(domain="internal.example.com", remark="managed", state="present")
    result = run(private_dns_zone.run_module)

    assert result["changed"] is True
    assert result["zone"]["ZoneId"] == "zone-1"
    client.CreatePrivateZone.assert_called_once()


def test_private_dns_zone_absent_is_idempotent(monkeypatch):
    client = SimpleNamespace()
    wire_module(monkeypatch, private_dns_zone, "_load_private_dns", "PrivatednsClient", client)
    monkeypatch.setattr(private_dns_zone, "find_zone", lambda *args: None)

    module_args(zone_id="zone-gone", state="absent")
    result = run(private_dns_zone.run_module)

    assert result["changed"] is False
    assert result["zone"] is None


def test_private_dns_record_creates(monkeypatch):
    client = SimpleNamespace(CreatePrivateZoneRecord=MagicMock(return_value=SimpleNamespace(RecordId="record-1")))
    wire_module(monkeypatch, private_dns_record, "_load_private_dns", "PrivatednsClient", client)
    monkeypatch.setattr(private_dns_record, "find_record", lambda *args: None)
    record = {
        "RecordId": "record-1", "SubDomain": "api", "RecordType": "A",
        "RecordValue": "10.0.0.8", "TTL": 300, "Remark": "",
    }
    monkeypatch.setattr(private_dns_record, "wait_for_record", MagicMock(return_value=record))

    module_args(
        zone_id="zone-1", subdomain="api", record_type="A",
        value="10.0.0.8", state="present",
    )
    result = run(private_dns_record.run_module)

    assert result["changed"] is True
    assert result["record"]["RecordId"] == "record-1"
    client.CreatePrivateZoneRecord.assert_called_once()


def test_private_dns_record_check_mode_does_not_write(monkeypatch):
    client = SimpleNamespace(CreatePrivateZoneRecord=MagicMock())
    wire_module(monkeypatch, private_dns_record, "_load_private_dns", "PrivatednsClient", client)
    monkeypatch.setattr(private_dns_record, "find_record", lambda *args: None)

    module_args(
        zone_id="zone-1", subdomain="api", record_type="A", value="10.0.0.8",
        state="present", _ansible_check_mode=True,
    )
    result = run(private_dns_record.run_module)

    assert result["changed"] is True
    assert "diff" in result
    client.CreatePrivateZoneRecord.assert_not_called()
