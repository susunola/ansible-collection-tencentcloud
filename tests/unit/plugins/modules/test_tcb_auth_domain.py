from ansible_collections.susunola.tencentcloud.plugins.modules.tcb_auth_domain import create_request, delete_request, describe_request


class Value(object):
    pass


class Models(object):
    DescribeAuthDomainsRequest = Value
    CreateAuthDomainRequest = Value
    DeleteAuthDomainRequest = Value


def test_auth_domain_requests_are_environment_scoped():
    assert describe_request(Models, "env-1").EnvId == "env-1"
    create = create_request(Models, "env-1", "app.example.com")
    assert create.Domains == ["app.example.com"]
    delete = delete_request(Models, "env-1", "domain-1")
    assert delete.DomainIds == ["domain-1"]
