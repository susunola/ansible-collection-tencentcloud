from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_product_secret import (
    _objects,
    _request,
    comparable,
    create_request,
    wait_task,
)


class Value(object):
    pass


class Models(object):
    CreateProductSecretRequest = Value
    DescribeAsyncRequestInfoRequest = Value
    ProductPrivilegeUnit = Value
    Tag = Value


def params():
    return {
        "secret_name": "orders-db",
        "username_prefix": "ssmapp",
        "product_name": "Mysql",
        "instance_id": "cdb-1",
        "domains": ["10.%"],
        "privileges": [{"privilege_name": "GlobalPrivileges", "privileges": ["SELECT"]}],
        "description": "orders",
        "kms_key_id": "kms-1",
        "kms_hsm_cluster_id": None,
        "encrypt_type": 0,
        "tags": {"env": "prod"},
        "rotation_begin_time": "2026-09-02 02:00:00",
        "rotation_enabled": True,
        "rotation_frequency": 30,
        "account_remark": None,
        "account_type": None,
    }


def test_create_request_maps_privileges_tags_and_rotation():
    request = create_request(Models, params())
    assert request.SecretName == "orders-db"
    assert request.PrivilegesList[0].PrivilegeName == "GlobalPrivileges"
    assert request.PrivilegesList[0].Privileges == ["SELECT"]
    assert (request.Tags[0].TagKey, request.Tags[0].TagValue) == ("env", "prod")
    assert request.EnableRotation is True
    assert request.RotationFrequency == 30


def test_request_omits_none_and_object_mapping_is_deterministic():
    request = _request(Models, "DescribeAsyncRequestInfoRequest", FlowID=12, Ignored=None)
    assert request.FlowID == 12
    assert not hasattr(request, "Ignored")
    values = _objects(Models, "Tag", [{"key": "a", "value": "b"}])
    assert values[0].TagKey == "a"


def test_comparable_uses_stable_product_identity():
    assert comparable({"SecretName": "s", "ProductName": "Mysql", "ResourceID": "cdb-1", "Status": "Enabled", "RotationStatus": 1, "RotationFrequency": 30}) == {"SecretName": "s", "Description": "", "ProductName": "Mysql", "ResourceID": "cdb-1", "Enabled": True, "RotationStatus": 1, "RotationFrequency": 30}


class Module(object):
    check_mode = False
    params = {"waiter_timeout": 10, "waiter_delay": 1}

    def __init__(self):
        self.failed = None

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        self.failed = kwargs
        raise AssertionError(kwargs)


class Client(object):
    def DescribeAsyncRequestInfo(self, request):
        response = Value()
        response.TaskStatus = 1
        response.Description = "done"
        return response


def test_wait_task_tracks_ssm_flow_to_success():
    assert wait_task(Module(), Client(), Models, 42).TaskStatus == 1
