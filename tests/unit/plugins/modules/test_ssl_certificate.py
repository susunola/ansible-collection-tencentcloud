"""Unit tests for the ssl_certificate write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.ssl_certificate import (
    build_describe_request,
    find_certificate,
    _upload,
    _rename,
    _deploy,
    _delete,
)


class FakeRequest(object):
    pass


class FakeTag(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeModels(object):
    DescribeCertificatesRequest = FakeRequest
    UploadCertificateRequest = FakeRequest
    ModifyCertificateAliasRequest = FakeRequest
    DeleteCertificateRequest = FakeRequest
    DeployCertificateInstanceRequest = FakeRequest
    Tags = FakeTag


class FakeCert(object):
    def __init__(self, cert_id, alias, status=1):
        self.CertificateId = cert_id
        self.Alias = alias
        self.CertificateType = "SVR"
        self.Status = status
        self.Domain = "api.example.com"

    def _serialize(self, allow_none=True):
        return {
            "CertificateId": self.CertificateId,
            "Alias": self.Alias,
            "CertificateType": self.CertificateType,
            "Status": self.Status,
            "Domain": self.Domain,
        }


class FakeListResponse(object):
    def __init__(self, certs):
        self.Certificates = certs


class FakeUploadResponse(object):
    def __init__(self, cert_id):
        self.CertificateId = cert_id


class FakeDeployResponse(object):
    def __init__(self, record_id):
        self.DeployRecordId = record_id


class FakeClient(object):
    def __init__(self, list_response=None, upload_response=None, deploy_response=None, exc=None):
        self.list_response = list_response
        self.upload_response = upload_response
        self.deploy_response = deploy_response
        self.exc = exc
        self.calls = []

    def DescribeCertificates(self, request):
        self.calls.append(("DescribeCertificates", request))
        if self.exc:
            raise self.exc
        return self.list_response

    def UploadCertificate(self, request):
        self.calls.append(("UploadCertificate", request))
        return self.upload_response

    def ModifyCertificateAlias(self, request):
        self.calls.append(("ModifyCertificateAlias", request))

    def DeleteCertificate(self, request):
        self.calls.append(("DeleteCertificate", request))

    def DeployCertificateInstance(self, request):
        self.calls.append(("DeployCertificateInstance", request))
        return self.deploy_response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


BASE_PARAMS = {
    "certificate_id": None,
    "alias": "api-tls",
    "cert_content": "-----BEGIN CERTIFICATE-----",
    "private_key": "-----BEGIN PRIVATE KEY-----",
    "certificate_type": "SVR",
    "project_id": None,
    "deploy_instances": None,
    "resource_type": "clb",
    "tags": {},
}


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "CERT-1", None)
    assert request.CertIds == ["CERT-1"]
    assert not hasattr(request, "SearchKey") or request.SearchKey is None


def test_build_describe_request_by_alias():
    request = build_describe_request(FakeModels, None, "api-tls")
    assert request.SearchKey == "api-tls"
    assert not hasattr(request, "CertIds") or request.CertIds is None


def test_find_certificate_by_id():
    client = FakeClient(FakeListResponse([FakeCert("CERT-1", "api-tls")]))
    module = FakeModule()
    cert = find_certificate(module, client, FakeModels, "CERT-1", None)
    assert cert["CertificateId"] == "CERT-1"


def test_find_certificate_by_exact_alias():
    client = FakeClient(FakeListResponse([
        FakeCert("CERT-1", "api-tls"),
        FakeCert("CERT-2", "api-tls-staging"),
    ]))
    module = FakeModule()
    cert = find_certificate(module, client, FakeModels, None, "api-tls")
    assert cert["CertificateId"] == "CERT-1"


def test_find_certificate_returns_none_when_absent():
    client = FakeClient(FakeListResponse([]))
    module = FakeModule()
    assert find_certificate(module, client, FakeModels, None, "api-tls") is None


def test_find_certificate_returns_none_when_alias_mismatch():
    client = FakeClient(FakeListResponse([FakeCert("CERT-1", "other")]))
    module = FakeModule()
    assert find_certificate(module, client, FakeModels, None, "api-tls") is None


def test_upload_sends_all_fields():
    client = FakeClient(upload_response=FakeUploadResponse("CERT-9"))
    module = FakeModule()
    cert_id = _upload(module, client, FakeModels, dict(BASE_PARAMS, project_id=5, tags={"env": "prod"}))
    assert cert_id == "CERT-9"
    request = client.calls[-1][1]
    assert request.CertificatePublicKey == "-----BEGIN CERTIFICATE-----"
    assert request.CertificatePrivateKey == "-----BEGIN PRIVATE KEY-----"
    assert request.CertificateType == "SVR"
    assert request.Alias == "api-tls"
    assert request.ProjectId == 5
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("env", "prod")]


def test_upload_omits_optional_fields():
    client = FakeClient(upload_response=FakeUploadResponse("CERT-9"))
    module = FakeModule()
    _upload(module, client, FakeModels, BASE_PARAMS)
    request = client.calls[-1][1]
    assert request.CertificatePublicKey == "-----BEGIN CERTIFICATE-----"
    assert not hasattr(request, "ProjectId")
    assert not hasattr(request, "Tags")


def test_rename_sends_id_and_alias():
    client = FakeClient()
    module = FakeModule()
    _rename(module, client, FakeModels, "CERT-1", "renamed")
    request = client.calls[-1][1]
    assert request.CertificateId == "CERT-1"
    assert request.Alias == "renamed"


def test_deploy_sends_instances_and_resource_type():
    client = FakeClient(deploy_response=FakeDeployResponse(42))
    module = FakeModule()
    record_id = _deploy(module, client, FakeModels, "CERT-1", ["lb-1"], "clb")
    assert record_id == 42
    request = client.calls[-1][1]
    assert request.CertificateId == "CERT-1"
    assert request.InstanceIdList == ["lb-1"]
    assert request.ResourceType == "clb"


def test_delete_sends_certificate_id():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "CERT-1")
    request = client.calls[-1][1]
    assert request.CertificateId == "CERT-1"
