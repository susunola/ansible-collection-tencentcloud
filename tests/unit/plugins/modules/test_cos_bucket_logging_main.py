"""Unit tests for the cos_bucket_logging write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put_bucket_logging`` operations mutate an access-logging store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on an unconfigured bucket (idempotent no-op, empty put) and on a
  configured bucket (check-mode dry run, real disable via empty put)
* enablement when missing (happy path, check mode)
* no-op when the destination already matches; target_prefix drift triggers put
* bucket-level 404 maps to "not configured"
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_logging as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

NORMALIZED = {
    "LoggingEnabled": {"TargetBucket": "audit-logs-1250000000", "TargetPrefix": "cos/application-data/"}
}


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
    """In-memory COS client mutating a bucket access-logging store.

    ``enabled`` holds the effective LoggingEnabled dict (None when logging
    is disabled). ``bucket_missing`` simulates a deleted source bucket.
    """

    def __init__(self, enabled=None, bucket_missing=False):
        self.enabled = copy.deepcopy(enabled)
        self.bucket_missing = bucket_missing
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_logging(self, Bucket, **kwargs):
        self._record("get_bucket_logging", Bucket)
        if self.bucket_missing:
            raise FakeCosError("NoSuchBucket")
        if self.enabled is None:
            return {"BucketLoggingStatus": {}}
        return {"BucketLoggingStatus": {"LoggingEnabled": copy.deepcopy(self.enabled)}}

    def put_bucket_logging(self, Bucket, BucketLoggingStatus, **kwargs):
        self._record("put_bucket_logging", BucketLoggingStatus)
        enabled = BucketLoggingStatus.get("LoggingEnabled") if BucketLoggingStatus else None
        self.enabled = copy.deepcopy(enabled)


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def test_absent_unconfigured_is_idempotent(monkeypatch):
    fake = FakeCosClient(enabled=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["logging"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_logging"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(enabled=NORMALIZED["LoggingEnabled"])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.enabled is not None
    assert "put_bucket_logging" not in [c for c, unused in fake.calls]


def test_absent_disables_logging(monkeypatch):
    fake = FakeCosClient(enabled=NORMALIZED["LoggingEnabled"])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.enabled is None
    puts = [req for name, req in fake.calls if name == "put_bucket_logging"]
    assert puts == [{}]


def test_create_logging(monkeypatch):
    fake = FakeCosClient(enabled=None)
    _make_module(monkeypatch, fake)
    _config(state="present", target_bucket="audit-logs-1250000000", target_prefix="cos/application-data/")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logging"] == NORMALIZED
    assert fake.enabled == NORMALIZED["LoggingEnabled"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_logging"
    assert "put_bucket_logging" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(enabled=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", target_bucket="audit-logs-1250000000", target_prefix="cos/application-data/")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.enabled is None
    assert "put_bucket_logging" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(enabled=NORMALIZED["LoggingEnabled"])
    _make_module(monkeypatch, fake)
    _config(state="present", target_bucket="audit-logs-1250000000", target_prefix="cos/application-data/")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_logging" not in [c for c, unused in fake.calls]


def test_prefix_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(enabled=NORMALIZED["LoggingEnabled"])
    _make_module(monkeypatch, fake)
    _config(state="present", target_bucket="audit-logs-1250000000", target_prefix="cos/other/")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logging"]["LoggingEnabled"]["TargetPrefix"] == "cos/other/"
    assert fake.enabled["TargetPrefix"] == "cos/other/"
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_logging" in ops


def test_bucket_missing_maps_to_not_configured(monkeypatch):
    fake = FakeCosClient(enabled=None, bucket_missing=True)
    _make_module(monkeypatch, fake)
    _config(state="present", target_bucket="audit-logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.enabled == {"TargetBucket": "audit-logs-1250000000", "TargetPrefix": ""}
    assert "put_bucket_logging" in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_logging(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present", target_bucket="audit-logs-1250000000")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
