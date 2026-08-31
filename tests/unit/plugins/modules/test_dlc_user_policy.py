from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_user_policy import attach_request, delta, describe_request, detach_request, normalize_policy


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)
class Models:
    DescribeUsersRequest = Object
    AttachUserPolicyRequest = Object
    DetachUserPolicyRequest = Object
    Policy = Object


def test_policy_normalization_ignores_server_metadata():
    base = {"Database": "sales", "Operation": "SELECT", "PolicyType": "DATABASE"}
    assert normalize_policy({**base, "PolicyId": 42}) == normalize_policy(base)


def test_delta_is_exact_and_stable():
    current = [{"Database": "old", "Operation": "SELECT", "PolicyType": "DATABASE"}]
    target = [{"Database": "new", "Operation": "SELECT", "PolicyType": "DATABASE"}]
    added, removed = delta(current, target)
    assert added[0]["Database"] == "new" and removed[0]["Database"] == "old"


def test_requests_include_user_source_and_prefer_ids():
    values = [{"Database": "sales"}]
    assert describe_request(Models, "10001", "TencentAccount", 100).Offset == 100
    assert attach_request(Models, "10001", "TencentAccount", values).AccountType == "TencentAccount"
    detached = detach_request(Models, "10001", "TencentAccount", values, ["42"])
    assert detached.PolicyIds == ["42"] and not hasattr(detached, "PolicySet")
