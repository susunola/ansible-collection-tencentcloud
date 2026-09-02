"""Unit tests for the kms_key write module (helpers + run_module paths).

Covers the create / absent / update / check-mode / validation flows of
``plugins/modules/kms_key.py`` with an in-memory fake KMS client,
following the collection's module test harness (see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import kms_key
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

KEY = {
    "KeyId": "kms-abc123",
    "Alias": "app-key",
    "Description": "app key",
    "KeyUsage": "ENCRYPT_DECRYPT",
    "Type": 1,
    "KeyState": "Enabled",
    "RotateDays": 365,
}


class JsonResource(object):
    """SDK-model stand-in exposing attributes plus ``to_json_string()``.

    ``describe_key``/``find_key_by_alias`` funnel results through
    ``json.loads(value.to_json_string())``, so the fake response objects
    must provide ``to_json_string`` (not just ``_serialize``).
    """

    def __init__(self, data):
        self._data = dict(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "_data":
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def to_json_string(self):
        return json.dumps(self._data)


class FakeKmsClient(object):
    """In-memory KMS client that mutates a small key store."""

    def __init__(self, keys=None):
        self.keys = [dict(k) for k in (keys or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeKey(self, request):
        self._record("DescribeKey", request)
        found = next((k for k in self.keys if k["KeyId"] == request.KeyId), None)
        return SimpleNamespace(KeyMetadata=JsonResource(found) if found else None)

    def ListKeyDetail(self, request):
        self._record("ListKeyDetail", request)
        matched = [k for k in self.keys if k.get("Alias") == request.SearchKeyAlias]
        return SimpleNamespace(
            KeyMetadatas=[JsonResource(k) for k in matched],
            TotalCount=len(matched),
        )

    def CreateKey(self, request):
        self._record("CreateKey", request)
        key = {
            "KeyId": "kms-new0001",
            "Alias": request.Alias,
            "Description": getattr(request, "Description", ""),
            "KeyUsage": request.KeyUsage,
            "Type": request.Type,
            "KeyState": "Enabled",
            "RotateDays": 365,
        }
        self.keys.append(key)
        return SimpleNamespace(KeyId=key["KeyId"])

    def ScheduleKeyDeletion(self, request):
        self._record("ScheduleKeyDeletion", request)
        next(k for k in self.keys if k["KeyId"] == request.KeyId)["KeyState"] = "PendingDelete"
        return SimpleNamespace()

    def CancelKeyDeletion(self, request):
        self._record("CancelKeyDeletion", request)
        next(k for k in self.keys if k["KeyId"] == request.KeyId)["KeyState"] = "Enabled"
        return SimpleNamespace()

    def EnableKey(self, request):
        self._record("EnableKey", request)
        next(k for k in self.keys if k["KeyId"] == request.KeyId)["KeyState"] = "Enabled"
        return SimpleNamespace()

    def DisableKey(self, request):
        self._record("DisableKey", request)
        next(k for k in self.keys if k["KeyId"] == request.KeyId)["KeyState"] = "Disabled"
        return SimpleNamespace()

    def UpdateKeyDescription(self, request):
        self._record("UpdateKeyDescription", request)
        next(k for k in self.keys if k["KeyId"] == request.KeyId)["Description"] = request.Description
        return SimpleNamespace()

    def GetKeyRotationStatus(self, request):
        self._record("GetKeyRotationStatus", request)
        return SimpleNamespace(KeyRotationEnabled=True)

    def EnableKeyRotation(self, request):
        self._record("EnableKeyRotation", request)
        return SimpleNamespace()

    def DisableKeyRotation(self, request):
        self._record("DisableKeyRotation", request)
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helper functions that only need params/sdk_call."""

    def __init__(self, **params):
        self.params = dict(params)
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeKmsClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        kms_key, "_load_kms",
        lambda: (FakeModels(), SimpleNamespace(KmsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_key_returns_none_without_id():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    assert kms_key.describe_key(module, FakeKmsClient(), FakeModels(), None) is None


def test_describe_key_maps_metadata_to_dict():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeKmsClient(keys=[KEY])
    result = kms_key.describe_key(module, client, FakeModels(), "kms-abc123")
    assert result["KeyId"] == "kms-abc123"
    assert result["KeyState"] == "Enabled"


def test_build_list_key_request_sets_paging_and_filter():
    request = kms_key.build_list_key_request(FakeModels(), "web-key", offset=40)
    assert request.Offset == 40
    assert request.Limit == 200
    assert request.KeyState == 0
    assert request.SearchKeyAlias == "web-key"


def test_find_key_by_alias_exact_match_only():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeKmsClient(keys=[dict(KEY, KeyId="kms-1"), dict(KEY, KeyId="kms-2", Alias="other-key")])
    found = kms_key.find_key_by_alias(module, client, FakeModels(), "app-key")
    assert found["KeyId"] == "kms-1"
    assert client.calls[0][0] == "ListKeyDetail"


def test_find_key_by_alias_no_match_returns_none():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    assert kms_key.find_key_by_alias(module, FakeKmsClient(), FakeModels(), "nope") is None


def test_find_key_by_alias_multiple_matches_fails():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeKmsClient(keys=[dict(KEY, KeyId="kms-1"), dict(KEY, KeyId="kms-2")])
    with pytest.raises(AnsibleFailJson) as exc:
        kms_key.find_key_by_alias(module, client, FakeModels(), "app-key")
    assert "Multiple" in exc.value.args[0]["msg"]


def test_wait_for_key_state_returns_on_expected_state():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeKmsClient(keys=[KEY])
    result = kms_key.wait_for_key_state(module, client, FakeModels(), "kms-abc123", ("Enabled",))
    assert result["KeyState"] == "Enabled"


def test_wait_for_key_state_times_out():
    module = FakeModule(waiter_timeout=0.01, waiter_delay=0)
    client = FakeKmsClient(keys=[dict(KEY, KeyState="Disabled")])
    with patch.object(kms_key.time, "time", side_effect=[100.0, 101.0]):
        with pytest.raises(AnsibleFailJson) as exc:
            kms_key.wait_for_key_state(module, client, FakeModels(), "kms-abc123", ("Enabled",))
    assert "Timed out" in exc.value.args[0]["msg"]


def test_build_rotation_request_branches():
    models = FakeModels()
    assert kms_key.build_rotation_request(models, "kms-1", None, None).KeyId == "kms-1"
    enable_req = kms_key.build_rotation_request(models, "kms-1", True, 30)
    assert enable_req.RotateDays == 30
    assert kms_key.build_rotation_request(models, "kms-1", False, None).KeyId == "kms-1"


def test_set_rotation_enables_and_disables():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeKmsClient()
    kms_key.set_rotation(module, client, FakeModels(), "kms-1", True, 30)
    kms_key.set_rotation(module, client, FakeModels(), "kms-1", False, 30)
    names = [c[0] for c in client.calls]
    assert "EnableKeyRotation" in names
    assert "DisableKeyRotation" in names


def test_build_create_request_sorts_tags():
    request = kms_key.build_create_request(
        FakeModels(),
        {"alias": "app-key", "description": "d", "key_usage": "ENCRYPT_DECRYPT",
         "key_type": None, "tags": {"z": "1", "a": "2"}},
    )
    assert [t.TagKey for t in request.Tags] == ["a", "z"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_create_reports_changed(client):
    module_args(state="present", alias="app-key")
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert result["key"]["KeyId"] == "kms-new0001"
    assert any(name == "CreateKey" for name, _ in client.calls)


def test_second_run_is_idempotent(client):
    client.keys = [dict(KEY)]
    module_args(state="present", alias="app-key", description="app key", rotation_enabled=True)
    result = run(kms_key.run_module)
    assert result["changed"] is False
    assert not any(name in ("CreateKey", "UpdateKeyDescription") for name, _ in client.calls)


def test_absent_schedules_deletion(client):
    client.keys = [dict(KEY)]
    module_args(state="absent", alias="app-key")
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert any(name == "ScheduleKeyDeletion" for name, _ in client.calls)
    assert client.keys[0]["KeyState"] == "PendingDelete"


def test_absent_on_missing_key_is_unchanged(client):
    module_args(state="absent", alias="app-key")
    result = run(kms_key.run_module)
    assert result["changed"] is False


def test_absent_on_pending_delete_is_unchanged(client):
    client.keys = [dict(KEY, KeyState="PendingDelete")]
    module_args(state="absent", alias="app-key")
    result = run(kms_key.run_module)
    assert result["changed"] is False


def test_check_mode_create_makes_no_writes(client):
    module_args(state="present", alias="app-key", _ansible_check_mode=True)
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert not any(name not in ("DescribeKey", "ListKeyDetail") for name, _ in client.calls)


def test_present_requires_alias_or_key_id(client):
    module_args(state="present")
    with pytest.raises(AnsibleFailJson):
        run(kms_key.run_module)


def test_deletion_window_out_of_range_fails(client):
    module_args(state="absent", alias="app-key", deletion_window_days=5)
    with pytest.raises(AnsibleFailJson):
        run(kms_key.run_module)


def test_immutable_drift_fails(client):
    client.keys = [dict(KEY)]
    module_args(state="present", alias="app-key", key_usage="ASYMMETRIC_SIGN_VERIFY_SM2")
    with pytest.raises(AnsibleFailJson):
        run(kms_key.run_module)


def test_update_description_reports_changed(client):
    client.keys = [dict(KEY)]
    module_args(state="present", alias="app-key", description="renamed")
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert any(name == "UpdateKeyDescription" for name, _ in client.calls)


def test_update_enabled_state_toggles_key(client):
    client.keys = [dict(KEY)]
    module_args(state="present", alias="app-key", enabled=False)
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert any(name == "DisableKey" for name, _ in client.calls)
    assert client.keys[0]["KeyState"] == "Disabled"


def test_cancel_pending_deletion_when_present_again(client):
    client.keys = [dict(KEY, KeyState="PendingDelete")]
    module_args(state="present", alias="app-key")
    result = run(kms_key.run_module)
    assert result["changed"] is True
    assert any(name == "CancelKeyDeletion" for name, _ in client.calls)
    assert client.keys[0]["KeyState"] == "Enabled"
