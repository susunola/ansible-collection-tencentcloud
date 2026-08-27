"""Unit tests for the vpn_gateway write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.vpn_gateway import (
    _create,
    _delete,
    _update,
    build_describe_request,
    find_gateway,
)


class FakeFilter(object):
    """Mimics the Tencent SDK Filter model: zero-arg constructor."""

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeVpnGatewaysRequest = FakeRequest
    CreateVpnGatewayRequest = FakeRequest
    ModifyVpnGatewayAttributeRequest = FakeRequest
    DeleteVpnGatewayRequest = FakeRequest


class FakeGateway(object):
    def __init__(self, vpngw_id, name, state="AVAILABLE"):
        self.VpnGatewayId = vpngw_id
        self.VpnGatewayName = name
        self.State = state
        self.MaxConnection = 5
        self.BgpAsn = 64512
        self.InternetMaxBandwidthOut = 10

    def _serialize(self, allow_none=True):
        return {
            "VpnGatewayId": self.VpnGatewayId,
            "VpnGatewayName": self.VpnGatewayName,
            "State": self.State,
            "MaxConnection": self.MaxConnection,
            "BgpAsn": self.BgpAsn,
            "InternetMaxBandwidthOut": self.InternetMaxBandwidthOut,
        }


class FakeResponse(object):
    def __init__(self, gateways):
        self.VpnGatewaySet = gateways


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeVpnGateways(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateVpnGateway(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyVpnGatewayAttribute(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteVpnGateway(self, request):
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
    request = build_describe_request(FakeModels, "vpngw-123", None, None)
    assert request.VpnGatewayIds == ["vpngw-123"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name_and_vpc():
    request = build_describe_request(FakeModels, None, "office-vpn", "vpc-1")
    names = [f.Name for f in request.Filters]
    assert "vpn-gateway-name" in names
    assert "vpc-id" in names
    assert not hasattr(request, "VpnGatewayIds") or request.VpnGatewayIds is None


def test_find_gateway_returns_first_match():
    client = FakeClient(FakeResponse([FakeGateway("vpngw-1", "office-vpn")]))
    module = FakeModule()
    gateway = find_gateway(module, client, FakeModels, None, "office-vpn", "vpc-1")
    assert gateway["VpnGatewayId"] == "vpngw-1"
    assert len(client.calls) == 1


def test_find_gateway_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_gateway(module, client, FakeModels, "vpngw-9", None, None) is None


def test_find_gateway_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_gateway(module, client, FakeModels, "vpngw-9", None, None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "vpc_id": "vpc-1",
        "name": "office-vpn",
        "internet_max_bandwidth_out": 20,
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "type": "IPSEC",
        "max_connection": 10,
        "zone": "ap-guangzhou-3",
        "bgp_asn": 64513,
    })
    request = client.calls[-1]
    assert request.VpcId == "vpc-1"
    assert request.VpnGatewayName == "office-vpn"
    assert request.InternetMaxBandwidthOut == 20
    assert request.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert request.Type == "IPSEC"
    assert request.MaxConnection == 10
    assert request.Zone == "ap-guangzhou-3"
    assert request.BgpAsn == 64513


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "vpc_id": "vpc-1",
        "name": "office-vpn",
        "internet_max_bandwidth_out": None,
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "type": "IPSEC",
        "max_connection": None,
        "zone": None,
        "bgp_asn": None,
    })
    request = client.calls[-1]
    assert request.VpcId == "vpc-1"
    assert not hasattr(request, "InternetMaxBandwidthOut")
    assert not hasattr(request, "MaxConnection")
    assert not hasattr(request, "Zone")
    assert not hasattr(request, "BgpAsn")


def test_update_sets_all_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "vpngw-1", "renamed", 20, 64514)
    request = client.calls[-1]
    assert request.VpnGatewayId == "vpngw-1"
    assert request.VpnGatewayName == "renamed"
    assert request.MaxConnection == 20
    assert request.BgpAsn == 64514


def test_update_skips_none_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "vpngw-1", None, None, None)
    request = client.calls[-1]
    assert request.VpnGatewayId == "vpngw-1"
    assert not hasattr(request, "VpnGatewayName")
    assert not hasattr(request, "MaxConnection")
    assert not hasattr(request, "BgpAsn")


def test_delete_sends_gateway_id():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "vpngw-1")
    assert client.calls[-1].VpnGatewayId == "vpngw-1"
