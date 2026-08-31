from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_work_group_membership import delta, membership_request


class Info: pass
class Request: pass
Models=type("Models",(),{"UserIdSetOfWorkGroupId":Info,"AddUsersToWorkGroupRequest":Request,"DeleteUsersFromWorkGroupRequest":Request})


def test_delta_is_exact_and_order_independent():
    assert delta(["u2","u1"],["u2","u3"])==(["u3"],["u1"])


def test_membership_request_scopes_group_and_users():
    request=membership_request(Models,42,["u1","u2"],True)
    assert request.AddInfo.WorkGroupId==42
    assert request.AddInfo.UserIds==["u1","u2"]
