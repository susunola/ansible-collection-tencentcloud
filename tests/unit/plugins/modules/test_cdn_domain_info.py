from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cdn_domain_info


class FakeDomainFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    DomainFilter = FakeDomainFilter
    DescribeDomainsRequest = FakeRequest


def test_build_request_uses_int_pagination():
    request = cdn_domain_info.build_request(FakeModels, {}, 20, 100)
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters_into_domain_filter_value():
    request = cdn_domain_info.build_request(
        FakeModels, {"domain": ["www.example.com"], "serviceType": ["web"]}, 0, 100)
    assert [(item.Name, item.Value) for item in request.Filters] == [
        ("domain", ["www.example.com"]), ("serviceType", ["web"]),
    ]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_number):
        self.Domains = items
        self.TotalNumber = total_number


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeDomains(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(Exception):
    pass


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise AssertionError("fail_json called: %r" % (kwargs,))


def _run(monkeypatch, client, **params):
    service = types.ModuleType("tencentcloud.cdn.v20180606")
    service.models = FakeModels
    service.cdn_client = types.SimpleNamespace(CdnClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdn", types.ModuleType("tencentcloud.cdn"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdn.v20180606", service)
    fake = FakeModule(params)
    monkeypatch.setattr(cdn_domain_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cdn_domain_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cdn_domain_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cdn_domain_info.run_module()
    return fake


def test_run_module_paginates_until_total_number(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["domains"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
