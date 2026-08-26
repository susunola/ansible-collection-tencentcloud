"""Unit tests for the cvm_instance write module helpers."""

from ansible_collections.tencentcloud.cloud.plugins.modules.cvm_instance import (
    _InstanceGone,
    build_describe_request,
    build_run_request,
    find_instance,
    immutable_drift,
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
    TagSpecification = FakeRequest
    Placement = FakeRequest
    VirtualPrivateCloud = FakeRequest
    InternetAccessible = FakeRequest
    LoginSettings = FakeRequest
    DescribeInstancesRequest = FakeRequest
    RunInstancesRequest = FakeRequest


class FakeInstance(object):
    def __init__(self, instance_id, name, state="RUNNING"):
        self.InstanceId = instance_id
        self.InstanceName = name
        self.InstanceState = state

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "InstanceState": self.InstanceState,
        }


class FakeResponse(object):
    def __init__(self, instances):
        self.InstanceSet = instances


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeInstances(self, request):
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
        "instance_name": None,
        "image_id": "img-1",
        "instance_type": "S5.MEDIUM2",
        "instance_charge_type": "POSTPAID_BY_HOUR",
        "vpc_id": None,
        "subnet_id": None,
        "security_group_ids": None,
        "hostname": None,
        "password": None,
        "key_ids": None,
        "internet_charge_type": None,
        "internet_max_bandwidth_out": None,
        "public_ip_assigned": None,
        "dry_run": False,
        "tags": {},
    }
    params.update(overrides)
    return params


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "ins-123", None)
    assert request.InstanceIds == ["ins-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "web-01")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["web-01"]
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_returns_first_match():
    client = FakeClient(FakeResponse([FakeInstance("ins-1", "web-01")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "web-01")
    assert instance["InstanceId"] == "ins-1"
    assert len(client.calls) == 1


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, None, "web-01") is None


def test_find_instance_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, None, "web-01") is None


def test_find_instance_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "InvalidInstanceId.NotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_instance(module, client, FakeModels, "ins-1", None)
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_build_run_request_minimal():
    request = build_run_request(FakeModels, _params())
    assert request.ImageId == "img-1"
    assert request.InstanceType == "S5.MEDIUM2"
    assert request.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert request.Placement is not None
    assert not hasattr(request, "DryRun")
    assert not hasattr(request, "InstanceName")
    assert not hasattr(request, "VirtualPrivateCloud")
    assert not hasattr(request, "InternetAccessible")
    assert not hasattr(request, "LoginSettings")
    assert not hasattr(request, "TagSpecification")


def test_build_run_request_full():
    request = build_run_request(FakeModels, _params(
        instance_name="web-01",
        hostname="web-01",
        security_group_ids=["sg-1", "sg-2"],
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        password="secret",
        internet_charge_type="TRAFFIC_POSTPAID_BY_HOUR",
        internet_max_bandwidth_out=10,
        public_ip_assigned=True,
        dry_run=True,
        tags={"env": "prod"},
    ))
    assert request.InstanceName == "web-01"
    assert request.HostName == "web-01"
    assert request.SecurityGroupIds == ["sg-1", "sg-2"]
    assert request.VirtualPrivateCloud.VpcId == "vpc-1"
    assert request.VirtualPrivateCloud.SubnetId == "subnet-1"
    assert request.LoginSettings.Password == "secret"
    assert not hasattr(request.LoginSettings, "KeyIds")
    assert request.InternetAccessible.InternetChargeType == "TRAFFIC_POSTPAID_BY_HOUR"
    assert request.InternetAccessible.InternetMaxBandwidthOut == 10
    assert request.InternetAccessible.PublicIpAssigned is True
    assert request.DryRun is True
    assert request.TagSpecification[0].ResourceType == "instance"
    tag = request.TagSpecification[0].Tags[0]
    assert tag.Key == "env"
    assert tag.Value == "prod"


def test_build_run_request_key_ids():
    request = build_run_request(FakeModels, _params(key_ids=["skey-1"]))
    assert request.LoginSettings.KeyIds == ["skey-1"]
    assert not hasattr(request.LoginSettings, "Password")


def test_immutable_drift_none():
    current = {
        "ImageId": "img-1",
        "InstanceType": "S5.MEDIUM2",
        "VirtualPrivateCloud": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
    }
    assert immutable_drift(current, image_id="img-1", instance_type="S5.MEDIUM2",
                           vpc_id="vpc-1", subnet_id="subnet-1") == []


def test_immutable_drift_detects_changes():
    current = {
        "ImageId": "img-1",
        "InstanceType": "S5.MEDIUM2",
        "VirtualPrivateCloud": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
    }
    assert immutable_drift(current, image_id="img-2") == ["image_id"]
    assert immutable_drift(current, instance_type="S5.LARGE4") == ["instance_type"]
    assert immutable_drift(current, vpc_id="vpc-2") == ["vpc_id"]
    assert immutable_drift(current, subnet_id="subnet-2") == ["subnet_id"]


def test_immutable_drift_ignores_unset_params():
    current = {"ImageId": "img-1", "VirtualPrivateCloud": None}
    assert immutable_drift(current) == []


def test_instance_gone_reports_not_found_code():
    assert _InstanceGone("gone").get_code() == "InvalidInstanceId.NotFound"
