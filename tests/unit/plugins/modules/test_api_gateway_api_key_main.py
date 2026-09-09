"""Unit tests for the api_gateway_api_key write module (run_module flows).

Drives ``run_module()`` against an in-memory fake API Gateway client whose
create / update / delete operations mutate an API-key store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing key, identified by name or by ``access_key_id``
  (idempotent no-op; key_id path exercises the not-found guard)
* absent with a matching key (check-mode dry run, real delete)
* creation when missing (auto happy path, manual credentials, check mode)
* existing key without a secret (idempotent no-op)
* access-key-secret rotation (real update, check mode dry run)
* the duplicate-name guard and the ``name``-for-``present`` guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_api_key as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

KEY = {
    "AccessKeyId": "AKID-1001",
    "SecretName": "production-client",
    "AccessKeyType": "auto",
    "AccessKeySecret": "first-secret",
    "Status": 1,
}


def _key(**overrides):
    item = copy.deepcopy(KEY)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {"name": "production-client"}
    params.update(overrides)
    return module_args(**params)


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound"

    def get_request_id(self):
        return "req-err"


class FakeApigatewayClient(object):
    """In-memory API Gateway client mutating a small API-key store."""

    def __init__(self, keys=None):
        self.keys = [copy.deepcopy(t) for t in (keys or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, key_id):
        for item in self.keys:
            if item.get("AccessKeyId") == key_id:
                return item
        return None

    def DescribeApiKey(self, request):
        self._record("DescribeApiKey", request)
        item = self._by_id(getattr(request, "AccessKeyId", None))
        if item is None:
            raise NotFoundError("key not found")
        return SimpleNamespace(Result=FakeResource(item))

    def DescribeApiKeysStatus(self, request):
        self._record("DescribeApiKeysStatus", request)
        return SimpleNamespace(Result=SimpleNamespace(ApiKeySet=[FakeResource(t) for t in self.keys]))

    def CreateApiKey(self, request):
        self._record("CreateApiKey", request)
        self._next += 1
        item = {
            "AccessKeyId": getattr(request, "AccessKeyId", None) or "AKID-%d" % (2000 + self._next),
            "SecretName": getattr(request, "SecretName", None),
            "AccessKeyType": getattr(request, "AccessKeyType", "auto"),
            "AccessKeySecret": getattr(request, "AccessKeySecret", None),
            "Status": 1,
        }
        self.keys.append(item)
        return SimpleNamespace(Result=FakeResource(item), RequestId="req-fake")

    def UpdateApiKey(self, request):
        self._record("UpdateApiKey", request)
        item = self._by_id(getattr(request, "AccessKeyId", None))
        if item is not None:
            item["AccessKeySecret"] = getattr(request, "AccessKeySecret", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteApiKey(self, request):
        self._record("DeleteApiKey", request)
        self.keys = [t for t in self.keys if t.get("AccessKeyId") != getattr(request, "AccessKeyId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api_key"] is None
    assert _names(fake) == ["DescribeApiKeysStatus"]


def test_absent_missing_by_key_id_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", access_key_id="AKID-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api_key"] is None
    assert _names(fake) == ["DescribeApiKey"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_key"]["AccessKeyId"] == "AKID-1001"
    assert len(fake.keys) == 1
    assert "DeleteApiKey" not in _names(fake)


def test_absent_deletes_key(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", access_key_id="AKID-1001", name="production-client")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_key"] is None
    assert fake.keys == []
    assert "DeleteApiKey" in _names(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_without_name_fails(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", access_key_id="AKID-1001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_create_auto_key(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", key_type="auto")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_key"]["SecretName"] == "production-client"
    assert result["api_key"]["AccessKeyType"] == "auto"
    assert result["api_key"]["AccessKeyId"]
    assert "AccessKeySecret" not in result["api_key"]
    assert len(fake.keys) == 1
    ops = _names(fake)
    assert ops[0] == "DescribeApiKeysStatus"
    assert "CreateApiKey" in ops


def test_create_manual_key(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        key_type="manual",
        access_key_id="AKID-manual",
        access_key_secret="manual-secret",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_key"]["AccessKeyId"] == "AKID-manual"
    assert "AccessKeySecret" not in result["api_key"]
    assert fake.keys[0]["AccessKeySecret"] == "manual-secret"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(keys=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.keys == []
    assert "CreateApiKey" not in _names(fake)


def test_duplicate_name_match_fails(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key(), _key(AccessKeyId="AKID-1002")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple API keys have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-key flows
# ---------------------------------------------------------------------------


def test_existing_key_no_secret_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api_key"]["AccessKeyId"] == "AKID-1001"
    assert "AccessKeySecret" not in result["api_key"]
    assert "UpdateApiKey" not in _names(fake)


def test_secret_rotation_updates_key(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", access_key_secret="rotated-secret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_key"]["AccessKeyId"] == "AKID-1001"
    assert fake.keys[0]["AccessKeySecret"] == "rotated-secret"
    assert "UpdateApiKey" in _names(fake)


def test_secret_rotation_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(keys=[_key()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", access_key_secret="rotated-secret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.keys[0]["AccessKeySecret"] == "first-secret"
    assert "UpdateApiKey" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeApiKeysStatus(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
