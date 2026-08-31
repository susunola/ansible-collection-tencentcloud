from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_template_info import request


class Value(object): pass
class Models(object): DescribeAllConfigFileTemplatesRequest = Value


def test_template_request_maps_instance_id():
    assert request(Models, "ins-1").InstanceId == "ins-1"
