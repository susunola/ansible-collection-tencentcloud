from __future__ import absolute_import, division, print_function

import json
from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.monitor import find_policy


class FakePolicy:
    def __init__(self, value):
        self.value = value

    def to_json_string(self):
        return json.dumps(self.value)


class FakeModule:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requests = []

    def sdk_call(self, operation, request):
        self.requests.append(request)
        return self.pages.pop(0)

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


def test_find_policy_uses_describe_alarm_policies_response_and_paginates():
    target = {"PolicyId": "policy-target", "PolicyName": "target"}
    first_page = [FakePolicy({"PolicyId": "policy-other", "PolicyName": "other"}) for _ in range(100)]
    module = FakeModule([
        SimpleNamespace(Policies=first_page, TotalCount=101),
        SimpleNamespace(Policies=[FakePolicy(target)], TotalCount=101),
    ])
    models = SimpleNamespace(DescribeAlarmPoliciesRequest=SimpleNamespace)
    result = find_policy(module, SimpleNamespace(DescribeAlarmPolicies=object()), models,
                         "policy-target", None, "monitor")
    assert result == target
    assert [request.PageNumber for request in module.requests] == [1, 2]
    assert all(request.Module == "monitor" for request in module.requests)
