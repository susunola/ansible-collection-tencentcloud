"""Unit tests for the cdn_domain write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cdn_domain import (
    _add,
    _delete,
    _start,
    _stop,
    build_add_request,
    build_describe_request,
    find_domain,
)


class FakeRequest(object):
    pass


class FakeDomainFilter(object):
    def __init__(self):
        self.Name = None
        self.Value = None


class FakeOrigin(object):
    def __init__(self):
        self.Origins = None
        self.OriginType = None
        self.OriginPullProtocol = None
        self.BackupOrigins = None


class FakeModels(object):
    DomainFilter = FakeDomainFilter
    DescribeDomainsRequest = FakeRequest
    AddCdnDomainRequest = FakeRequest
    DeleteCdnDomainRequest = FakeRequest
    StartCdnDomainRequest = FakeRequest
    StopCdnDomainRequest = FakeRequest
    Origin = FakeOrigin


class FakeDomain(object):
    def __init__(self, domain, status="online"):
        self.Domain = domain
        self.Status = status
        self.ServiceType = "web"

    def _serialize(self, allow_none=True):
        return {
            "Domain": self.Domain,
            "Status": self.Status,
            "ServiceType": self.ServiceType,
        }


class FakeResponse(object):
    def __init__(self, domains):
        self.Domains = domains


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeDomains(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def AddCdnDomain(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteCdnDomain(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def StartCdnDomain(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def StopCdnDomain(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_domain():
    request = build_describe_request(FakeModels, "cdn.example.com")
    assert request.Filters[0].Name == "domain"
    assert request.Filters[0].Value == ["cdn.example.com"]
    assert request.Limit == 100


def test_find_domain_returns_match():
    client = FakeClient(FakeResponse([FakeDomain("cdn.example.com")]))
    module = FakeModule()
    domain = find_domain(module, client, FakeModels, "cdn.example.com")
    assert domain["Domain"] == "cdn.example.com"
    assert len(client.calls) == 1


def test_find_domain_ignores_other_domains():
    client = FakeClient(FakeResponse([FakeDomain("other.example.com")]))
    module = FakeModule()
    assert find_domain(module, client, FakeModels, "cdn.example.com") is None


def test_find_domain_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_domain(module, client, FakeModels, "cdn.example.com") is None


def test_build_add_request_sends_core_fields():
    request = build_add_request(FakeModels, {
        "domain": "cdn.example.com",
        "service_type": "web",
        "origins": ["origin.example.com"],
        "origin_type": "domain",
        "origin_protocol": "http",
        "backup_origins": None,
        "project_id": None,
        "area": None,
    })
    assert request.Domain == "cdn.example.com"
    assert request.ServiceType == "web"
    assert request.Origin.Origins == ["origin.example.com"]
    assert request.Origin.OriginType == "domain"
    assert request.Origin.OriginPullProtocol == "http"


def test_build_add_request_sends_optional_fields():
    request = build_add_request(FakeModels, {
        "domain": "cdn.example.com",
        "service_type": "media",
        "origins": ["1.2.3.4"],
        "origin_type": "ip",
        "origin_protocol": "https",
        "backup_origins": ["5.6.7.8"],
        "project_id": 100,
        "area": "global",
    })
    assert request.Origin.OriginPullProtocol == "https"
    assert request.Origin.BackupOrigins == ["5.6.7.8"]
    assert request.ProjectId == 100
    assert request.Area == "global"


def test_add_sends_request():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _add(module, client, FakeModels, {
        "domain": "cdn.example.com",
        "service_type": "web",
        "origins": ["origin.example.com"],
        "origin_type": "domain",
        "origin_protocol": None,
        "backup_origins": None,
        "project_id": None,
        "area": None,
    })
    assert len(client.calls) == 1
    assert client.calls[0].Domain == "cdn.example.com"


def test_delete_sends_domain():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "cdn.example.com")
    assert client.calls[-1].Domain == "cdn.example.com"


def test_start_sends_domain():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _start(module, client, FakeModels, "cdn.example.com")
    assert client.calls[-1].Domain == "cdn.example.com"


def test_stop_sends_domain():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _stop(module, client, FakeModels, "cdn.example.com")
    assert client.calls[-1].Domain == "cdn.example.com"
