"""Unit tests for the cos_bucket_referer write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_referer`` operations mutate a referer-config store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode), default allow_empty=true
* no-op when rules already match; referer type / allow_empty / domain drift
  triggers ``put``
* disabled configurations read back as absent (normalize drops non-Enabled)
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_referer as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

NORMALIZED = {
    "Status": "Enabled",
    "RefererType": "White-List",
    "EmptyReferConfiguration": "Allow",
    "DomainList": {"Domain": ["api.example.com", "www.example.com"]},
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
    """In-memory COS client mutating a referer-configuration store."""

    def __init__(self, referer=None):
        self.referer = copy.deepcopy(referer)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_referer(self, Bucket, **kwargs):
        self._record("get_bucket_referer", Bucket)
        if self.referer is None:
            raise FakeCosError("NoSuchBucket")
        return {"RefererConfiguration": copy.deepcopy(self.referer)}

    def put_bucket_referer(self, Bucket, RefererConfiguration, **kwargs):
        self._record("put_bucket_referer", RefererConfiguration)
        self.referer = copy.deepcopy(RefererConfiguration)

    def delete_bucket_referer(self, Bucket, **kwargs):
        self._record("delete_bucket_referer", Bucket)
        self.referer = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def _referer_args(**overrides):
    params = {
        "state": "present",
        "referer_type": "White-List",
        "allow_empty": True,
        "domains": ["api.example.com", "www.example.com"],
    }
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(referer=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["referer"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_referer"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(referer=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.referer is not None
    assert "delete_bucket_referer" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(referer=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.referer is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_referer" in ops


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(referer=None)
    _make_module(monkeypatch, fake)
    _config(**_referer_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["referer"] == NORMALIZED
    assert fake.referer == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_referer"
    assert "put_bucket_referer" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(referer=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_referer_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    # Check mode reports the *current* configuration, which is absent here.
    assert result["referer"] is None
    assert fake.referer is None
    assert "put_bucket_referer" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(referer=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_referer_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_referer" not in [c for c, unused in fake.calls]


def test_allow_empty_false_sets_deny(monkeypatch):
    fake = FakeCosClient(referer=None)
    _make_module(monkeypatch, fake)
    _config(**_referer_args(allow_empty=False))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["referer"]["EmptyReferConfiguration"] == "Deny"
    assert fake.referer["EmptyReferConfiguration"] == "Deny"


def test_domain_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(referer=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_referer_args(domains=["api.example.com"]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["referer"]["DomainList"]["Domain"] == ["api.example.com"]
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_referer" in ops


def test_disabled_config_reads_as_absent(monkeypatch):
    # A configuration whose Status is not Enabled normalizes to None, so
    # reconciling present re-issues the put.
    fake = FakeCosClient(referer={"Status": "Disabled", "RefererType": "White-List"})
    _make_module(monkeypatch, fake)
    _config(**_referer_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_referer" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_referer(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_referer_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
