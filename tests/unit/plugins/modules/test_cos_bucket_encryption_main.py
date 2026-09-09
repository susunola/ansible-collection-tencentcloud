"""Unit tests for the cos_bucket_encryption write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_encryption`` operations mutate an encryption-config
store. The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when rules already match; rule drift triggers ``put``
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_encryption as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

RULES = [
    {
        "ApplyServerSideEncryptionByDefault": {
            "SSEAlgorithm": "AES256",
            "KMSMasterKeyID": "",
        }
    }
]

NORMALIZED = {"Rule": copy.deepcopy(RULES)}


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status


class FakeCosClient(object):
    """In-memory COS client mutating an encryption-configuration store."""

    def __init__(self, encryption=None):
        self.encryption = copy.deepcopy(encryption)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_encryption(self, Bucket, **kwargs):
        self._record("get_bucket_encryption", Bucket)
        if self.encryption is None:
            raise FakeCosError("NoSuchBucket")
        return {"ServerSideEncryptionConfiguration": copy.deepcopy(self.encryption)}

    def put_bucket_encryption(self, Bucket, ServerSideEncryptionConfiguration, **kwargs):
        self._record("put_bucket_encryption", ServerSideEncryptionConfiguration)
        self.encryption = copy.deepcopy(ServerSideEncryptionConfiguration)

    def delete_bucket_encryption(self, Bucket, **kwargs):
        self._record("delete_bucket_encryption", Bucket)
        self.encryption = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _rules():
    return copy.deepcopy(RULES)


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(encryption=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["encryption"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_encryption"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(encryption=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["encryption"] == NORMALIZED
    assert fake.encryption is not None
    assert "delete_bucket_encryption" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(encryption=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["encryption"] is None
    assert fake.encryption is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_encryption" in ops


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(encryption=None)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["encryption"] == NORMALIZED
    assert fake.encryption == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_encryption"
    assert "put_bucket_encryption" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(encryption=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["encryption"] == NORMALIZED
    assert fake.encryption is None
    assert "put_bucket_encryption" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(encryption=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["encryption"] == NORMALIZED
    assert "put_bucket_encryption" not in [c for c, unused in fake.calls]


def test_rule_drift_triggers_update(monkeypatch):
    updated = [
        {
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "KMS",
                "KMSMasterKeyID": "kms-abc123",
            }
        }
    ]
    fake = FakeCosClient(encryption=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=updated)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["encryption"]["Rule"][0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "KMS"
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_encryption" in ops


def test_check_mode_drift_does_not_write(monkeypatch):
    updated = [
        {
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "KMS",
                "KMSMasterKeyID": "kms-abc123",
            }
        }
    ]
    fake = FakeCosClient(encryption=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", rules=updated)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.encryption == NORMALIZED
    assert "put_bucket_encryption" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_encryption(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
