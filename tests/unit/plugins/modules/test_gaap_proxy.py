"""Unit tests for the gaap_proxy write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_proxy import (
    _close,
    _create,
    _destroy,
    _open,
    _rename,
    build_create_request,
    build_describe_request,
    find_proxy,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeProxiesRequest = FakeRequest
    CreateProxyRequest = FakeRequest
    ModifyProxiesAttributeRequest = FakeRequest
    OpenProxiesRequest = FakeRequest
    CloseProxiesRequest = FakeRequest
    DestroyProxiesRequest = FakeRequest


class FakeProxy(object):
    def __init__(self, proxy_id, name, status="running"):
        self.ProxyId = proxy_id
        self.ProxyName = name
        self.Status = status

    def _serialize(self, allow_none=True):
        return {
            "ProxyId": self.ProxyId,
            "ProxyName": self.ProxyName,
            "Status": self.Status,
        }


class FakeResponse(object):
    def __init__(self, proxies):
        self.ProxySet = proxies


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeProxies(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateProxy(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyProxiesAttribute(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def OpenProxies(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CloseProxies(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DestroyProxies(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "proxy-123", None)
    assert request.ProxyIds == ["proxy-123"]
    assert request.Limit == 100


def test_build_describe_request_by_name_has_no_filter():
    # The API has no proxy-name filter; the name is matched client-side.
    request = build_describe_request(FakeModels, None, "prod-gaap")
    assert not hasattr(request, "ProxyIds") or request.ProxyIds is None
    assert not hasattr(request, "Filters") or request.Filters is None


def test_find_proxy_by_id_returns_first():
    client = FakeClient(FakeResponse([FakeProxy("proxy-1", "prod-gaap")]))
    module = FakeModule()
    proxy = find_proxy(module, client, FakeModels, "proxy-1", None)
    assert proxy["ProxyId"] == "proxy-1"
    assert len(client.calls) == 1


def test_find_proxy_by_name_matches_name():
    client = FakeClient(FakeResponse([
        FakeProxy("proxy-1", "other"),
        FakeProxy("proxy-2", "prod-gaap"),
    ]))
    module = FakeModule()
    proxy = find_proxy(module, client, FakeModels, None, "prod-gaap")
    assert proxy["ProxyId"] == "proxy-2"


def test_find_proxy_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_proxy(module, client, FakeModels, "proxy-9", None) is None


def test_build_create_request_sends_core_fields():
    request = build_create_request(FakeModels, {
        "name": "prod-gaap",
        "access_region": "ap-guangzhou",
        "real_server_region": "ap-hongkong",
        "bandwidth": 20,
        "concurrent": 2,
        "project_id": None,
        "billing_type": None,
        "network_type": None,
        "ip_address_version": None,
        "group_id": None,
    })
    assert request.ProxyName == "prod-gaap"
    assert request.AccessRegion == "ap-guangzhou"
    assert request.RealServerRegion == "ap-hongkong"
    assert request.Bandwidth == 20
    assert request.Concurrent == 2


def test_build_create_request_sends_optional_fields():
    request = build_create_request(FakeModels, {
        "name": "prod-gaap",
        "access_region": "ap-guangzhou",
        "real_server_region": "ap-hongkong",
        "bandwidth": 20,
        "concurrent": 2,
        "project_id": 100,
        "billing_type": 1,
        "network_type": "cn2",
        "ip_address_version": "IPv6",
        "group_id": "grp-xxxxxxxx",
    })
    assert request.ProjectId == 100
    assert request.BillingType == 1
    assert request.NetworkType == "cn2"
    assert request.IPAddressVersion == "IPv6"
    assert request.GroupId == "grp-xxxxxxxx"


def test_create_sends_request():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "name": "prod-gaap",
        "access_region": "ap-guangzhou",
        "real_server_region": "ap-hongkong",
        "bandwidth": 20,
        "concurrent": 2,
        "project_id": None,
        "billing_type": None,
        "network_type": None,
        "ip_address_version": None,
        "group_id": None,
    })
    assert len(client.calls) == 1
    assert client.calls[0].ProxyName == "prod-gaap"


def test_rename_sends_proxy_ids_and_name():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _rename(module, client, FakeModels, "proxy-1", "prod-gaap-v2")
    request = client.calls[-1]
    assert request.ProxyIds == ["proxy-1"]
    assert request.ProxyName == "prod-gaap-v2"


def test_open_sends_proxy_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _open(module, client, FakeModels, "proxy-1")
    assert client.calls[-1].ProxyIds == ["proxy-1"]


def test_close_sends_proxy_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _close(module, client, FakeModels, "proxy-1")
    assert client.calls[-1].ProxyIds == ["proxy-1"]


def test_destroy_sends_proxy_ids_and_force():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _destroy(module, client, FakeModels, "proxy-1")
    request = client.calls[-1]
    assert request.ProxyIds == ["proxy-1"]
    assert request.Force == 1
