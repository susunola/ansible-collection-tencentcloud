from ansible_collections.susunola.tencentcloud.plugins.modules.tdcpg_account import description_request, password_request


class Value(object):
    pass


class Models(object):
    ModifyAccountDescriptionRequest = Value
    ResetAccountPasswordRequest = Value


def test_account_requests_map_identity_and_secret():
    p = {"cluster_id": "c1", "account_name": "root", "description": "admin", "password": "secret"}
    assert description_request(Models, p).AccountDescription == "admin"
    assert password_request(Models, p).AccountPassword == "secret"
