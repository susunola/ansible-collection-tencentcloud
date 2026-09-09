"""Unit tests for the vpc_flow_log write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client whose
write operations mutate the flow-log store, so the post-write describe
refetch and the ``wait_for_flow_log`` waiter converge on the first poll.

Scenario matrix:

* absent on a missing flow log (idempotent no-op)
* absent with a matching flow log (check-mode dry run and the real delete)
* creation when missing (missing creation parameters, check-mode dry run and
  the happy path)
* no-op when nothing drifts
* attribute drift updates (name / description / period)
* enable/disable collection drift and its check mode
* the ambiguous-name guard, the invalid-choice guard, required_one_of guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpc_flow_log as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VPC_ID = "vpc-abc"
FLOW_LOG_ID = "fl-1a2b3c4d"

FLOW_LOG = {
    "FlowLogId": FLOW_LOG_ID,
    "FlowLogName": "app-eni-traffic",
    "VpcId": VPC_ID,
    "ResourceType": "NETWORKINTERFACE",
    "ResourceId": "eni-xyz",
    "TrafficType": "ALL",
    "CloudLogId": "topic-12345678",
    "FlowLogDescription": "",
    "StorageType": "cls",
    "Enable": True,
}


def _flow_log(**overrides):
    item = copy.deepcopy(FLOW_LOG)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, traffic_type, period,
    # resource_type) must not be pre-filled with None. flow_log_id/name are a
    # required_one_of pair so the _name_args/_id_args helpers supply exactly
    # one of them. vpc_id is always required.
    params = {"vpc_id": VPC_ID}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"vpc_id": VPC_ID, "name": "app-eni-traffic"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"vpc_id": VPC_ID, "flow_log_id": FLOW_LOG_ID}
    params.update(overrides)
    return module_args(**params)


_CREATE_REQUIRED = {
    "name": "app-eni-traffic",
    "resource_type": "NETWORKINTERFACE",
    "resource_id": "eni-xyz",
    "cls_topic_id": "topic-12345678",
}


class FakeVpcClient(object):
    """In-memory VPC client mutating a small flow-log store."""

    def __init__(self, flow_logs=None):
        self.flow_logs = [copy.deepcopy(t) for t in (flow_logs or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _log(self, flow_log_id):
        for item in self.flow_logs:
            if item.get("FlowLogId") == flow_log_id:
                return item
        return None

    def DescribeFlowLogs(self, request):
        self._record("DescribeFlowLogs", request)
        page = [dict(t) for t in self.flow_logs if t.get("VpcId") == getattr(request, "VpcId", None)]
        return SimpleNamespace(
            FlowLogSet=[FakeResource(t) for t in page],
            TotalNum=len(page),
        )

    def CreateFlowLog(self, request):
        self._record("CreateFlowLog", request)
        flow_log_id = "fl-new-%d" % (len(self.flow_logs) + 1)
        item = {
            "FlowLogId": flow_log_id,
            "FlowLogName": getattr(request, "FlowLogName", None),
            "VpcId": getattr(request, "VpcId", None),
            "ResourceType": getattr(request, "ResourceType", None),
            "ResourceId": getattr(request, "ResourceId", None),
            "TrafficType": getattr(request, "TrafficType", None),
            "CloudLogId": getattr(request, "CloudLogId", None),
            "CloudLogRegion": getattr(request, "CloudLogRegion", None),
            "FlowLogDescription": getattr(request, "FlowLogDescription", ""),
            "StorageType": getattr(request, "StorageType", "cls"),
            "Period": getattr(request, "Period", None),
            "Enable": True,
        }
        self.flow_logs.append(item)
        return SimpleNamespace(
            FlowLog=FakeResource({"FlowLogId": flow_log_id}),
            RequestId="req-fake",
        )

    def ModifyFlowLogAttribute(self, request):
        self._record("ModifyFlowLogAttribute", request)
        item = self._log(getattr(request, "FlowLogId", None))
        if item is not None:
            for attr in ("FlowLogName", "FlowLogDescription", "Period"):
                value = getattr(request, attr, None)
                if value is not None:
                    item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def EnableFlowLogs(self, request):
        self._record("EnableFlowLogs", request)
        for flow_log_id in (getattr(request, "FlowLogIds", None) or []):
            item = self._log(flow_log_id)
            if item is not None:
                item["Enable"] = True
        return SimpleNamespace(RequestId="req-fake")

    def DisableFlowLogs(self, request):
        self._record("DisableFlowLogs", request)
        for flow_log_id in (getattr(request, "FlowLogIds", None) or []):
            item = self._log(flow_log_id)
            if item is not None:
                item["Enable"] = False
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFlowLog(self, request):
        self._record("DeleteFlowLog", request)
        self.flow_logs = [t for t in self.flow_logs if t.get("FlowLogId") != getattr(request, "FlowLogId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_log_is_idempotent(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-log")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["flow_log"] is None
    assert result["msg"] == "Flow log is absent"
    assert [c for c, unused in fake.calls] == ["DescribeFlowLogs"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete flow log"
    assert result["flow_log"]["FlowLogId"] == FLOW_LOG_ID
    assert len(fake.flow_logs) == 1
    assert "DeleteFlowLog" not in [c for c, unused in fake.calls]


def test_absent_deletes_flow_log(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Flow log deleted"
    assert result["flow_log"] is None
    assert fake.flow_logs == []
    assert "DeleteFlowLog" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_resource_fields(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="app-eni-traffic")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Required when creating:" in payload["msg"]
    for field in ("resource_type", "resource_id", "cls_topic_id"):
        assert field in payload["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", **_CREATE_REQUIRED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create flow log"
    assert result["flow_log"] is None
    assert fake.flow_logs == []
    assert "CreateFlowLog" not in [c for c, unused in fake.calls]


def test_create_flow_log(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        traffic_type="ALL",
        cls_region="ap-guangzhou",
        description="app ENI traffic",
        **_CREATE_REQUIRED,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Flow log updated"
    flow_log = result["flow_log"]
    assert flow_log["FlowLogId"].startswith("fl-")
    assert flow_log["FlowLogName"] == "app-eni-traffic"
    assert flow_log["Enable"] is True
    assert len(fake.flow_logs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeFlowLogs"
    assert "CreateFlowLog" in ops


# ---------------------------------------------------------------------------
# existing-flow-log flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Flow log is up to date"
    assert result["flow_log"]["FlowLogId"] == FLOW_LOG_ID
    assert "ModifyFlowLogAttribute" not in [c for c, unused in fake.calls]


def test_rename_flow_log(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-log")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Flow log updated"
    assert result["flow_log"]["FlowLogName"] == "renamed-log"
    assert fake.flow_logs[0]["FlowLogName"] == "renamed-log"
    assert "ModifyFlowLogAttribute" in [c for c, unused in fake.calls]


def test_description_drift_update(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", description="now with a purpose")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["flow_log"]["FlowLogDescription"] == "now with a purpose"
    assert "ModifyFlowLogAttribute" in [c for c, unused in fake.calls]


def test_period_drift_update(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", period=300)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["flow_log"]["Period"] == 300
    assert "ModifyFlowLogAttribute" in [c for c, unused in fake.calls]


def test_disable_collection(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Flow log updated"
    assert result["flow_log"]["Enable"] is False
    assert fake.flow_logs[0]["Enable"] is False
    ops = [c for c, unused in fake.calls]
    assert "DisableFlowLogs" in ops
    assert "EnableFlowLogs" not in ops


def test_enable_collection(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log(Enable=False)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["flow_log"]["Enable"] is True
    ops = [c for c, unused in fake.calls]
    assert "EnableFlowLogs" in ops
    assert "DisableFlowLogs" not in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", name="renamed-log", description="new purpose")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update flow log"
    assert fake.flow_logs[0]["FlowLogName"] == "app-eni-traffic"
    assert "ModifyFlowLogAttribute" not in [c for c, unused in fake.calls]
    assert "DisableFlowLogs" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_ambiguous_name_fails(monkeypatch):
    fake = FakeVpcClient(flow_logs=[_flow_log(), _flow_log(FlowLogId="fl-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous flow log reference" in payload["msg"]
    assert payload["ambiguous"] is True
    assert payload["match_count"] == 2


def test_missing_identity_fails(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "flow_log_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_invalid_traffic_type_choice_fails(monkeypatch):
    fake = FakeVpcClient(flow_logs=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", traffic_type="DROP", **_CREATE_REQUIRED)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value of traffic_type must be one of" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeFlowLogs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_vpc_flow_log.py)
# ---------------------------------------------------------------------------


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "eni-flow",
        "vpc_id": "vpc-1",
        "resource_type": "NETWORKINTERFACE",
        "resource_id": "eni-1",
        "traffic_type": "ALL",
        "cls_topic_id": "topic-1",
        "description": "audit",
        "cls_region": None,
        "period": None,
        "tags": {"env": "prod"},
    }
    create = mod.build_create_request(models, params)
    assert create.ResourceId == "eni-1"
    assert create.CloudLogId == "topic-1"
    assert create.Tags[0].Key == "env"
    assert mod.build_toggle_request(models, True, "fl-1").FlowLogIds == ["fl-1"]
    assert mod.build_delete_request(models, "vpc-1", "fl-1").FlowLogId == "fl-1"
