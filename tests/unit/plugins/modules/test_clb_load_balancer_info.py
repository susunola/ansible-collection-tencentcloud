from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import clb_load_balancer_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeLoadBalancersRequest = FakeRequest


def test_build_request_maps_ids_and_int_pagination():
    request = clb_load_balancer_info.build_request(FakeModels, ["lb-123"], {}, 20, 100)
    assert request.LoadBalancerIds == ["lb-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_sorts_filters():
    request = clb_load_balancer_info.build_request(
        FakeModels, [], {"load-balancer-name": ["web"], "zone": ["ap-guangzhou-1"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("load-balancer-name", ["web"]), ("zone", ["ap-guangzhou-1"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = clb_load_balancer_info.build_request(FakeModels, [], {"zone": "ap-guangzhou-1"}, 0, 100)
    assert request.Filters[0].Values == ["ap-guangzhou-1"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.LoadBalancerSet = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeLoadBalancers(self, request):
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
    service = types.ModuleType("tencentcloud.clb.v20180317")
    service.models = FakeModels
    service.clb_client = types.SimpleNamespace(ClbClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.clb", types.ModuleType("tencentcloud.clb"))
    monkeypatch.setitem(sys.modules, "tencentcloud.clb.v20180317", service)
    fake = FakeModule(params)
    monkeypatch.setattr(clb_load_balancer_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(clb_load_balancer_info, "create_credential", lambda module: object())
    monkeypatch.setattr(clb_load_balancer_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        clb_load_balancer_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                load_balancer_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["load_balancers"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_passes_ids_and_filters(monkeypatch):
    client = FakeClient([FakeResponse([FakeItem("a")], 1)])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                load_balancer_ids=["lb-1"], filters={"zone": ["ap-guangzhou-1"]}, page_size=100)
    request = client.requests[0]
    assert request.LoadBalancerIds == ["lb-1"]
    assert request.Filters[0].Name == "zone"
    assert fake.exit_payload["total_count"] == 1
