"""Unit tests for the monitor_alarm_policy_notice write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Monitor client.
The module reuses the shared alarm-policy helpers from ``module_utils/monitor``
(``find_policy`` / ``build_notice_request``), whose Describe feeds on policy
items exposed through ``to_json_string`` like the real SDK models.

Scenario matrix:

* a missing policy fails with an explicit guard
* no-op when notice ids / hierarchical notices / content templates match
* drift in each of the three binding dimensions triggers ``ModifyAlarmPolicyNotice``
* check-mode dry run (changed True, no modify call)
* the refind-after-update flow
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_alarm_policy_notice as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeRequest,
    module_args,
    run,
)

POLICY = {
    "PolicyId": "policy-1a2b3c4d",
    "PolicyName": "cvm-cpu-high",
    "NoticeIds": ["notice-1"],
    "HierarchicalNotices": [{"NoticeId": "hn-1", "State": 1}],
    "NoticeContentTmplBindInfos": [{"TemplateId": "tmpl-1"}],
}


def _policy(**overrides):
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"policy_id": "policy-1a2b3c4d"}
    params.update(overrides)
    return module_args(**params)


class FakePolicyItem(object):
    """Describe response item; ``find_policy`` reads it through to_json_string."""

    def __init__(self, data):
        self._data = dict(data)

    def to_json_string(self):
        return json.dumps(self._data)


def _plain(value):
    """Convert SDK model stand-ins (FakeRequest) back into plain structures."""
    if isinstance(value, FakeRequest):
        return _plain(value.__dict__)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class FakeMonitorClient(object):
    """In-memory Cloud Monitor client mutating a small alarm-policy store."""

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(t) for t in (policies or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, policy_id):
        for item in self.policies:
            if item.get("PolicyId") == policy_id:
                return item
        return None

    def DescribeAlarmPolicies(self, request):
        self._record("DescribeAlarmPolicies", request)
        matched = list(self.policies)
        return SimpleNamespace(
            PolicyList=[FakePolicyItem(t) for t in matched],
            TotalCount=len(matched),
        )

    def ModifyAlarmPolicyNotice(self, request):
        self._record("ModifyAlarmPolicyNotice", request)
        item = self._find(getattr(request, "PolicyId", None))
        if item is not None:
            item["NoticeIds"] = list(getattr(request, "NoticeIds", None) or [])
            if getattr(request, "HierarchicalNotices", None) is not None:
                item["HierarchicalNotices"] = _plain(request.HierarchicalNotices)
            if getattr(request, "NoticeContentTmplBindInfos", None) is not None:
                item["NoticeContentTmplBindInfos"] = _plain(request.NoticeContentTmplBindInfos)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_monitor", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_missing_policy_fails(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Alarm policy was not found"
    assert payload["policy_id"] == "policy-1a2b3c4d"


# ---------------------------------------------------------------------------
# idempotent flow
# ---------------------------------------------------------------------------


def test_notices_up_to_date_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _args(
        notice_ids=["notice-1"],
        hierarchical_notices=[{"NoticeId": "hn-1", "State": 1}],
        notice_content_template_bindings=[{"TemplateId": "tmpl-1"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Alarm policy notices are up to date"
    assert result["notice"]["notice_ids"] == ["notice-1"]
    assert [c for c, unused in fake.calls] == ["DescribeAlarmPolicies"]


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_notice_ids_drift_updates(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _args(
        notice_ids=["notice-2"],
        hierarchical_notices=[{"NoticeId": "hn-1", "State": 1}],
        notice_content_template_bindings=[{"TemplateId": "tmpl-1"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Alarm policy notices updated"
    assert result["notice"]["notice_ids"] == ["notice-2"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyNotice" in ops
    assert fake.policies[0]["NoticeIds"] == ["notice-2"]


def test_hierarchical_notices_drift_updates(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _args(
        notice_ids=["notice-1"],
        hierarchical_notices=[{"NoticeId": "hn-2", "State": 1}],
        notice_content_template_bindings=[{"TemplateId": "tmpl-1"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notice"]["hierarchical_notices"] == [{"NoticeId": "hn-2", "State": 1}]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyNotice" in ops


def test_content_template_bindings_drift_updates(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _args(
        notice_ids=["notice-1"],
        hierarchical_notices=[{"NoticeId": "hn-1", "State": 1}],
        notice_content_template_bindings=[{"TemplateId": "tmpl-2"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notice"]["notice_content_template_bindings"] == [{"TemplateId": "tmpl-2"}]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyNotice" in ops


# ---------------------------------------------------------------------------
# check mode
# ---------------------------------------------------------------------------


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _args(
        _ansible_check_mode=True,
        notice_ids=["notice-2"],
        hierarchical_notices=[{"NoticeId": "hn-1", "State": 1}],
        notice_content_template_bindings=[{"TemplateId": "tmpl-1"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update alarm policy notices"
    assert result["notice"]["notice_ids"] == ["notice-1"]
    assert "ModifyAlarmPolicyNotice" not in [c for c, unused in fake.calls]
    assert fake.policies[0]["NoticeIds"] == ["notice-1"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAlarmPolicies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
