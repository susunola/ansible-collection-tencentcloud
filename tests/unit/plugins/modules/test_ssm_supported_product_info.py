from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_supported_product_info import request


class Value(object):
    pass


class Models(object):
    DescribeSupportedProductsRequest = Value


def test_request_has_no_hidden_required_fields():
    value = request(Models)
    assert isinstance(value, Value)
    assert vars(value) == {}
