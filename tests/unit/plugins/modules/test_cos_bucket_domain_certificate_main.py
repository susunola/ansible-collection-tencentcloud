"""Unit tests for the cos_bucket_domain_certificate write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_domain_certificate`` operations mutate a
certificate store keyed by domain name. The module reaches ``qcloud_cos``
via ``module_utils/cos.py``, so ``cos.require_cos_sdk`` and
``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing certificate (idempotent no-op) and on an existing one
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the certificate already matches; certificate-id drift triggers put
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_domain_certificate as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

DOMAIN = "static.example.com"
CERT_ID = "8u9example"
NORMALIZED = {
    "Status": "Enabled",
    "CertType": "CustomCert",
    "CertificateInfo": {"CertID": CERT_ID},
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
    """In-memory COS client mutating a per-domain certificate store."""

    def __init__(self, certs=None):
        # certs: {domain_name: raw get response}
        self.certs = copy.deepcopy(certs) if certs is not None else {}
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_domain_certificate(self, Bucket, DomainName, **kwargs):
        self._record("get_bucket_domain_certificate", DomainName)
        if DomainName not in self.certs:
            raise FakeCosError("NoSuchKey")
        return copy.deepcopy(self.certs[DomainName])

    def put_bucket_domain_certificate(self, Bucket, DomainCertificateConfiguration, **kwargs):
        self._record("put_bucket_domain_certificate", DomainCertificateConfiguration)
        cert = DomainCertificateConfiguration.get("CertificateInfo", {})
        custom = cert.get("CustomCert") or {}
        self.certs[DOMAIN] = {
            "DomainCertificate": {
                "Status": "Enabled",
                "CertType": "CustomCert",
                "CertificateInfo": {"CertID": custom.get("CertID")},
            }
        }

    def delete_bucket_domain_certificate(self, Bucket, DomainName, **kwargs):
        self._record("delete_bucket_domain_certificate", DomainName)
        self.certs.pop(DomainName, None)


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000", "domain_name": DOMAIN}
    params.update(overrides)
    return module_args(**params)


def _present_args(**overrides):
    params = {"state": "present", "certificate_id": CERT_ID}
    params.update(overrides)
    return params


def _seed_cert(client, cert_id=CERT_ID):
    client.certs[DOMAIN] = {
        "DomainCertificate": {
            "Status": "Enabled",
            "CertType": "CustomCert",
            "CertificateInfo": {"CertID": cert_id},
        }
    }


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(certs={})
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domain_certificate"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_domain_certificate"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(certs={})
    _seed_cert(fake)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert DOMAIN in fake.certs
    assert "delete_bucket_domain_certificate" not in [c for c, unused in fake.calls]


def test_absent_deletes_certificate(monkeypatch):
    fake = FakeCosClient(certs={})
    _seed_cert(fake)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert DOMAIN not in fake.certs
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_domain_certificate" in ops


def test_create_certificate(monkeypatch):
    fake = FakeCosClient(certs={})
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain_certificate"] == NORMALIZED
    assert fake.certs[DOMAIN]["DomainCertificate"]["CertificateInfo"]["CertID"] == CERT_ID
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_domain_certificate"
    assert "put_bucket_domain_certificate" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(certs={})
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain_certificate"] == NORMALIZED
    assert DOMAIN not in fake.certs
    assert "put_bucket_domain_certificate" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(certs={})
    _seed_cert(fake)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_domain_certificate" not in [c for c, unused in fake.calls]


def test_certificate_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(certs={})
    _seed_cert(fake, cert_id="old-cert-123")
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain_certificate"]["CertificateInfo"]["CertID"] == CERT_ID
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_domain_certificate" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_domain_certificate(self, Bucket, DomainName, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
