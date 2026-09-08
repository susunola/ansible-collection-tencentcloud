"""Unit tests for the ssl_certificate write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SSL client
whose write operations mutate the certificate store, so post-write
``find_certificate`` refetches return the mutated state.

Scenario matrix:

* the certificate_id-or-alias identity guard
* absent on a missing certificate (idempotent no-op)
* absent with a matching certificate (check-mode dry run and real delete)
* upload when missing (cert_content/private_key required, check mode, deploy)
* no-op when nothing drifts
* alias rename and deploy-on-existing updates
* update check-mode dry run
* the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssl_certificate as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CERT = {
    "CertificateId": "crt-9f2b7a11",
    "Alias": "api-tls",
    "CertificateType": "SVR",
    "Status": 1,
    "Domain": "api.example.com",
}


def _cert(**overrides):
    item = copy.deepcopy(CERT)
    item.update(overrides)
    return item


def _alias_base(**overrides):
    params = {"alias": "api-tls"}
    params.update(overrides)
    return module_args(**params)


def _id_base(**overrides):
    params = {"certificate_id": "crt-9f2b7a11"}
    params.update(overrides)
    return module_args(**params)


def _upload_args(**overrides):
    params = {
        "alias": "api-tls",
        "cert_content": "-----BEGIN CERTIFICATE-----\nMIIB...\n-----END CERTIFICATE-----",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----",
    }
    params.update(overrides)
    return module_args(**params)


class FakeSslClient(object):
    """In-memory SSL client mutating a certificate store."""

    def __init__(self, certs=None):
        self.certs = [copy.deepcopy(t) for t in (certs or [])]
        self.calls = []
        self._next = 1

    def _record(self, name, request):
        self.calls.append((name, request))

    def DescribeCertificates(self, request):
        self._record("DescribeCertificates", request)
        items = [dict(t) for t in self.certs]
        ids = list(getattr(request, "CertIds", None) or [])
        if ids:
            items = [t for t in items if t.get("CertificateId") in ids]
        search = getattr(request, "SearchKey", None)
        if search:
            items = [
                t for t in items
                if search in t.get("Alias", "") or search in t.get("CertificateId", "")
            ]
        return SimpleNamespace(Certificates=[FakeResource(t) for t in items])

    def UploadCertificate(self, request):
        self._record("UploadCertificate", request)
        item = {
            "CertificateId": "crt-new-%04d" % self._next,
            "Alias": getattr(request, "Alias", None),
            "CertificateType": getattr(request, "CertificateType", "SVR"),
            "ProjectId": getattr(request, "ProjectId", None),
            "Status": 1,
            "Domain": None,
        }
        self._next += 1
        self.certs.append(item)
        return SimpleNamespace(CertificateId=item["CertificateId"], RequestId="req-fake")

    def ModifyCertificateAlias(self, request):
        self._record("ModifyCertificateAlias", request)
        for item in self.certs:
            if item.get("CertificateId") == request.CertificateId:
                item["Alias"] = request.Alias
        return SimpleNamespace(RequestId="req-fake")

    def DeployCertificateInstance(self, request):
        self._record("DeployCertificateInstance", request)
        return SimpleNamespace(DeployRecordId="rec-12345", RequestId="req-fake")

    def DeleteCertificate(self, request):
        self._record("DeleteCertificate", request)
        self.certs = [
            t for t in self.certs if t.get("CertificateId") != request.CertificateId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_ssl", lambda: (models or FakeModels(), SimpleNamespace(SslClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identity guard
# ---------------------------------------------------------------------------


def test_id_or_alias_required(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "certificate_id or alias is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_certificate_is_idempotent(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _alias_base(state="absent", alias="ghost-cert")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Certificate already absent"
    assert [c for c, unused in fake.calls] == ["DescribeCertificates"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _alias_base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete certificate"
    assert "DeleteCertificate" not in [c for c, unused in fake.calls]


def test_absent_deletes_certificate(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _alias_base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate"] is None
    assert fake.certs == []
    assert "DeleteCertificate" in [c for c, unused in fake.calls]


def test_absent_by_id(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _id_base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.certs == []


# ---------------------------------------------------------------------------
# upload (creation) flows
# ---------------------------------------------------------------------------


def test_upload_requires_cert_content_and_private_key(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _alias_base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cert_content and private_key are required" in exc.value.args[0]["msg"]


def test_upload_check_mode_is_dry_run(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _upload_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would upload certificate"
    assert fake.certs == []
    assert "UploadCertificate" not in [c for c, unused in fake.calls]


def test_upload_certificate(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _upload_args(state="present", project_id=100)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Certificate uploaded"
    assert result["certificate"]["Alias"] == "api-tls"
    assert result["certificate"]["CertificateType"] == "SVR"
    assert result["deploy_record_id"] is None
    assert len(fake.certs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCertificates"
    assert "UploadCertificate" in ops


def test_upload_with_deploy(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _upload_args(state="present", deploy_instances=["lb-aaaaaaaa"], resource_type="clb")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate"]["DeployedTo"] == ["lb-aaaaaaaa"]
    assert result["deploy_record_id"] == "rec-12345"
    ops = [c for c, unused in fake.calls]
    assert "UploadCertificate" in ops
    assert "DeployCertificateInstance" in ops


def test_upload_creates_tag_objects(monkeypatch):
    fake = FakeSslClient()
    _make_module(monkeypatch, fake)
    _upload_args(state="present", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is True
    request = [r for name, r in fake.calls if name == "UploadCertificate"][0]
    assert request.Tags[0].TagKey == "env"
    assert request.Tags[0].TagValue == "prod"


# ---------------------------------------------------------------------------
# existing-certificate flows
# ---------------------------------------------------------------------------


def test_certificate_no_drift_is_idempotent(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _alias_base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["certificate"]["CertificateId"] == "crt-9f2b7a11"
    assert "ModifyCertificateAlias" not in [c for c, unused in fake.calls]


def test_rename_alias_by_id(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _id_base(state="present", alias="api-tls-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate"]["Alias"] == "api-tls-v2"
    assert "ModifyCertificateAlias" in [c for c, unused in fake.calls]
    assert "updated" in result["msg"]


def test_deploy_to_existing_certificate(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _alias_base(state="present", deploy_instances=["lb-aaaaaaaa"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate"]["CertificateId"] == "crt-9f2b7a11"
    assert result["deploy_record_id"] == "rec-12345"
    assert "DeployCertificateInstance" in [c for c, unused in fake.calls]


def test_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeSslClient(certs=[_cert()])
    _make_module(monkeypatch, fake)
    _id_base(_ansible_check_mode=True, state="present", alias="api-tls-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update certificate"
    assert "ModifyCertificateAlias" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCertificates(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _alias_base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
