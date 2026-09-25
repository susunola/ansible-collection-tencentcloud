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


# ---------------------------------------------------------------------------
# an ambiguous name is refused rather than guessed at
# ---------------------------------------------------------------------------

def test_find_policy_rejects_an_ambiguous_name():
    """Two policies can share a name; picking one would manage the wrong
    alarm policy, so the lookup fails and asks for an id instead."""
    module = FakeModule([SimpleNamespace(
        Policies=[FakePolicy({"PolicyId": "policy-1", "PolicyName": "same"}),
                  FakePolicy({"PolicyId": "policy-2", "PolicyName": "same"})],
        TotalCount=2)])
    models = SimpleNamespace(DescribeAlarmPoliciesRequest=SimpleNamespace)

    def fail_json(**kwargs):
        raise ValueError(kwargs["msg"])

    module.fail_json = fail_json
    with pytest.raises(ValueError, match="Multiple alarm policies"):
        find_policy(module, SimpleNamespace(DescribeAlarmPolicies=object()), models,
                    None, "same", "monitor")


def test_an_empty_page_ends_the_walk():
    module = FakeModule([SimpleNamespace(Policies=[], TotalCount=0)])
    models = SimpleNamespace(DescribeAlarmPoliciesRequest=SimpleNamespace)
    assert find_policy(module, SimpleNamespace(DescribeAlarmPolicies=object()), models,
                       "policy-9", None, "monitor") is None


# ---------------------------------------------------------------------------
# convergence and the waiter around it
# ---------------------------------------------------------------------------

def desired_policy(**overrides):
    """The mapping ``_policy_converged`` compares against.

    ``Remark`` and ``Enable`` are read unconditionally, so every caller has to
    carry them; the rest are optional and None means "not requested".
    """
    desired = {
        "PolicyName": "x", "Remark": "", "Enable": True, "Condition": None,
        "EventCondition": None, "Filter": None, "GroupBy": None,
        "TriggerTasks": None, "HierarchicalNotices": None,
        "NoticeContentTmplBindInfos": None, "NoticeIds": [],
    }
    desired.update(overrides)
    return desired


def test_a_policy_that_does_not_exist_has_not_converged():
    assert monitor._policy_converged(None, desired_policy()) is False


def test_a_policy_converges_when_the_requested_fields_match():
    current = {"PolicyName": "x", "Remark": "", "Enable": 1, "NoticeIds": ["b", "a"]}
    assert monitor._policy_converged(current, desired_policy(NoticeIds=["a", "b"])) is True


def test_a_policy_has_not_converged_while_a_remark_differs():
    current = {"PolicyName": "x", "Remark": "old", "Enable": 1, "NoticeIds": []}
    assert monitor._policy_converged(current, desired_policy(Remark="new")) is False


def test_a_waiter_returns_the_converged_policy(monkeypatch):
    converged = {"PolicyId": "policy-1", "PolicyName": "x", "Remark": "",
                 "Enable": 1, "NoticeIds": []}
    monkeypatch.setattr(monitor, "find_policy", lambda *args: converged)
    monkeypatch.setattr(monitor.time, "sleep", lambda delay: None)
    module = SimpleNamespace(params={"waiter_timeout": 10, "waiter_delay": 0})
    assert monitor.wait_for_policy(module, object(), object(), "policy-1", "x", "monitor",
                                   desired=desired_policy()) == converged


def test_an_absent_waiter_returns_when_the_policy_is_gone(monkeypatch):
    monkeypatch.setattr(monitor, "find_policy", lambda *args: None)
    monkeypatch.setattr(monitor.time, "sleep", lambda delay: None)
    module = SimpleNamespace(params={"waiter_timeout": 10, "waiter_delay": 0})
    assert monitor.wait_for_policy(module, object(), object(), "policy-1", "x", "monitor",
                                   absent=True) is None


def fail_json(**kwargs):
    """Stand in for the module's fail_json, which exits the process."""
    raise ValueError(kwargs["msg"])


def test_a_waiter_fails_when_the_policy_never_converges(monkeypatch):
    monkeypatch.setattr(monitor, "find_policy",
                        lambda *args: {"PolicyName": "other", "Remark": "", "Enable": 1})
    ticks = iter([0, 2])
    monkeypatch.setattr(monitor.time, "time", lambda: next(ticks))
    module = SimpleNamespace(params={"waiter_timeout": 1, "waiter_delay": 0},
                             fail_json=fail_json)
    with pytest.raises(ValueError, match="Timed out waiting for alarm policy convergence"):
        monitor.wait_for_policy(module, object(), object(), "policy-1", "x", "monitor",
                                desired=desired_policy())


def test_an_absent_waiter_fails_when_the_policy_stays(monkeypatch):
    monkeypatch.setattr(monitor, "find_policy", lambda *args: {"PolicyId": "policy-1"})
    ticks = iter([0, 2])
    monkeypatch.setattr(monitor.time, "time", lambda: next(ticks))
    module = SimpleNamespace(params={"waiter_timeout": 1, "waiter_delay": 0},
                             fail_json=fail_json)
    with pytest.raises(ValueError, match="Timed out waiting"):
        monitor.wait_for_policy(module, object(), object(), "policy-1", "x", "monitor",
                                absent=True)


# ---------------------------------------------------------------------------
# the request builder
# ---------------------------------------------------------------------------

class FakeModels(object):
    """Every model name resolves to a plain attribute store."""

    def __getattr__(self, name):
        return type(name, (object,), {})


def create_params(**overrides):
    params = {
        "module": "monitor", "name": "cpu-high", "monitor_type": "MT_QCE",
        "namespace": "QCE/CVM", "remark": "", "enabled": True,
        "condition": None, "event_condition": None, "notice_ids": ["notice-1"],
        "project_id": None, "filter": None, "group_by": None,
        "trigger_tasks": None, "hierarchical_notices": None,
        "notice_content_template_bindings": None, "tags": None,
    }
    params.update(overrides)
    return params


def test_create_request_sends_tags_in_a_stable_order():
    """Tags are a mapping, and the request is compared field by field, so the
    order they are written in has to be the same on every run."""
    request = monitor.build_create_request(
        FakeModels(), create_params(tags={"env": "prod", "team": "core"}))
    assert [(tag.Key, tag.Value) for tag in request.Tags] == [
        ("env", "prod"), ("team", "core")]
    assert request.Enable == 1


def test_create_request_omits_tags_when_none_are_given():
    request = monitor.build_create_request(FakeModels(), create_params())
    assert not hasattr(request, "Tags")


def test_a_disabled_policy_is_sent_as_zero():
    request = monitor.build_create_request(FakeModels(), create_params(enabled=False))
    assert request.Enable == 0
