from ansible_collections.susunola.tencentcloud.plugins.modules.tse_instance_tag_info import request


class Value(object): pass
class Models(object): DescribeInstanceTagInfosRequest = Value


def test_instance_tag_request_maps_instance_id():
    assert request(Models, "ins-1").InstanceId == "ins-1"
