"""Unit tests for the nat_gateway write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.nat_gateway import (
    _create,
    _delete,
    _set_deletion_protection,
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
    DescribeNatGatewaysRequest = FakeRequest
    CreateNatGatewayRequest = FakeRequest
    ModifyNatGatewayAttributeRequest = FakeRequest
    DeleteNatGatewayRequest = FakeRequest


class FakeGateway(object):
    def __init__(self, nat_id, name, state="AVAILABLE"):
        self.NatGatewayId = nat_id
        self.NatGatewayName = name
        self.State = state
        self.InternetMaxBandwidthOut = 100
        self.DeletionProtectionEnabled = False

    def _serialize(self, allow_none=True):
        return {
            "NatGatewayId": self.NatGatewayId,
            "NatGatewayName": self.NatGatewayName,
            "State": self.State,
            "InternetMaxBandwidthOut": self.InternetMaxBandwidthOut,
            "DeletionProtectionEnabled": self.DeletionProtectionEnabled,
        }


class FakeResponse(object):
    def __init__(self, gateways):
        self.NatGatewaySet = gateways


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeNatGateways(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateNatGateway(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyNatGatewayAttribute(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteNatGateway(self, request):
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
    request = build_describe_request(FakeModels, "nat-123", None, None)
    assert request.NatGatewayIds == ["nat-123"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name_and_vpc():
    request = build_describe_request(FakeModels, None, "prod-nat", "vpc-1")
    names = [f.Name for f in request.Filters]
    assert "nat-gateway-name" in names
    assert "vpc-id" in names
    assert not hasattr(request, "NatGatewayIds") or request.NatGatewayIds is None


def test_find_gateway_returns_first_match():
    client = FakeClient(FakeResponse([FakeGateway("nat-1", "prod-nat")]))
    module = FakeModule()
    gateway = find_gateway(module, client, FakeModels, None, "prod-nat", "vpc-1")
    assert gateway["NatGatewayId"] == "nat-1"
    assert len(client.calls) == 1


def test_find_gateway_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_gateway(module, client, FakeModels, "nat-9", None, None) is None


def test_find_gateway_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_gateway(module, client, FakeModels, "nat-9", None, None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "vpc_id": "vpc-1",
        "name": "prod-nat",
        "internet_max_bandwidth_out": 200,
        "max_concurrent_connection": 1000000,
        "address_count": 2,
        "public_ip_addresses": ["1.2.3.4"],
        "zone": "ap-guangzhou-3",
    })
    request = client.calls[-1]
    assert request.VpcId == "vpc-1"
    assert request.NatGatewayName == "prod-nat"
    assert request.InternetMaxBandwidthOut == 200
    assert request.MaxConcurrentConnection == 1000000
    assert request.AddressCount == 2
    assert request.PublicIpAddresses == ["1.2.3.4"]
    assert request.Zone == "ap-guangzhou-3"


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "vpc_id": "vpc-1",
        "name": "prod-nat",
        "internet_max_bandwidth_out": None,
        "max_concurrent_connection": None,
        "address_count": None,
        "public_ip_addresses": None,
        "zone": None,
    })
    request = client.calls[-1]
    assert request.VpcId == "vpc-1"
    assert not hasattr(request, "InternetMaxBandwidthOut")
    assert not hasattr(request, "MaxConcurrentConnection")
    assert not hasattr(request, "AddressCount")
    assert not hasattr(request, "PublicIpAddresses")
    assert not hasattr(request, "Zone")


def test_update_sets_name_and_bandwidth():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "nat-1", "renamed", 300)
    request = client.calls[-1]
    assert request.NatGatewayId == "nat-1"
    assert request.NatGatewayName == "renamed"
    assert request.InternetMaxBandwidthOut == 300


def test_update_skips_none_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "nat-1", None, None)
    request = client.calls[-1]
    assert request.NatGatewayId == "nat-1"
    assert not hasattr(request, "NatGatewayName")
    assert not hasattr(request, "InternetMaxBandwidthOut")


def test_set_deletion_protection_on():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _set_deletion_protection(module, client, FakeModels, "nat-1", True)
    request = client.calls[-1]
    assert request.NatGatewayId == "nat-1"
    assert request.DeletionProtectionEnabled is True


def test_set_deletion_protection_off():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _set_deletion_protection(module, client, FakeModels, "nat-1", False)
    assert client.calls[-1].DeletionProtectionEnabled is False


def test_delete_sends_gateway_id():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "nat-1", False)
    request = client.calls[-1]
    assert request.NatGatewayId == "nat-1"
    assert not hasattr(request, "IgnoreOperationRisk")


def test_delete_with_ignore_operation_risk():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "nat-1", True)
    assert client.calls[-1].IgnoreOperationRisk is True
