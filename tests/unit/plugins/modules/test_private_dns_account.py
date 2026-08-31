from ansible_collections.susunola.tencentcloud.plugins.modules.private_dns_account import account_object, list_request, mutation_request


class Value(object): pass
class Models(object):
    PrivateDNSAccount = Value
    CreatePrivateDNSAccountRequest = Value
    DeletePrivateDNSAccountRequest = Value
    DescribePrivateDNSAccountListRequest = Value


def test_account_mutation_requests_preserve_string_uin():
    value = mutation_request(Models, "CreatePrivateDNSAccountRequest", "100000000001", "consumer@example.com")
    assert value.Account.Uin == "100000000001"
    assert value.Account.Account == "consumer@example.com"
    assert account_object(Models, "1", "a").Uin == "1"


def test_account_list_request_is_bounded():
    value = list_request(Models, 200)
    assert (value.Offset, value.Limit) == (200, 100)
