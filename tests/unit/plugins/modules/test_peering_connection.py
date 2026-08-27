"""Unit tests for the peering_connection write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.peering_connection import (
    _accept,
    _create,
    _delete,
    _update,
    build_describe_request,
    find_connection,
)


class FakeFilter(object):
    """Mimics the Tencent SDK Filter model: zero-arg constructor."""

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeVpcPeeringConnectionsRequest = FakeRequest
    CreateVpcPeeringConnectionRequest = FakeRequest
    AcceptVpcPeeringConnectionRequest = FakeRequest
    ModifyVpcPeeringConnectionRequest = FakeRequest
    DeleteVpcPeeringConnectionRequest = FakeRequest


class FakeConnection(object):
    def __init__(self, pcx_id, name, state="ACTIVE"):
        self.PeeringConnectionId = pcx_id
        self.PeeringConnectionName = name
        self.State = state
        self.Bandwidth = 100
        self.ChargeType = "POSTPAID_BY_DAY"

    def _serialize(self, allow_none=True):
        return {
            "PeeringConnectionId": self.PeeringConnectionId,
            "PeeringConnectionName": self.PeeringConnectionName,
            "State": self.State,
            "Bandwidth": self.Bandwidth,
            "ChargeType": self.ChargeType,
        }


class FakeResponse(object):
    def __init__(self, connections):
        self.PeerConnectionSet = connections


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeVpcPeeringConnections(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateVpcPeeringConnection(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def AcceptVpcPeeringConnection(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyVpcPeeringConnection(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteVpcPeeringConnection(self, request):
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
    request = build_describe_request(FakeModels, "pcx-123", None, None)
    assert request.PeeringConnectionIds == ["pcx-123"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name_and_vpc():
    request = build_describe_request(FakeModels, None, "app-to-db", "vpc-1")
    names = [f.Name for f in request.Filters]
    assert "peering-connection-name" in names
    assert "vpc-id" in names
    assert not hasattr(request, "PeeringConnectionIds") or request.PeeringConnectionIds is None


def test_build_describe_request_no_filters():
    request = build_describe_request(FakeModels, None, None, None)
    assert not hasattr(request, "Filters") or request.Filters is None
    assert not hasattr(request, "PeeringConnectionIds") or request.PeeringConnectionIds is None


def test_find_connection_returns_first_match():
    client = FakeClient(FakeResponse([FakeConnection("pcx-1", "app-to-db")]))
    module = FakeModule()
    connection = find_connection(module, client, FakeModels, None, "app-to-db", "vpc-1")
    assert connection["PeeringConnectionId"] == "pcx-1"
    assert len(client.calls) == 1


def test_find_connection_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_connection(module, client, FakeModels, "pcx-9", None, None) is None


def test_find_connection_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_connection(module, client, FakeModels, "pcx-9", None, None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "source_vpc_id": "vpc-1",
        "destination_vpc_id": "vpc-2",
        "name": "app-to-db",
        "destination_region": "ap-shanghai",
        "destination_uin": "12345",
        "bandwidth": 500,
        "charge_type": "BANDWIDTH_POSTPAID_BY_HOUR",
        "qos_level": "PT",
    })
    request = client.calls[-1]
    assert request.SourceVpcId == "vpc-1"
    assert request.DestinationVpcId == "vpc-2"
    assert request.PeeringConnectionName == "app-to-db"
    assert request.DestinationRegion == "ap-shanghai"
    assert request.DestinationUin == "12345"
    assert request.Bandwidth == 500
    assert request.ChargeType == "BANDWIDTH_POSTPAID_BY_HOUR"
    assert request.QosLevel == "PT"


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "source_vpc_id": "vpc-1",
        "destination_vpc_id": "vpc-2",
        "name": "app-to-db",
        "destination_region": None,
        "destination_uin": None,
        "bandwidth": None,
        "charge_type": None,
        "qos_level": None,
    })
    request = client.calls[-1]
    assert request.SourceVpcId == "vpc-1"
    assert not hasattr(request, "Bandwidth")
    assert not hasattr(request, "DestinationRegion")
    assert not hasattr(request, "ChargeType")
    assert not hasattr(request, "QosLevel")


def test_accept_sends_connection_id():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _accept(module, client, FakeModels, "pcx-1")
    assert client.calls[-1].PeeringConnectionId == "pcx-1"


def test_update_sets_all_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "pcx-1", "renamed", 200, "POSTPAID_BY_DAY")
    request = client.calls[-1]
    assert request.PeeringConnectionId == "pcx-1"
    assert request.PeeringConnectionName == "renamed"
    assert request.Bandwidth == 200
    assert request.ChargeType == "POSTPAID_BY_DAY"


def test_update_skips_none_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "pcx-1", None, None, None)
    request = client.calls[-1]
    assert request.PeeringConnectionId == "pcx-1"
    assert not hasattr(request, "PeeringConnectionName")
    assert not hasattr(request, "Bandwidth")
    assert not hasattr(request, "ChargeType")


def test_delete_sends_connection_id():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "pcx-1")
    assert client.calls[-1].PeeringConnectionId == "pcx-1"
