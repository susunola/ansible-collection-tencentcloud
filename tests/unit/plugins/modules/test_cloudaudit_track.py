"""Tests for cloudaudit_track."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import cloudaudit_track
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

PARAMS = {
    "name": "events",
    "enabled": True,
    "action_type": "*",
    "resource_type": "*",
    "event_names": ["*"],
    "track_all_members": False,
    "storage_type": "cls",
    "storage_region": "ap-guangzhou",
    "storage_name": "topic-x",
    "storage_prefix": "",
    "storage_account_id": None,
    "storage_app_id": None,
    "compress": True,
}


def test_request_builders():
    models = FakeModels()
    create = cloudaudit_track.build_create_request(models, PARAMS)
    assert create.Status == 1
    assert create.Storage.StorageType == "cls"
    update = cloudaudit_track.build_update_request(models, 12, PARAMS)
    assert update.TrackId == 12
    assert cloudaudit_track.build_delete_request(models, 12).TrackId == 12
    assert cloudaudit_track.build_describe_request(models, 12).TrackId == 12


def test_exact_idempotency_ignores_unmanaged_storage_fields():
    desired = cloudaudit_track._desired(PARAMS)
    current = dict(desired)
    current["Storage"] = dict(desired["Storage"], StorageAccountId=None)
    assert cloudaudit_track._matches(current, desired)
    current["Status"] = 0
    assert not cloudaudit_track._matches(current, desired)
