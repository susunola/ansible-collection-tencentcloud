"""Unit tests for the monitor_alarm_policy write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Monitor client
whose write operations mutate the alarm-policy store, so the module's
post-write ``find_policy`` waiter converges immediately.

Scenario matrix:

* absent on a missing policy (idempotent no-op)
* absent with a matching policy (check-mode dry run and the real delete)
* creation when missing (required ``namespace`` guard, check mode, waiting)
* no-op when nothing drifts
* drift updates (remark, enabled status, notice ids, condition, group_by)
* the immutable ``project_id`` / ``tags`` guards
* identity guards (``policy_id`` or ``name``, ``namespace`` for create)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_alarm_policy as mod
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
    "Remark": "",
    "Enable": 1,
    "MonitorType": "MT_QCE",
    "Namespace": "QCE/CVM",
    "Condition": {"IsUnionRule": 0, "Rules": []},
    "EventCondition": None,
    "NoticeIds": [],
    "ProjectId": 0,
    "GroupBy": [],
    "Filter": None,
    "TriggerTasks": [],
    "HierarchicalNotices": [],
    "NoticeContentTmplBindInfos": [],
    "Tags": [],
}


def _policy(**overrides):
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "cvm-cpu-high"}
    params.update(overrides)
    return module_args(**params)


class FakePolicyItem(object):
    """Describe response item; the module reads it through ``to_json_string``."""

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
        self._next = 0

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
        name = getattr(request, "PolicyName", None)
        if name:
            matched = [t for t in matched if t.get("PolicyName") == name]
        return SimpleNamespace(
            PolicyList=[FakePolicyItem(t) for t in matched],
            TotalCount=len(matched),
        )

    def CreateAlarmPolicy(self, request):
        self._record("CreateAlarmPolicy", request)
        self._next += 1
        item = {
            "PolicyId": "policy-new-%03d" % self._next,
            "PolicyName": getattr(request, "PolicyName", None),
            "Remark": getattr(request, "Remark", ""),
            "Enable": getattr(request, "Enable", 1),
            "MonitorType": getattr(request, "MonitorType", None),
            "Namespace": getattr(request, "Namespace", None),
            "Condition": _plain(getattr(request, "Condition", None)),
            "EventCondition": _plain(getattr(request, "EventCondition", None)),
            "NoticeIds": list(getattr(request, "NoticeIds", None) or []),
            "ProjectId": getattr(request, "ProjectId", None),
            "Filter": _plain(getattr(request, "Filter", None)),
            "GroupBy": list(getattr(request, "GroupBy", None) or []),
            "TriggerTasks": _plain(getattr(request, "TriggerTasks", None)),
            "HierarchicalNotices": _plain(getattr(request, "HierarchicalNotices", None)),
            "NoticeContentTmplBindInfos": _plain(getattr(request, "NoticeContentTmplBindInfos", None)),
        }
        tags = getattr(request, "Tags", None)
        if tags is not None:
            item["Tags"] = [{"Key": tag.Key, "Value": tag.Value} for tag in tags]
        self.policies.append(item)
        return SimpleNamespace(PolicyId=item["PolicyId"], RequestId="req-fake")

    def DeleteAlarmPolicy(self, request):
        self._record("DeleteAlarmPolicy", request)
        ids = set(getattr(request, "PolicyIds", None) or [])
        self.policies = [t for t in self.policies if t.get("PolicyId") not in ids]
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAlarmPolicyInfo(self, request):
        self._record("ModifyAlarmPolicyInfo", request)
        item = self._find(getattr(request, "PolicyId", None))
        if item is not None:
            key = getattr(request, "Key", None)
            if key == "NAME":
                item["PolicyName"] = getattr(request, "Value", None)
            elif key == "REMARK":
                item["Remark"] = getattr(request, "Value", None)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAlarmPolicyStatus(self, request):
        self._record("ModifyAlarmPolicyStatus", request)
        item = self._find(getattr(request, "PolicyId", None))
        if item is not None:
            item["Enable"] = getattr(request, "Enable", item.get("Enable"))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAlarmPolicyCondition(self, request):
        self._record("ModifyAlarmPolicyCondition", request)
        item = self._find(getattr(request, "PolicyId", None))
        if item is not None:
            if getattr(request, "Condition", None) is not None:
                item["Condition"] = _plain(request.Condition)
            if getattr(request, "EventCondition", None) is not None:
                item["EventCondition"] = _plain(request.EventCondition)
            if getattr(request, "Filter", None) is not None:
                item["Filter"] = _plain(request.Filter)
            if getattr(request, "GroupBy", None) is not None:
                item["GroupBy"] = list(request.GroupBy)
            item["NoticeIds"] = list(getattr(request, "NoticeIds", None) or [])
        return SimpleNamespace(RequestId="req-fake")

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

    def ModifyAlarmPolicyTasks(self, request):
        self._record("ModifyAlarmPolicyTasks", request)
        item = self._find(getattr(request, "PolicyId", None))
        if item is not None:
            item["TriggerTasks"] = _plain(getattr(request, "TriggerTasks", None)) or []
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_monitor", lambda: (models or FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identity guards
# ---------------------------------------------------------------------------


def test_requires_policy_id_or_name(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _base(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "policy_id or name is required" in exc.value.args[0]["msg"]


def test_create_requires_namespace(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "namespace is required to create an alarm policy" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_policy_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-policy")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAlarmPolicies"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is not None
    assert len(fake.policies) == 1
    assert "DeleteAlarmPolicy" not in [c for c, unused in fake.calls]


def test_absent_deletes_policy(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="absent", policy_id="policy-1a2b3c4d", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    assert fake.policies == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteAlarmPolicy" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_policy(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="cvm-cpu-high",
        namespace="QCE/CVM",
        remark="high cpu",
        condition={"IsUnionRule": 0, "Rules": [{"MetricName": "cpu_usage"}]},
        notice_ids=["notice-1"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyId"].startswith("policy-new-")
    assert result["policy"]["PolicyName"] == "cvm-cpu-high"
    assert result["policy"]["Remark"] == "high cpu"
    assert result["policy"]["Condition"]["IsUnionRule"] == 0
    assert result["policy"]["NoticeIds"] == ["notice-1"]
    assert len(fake.policies) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAlarmPolicies"
    assert "CreateAlarmPolicy" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(policies=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="cvm-cpu-high",
        namespace="QCE/CVM",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    assert fake.policies == []
    assert "CreateAlarmPolicy" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-policy flows
# ---------------------------------------------------------------------------


def test_existing_policy_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["PolicyId"] == "policy-1a2b3c4d"


def test_update_remark(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", remark="tuned by sre")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Remark"] == "tuned by sre"
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyInfo" in ops


def test_update_disables_policy(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Enable"] == 0
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyStatus" in ops


def test_update_notice_ids(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", notice_ids=["notice-9"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["NoticeIds"] == ["notice-9"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyNotice" in ops


def test_update_condition(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", condition={"IsUnionRule": 1})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Condition"] == {"IsUnionRule": 1}
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyCondition" in ops


def test_update_group_by(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy(GroupBy=[])])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", group_by=["instance_id"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["GroupBy"] == ["instance_id"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyCondition" in ops


def test_update_trigger_tasks(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", trigger_tasks=[{"TaskType": "RUN_GROUP"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["TriggerTasks"] == [{"TaskType": "RUN_GROUP"}]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAlarmPolicyTasks" in ops


def test_update_requires_wait_to_converge(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", remark="waited remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    # update paths always wait for convergence through a second describe
    describes = [c for c, unused in fake.calls if c == "DescribeAlarmPolicies"]
    assert len(describes) >= 2


# ---------------------------------------------------------------------------
# immutable guards
# ---------------------------------------------------------------------------


def test_immutable_project_id_drift_fails(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy(ProjectId=1)])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", project_id=99)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Alarm policy has immutable attribute drift"
    assert "project_id" in payload["immutable_drift"]


def test_immutable_tags_drift_fails(monkeypatch):
    fake = FakeMonitorClient(policies=[_policy(Tags=[{"Key": "env", "Value": "prod"}])])
    _make_module(monkeypatch, fake)
    _base(state="present", namespace="QCE/CVM", tags={"env": "dev"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Alarm policy has immutable attribute drift"
    assert "tags" in payload["immutable_drift"]


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
    _base(state="present", namespace="QCE/CVM")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
