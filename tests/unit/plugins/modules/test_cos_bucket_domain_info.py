"""Tests for cos_bucket_domain_info, plus the helpers it shares.

The first two tests cover the normalisers the write module and the shared COS
reader expose. The rest drive ``run_module()`` end to end through the shared
harness: the custom-domain rules come back sorted and normalised from the real
``get_domains`` reader, the bucket is addressed as ``<name>-<appid>``, a bucket
with no rules (and a bucket that no longer exists) is an empty result rather
than a failure, and a COS service error maps to the module's failure envelope.

COS is read through ``qcloud_cos``, not the API 3.0 SDK, so the client comes
from patching ``cos.create_cos_client`` -- the same seam the sibling COS tests
use -- and the fake client speaks the ``get_bucket_domain`` response shape.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_certificate
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_domain_info
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_domain import normalize as normalize_domains
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
BUCKET = "public-site-1300000000"
TXT_VERIFICATION = "cos-verify-20260105"


def test_domain_normalize_sorts_rules():
    value = {"DomainRule": [{"Name": "z.example"}, {"Name": "a.example"}]}
    assert [x["Name"] for x in normalize_domains(value)["DomainRule"]] == ["a.example", "z.example"]


def test_certificate_normalize_projects_managed_identity():
    value = {"Status": "Enabled", "CertificateInfo": {"CertType": "CustomCert", "CertID": "cert-1"}}
    assert normalize_certificate(value) == {"Status": "Enabled", "CertType": "CustomCert", "CertificateInfo": {"CertID": "cert-1"}}


#: What ``get_bucket_domain`` returns: the rules live under
#: ``DomainConfiguration`` and the verification value is a response header.
DOMAIN_RESPONSE = {
    "DomainConfiguration": {
        "DomainRule": [
            {"Name": "z.example.com", "Status": "ENABLED"},
            {"Name": "a.example.com", "Status": "ENABLED"},
        ]
    },
    "x-cos-domain-txt-verification": TXT_VERIFICATION,
}

NORMALIZED_DOMAINS = {
    "DomainRule": [
        {"Name": "a.example.com", "Status": "ENABLED"},
        {"Name": "z.example.com", "Status": "ENABLED"},
    ]
}


class FakeCosServiceError(Exception):
    """Stand-in for the ``qcloud_cos`` ``CosServiceError``."""

    def __init__(self, message, code="AccessDenied", status=403, request_id="req-cos"):
        super(FakeCosServiceError, self).__init__(message)
        self._code = code
        self._status = status
        self._request_id = request_id

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status

    def get_request_id(self):
        return self._request_id


class FakeCosClient:
    """COS client answering ``get_bucket_domain`` with one canned result."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.buckets = []

    def get_bucket_domain(self, Bucket=None):
        self.buckets.append(Bucket)
        if self.error is not None:
            raise self.error
        return self.response


def _patch_cos_client(monkeypatch, client):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: client)


def test_run_module_returns_sorted_domains_and_the_txt_value(monkeypatch):
    client = FakeCosClient(DOMAIN_RESPONSE)
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    payload = run(cos_bucket_domain_info.run_module)

    assert payload == {
        "changed": False,
        "domain_configurations": [NORMALIZED_DOMAINS],
        "domains": NORMALIZED_DOMAINS,
        "txt_verification": TXT_VERIFICATION,
    }
    assert client.buckets == [BUCKET]


def test_run_module_returns_empty_keys_when_no_domain_is_configured(monkeypatch):
    client = FakeCosClient({})
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    payload = run(cos_bucket_domain_info.run_module)

    assert payload == {
        "changed": False,
        "domain_configurations": [],
        "domains": None,
        "txt_verification": None,
    }
    assert client.buckets == [BUCKET]


def test_run_module_treats_a_missing_bucket_as_an_empty_result(monkeypatch):
    client = FakeCosClient(error=FakeCosServiceError(
        "bucket not found", code="NoSuchBucket", status=404))
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    payload = run(cos_bucket_domain_info.run_module)

    assert payload["domain_configurations"] == []
    assert payload["domains"] is None
    assert payload["txt_verification"] is None


def test_run_module_fails_with_the_cos_error_envelope(monkeypatch):
    client = FakeCosClient(error=FakeCosServiceError("no permission to read the bucket"))
    _patch_cos_client(monkeypatch, client)
    module_args(name="public-site", appid=APPID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(cos_bucket_domain_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "no permission to read the bucket" in payload["error"]
    assert payload["error_code"] == "AccessDenied"
    assert payload["request_id"] == "req-cos"
    assert client.buckets == [BUCKET]
