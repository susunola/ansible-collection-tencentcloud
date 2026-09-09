"""Unit tests for the cmq_queue write module (run_module flows).

The module reconciles a CMQ queue lifecycle and delivery settings using the
TDMQ CMQ management actions. The fake TDMQ client mutates a queue store so
the post-write describe and the module's convergence waiter return
immediately.

Scenario matrix:

* argument validation (missing queue_name)
* no-op when delivery settings match
* queue creation (real and check-mode dry run)
* delivery-setting drift applies ``ModifyCmqQueueAttribute``
* immutable ``max_msg_size`` drift fails
* deletion flows (present, absent no-op, check-mode dry run)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cmq_queue as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

P = {
    "queue_name": "jobs",
    "max_msg_heap_num": 1000000,
    "polling_wait_seconds": 10,
    "visibility_timeout": 30,
    "max_msg_size": 65536,
    "msg_retention_seconds": 345600,
    "rewind_seconds": 0,
}

QUEUE = {
    "QueueName": "jobs",
    "MaxMsgHeapNum": 1000000,
    "PollingWaitSeconds": 10,
    "VisibilityTimeout": 30,
    "MaxMsgSize": 65536,
    "MsgRetentionSeconds": 345600,
    "RewindSeconds": 0,
}


def _args(**overrides):
    params = dict(P)
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a CMQ queue store."""

    def __init__(self, queues=None):
        self.queues = [copy.deepcopy(q) for q in (queues or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCmqQueues(self, request):
        self._record("DescribeCmqQueues", request)
        name = getattr(request, "QueueName", None)
        matches = [q for q in self.queues if q.get("QueueName") == name]
        return SimpleNamespace(QueueList=[FakeResource(q) for q in matches])

    def CreateCmqQueue(self, request):
        self._record("CreateCmqQueue", request)
        self.queues.append(self._from_request(request))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyCmqQueueAttribute(self, request):
        self._record("ModifyCmqQueueAttribute", request)
        for queue in self.queues:
            if queue.get("QueueName") == getattr(request, "QueueName", None):
                for key in QUEUE:
                    if key == "QueueName":
                        continue
                    value = getattr(request, key, None)
                    if value is not None:
                        queue[key] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCmqQueue(self, request):
        self._record("DeleteCmqQueue", request)
        self.queues = [q for q in self.queues if q.get("QueueName") != getattr(request, "QueueName", None)]
        return SimpleNamespace(RequestId="req-fake")

    def _from_request(self, request):
        return {key: getattr(request, key, None) for key in QUEUE}


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cmq", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_queue_name_fails(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_settings_match(monkeypatch):
    fake = FakeTdmqClient(queues=[QUEUE])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"]["QueueName"] == "jobs"
    assert [c for c, unused in fake.calls] == ["DescribeCmqQueues"]


def test_create_queue(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["VisibilityTimeout"] == 30
    assert len(fake.queues) == 1
    create_call = next((c, r) for c, r in fake.calls if c == "CreateCmqQueue")
    assert getattr(create_call[1], "QueueName") == "jobs"
    assert getattr(create_call[1], "PollingWaitSeconds") == 10


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.queues == []
    assert "CreateCmqQueue" not in [c for c, unused in fake.calls]


def test_visibility_drift_updates_queue(monkeypatch):
    stored = dict(QUEUE)
    stored["VisibilityTimeout"] = 30
    fake = FakeTdmqClient(queues=[stored])
    _make_module(monkeypatch, fake)
    _args(visibility_timeout=45)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"]["VisibilityTimeout"] == 45
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyCmqQueueAttribute")
    assert getattr(modify_call[1], "VisibilityTimeout") == 45
    assert getattr(modify_call[1], "MaxMsgSize") is None


def test_immutable_max_msg_size_drift_fails(monkeypatch):
    stored = dict(QUEUE)
    stored["MaxMsgSize"] = 1048576
    fake = FakeTdmqClient(queues=[stored])
    _make_module(monkeypatch, fake)
    _args(max_msg_size=65536)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "MaxMsgSize" in payload["immutable_changes"]


def test_delete_queue(monkeypatch):
    fake = FakeTdmqClient(queues=[QUEUE])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["queue"] is None
    assert fake.queues == []
    delete_call = next((c, r) for c, r in fake.calls if c == "DeleteCmqQueue")
    assert getattr(delete_call[1], "QueueName") == "jobs"


def test_delete_missing_queue_is_idempotent(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["queue"] is None
    assert "DeleteCmqQueue" not in [c for c, unused in fake.calls]


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(queues=[QUEUE])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.queues) == 1
    assert "DeleteCmqQueue" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCmqQueues(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cmq_queue.py)
# ---------------------------------------------------------------------------


def test_request_builders_map_attributes():
    assert mod.build_describe_request(FakeModels(), "jobs").QueueName == "jobs"
    assert mod.build_create_request(FakeModels(), P).PollingWaitSeconds == 10
    assert mod.build_update_request(FakeModels(), P).VisibilityTimeout == 30
    assert mod.build_delete_request(FakeModels(), "jobs").QueueName == "jobs"
