"""Unit tests for the ckafka_datahub_topic write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CKafka client whose
datahub-topic store is mutated by create / modify / delete so post-write
describes converge immediately. The fake DescribeDatahubTopic response carries
``Result`` (a single serializable topic) exactly as the module consumes it.

Scenario matrix:

* absent on a missing topic (idempotent no-op, and a ResourceNotFound variant
  that the module folds into "absent")
* absent with a matching topic (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the topic already matches (note/retention/partition)
* retention/note drift triggers an update; partition drift is immutable and
  fails
* returned credentials are sanitised out of the payload
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_datahub_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = {
    "Name": "1250000000-orders-stream",
    "PartitionNum": 6,
    "RetentionMs": 604800000,
    "Note": "Order event stream",
    "UserName": "secret-username",
    "Password": "secret-password",
}


class FakeNotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.DatahubTopic"


def _topic(**overrides):
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "name": "1250000000-orders-stream",
        "partition_num": 6,
        "retention_ms": 604800000,
        "note": "Order event stream",
    }
    params.update(overrides)
    return module_args(**params)


class FakeCkafkaClient(object):
    """In-memory CKafka client mutating a single-topic-per-name store."""

    def __init__(self, topic=None, raise_when_missing=False):
        self.topic = copy.deepcopy(topic)
        self.raise_when_missing = raise_when_missing
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDatahubTopic(self, request):
        self._record("DescribeDatahubTopic", request)
        if self.topic is None and self.raise_when_missing:
            raise FakeNotFound("no such topic")
        return SimpleNamespace(Result=FakeResource(self.topic) if self.topic is not None else None)

    def CreateDatahubTopic(self, request):
        self._record("CreateDatahubTopic", request)
        self.topic = {
            "Name": request.Name,
            "PartitionNum": request.PartitionNum,
            "RetentionMs": request.RetentionMs,
            "Note": request.Note or "",
        }
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDatahubTopic(self, request):
        self._record("ModifyDatahubTopic", request)
        if self.topic is not None:
            self.topic["RetentionMs"] = request.RetentionMs
            self.topic["Note"] = request.Note or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDatahubTopic(self, request):
        self._record("DeleteDatahubTopic", request)
        self.topic = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_topic_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(topic=None)
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["datahub_topic"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDatahubTopic"]


def test_absent_not_found_exception_is_idempotent(monkeypatch):
    # The SDK raises ResourceNotFound for a missing topic; the module treats
    # that as "absent" instead of failing.
    fake = FakeCkafkaClient(topic=None, raise_when_missing=True)
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["datahub_topic"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(topic=_topic())
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"]["Name"] == "1250000000-orders-stream"
    assert fake.topic is not None
    assert "DeleteDatahubTopic" not in [c for c, unused in fake.calls]


def test_absent_deletes_topic(monkeypatch):
    fake = FakeCkafkaClient(topic=_topic())
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"] is None
    assert fake.topic is None
    ops = [c for c, unused in fake.calls]
    assert "DeleteDatahubTopic" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_topic_sanitises_credentials(monkeypatch):
    fake = FakeCkafkaClient(topic=None)
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"]["Name"] == "1250000000-orders-stream"
    assert result["datahub_topic"]["PartitionNum"] == 6
    assert "UserName" not in result["datahub_topic"]
    assert "Password" not in result["datahub_topic"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDatahubTopic"
    assert "CreateDatahubTopic" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(topic=None)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"] is None
    assert fake.topic is None
    assert "CreateDatahubTopic" not in [c for c, unused in fake.calls]


def test_create_when_describe_reports_not_found(monkeypatch):
    # ResourceNotFound from the describe is folded into "absent", then the
    # create proceeds normally.
    fake = FakeCkafkaClient(topic=None, raise_when_missing=True)
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"]["Name"] == "1250000000-orders-stream"
    ops = [c for c, unused in fake.calls]
    assert "CreateDatahubTopic" in ops


# ---------------------------------------------------------------------------
# existing-topic flows
# ---------------------------------------------------------------------------


def test_existing_topic_no_drift_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(topic=_topic())
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["datahub_topic"]["Name"] == "1250000000-orders-stream"
    assert "ModifyDatahubTopic" not in [c for c, unused in fake.calls]
    assert "CreateDatahubTopic" not in [c for c, unused in fake.calls]


def test_retention_drift_triggers_update(monkeypatch):
    fake = FakeCkafkaClient(topic=_topic(RetentionMs=86400000, Note=""))
    _make_module(monkeypatch, fake)
    _args(state="present", retention_ms=604800000, note="Order event stream")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_topic"]["RetentionMs"] == 604800000
    assert result["datahub_topic"]["Note"] == "Order event stream"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDatahubTopic" in ops


def test_partition_drift_is_immutable(monkeypatch):
    fake = FakeCkafkaClient(topic=_topic(PartitionNum=3))
    _make_module(monkeypatch, fake)
    _args(state="present", partition_num=6)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "PartitionNum" in payload["immutable_changes"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDatahubTopic(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
