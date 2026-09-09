"""Unit tests for the cos_bucket_domain write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_domain`` operations mutate a domain-rule store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when rules already match; rule drift triggers put
* the ``x-cos-domain-txt-verification`` header round-trips from get
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

NORMALIZED = {
    "DomainRule": [
        {"Name": "downloads.example.com", "Type": "REST", "Status": "ENABLED"},
        {"Name": "static.example.com", "Type": "REST", "Status": "ENABLED"},
    ]
}
RULES = [
    {"Name": "static.example.com", "Type": "REST", "Status": "ENABLED"},
    {"Name": "downloads.example.com", "Type": "REST", "Status": "ENABLED"},
]
TXT = "cos-domain-verification-abc123"


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
    """In-memory COS client mutating a domain-rule store."""

    def __init__(self, rules=None, txt=None):
        self.rules = copy.deepcopy(rules)
        self.txt = txt
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_domain(self, Bucket, **kwargs):
        self._record("get_bucket_domain", Bucket)
        if self.rules is None:
            raise FakeCosError("NoSuchBucket")
        payload = {"DomainConfiguration": {"DomainRule": copy.deepcopy(self.rules)}}
        if self.txt:
            payload["x-cos-domain-txt-verification"] = self.txt
        return payload

    def put_bucket_domain(self, Bucket, DomainConfiguration, **kwargs):
        self._record("put_bucket_domain", DomainConfiguration)
        self.rules = copy.deepcopy(DomainConfiguration.get("DomainRule") or [])

    def delete_bucket_domain(self, Bucket, **kwargs):
        self._record("delete_bucket_domain", Bucket)
        self.rules = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def _present_args(**overrides):
    params = {"state": "present", "rules": copy.deepcopy(RULES)}
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(rules=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domains"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_domain"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(rules=NORMALIZED["DomainRule"])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules is not None
    assert "delete_bucket_domain" not in [c for c, unused in fake.calls]


def test_absent_deletes_rules(monkeypatch):
    fake = FakeCosClient(rules=NORMALIZED["DomainRule"])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_domain" in ops


def test_create_rules(monkeypatch):
    fake = FakeCosClient(rules=None)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domains"] == NORMALIZED
    assert fake.rules == NORMALIZED["DomainRule"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_domain"
    assert "put_bucket_domain" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(rules=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules is None
    assert "put_bucket_domain" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(rules=NORMALIZED["DomainRule"])
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_domain" not in [c for c, unused in fake.calls]


def test_rule_drift_triggers_update(monkeypatch):
    single = [{"Name": "static.example.com", "Type": "REST", "Status": "ENABLED"}]
    fake = FakeCosClient(rules=single)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domains"] == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_domain" in ops


def test_txt_verification_round_trips(monkeypatch):
    fake = FakeCosClient(rules=NORMALIZED["DomainRule"], txt=TXT)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["txt_verification"] == TXT


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_domain(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
