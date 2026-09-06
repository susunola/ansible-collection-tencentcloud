from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file import contains, delete_request, desired


class Value(object):
    pass


class Models(object):
    DeleteConfigFilesRequest = Value


def test_config_file_identity_content_and_delete_id():
    p = {
        "instance_id": "i1",
        "namespace": "prod",
        "group": "app",
        "name": "a.yaml",
        "content": "x",
        "format": "YAML",
        "comment": None,
        "tags": None,
        "supported_client": None,
        "persistent": None,
        "encrypted": None,
        "encrypt_algo": None,
    }
    target = desired(p)
    assert contains(dict(target, Status="EDITING"), target)
    assert delete_request(Models, p, {"Id": "f1"}).Id == "f1"
