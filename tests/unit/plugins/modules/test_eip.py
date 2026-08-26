"""Unit tests for the eip write module helpers."""

from ansible_collections.tencentcloud.cloud.plugins.modules.eip import (
    build_describe_request,
    find_address,
    _create,
    _delete,
)


class FakeFilter(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeTag(object):
    def __init__(self):
        self.Key = None
        self.Value = None


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    Tag = FakeTag
    DescribeAddressesRequest = FakeRequest
    AllocateAddressesRequest = FakeRequest
    ReleaseAddressesRequest = FakeRequest
    DisassociateAddressRequest = FakeRequest


class FakeAddress(object):
    def __init__(self, address_id, name, ip, instance_id=None, tags=None):
        self.AddressId = address_id
        self.AddressName = name
        self.AddressIp = ip
        self.InstanceId = instance_id
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {
            "AddressId": self.AddressId,
            "AddressName": self.AddressName,
            "AddressIp": self.AddressIp,
            "InstanceId": self.InstanceId,
            "TagSet": [{"Key": t.Key, "Value": t.Value} for t in self.TagSet],
        }


class FakeDescribeResponse(object):
    def __init__(self, addresses):
        self.AddressSet = addresses
        self.TotalCount = len(addresses or [])


class FakeAllocateResponse(object):
    def __init__(self, address_ids):
        self.AddressSet = address_ids
        self.TaskId = "task-1"


class FakeClient(object):
    def __init__(self, describe_response=None, allocate_response=None, exc=None):
        self.describe_response = describe_response
        self.allocate_response = allocate_response
        self.exc = exc
        self.calls = []

    def DescribeAddresses(self, request):
        self.calls.append(("DescribeAddresses", request))
        if self.exc:
            raise self.exc
        return self.describe_response

    def AllocateAddresses(self, request):
        self.calls.append(("AllocateAddresses", request))
        return self.allocate_response

    def ReleaseAddresses(self, request):
        self.calls.append(("ReleaseAddresses", request))

    def DisassociateAddress(self, request):
        self.calls.append(("DisassociateAddress", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "region": "ap-guangzhou"}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "eip-123", None, None)
    assert request.AddressIds == ["eip-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_describe_request_by_ip():
    request = build_describe_request(FakeModels, None, "1.2.3.4", "web")
    assert request.Filters[0].Name == "address-ip"
    assert request.Filters[0].Values == ["1.2.3.4"]
    assert not hasattr(request, "AddressIds")


def test_build_describe_request_by_name_fallback():
    request = build_describe_request(FakeModels, None, None, "web")
    assert request.Filters[0].Name == "address-name"
    assert request.Filters[0].Values == ["web"]


def test_find_address_returns_first_match():
    client = FakeClient(FakeDescribeResponse([FakeAddress("eip-1", "web", "1.2.3.4")]))
    module = FakeModule()
    address = find_address(module, client, FakeModels, None, "1.2.3.4", None)
    assert address["AddressId"] == "eip-1"
    assert len(client.calls) == 1


def test_find_address_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_address(module, client, FakeModels, None, "1.2.3.4", None) is None


def test_find_address_handles_none_set():
    client = FakeClient(FakeDescribeResponse(None))
    module = FakeModule()
    assert find_address(module, client, FakeModels, "eip-1", None, None) is None


def test_find_address_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_address(module, client, FakeModels, "eip-1", None, None)
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_create_builds_allocate_request_and_returns_id():
    module = FakeModule()
    client = FakeClient(allocate_response=FakeAllocateResponse(["eip-9"]))
    address_id = _create(module, client, FakeModels, "web", "TRAFFIC_POSTPAID_BY_HOUR", 10, {"env": "prod"})
    assert address_id == "eip-9"
    request = client.calls[0][1]
    assert request.AddressCount == 1
    assert request.AddressName == "web"
    assert request.InternetChargeType == "TRAFFIC_POSTPAID_BY_HOUR"
    assert request.InternetMaxBandwidthOut == 10
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]


def test_create_omits_optional_fields():
    module = FakeModule()
    client = FakeClient(allocate_response=FakeAllocateResponse(["eip-9"]))
    address_id = _create(module, client, FakeModels, None, None, None, {})
    assert address_id == "eip-9"
    request = client.calls[0][1]
    assert request.AddressCount == 1
    assert not hasattr(request, "AddressName")
    assert not hasattr(request, "InternetChargeType")
    assert not hasattr(request, "InternetMaxBandwidthOut")
    assert not hasattr(request, "Tags")


def test_delete_releases_unbound_address_directly():
    module = FakeModule()
    client = FakeClient()
    _delete(module, client, FakeModels, "eip-1", bound=False)
    names = [call[0] for call in client.calls]
    assert names == ["ReleaseAddresses"]
    request = client.calls[0][1]
    assert request.AddressIds == ["eip-1"]


def test_delete_disassociates_bound_address_first():
    module = FakeModule()
    client = FakeClient()
    _delete(module, client, FakeModels, "eip-1", bound=True)
    names = [call[0] for call in client.calls]
    assert names == ["DisassociateAddress", "ReleaseAddresses"]
    assert client.calls[0][1].AddressId == "eip-1"
    assert client.calls[1][1].AddressIds == ["eip-1"]
