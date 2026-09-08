"""Unit tests for the tse_gateway_certificate write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE gateway
client whose write operations mutate the certificate store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing certificate (idempotent no-op), reference-count guard
  (force_delete), check-mode dry run and the real delete path
* creation validation (missing fields, ssl vs native material), SSL create
  happy path and check-mode dry run
* no-drift idempotency, immutable source/type/usage drift, material-change
  without rotation, SSL rotation and metadata-only updates
* multiple-match guard and the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_certificate as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SSL_CERT = {
    "Id": "cert-gw-1",
    "Name": "public-api",
    "CertSource": "ssl",
    "CertType": "SVR",
    "CertUsage": "SERVER",
    "CertId": "jDZJ5jSa",
    "BindDomains": ["api.example.com"],
    "ReferCount": 0,
}

NATIVE_CERT = {
    "Id": "cert-gw-2",
    "Name": "native-tls",
    "CertSource": "native",
    "CertType": "SVR",
    "CertUsage": "SERVER",
    "Key": "private-key-material",
    "Crt": "cert-chain-material",
    "BindDomains": ["legacy.example.com"],
    "ReferCount": 0,
}


def _cert(**overrides):
    item = copy.deepcopy(SSL_CERT)
    item.update(overrides)
    return item


class FakeTseGatewayClient(object):
    """In-memory TSE cloud-native gateway certificate client."""

    def __init__(self, certificates=None):
        self.certificates = [copy.deepcopy(t) for t in (certificates or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, certificate_id):
        for item in self.certificates:
            if item.get("Id") == certificate_id:
                return item
        return None

    def _by_name(self, name):
        for item in self.certificates:
            if item.get("Name") == name:
                return item
        return None

    def DescribeCloudNativeAPIGatewayCertificates(self, request):
        self._record("DescribeCloudNativeAPIGatewayCertificates", request)
        values = []
        for item in self.certificates:
            value = dict(item)
            values.append(FakeResource(value))
        return SimpleNamespace(Result=SimpleNamespace(CertificatesList=values, Total=len(values)))

    def DescribeCloudNativeAPIGatewayCertificateDetails(self, request):
        self._record("DescribeCloudNativeAPIGatewayCertificateDetails", request)
        cert = self._by_id(getattr(request, "Id", None))
        return SimpleNamespace(Result=SimpleNamespace(Cert=FakeResource(cert) if cert else None))

    def CreateCloudNativeAPIGatewayCertificate(self, request):
        self._record("CreateCloudNativeAPIGatewayCertificate", request)
        payload = request.__dict__
        item = {
            "Id": "cert-new-%d" % (len(self.certificates) + 1),
            "Name": payload.get("Name"),
            "CertSource": "ssl" if payload.get("CertId") else "native",
            "CertType": payload.get("CertType"),
            "CertUsage": payload.get("CertUsage"),
            "BindDomains": payload.get("BindDomains") or [],
            "ReferCount": 0,
        }
        if payload.get("CertId"):
            item["CertId"] = payload["CertId"]
        if payload.get("Crt"):
            item["Crt"] = payload["Crt"]
        if payload.get("Key"):
            item["Key"] = payload["Key"]
        self.certificates.append(item)
        return SimpleNamespace(Result=SimpleNamespace(Id=item["Id"]), RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayCertificate(self, request):
        self._record("ModifyCloudNativeAPIGatewayCertificate", request)
        payload = request.__dict__
        cert = self._by_id(payload.get("Id"))
        if cert is not None:
            for key, value in payload.items():
                if key not in ("GatewayId", "Id"):
                    cert[key] = value
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def UpdateCloudNativeAPIGatewayCertificateInfo(self, request):
        self._record("UpdateCloudNativeAPIGatewayCertificateInfo", request)
        cert = self._by_id(getattr(request, "Id", None))
        if cert is not None:
            if getattr(request, "Name", None) is not None:
                cert["Name"] = request.Name
            if getattr(request, "BindDomains", None) is not None:
                cert["BindDomains"] = request.BindDomains
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayCertificate(self, request):
        self._record("DeleteCloudNativeAPIGatewayCertificate", request)
        certificate_id = getattr(request, "Id", None)
        self.certificates = [item for item in self.certificates if item.get("Id") != certificate_id]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ssl_args(**overrides):
    params = {
        "gateway_id": "gateway-abc",
        "name": "public-api",
        "cert_source": "ssl",
        "ssl_certificate_id": "jDZJ5jSa",
        "bind_domains": ["api.example.com"],
        "cert_type": "SVR",
        "cert_usage": "SERVER",
    }
    params.update(overrides)
    return module_args(**params)


def _native_args(**overrides):
    params = {
        "gateway_id": "gateway-abc",
        "name": "native-tls",
        "cert_source": "native",
        "private_key": "new-private-key",
        "certificate": "new-cert-chain",
        "bind_domains": ["legacy.example.com"],
        "cert_type": "SVR",
        "cert_usage": "SERVER",
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_certificate_is_idempotent(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-abc", certificate_id="cert-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["certificate_info"] is None


def test_absent_referenced_requires_force_delete(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert(ReferCount=2)])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-abc", certificate_id="cert-gw-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "force_delete=true" in exc.value.args[0]["msg"]


def test_absent_referenced_force_delete_applies(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert(ReferCount=2)])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-abc", certificate_id="cert-gw-1", force_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.certificates == []
    assert "DeleteCloudNativeAPIGatewayCertificate" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", gateway_id="gateway-abc", certificate_id="cert-gw-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.certificates) == 1
    assert "DeleteCloudNativeAPIGatewayCertificate" not in [c for c, unused in fake.calls]


def test_absent_deletes_certificate(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-abc", certificate_id="cert-gw-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.certificates == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_fields(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-abc", name="public-api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Required for certificate creation" in exc.value.args[0]["msg"]


def test_create_ssl_requires_ssl_certificate_id(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    _ssl_args(ssl_certificate_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ssl_certificate_id is required when cert_source=ssl" in exc.value.args[0]["msg"]


def test_create_native_requires_material(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    _native_args(private_key=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "private_key and certificate are required when cert_source=native" in exc.value.args[0]["msg"]


def test_create_ssl_certificate(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    _ssl_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate_info"]["Name"] == "public-api"
    assert result["certificate_info"]["CertId"] == "jDZJ5jSa"
    assert len(fake.certificates) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateCloudNativeAPIGatewayCertificate" in ops
    assert ops[-1] == "DescribeCloudNativeAPIGatewayCertificateDetails"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[])
    _make_module(monkeypatch, fake)
    _ssl_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate_info"]["Name"] == "public-api"
    assert fake.certificates == []
    assert "CreateCloudNativeAPIGatewayCertificate" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-certificate flows
# ---------------------------------------------------------------------------


def test_existing_certificate_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    _ssl_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["certificate_info"]["Id"] == "cert-gw-1"
    assert "UpdateCloudNativeAPIGatewayCertificateInfo" not in [c for c, unused in fake.calls]


def test_immutable_cert_fields_fail(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    _ssl_args(cert_type="CA")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be changed in place" in exc.value.args[0]["msg"]


def test_material_change_requires_rotate(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    _ssl_args(ssl_certificate_id="aNewSslId")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "set rotate_certificate=true" in exc.value.args[0]["msg"]


def test_rotate_ssl_certificate(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    _ssl_args(ssl_certificate_id="aNewSslId", rotate_certificate=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate_info"]["CertId"] == "aNewSslId"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGatewayCertificate" in ops
    assert "UpdateCloudNativeAPIGatewayCertificateInfo" not in ops


def test_rotate_native_requires_material(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert(Name="native-tls", CertSource="native", CertId=None, Key="old-key", Crt="old-crt")])
    _make_module(monkeypatch, fake)
    _native_args(rotate_certificate=True, private_key=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "private_key and certificate are required for native certificate rotation" in exc.value.args[0]["msg"]


def test_rotate_native_certificate(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert(Name="native-tls", CertSource="native", CertId=None, Key="old-key", Crt="old-crt")])
    _make_module(monkeypatch, fake)
    _native_args(rotate_certificate=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate_info"]["Crt"] == "new-cert-chain"
    assert "Key" not in result["certificate_info"]
    assert "ModifyCloudNativeAPIGatewayCertificate" in [c for c, unused in fake.calls]


def test_metadata_update_uses_update_info(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert()])
    _make_module(monkeypatch, fake)
    _ssl_args(bind_domains=["api.example.com", "www.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["certificate_info"]["BindDomains"] == ["api.example.com", "www.example.com"]
    ops = [c for c, unused in fake.calls]
    assert "UpdateCloudNativeAPIGatewayCertificateInfo" in ops
    assert "ModifyCloudNativeAPIGatewayCertificate" not in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseGatewayClient(certificates=[_cert(), _cert(Id="cert-gw-dup")])
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-abc", name="public-api", cert_source="ssl", ssl_certificate_id="jDZJ5jSa",
                cert_type="SVR", cert_usage="SERVER")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway certificates matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayCertificates(self, request):
            raise Boom("gateway unreachable")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _ssl_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "gateway unreachable" in payload["error"]
