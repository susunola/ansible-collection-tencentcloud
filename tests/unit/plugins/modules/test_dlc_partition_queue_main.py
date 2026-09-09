"""Unit tests for the dlc_partition_queue write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_partition_queue as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USAGE = [
    {
        "ResourceSpec": {
            "ResourceType": "CU",
            "BillingItem": "sv_dlc_standard_cu_standard_cu",
            "Spec": "0:1:4:0",
        },
        "Min": 32,
        "Max": 128,
    }
]
QUEUE = {
    "Id": 101,
    "PartitionCode": "rp-8b0a1c2d",
    "QueueName": "notebooks",
    "QueueType": 1,
    "Description": "Interactive analytics capacity",
    "IsDefault": False,
    "ResourceUsage": USAGE,
}


def _queue(**overrides):
    item = copy.deepcopy(QUEUE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"partition_code": "rp-8b0a1c2d", "name": "notebooks"}
    params.update(overrides)
    return module_args(**params)


def _usages():
    return [
        {
            "resource_type": "CU",
            "billing_item": "sv_dlc_standard_cu_standard_cu",
            "spec": "0:1:4:0",
            "min": 32,
            "max": 128,
        }
    ]


class FakeDlcClient(object):
    """In-memory DLC client mutating a partition-queue store."""

    def __init__(self, queues=None):
        self.queues = [copy.deepcopy(t) for t in (queues or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, name, partition_code):
        for item in self.queues:
            if item.get("QueueName") == name and item.get("PartitionCode") == partition_code:
                return item
        return None

    def DescribePartitionQueues(self, request):
        self._record("DescribePartitionQueues", request)
        matches = [t for t in self.queues if t.get("PartitionCode") == getattr(request, "PartitionCode", None)]
        return SimpleNamespace(QueueList=[FakeResource(dict(t)) for t in matches], Total=len(matches))

    def CreatePartitionQueue(self, request):
        self._record("CreatePartitionQueue", request)
        self._next += 1
        item = {"Id": 1000 + self._next, "PartitionCode": request.PartitionCode, "QueueName": request.QueueName, "IsDefault": False}
        for attr in ("Description", "QueueType", "ResourceUsages"):
            if hasattr(request, attr):
                value = getattr(request, attr)
                if attr == "ResourceUsages":
                    item["ResourceUsage"] = value
                else:
                    item[attr] = value
        self.queues.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def ModifyPartitionQueue(self, request):
        self._record("ModifyPartitionQueue", request)
        item = None
        for candidate in self.queues:
            if candidate.get("Id") == getattr(request, "Id", None):
                item = candidate
                break
        if item is None:
            item = self._find(getattr(request, "QueueName", None), getattr(request, "PartitionCode", None))
        if item is not None:
            for attr in ("Description", "QueueType"):
                if hasattr(request, attr):
                    item[attr] = getattr(request, attr)
            if hasattr(request, "ResourceUsages"):
                item["ResourceUsage"] = getattr(request, "ResourceUsages")
        return SimpleNamespace(RequestId="req-fake")

    def DeletePartitionQueue(self, request):
        self._record("DeletePartitionQueue", request)
        self.queues = [t for t in self.queues if t.get("Id") != getattr(request, "Id", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_resource_usage_min_above_max_fails(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    usage = _usages()[0]
    usage["min"] = 128
    usage["max"] = 32
    _base(state="absent", resource_usages=[usage])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "min must not exceed max" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"] is None
    assert result["queue_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribePartitionQueues"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_default_queue_requires_allow_delete_default(monkeypatch):
    fake = FakeDlcClient(queues=[_queue(IsDefault=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_default=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"] is None
    assert len(fake.queues) == 1
    assert "DeletePartitionQueue" not in [c for c, unused in fake.calls]


def test_absent_deletes_queue(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"] is None
    assert fake.queues == []
    ops = [c for c, unused in fake.calls]
    assert "DeletePartitionQueue" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["queue_type", "resource_usages"]


def test_create_queue(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        queue_type=1,
        description="Interactive analytics capacity",
        resource_usages=_usages(),
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["QueueName"] == "notebooks"
    assert result["queue"]["QueueType"] == 1
    assert result["queue"]["ResourceUsage"][0]["Min"] == 32
    assert result["queue_id"] == 1001
    assert len(fake.queues) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePartitionQueues"
    assert "CreatePartitionQueue" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        queue_type=1,
        resource_usages=_usages(),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["QueueName"] == "notebooks"
    assert result["queue_id"] is None
    assert fake.queues == []
    assert "CreatePartitionQueue" not in [c for c, unused in fake.calls]


def test_create_queue_without_wait(monkeypatch):
    fake = FakeDlcClient(queues=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        queue_type=2,
        resource_usages=_usages(),
        wait=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue_id"] == 1001


# ---------------------------------------------------------------------------
# existing-queue flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        queue_type=1,
        description="Interactive analytics capacity",
        resource_usages=_usages(),
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"]["Id"] == 101
    assert result["queue_id"] == 101
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribePartitionQueues"]


def test_update_description(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["Description"] == "renamed"
    assert "ModifyPartitionQueue" in [c for c, unused in fake.calls]


def test_resource_scale_down_requires_allow_scale_down(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    usage = _usages()[0]
    usage["min"] = 16
    _base(state="present", resource_usages=[usage])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_scale_down=true" in payload["msg"]
    drift = payload["resource_usage_drift"]
    assert drift[0][0]["Min"] == 32
    assert drift[1][0]["Min"] == 16


def test_resource_scale_down_authorized_applies(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    usage = _usages()[0]
    usage["min"] = 16
    _base(state="present", resource_usages=[usage], allow_scale_down=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["ResourceUsage"][0]["Min"] == 16
    assert "ModifyPartitionQueue" in [c for c, unused in fake.calls]


def test_resource_scale_up_applies_without_guard(monkeypatch):
    fake = FakeDlcClient(queues=[_queue()])
    _make_module(monkeypatch, fake)
    usage = _usages()[0]
    usage["max"] = 256
    _base(state="present", resource_usages=[usage], wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["ResourceUsage"][0]["Max"] == 256


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(queues=[_queue(), _queue(Id=102)])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC partition queues matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePartitionQueues(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_partition_queue.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    DescribePartitionQueuesRequest = LegacyObject
    CreatePartitionQueueRequest = LegacyObject
    ModifyPartitionQueueRequest = LegacyObject
    DeletePartitionQueueRequest = LegacyObject


def legacy_params():
    return {
        "partition_code": "rp-1",
        "name": "notebooks",
        "queue_type": 1,
        "description": "interactive",
        "resource_usages": [
            {"resource_type": "CU", "billing_item": "standard", "instance_type": None, "spec": "0:1:4:0", "gpu_type": None, "min": 32, "max": 128}
        ],
    }


def test_describe_scopes_partition_and_page():
    request = mod.describe_request(LegacyModels, "rp-1", 2)
    assert request.PartitionCode == "rp-1" and request.Page == 2 and request.PageSize == 200


def test_create_maps_nested_resource_contract():
    request = mod.make_request(LegacyModels, legacy_params())
    assert request.QueueName == "notebooks" and request.ResourceUsages[0]["ResourceSpec"]["BillingItem"] == "standard"


def test_modify_and_delete_use_stable_id():
    assert mod.make_request(LegacyModels, legacy_params(), update=True, queue_id=42).Id == 42
    assert mod.delete_request(LegacyModels, legacy_params(), 42).Id == 42


def test_normalized_readback_is_idempotent():
    current = mod.normalize(
        {
            "Description": "interactive",
            "QueueType": 1,
            "ResourceUsage": [
                {"ResourceSpec": {"ResourceType": "CU", "BillingItem": "standard", "Spec": "0:1:4:0", "SpecDesc": "ignored"}, "Min": 32, "Max": 128}
            ],
        }
    )
    assert mod.drift(legacy_params(), current) == {}


def test_scale_down_detects_reduction_and_removal():
    old = mod.normalize({"ResourceUsage": [{"ResourceSpec": {"BillingItem": "standard"}, "Min": 32, "Max": 128}]})["ResourceUsage"]
    lower = mod.normalize({"ResourceUsage": [{"ResourceSpec": {"BillingItem": "standard"}, "Min": 16, "Max": 64}]})["ResourceUsage"]
    assert mod.scale_down(old, lower) is True and mod.scale_down(old, []) is True and mod.scale_down(lower, old) is False
