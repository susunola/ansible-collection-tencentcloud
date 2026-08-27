from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import vpn_gateway_info


class FakeFilterObject:
    pass


class FakeRequest:
    pass


class FakeModels:
    FilterObject = FakeFilterObject
    DescribeVpnGatewaysRequest = FakeRequest


def test_build_request_maps_ids_and_int_pagination():
    request = vpn_gateway_info.build_request(FakeModels, ["vpngw-123"], {}, 20, 100)
    assert request.VpnGatewayIds == ["vpngw-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_sorts_filters():
    request = vpn_gateway_info.build_request(
        FakeModels, [], {"vpc-id": ["vpc-123"], "vpn-gateway-name": ["gw"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("vpc-id", ["vpc-123"]), ("vpn-gateway-name", ["gw"]),
    ]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.VpnGatewaySet = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeVpnGateways(self, request):
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
    service = types.ModuleType("tencentcloud.vpc.v20170312")
    service.models = FakeModels
    service.vpc_client = types.SimpleNamespace(VpcClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.vpc", types.ModuleType("tencentcloud.vpc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.vpc.v20170312", service)
    fake = FakeModule(params)
    monkeypatch.setattr(vpn_gateway_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(vpn_gateway_info, "create_credential", lambda module: object())
    monkeypatch.setattr(vpn_gateway_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        vpn_gateway_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                vpn_gateway_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["vpn_gateways"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
