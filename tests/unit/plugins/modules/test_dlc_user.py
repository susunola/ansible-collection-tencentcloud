from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_user import create_request, delete_request, describe_request, modify_request, type_request


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)
class Models:
    DescribeUsersRequest = Object
    CreateUserRequest = Object
    ModifyUserRequest = Object
    ModifyUserTypeRequest = Object
    DeleteUserRequest = Object


def params(): return {"user_id": "10001", "description": "analytics", "user_type": "COMMON", "alias": "analyst", "principal_type": "UserAccount", "account_source": "TencentAccount", "initial_policies": None, "initial_work_group_ids": [42]}


def test_describe_uses_exact_identity_and_pagination():
    request = describe_request(Models, params(), 100)
    assert request.UserId == "10001" and request.Offset == 100 and request.Limit == 100
    assert request.AccountType == "TencentAccount"


def test_create_maps_initial_access_contract():
    request = create_request(Models, params())
    assert request.UserId == "10001" and request.UserType == "COMMON" and request.WorkGroupIds == [42]
    assert request.AccountType == "UserAccount"


def test_mutation_requests_keep_account_identity():
    p = params()
    assert modify_request(Models, p).UserDescription == "analytics"
    assert type_request(Models, p).UserType == "COMMON"
    assert delete_request(Models, p).UserIds == ["10001"]
