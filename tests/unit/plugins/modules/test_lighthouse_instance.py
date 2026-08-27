"""Unit tests for the lighthouse_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_instance import (
    _create,
    _immutable_drift,
    _isolate,
    _start,
    _stop,
    _update_name,
    build_create_request,
    build_describe_request,
    find_instance,
)


class FakeFilter(object):
    """Mimics the Tencent SDK Filter model: zero-arg constructor."""

    def __init__(self):
        pass


class FakeLoginConfiguration(object):
    def __init__(self):
        self.Password = None


class FakeChargePrepaid(object):
    def __init__(self):
        self.Period = None


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    LoginConfiguration = FakeLoginConfiguration
    InstanceChargePrepaid = FakeChargePrepaid
    DescribeInstancesRequest = FakeRequest
    CreateInstancesRequest = FakeRequest
    ModifyInstancesAttributeRequest = FakeRequest
    StartInstancesRequest = FakeRequest
    StopInstancesRequest = FakeRequest
    IsolateInstancesRequest = FakeRequest


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

    def _record(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DescribeInstances(self, request):
        return self._record(request)

    def CreateInstances(self, request):
        return self._record(request)

    def ModifyInstancesAttribute(self, request):
        return self._record(request)

    def StartInstances(self, request):
        return self._record(request)

    def StopInstances(self, request):
        return self._record(request)

    def IsolateInstances(self, request):
        return self._record(request)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


CREATE_PARAMS = {
    "bundle_id": "bundle_2022_std_1c1g",
    "blueprint_id": "lhbp-1",
    "instance_count": 1,
    "instance_name": "blog-01",
    "zones": ["ap-guangzhou-3"],
    "password": "secret",
    "prepaid_period": 1,
}


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "lhins-1", None)
    assert request.InstanceIds == ["lhins-1"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "blog-01")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["blog-01"]
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_returns_first_match():
    client = FakeClient(FakeResponse([FakeInstance("lhins-1", "blog-01")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "blog-01")
    assert instance["InstanceId"] == "lhins-1"
    assert len(client.calls) == 1


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, "lhins-9", None) is None


def test_build_create_request_full():
    request = build_create_request(FakeModels, CREATE_PARAMS)
    assert request.BundleId == "bundle_2022_std_1c1g"
    assert request.BlueprintId == "lhbp-1"
    assert request.InstanceCount == 1
    assert request.InstanceName == "blog-01"
    assert request.Zones == ["ap-guangzhou-3"]
    assert request.LoginConfiguration.Password == "secret"
    assert request.InstanceChargePrepaid.Period == 1


def test_build_create_request_minimal():
    params = {
        "bundle_id": "bundle_x",
        "blueprint_id": "lhbp-1",
        "instance_count": 1,
        "instance_name": None,
        "zones": None,
        "password": None,
        "prepaid_period": None,
    }
    request = build_create_request(FakeModels, params)
    assert request.InstanceCount == 1
    assert not hasattr(request, "InstanceName")
    assert not hasattr(request, "Zones")
    assert not hasattr(request, "LoginConfiguration")
    assert not hasattr(request, "InstanceChargePrepaid")


def test_create_delegates_to_build_create_request():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, CREATE_PARAMS)
    assert len(client.calls) == 1
    assert client.calls[0].BundleId == "bundle_2022_std_1c1g"


def test_start_sends_instance_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _start(module, client, FakeModels, "lhins-1")
    assert client.calls[-1].InstanceIds == ["lhins-1"]


def test_stop_sends_instance_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _stop(module, client, FakeModels, "lhins-1")
    assert client.calls[-1].InstanceIds == ["lhins-1"]


def test_isolate_sends_instance_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _isolate(module, client, FakeModels, "lhins-1")
    assert client.calls[-1].InstanceIds == ["lhins-1"]


def test_update_name():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update_name(module, client, FakeModels, "lhins-1", "blog-02")
    request = client.calls[-1]
    assert request.InstanceIds == ["lhins-1"]
    assert request.InstanceName == "blog-02"


def test_immutable_drift_detects_changes():
    current = {"BundleId": "bundle_old", "BlueprintId": "lhbp-1"}
    params = dict(CREATE_PARAMS, bundle_id="bundle_new", instance_count=2)
    drifted = _immutable_drift(current, params)
    assert "bundle_id" in drifted
    assert "blueprint_id" not in drifted
    assert "password" in drifted
    assert "instance_count" in drifted


def test_immutable_drift_empty_when_matching():
    current = {
        "BundleId": "bundle_2022_std_1c1g",
        "BlueprintId": "lhbp-1",
    }
    params = dict(CREATE_PARAMS, password=None)
    assert _immutable_drift(current, params) == []
