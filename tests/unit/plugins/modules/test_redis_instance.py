"""Unit tests for the redis_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules.redis_instance import (
    build_describe_request,
    find_instance,
    _create,
    _rename,
    _destroy,
    _wait_status,
)


class FakeRequest(object):
    pass


class FakeResourceTag(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeModels(object):
    DescribeInstancesRequest = FakeRequest
    CreateInstancesRequest = FakeRequest
    ModifyInstanceRequest = FakeRequest
    DestroyPostpaidInstanceRequest = FakeRequest
    DestroyPrepaidInstanceRequest = FakeRequest
    ResourceTag = FakeResourceTag


class FakeInstance(object):
    def __init__(self, instance_id, name, billing_mode="POSTPAID", status=0):
        self.InstanceId = instance_id
        self.InstanceName = name
        self.Status = status
        self.BillingMode = billing_mode
        self.RedisShardSize = 4096
        self.ZoneId = 100003

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "Status": self.Status,
            "BillingMode": self.BillingMode,
            "RedisShardSize": self.RedisShardSize,
            "ZoneId": self.ZoneId,
        }


class FakeDescribeResponse(object):
    def __init__(self, instances):
        self.InstanceSet = instances


class FakeCreateResponse(object):
    def __init__(self, instance_ids):
        self.InstanceIds = instance_ids


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None, exc=None):
        self.describe_response = describe_response
        self.describe_pages = []
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeInstances(self, request):
        self.calls.append(("DescribeInstances", request))
        if self.exc:
            raise self.exc
        if self.describe_pages:
            return FakeDescribeResponse(self.describe_pages.pop(0))
        return self.describe_response

    def CreateInstances(self, request):
        self.calls.append(("CreateInstances", request))
        return self.create_response

    def ModifyInstance(self, request):
        self.calls.append(("ModifyInstance", request))

    def DestroyPostpaidInstance(self, request):
        self.calls.append(("DestroyPostpaidInstance", request))

    def DestroyPrepaidInstance(self, request):
        self.calls.append(("DestroyPrepaidInstance", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "waiter_timeout": 10, "waiter_delay": 1}
        self.check_mode = False

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs["msg"] = args[0]
        kwargs["failed"] = True
        raise SystemExit(kwargs)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "crs-1", None)
    assert request.InstanceIds == ["crs-1"]
    assert not hasattr(request, "InstanceName") or request.InstanceName is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "prod-cache")
    assert request.InstanceName == "prod-cache"
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_by_id():
    client = FakeClient(FakeDescribeResponse([FakeInstance("crs-1", "prod-cache")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, "crs-1", None)
    assert instance["InstanceId"] == "crs-1"
    assert len(client.calls) == 1


def test_find_instance_by_exact_name():
    client = FakeClient(FakeDescribeResponse([
        FakeInstance("crs-1", "prod-cache"),
        FakeInstance("crs-2", "prod-cache-2"),
    ]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "prod-cache")
    assert instance["InstanceId"] == "crs-1"


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, "crs-9", None) is None


def test_create_sends_all_fields():
    client = FakeClient(create_response=FakeCreateResponse(["crs-9"]))
    module = FakeModule()
    created_id = _create(module, client, FakeModels, {
        "name": "prod-cache",
        "zone_name": "ap-guangzhou-3",
        "type_id": 1,
        "mem_size": 4096,
        "redis_shard_num": 1,
        "redis_replicas_num": 1,
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "password": "s3cret",
        "no_auth": False,
        "project_id": 5,
        "security_group_id_list": ["sg-1"],
        "tags": {"env": "prod"},
    })
    assert created_id == "crs-9"
    request = client.calls[-1][1]
    assert request.InstanceName == "prod-cache"
    assert request.ZoneName == "ap-guangzhou-3"
    assert request.TypeId == 1
    assert request.MemSize == 4096
    assert request.GoodsNum == 1
    assert request.RedisShardNum == 1
    assert request.RedisReplicasNum == 1
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.Password == "s3cret"
    assert request.ProjectId == 5
    assert request.SecurityGroupIdList == ["sg-1"]
    assert [(t.TagKey, t.TagValue) for t in request.ResourceTags] == [("env", "prod")]


def test_create_omits_optional_fields():
    client = FakeClient(create_response=FakeCreateResponse(["crs-9"]))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "name": "prod-cache",
        "zone_name": "ap-guangzhou-3",
        "type_id": 2,
        "mem_size": 8192,
        "redis_shard_num": None,
        "redis_replicas_num": None,
        "vpc_id": None,
        "subnet_id": None,
        "password": None,
        "no_auth": False,
        "project_id": None,
        "security_group_id_list": None,
        "tags": {},
    })
    request = client.calls[-1][1]
    assert request.InstanceName == "prod-cache"
    assert not hasattr(request, "VpcId")
    assert not hasattr(request, "SubnetId")
    assert not hasattr(request, "Password")
    assert not hasattr(request, "ProjectId")
    assert not hasattr(request, "SecurityGroupIdList")
    assert not hasattr(request, "ResourceTags")
    assert not hasattr(request, "NoAuth")


def test_rename_sends_id_and_name():
    client = FakeClient()
    module = FakeModule()
    _rename(module, client, FakeModels, "crs-1", "renamed")
    request = client.calls[-1][1]
    assert request.InstanceId == "crs-1"
    assert request.InstanceName == "renamed"


def test_destroy_postpaid_instance():
    client = FakeClient()
    module = FakeModule()
    _destroy(module, client, FakeModels, "crs-1", "POSTPAID")
    assert [c[0] for c in client.calls] == ["DestroyPostpaidInstance"]
    assert client.calls[-1][1].InstanceId == "crs-1"


def test_destroy_prepaid_instance():
    client = FakeClient()
    module = FakeModule()
    _destroy(module, client, FakeModels, "crs-1", "PREPAID")
    assert [c[0] for c in client.calls] == ["DestroyPrepaidInstance"]
    assert client.calls[-1][1].InstanceId == "crs-1"


def _wait_module(timeout=10, delay=1):
    module = FakeModule()
    module.params = {"retries": 2, "waiter_timeout": timeout, "waiter_delay": delay}
    return module


def test_wait_status_waits_for_running():
    client = FakeClient()
    client.describe_pages = [
        [FakeInstance("crs-1", "prod-cache", status=0)],
        [FakeInstance("crs-1", "prod-cache", status=1)],
        [FakeInstance("crs-1", "prod-cache", status=2)],
    ]
    module = _wait_module(timeout=10, delay=0.01)
    assert _wait_status(module, client, FakeModels, "crs-1", [2]) == 2
    assert len(client.calls) == 3


def test_wait_status_treats_missing_instance_as_gone_terminal():
    client = FakeClient()
    client.describe_pages = [[]]
    module = _wait_module(timeout=10, delay=0.01)
    assert _wait_status(module, client, FakeModels, "crs-1", [-3], gone_terminal=-3) == -3
    assert len(client.calls) == 1


def test_wait_status_times_out_on_stuck_state():
    client = FakeClient()
    client.describe_pages = [[FakeInstance("crs-1", "prod-cache", status=1)]] * 20
    module = _wait_module(timeout=0.15, delay=0.05)
    with pytest.raises(SystemExit) as excinfo:
        _wait_status(module, client, FakeModels, "crs-1", [2])
    assert "Timed out waiting for resource state" in excinfo.value.args[0]["msg"]
