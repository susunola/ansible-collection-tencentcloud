"""Unit tests for the mqtt_topic write module (run_module flows).

``mqtt_topic`` creates, updates (remark) and deletes an MQTT topic. A
missing topic surfaces as an SDK "not found" style error that the module's
``find`` swallows back to ``None``.

Scenario matrix:

* absent on a missing topic / present create (real, check mode)
* present on a matching topic (no-op)
* remark drift triggers a modify (real, check mode)
* absent on an existing topic (check-mode dry run, real delete)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mqtt_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = {
    "InstanceId": "mqtt-abc123",
    "Topic": "orders/created",
    "Remark": "Order events",
}


def _topic(**overrides):
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _t_args(**overrides):
    params = {"instance_id": "mqtt-abc123", "topic": "orders/created"}
    params.update(overrides)
    return module_args(**params)


class FakeMqttClient(object):
    """In-memory MQTT client mutating a topic store."""

    def __init__(self, topics=None):
        self.topics = [copy.deepcopy(t) for t in (topics or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeTopic(self, request):
        self._record("DescribeTopic", request)
        for topic in self.topics:
            if topic["InstanceId"] == request.InstanceId and topic["Topic"] == request.Topic:
                return FakeResource(dict(topic, RequestId="req-fake"))
        raise Exception("ResourceNotFound: MQTT topic not found")

    def CreateTopic(self, request):
        self._record("CreateTopic", request)
        self.topics.append({
            "InstanceId": request.InstanceId,
            "Topic": request.Topic,
            "Remark": getattr(request, "Remark", "") or "",
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyTopic(self, request):
        self._record("ModifyTopic", request)
        for topic in self.topics:
            if topic["InstanceId"] == request.InstanceId and topic["Topic"] == request.Topic:
                topic["Remark"] = getattr(request, "Remark", "") or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTopic(self, request):
        self._record("DeleteTopic", request)
        self.topics = [
            t for t in self.topics
            if not (t["InstanceId"] == request.InstanceId and t["Topic"] == request.Topic)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MqttClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_topic_is_idempotent(monkeypatch):
    fake = FakeMqttClient(topics=[])
    _make_module(monkeypatch, fake)
    _t_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic_info"] is None
    assert [c for c, unused in fake.calls] == ["DescribeTopic"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _t_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"] is None
    assert len(fake.topics) == 1
    assert "DeleteTopic" not in [c for c, unused in fake.calls]


def test_absent_deletes_topic(monkeypatch):
    fake = FakeMqttClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _t_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"] is None
    assert fake.topics == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteTopic" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeMqttClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _t_args(state="present", remark="Order events")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic_info"]["Topic"] == "orders/created"
    assert "ModifyTopic" not in [c for c, unused in fake.calls]


def test_present_creates_missing_topic(monkeypatch):
    fake = FakeMqttClient(topics=[])
    _make_module(monkeypatch, fake)
    _t_args(state="present", remark="Order events")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"]["Topic"] == "orders/created"
    assert result["topic_info"]["Remark"] == "Order events"
    assert len(fake.topics) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTopic"
    assert "CreateTopic" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient(topics=[])
    _make_module(monkeypatch, fake)
    _t_args(_ansible_check_mode=True, state="present", remark="Order events")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"]["Topic"] == "orders/created"
    assert fake.topics == []
    assert "CreateTopic" not in [c for c, unused in fake.calls]


def test_remark_drift_modifies_topic(monkeypatch):
    fake = FakeMqttClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _t_args(state="present", remark="Renamed remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"]["Remark"] == "Renamed remark"
    assert fake.topics[0]["Remark"] == "Renamed remark"
    ops = [c for c, unused in fake.calls]
    assert "ModifyTopic" in ops


def test_present_modify_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _t_args(_ansible_check_mode=True, state="present", remark="Renamed remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic_info"]["Remark"] == "Renamed remark"
    assert fake.topics[0]["Remark"] == "Order events"
    assert "ModifyTopic" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTopic(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _t_args(state="present", remark="Order events")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
