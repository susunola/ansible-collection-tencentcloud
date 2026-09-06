from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_rotation_info import request as rotation_request
from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_secret_info import list_request, read_list
from ansible_collections.susunola.tencentcloud.plugins.modules.ssm_secret_version_info import value_request


class Object:
    pass


class Models:
    ListSecretsRequest = TagFilter = GetSecretValueRequest = DescribeRotationDetailRequest = Object


def params():
    return {
        "page_size": 2,
        "max_pages": 5,
        "order": "ascending",
        "state_filter": 1,
        "search_name": "prod",
        "tag_filters": {"env": "prod"},
        "secret_type": 0,
        "product_name": None,
        "encrypt_type": 1,
        "instance_id": None,
    }


def test_secret_list_request_maps_filters_and_tags():
    request = list_request(Models, params(), 2)
    assert (request.Offset, request.Limit, request.OrderType, request.State) == (2, 2, 1, 1)
    assert request.TagFilters[0].TagKey == "env" and request.TagFilters[0].TagValue == ["prod"]


class Item:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"SecretName": self.name}


class Response:
    def __init__(self, names, total, request_id):
        self.SecretMetadatas, self.TotalCount, self.RequestId = [Item(x) for x in names], total, request_id


class Client:
    def __init__(self):
        self.values = [Response(["a", "b"], 3, "r1"), Response(["c"], 3, "r2")]

    def ListSecrets(self, request):
        return self.values.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_secret_list_reader_follows_pages():
    values, total, truncated, request_id = read_list(Module(), Client(), Models, params())
    assert [x["SecretName"] for x in values] == ["a", "b", "c"] and total == 3 and not truncated and request_id == "r2"


def test_sensitive_value_and_rotation_requests_keep_exact_identity():
    p = {"secret_name": "prod/db", "version_id": "v2", "encryption_public_key": "pk", "encryption_algorithm": "RSAES_OAEP_SHA_256"}
    value = value_request(Models, p)
    rotation = rotation_request(Models.DescribeRotationDetailRequest, "prod/db")
    assert (value.SecretName, value.VersionId, value.EncryptionPublicKey) == ("prod/db", "v2", "pk") and rotation.SecretName == "prod/db"
