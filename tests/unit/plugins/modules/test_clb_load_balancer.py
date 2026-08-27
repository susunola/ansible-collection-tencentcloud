"""Unit tests for the clb_load_balancer write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.clb_load_balancer import (
    _clb_tags_to_sdk_shape,
    build_create_request,
    build_describe_request,
    find_load_balancer,
    immutable_drift,
)


class FakeTagInfo(object):
    """Mimics the SDK TagInfo model: zero-arg constructor, attribute assignment.

    The real ``models.TagInfo.__init__`` accepts no keyword arguments; passing
    ``TagKey=...`` at construction time raises TypeError. Keeping this fake
    strict guards against the module regressing to kwargs construction.
    """

    def __init__(self):
        pass


class FakeInternetAccessible(object):
    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    TagInfo = FakeTagInfo
    InternetAccessible = FakeInternetAccessible
    DescribeLoadBalancersRequest = FakeRequest
    CreateLoadBalancerRequest = FakeRequest


class FakeLoadBalancer(object):
    def __init__(self, lb_id, name, vpc_id=None, status=1, tags=None):
        self.LoadBalancerId = lb_id
        self.LoadBalancerName = name
        self.VpcId = vpc_id
        self.Status = status
        self.Tags = tags or []

    def _serialize(self, allow_none=True):
        return {
            "LoadBalancerId": self.LoadBalancerId,
            "LoadBalancerName": self.LoadBalancerName,
            "VpcId": self.VpcId,
            "Status": self.Status,
            "Tags": list(self.Tags),
        }


class FakeResponse(object):
    def __init__(self, load_balancers):
        self.LoadBalancerSet = load_balancers


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeLoadBalancers(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def _params(**overrides):
    params = {
        "name": "web-lb",
        "load_balancer_type": "OPEN",
        "vpc_id": "vpc-xxxxxxxx",
        "subnet_id": None,
        "project_id": 0,
        "internet_charge_type": None,
        "internet_max_bandwidth_out": None,
        "client_token": None,
        "tags": {},
    }
    params.update(overrides)
    return params


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "lb-123", None, None)
    assert request.LoadBalancerIds == ["lb-123"]
    assert request.Limit == 100
    assert not hasattr(request, "LoadBalancerName") or request.LoadBalancerName is None


def test_build_describe_request_by_name_and_vpc():
    request = build_describe_request(FakeModels, None, "web-lb", "vpc-123")
    assert request.LoadBalancerName == "web-lb"
    assert request.VpcId == "vpc-123"
    assert not hasattr(request, "LoadBalancerIds") or request.LoadBalancerIds is None


def test_build_create_request_minimal():
    request = build_create_request(FakeModels, _params())
    assert request.Forward == 1
    assert request.LoadBalancerName == "web-lb"
    assert request.LoadBalancerType == "OPEN"
    assert request.VpcId == "vpc-xxxxxxxx"
    assert request.ProjectId == 0
    assert not hasattr(request, "ClientToken")
    assert not hasattr(request, "InternetAccessible")
    assert not hasattr(request, "Tags")


def test_build_create_request_full():
    request = build_create_request(FakeModels, _params(
        load_balancer_type="INTERNAL",
        subnet_id="subnet-xxxxxxxx",
        internet_charge_type="TRAFFIC_POSTPAID_BY_HOUR",
        internet_max_bandwidth_out=10,
        client_token="ansible-0001",
        tags={"env": "prod"},
    ))
    assert request.LoadBalancerType == "INTERNAL"
    assert request.SubnetId == "subnet-xxxxxxxx"
    assert request.ClientToken == "ansible-0001"
    assert request.InternetAccessible.InternetChargeType == "TRAFFIC_POSTPAID_BY_HOUR"
    assert request.InternetAccessible.InternetMaxBandwidthOut == 10
    assert len(request.Tags) == 1
    assert request.Tags[0].TagKey == "env"
    assert request.Tags[0].TagValue == "prod"


def test_find_load_balancer_matches_exact_name():
    """DescribeLoadBalancers matches names fuzzily; the module filters exactly."""
    client = FakeClient(FakeResponse([
        FakeLoadBalancer("lb-1", "web-lb-extended"),
        FakeLoadBalancer("lb-2", "web-lb"),
    ]))
    module = FakeModule()
    found = find_load_balancer(module, client, FakeModels, None, "web-lb", None)
    assert found["LoadBalancerId"] == "lb-2"


def test_find_load_balancer_matches_vpc():
    client = FakeClient(FakeResponse([
        FakeLoadBalancer("lb-1", "web-lb", vpc_id="vpc-other"),
        FakeLoadBalancer("lb-2", "web-lb", vpc_id="vpc-mine"),
    ]))
    module = FakeModule()
    found = find_load_balancer(module, client, FakeModels, None, "web-lb", "vpc-mine")
    assert found["LoadBalancerId"] == "lb-2"


def test_find_load_balancer_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_load_balancer(module, client, FakeModels, "lb-123", None, None) is None


def test_find_load_balancer_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_load_balancer(module, client, FakeModels, None, "web-lb", None) is None


def test_immutable_drift_detects_creation_only_changes():
    current = {"LoadBalancerType": "OPEN", "VpcId": "vpc-1", "SubnetId": None}
    assert immutable_drift(current) == []
    assert immutable_drift(current, load_balancer_type="OPEN", vpc_id="vpc-1") == []
    assert immutable_drift(current, load_balancer_type="INTERNAL") == ["load_balancer_type"]
    assert immutable_drift(current, vpc_id="vpc-2", subnet_id="subnet-1") == ["vpc_id", "subnet_id"]


def test_clb_tags_to_sdk_shape():
    tag_infos = [{"TagKey": "env", "TagValue": "prod"}, {"TagKey": "tier", "TagValue": "web"}]
    assert _clb_tags_to_sdk_shape(tag_infos) == [
        {"Key": "env", "Value": "prod"},
        {"Key": "tier", "Value": "web"},
    ]
    assert _clb_tags_to_sdk_shape(None) == []


def test_find_load_balancer_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_load_balancer(module, client, FakeModels, "lb-123", None, None)
        raise AssertionError("expected exception")
    except Boom:
        pass
