from __future__ import absolute_import, division, print_function

import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import monitor
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
    first_page = [FakePolicy({"PolicyId": "policy-other", "PolicyName": "other"}) for unused_index in range(100)]
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


def test_find_policy_by_id_does_not_filter_out_old_name():
    policy = {"PolicyId": "policy-target", "PolicyName": "old-name"}
    module = FakeModule([SimpleNamespace(Policies=[FakePolicy(policy)], TotalCount=1)])
    models = SimpleNamespace(DescribeAlarmPoliciesRequest=SimpleNamespace)
    result = find_policy(module, SimpleNamespace(DescribeAlarmPolicies=object()), models,
                         "policy-target", "new-name", "monitor")
    assert result == policy
    assert not hasattr(module.requests[0], "PolicyName")


def test_find_policy_continues_full_page_when_total_count_is_missing():
    first_page = [FakePolicy({"PolicyId": "other-%d" % index}) for index in range(100)]
    target = {"PolicyId": "policy-target", "PolicyName": "target"}
    module = FakeModule([
        SimpleNamespace(Policies=first_page, TotalCount=None),
        SimpleNamespace(Policies=[FakePolicy(target)], TotalCount=None),
    ])
    models = SimpleNamespace(DescribeAlarmPoliciesRequest=SimpleNamespace)
    assert find_policy(module, SimpleNamespace(DescribeAlarmPolicies=object()), models,
                       "policy-target", None, "monitor") == target
    assert [request.PageNumber for request in module.requests] == [1, 2]


def test_notice_waiter_observes_convergence(monkeypatch):
    stale = {"NoticeIds": ["old"], "HierarchicalNotices": [], "NoticeContentTmplBindInfos": []}
    current = {"NoticeIds": ["new"], "HierarchicalNotices": [], "NoticeContentTmplBindInfos": []}
    policies = iter([stale, current])
    monkeypatch.setattr(monitor, "find_policy", lambda *args: next(policies))
    monkeypatch.setattr(monitor.time, "sleep", lambda delay: None)
    module = SimpleNamespace(params={"waiter_timeout": 10, "waiter_delay": 0})
    desired = {"notice_ids": ["new"], "hierarchical_notices": [], "notice_content_template_bindings": []}
    assert monitor.wait_for_policy_notice(module, object(), object(), "policy-1", "monitor", desired) == current


def test_notice_waiter_fails_if_state_does_not_converge(monkeypatch):
    stale = {"NoticeIds": ["old"], "HierarchicalNotices": [], "NoticeContentTmplBindInfos": []}
    monkeypatch.setattr(monitor, "find_policy", lambda *args: stale)
    ticks = iter([0, 2])
    monkeypatch.setattr(monitor.time, "time", lambda: next(ticks))

    def fail_json(**kwargs):
        raise ValueError(kwargs["msg"])

    module = SimpleNamespace(
        params={"waiter_timeout": 1, "waiter_delay": 0},
        fail_json=fail_json,
    )
    desired = {"notice_ids": ["new"], "hierarchical_notices": [], "notice_content_template_bindings": []}
    with pytest.raises(ValueError, match="Timed out waiting"):
        monitor.wait_for_policy_notice(module, object(), object(), "policy-1", "monitor", desired)
