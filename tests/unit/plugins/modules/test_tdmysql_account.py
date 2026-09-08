from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import privileges_request
from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_account import create_request, delete_request, get, privileges_modify_request, reset_request


class Object:
    pass


class Models:
    CreateUsersRequest = DeleteUsersRequest = ModifyUserPrivilegesRequest = ResetUsersPasswordRequest = ResetUserPasswordInfo = DescribeUsersRequest = (
        DescribeUserPrivilegesRequest
    ) = User = Object


P = {
    "instance_id": "db1",
    "username": "report",
    "host": "10.%",
    "password": "secret",
    "encrypted_password": None,
    "description": "reporting",
    "global_privileges": ["SELECT"],
}


def test_account_requests_keep_composite_identity():
    create, delete, reset = create_request(Models, P), delete_request(Models, P), reset_request(Models, P)
    assert (create.Users[0].UserName, create.Users[0].Host) == ("report", "10.%")
    assert delete.Users[0].Host == "10.%" and reset.Users[0].Password == "secret"


def test_privilege_requests_use_global_scope_and_sorted_set():
    describe, modify = privileges_request(Models, P), privileges_modify_request(Models, P)
    assert (describe.DbName, describe.ObjectType, describe.Object, describe.ColName) == ("*", "*", "*", "*")
    assert modify.GlobalPrivileges == ["SELECT"]


class Item:
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return self.value


class Response:
    def __init__(self, users=None, privileges=None, request_id="r1"):
        self.Users, self.Privileges, self.RequestId = users, privileges, request_id


class Client:
    def DescribeUsers(self, request):
        return Response([Item({"UserName": "report", "Host": "10.%"}), Item({"UserName": "report", "Host": "%"})])

    def DescribeUserPrivileges(self, request):
        return Response(privileges=["UPDATE", "SELECT"], request_id="r2")


class Module:
    def sdk_call(self, fn, request):
        return fn(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_account_get_matches_username_and_host_and_enriches_privileges():
    value = get(Module(), Client(), Models, dict(P, include_global_privileges=True))
    assert value["Host"] == "10.%"
    assert value["GlobalPrivileges"] == ["SELECT", "UPDATE"]
