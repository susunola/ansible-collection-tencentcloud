from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_partition_queue import delete_request, describe_request, drift, make_request, normalize, scale_down


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)
class Models:
    DescribePartitionQueuesRequest = Object
    CreatePartitionQueueRequest = Object
    ModifyPartitionQueueRequest = Object
    DeletePartitionQueueRequest = Object


def params():
    return {"partition_code": "rp-1", "name": "notebooks", "queue_type": 1, "description": "interactive",
            "resource_usages": [{"resource_type": "CU", "billing_item": "standard", "instance_type": None,
                                 "spec": "0:1:4:0", "gpu_type": None, "min": 32, "max": 128}]}


def test_describe_scopes_partition_and_page():
    request = describe_request(Models, "rp-1", 2)
    assert request.PartitionCode == "rp-1" and request.Page == 2 and request.PageSize == 200


def test_create_maps_nested_resource_contract():
    request = make_request(Models, params())
    assert request.QueueName == "notebooks" and request.ResourceUsages[0]["ResourceSpec"]["BillingItem"] == "standard"


def test_modify_and_delete_use_stable_id():
    assert make_request(Models, params(), update=True, queue_id=42).Id == 42
    assert delete_request(Models, params(), 42).Id == 42


def test_normalized_readback_is_idempotent():
    current = normalize({"Description": "interactive", "QueueType": 1, "ResourceUsage": [{
        "ResourceSpec": {"ResourceType": "CU", "BillingItem": "standard", "Spec": "0:1:4:0", "SpecDesc": "ignored"},
        "Min": 32, "Max": 128}]})
    assert drift(params(), current) == {}


def test_scale_down_detects_reduction_and_removal():
    old = normalize({"ResourceUsage": [{"ResourceSpec": {"BillingItem": "standard"}, "Min": 32, "Max": 128}]})["ResourceUsage"]
    lower = normalize({"ResourceUsage": [{"ResourceSpec": {"BillingItem": "standard"}, "Min": 16, "Max": 64}]})["ResourceUsage"]
    assert scale_down(old, lower) is True and scale_down(old, []) is True and scale_down(lower, old) is False
