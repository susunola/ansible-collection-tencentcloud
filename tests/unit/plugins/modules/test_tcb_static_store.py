from ansible_collections.susunola.tencentcloud.plugins.modules.tcb_static_store import create_request, delete_request, describe_request


class Value(object):
    def from_json_string(self, raw): self.raw = raw
class Models(object):
    DescribeStaticStoreRequest = Value
    CreateStaticStoreRequest = Value
    DestroyStaticStoreRequest = Value
    ExternalStorage = Value


def test_static_store_requests_are_environment_scoped():
    assert describe_request(Models, "env-1").EnvId == "env-1"
    create = create_request(Models, {"env_id": "env-1", "enable_union": True, "external_storage": {"Type": "cos"}})
    assert create.EnableUnion is True
    assert '"Type": "cos"' in create.ExternalStorage.raw
    delete = delete_request(Models, "env-1", "cdn.example.com")
    assert delete.CdnDomain == "cdn.example.com"
