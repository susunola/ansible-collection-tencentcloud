"""Unit tests for the tse_gateway_consumer write module (run_module flows).

``run_module()`` creates, updates and deletes an instance-unique TSE API
gateway consumer. It is driven end to end against an in-memory fake client
whose list/create/modify/delete operations mutate a consumer store so the
post-write readback converges immediately.

Scenario matrix:

* absent without a matching consumer (idempotent) / check-mode delete /
  real delete by consumer_id
* creation when missing by name, defaulting priority to Medium (check mode
  and real, with the created id captured from the create response)
* idempotent no-op when the live consumer matches name/priority/description
* description and priority drift updates through the modify API
* create-time name requirement when an unknown consumer_id is supplied
* duplicate name matches require consumer_id
* invalid priority choice is rejected during argument validation
* blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tse_gateway_consumer.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_consumer as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY_ID = "gateway-abc"
NAME = "mobile-application"


def _base(**overrides):
    params = {"gateway_id": GATEWAY_ID, "name": NAME}
    params.update(overrides)
    return module_args(**params)


def _consumer(consumer_id="consumer-1", name=NAME, priority="Medium", description=None, **extra):
    value = {
        "ConsumerId": consumer_id,
        "Name": name,
        "Priority": priority,
        "Description": description,
        "GatewayId": GATEWAY_ID,
    }
    value.update(extra)
    return value


class FakeConsumerClient(object):
    """In-memory TSE consumer client holding consumers by id."""

    def __init__(self, consumers=None):
        self.consumers = {}
        for value in (consumers or []):
            self.consumers[value["ConsumerId"]] = copy.deepcopy(value)
        self.next_id = max([int(key.rsplit("-", 1)[1]) for key in self.consumers] or [0]) + 1
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _values(self):
        return sorted(self.consumers.values(), key=lambda item: item["ConsumerId"])

    def DescribeCloudNativeAPIGatewayConsumerList(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumerList", request)
        assert request.GatewayId == GATEWAY_ID
        page = self._values()[request.Offset: request.Offset + request.Limit]
        return SimpleNamespace(
            Result=SimpleNamespace(
                Consumers=[FakeResource(copy.deepcopy(item)) for item in page],
                TotalCount=len(self.consumers),
            ),
            RequestId="req-fake",
        )

    def DescribeCloudNativeAPIGatewayConsumer(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumer", request)
        value = self.consumers.get(request.ConsumerId)
        return SimpleNamespace(
            Result=FakeResource(copy.deepcopy(value)) if value else None,
            RequestId="req-fake",
        )

    def CreateCloudNativeAPIGatewayConsumer(self, request):
        self._record("CreateCloudNativeAPIGatewayConsumer", request)
        consumer_id = "consumer-%d" % self.next_id
        self.next_id += 1
        self.consumers[consumer_id] = {
            "ConsumerId": consumer_id,
            "GatewayId": request.GatewayId,
            "Name": request.Name,
            "Priority": request.Priority,
            "Description": request.Description,
        }
        return SimpleNamespace(Result=SimpleNamespace(ID=consumer_id), RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayConsumer(self, request):
        self._record("ModifyCloudNativeAPIGatewayConsumer", request)
        value = self.consumers[request.ConsumerId]
        value["Name"] = request.Name
        value["Priority"] = request.Priority
        value["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayConsumer(self, request):
        self._record("DeleteCloudNativeAPIGatewayConsumer", request)
        self.consumers.pop(request.ConsumerId, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_consumer_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer"] is None
    assert _ops(fake) == ["DescribeCloudNativeAPIGatewayConsumerList"]


def test_absent_deletes_existing_consumer_by_id(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient(consumers=[_consumer()]))
    _base(state="absent", consumer_id="consumer-1", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"] is None
    assert fake.consumers == {}
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayConsumerList",
        "DescribeCloudNativeAPIGatewayConsumer",
        "DeleteCloudNativeAPIGatewayConsumer",
    ]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient(consumers=[_consumer()]))
    _base(state="absent", consumer_id="consumer-1", name=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"] is None
    assert len(fake.consumers) == 1
    assert "DeleteCloudNativeAPIGatewayConsumer" not in _ops(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_creates_consumer_by_name(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base(description="mobile app", priority="High")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"]["ConsumerId"] == "consumer-1"
    assert result["consumer"]["Name"] == NAME
    assert result["consumer"]["Priority"] == "High"
    assert result["consumer"]["Description"] == "mobile app"
    assert list(fake.consumers) == ["consumer-1"]
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayConsumerList",
        "CreateCloudNativeAPIGatewayConsumer",
        "DescribeCloudNativeAPIGatewayConsumerList",
        "DescribeCloudNativeAPIGatewayConsumer",
    ]


def test_present_create_defaults_priority_to_medium(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"]["Priority"] == "Medium"
    assert fake.consumers["consumer-1"]["Priority"] == "Medium"


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base(_ansible_check_mode=True, priority="High")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"] == {"Name": NAME, "Priority": "High", "Description": None}
    assert "diff" in result
    assert fake.consumers == {}
    assert "CreateCloudNativeAPIGatewayConsumer" not in _ops(fake)


def test_present_unknown_consumer_id_requires_name(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base(consumer_id="consumer-missing", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "name is required for a new TSE gateway consumer"
    assert fake.consumers == {}


# ---------------------------------------------------------------------------
# idempotent and drift flows
# ---------------------------------------------------------------------------


def test_converged_consumer_by_id_is_idempotent(monkeypatch):
    fake = _make_module(
        monkeypatch,
        FakeConsumerClient(consumers=[_consumer(description="notes", CreateTime="2026-01-01")]),
    )
    _base(consumer_id="consumer-1", name=None, description="notes", priority="Medium")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer"]["ConsumerId"] == "consumer-1"
    assert result["consumer"]["CreateTime"] == "2026-01-01"
    assert "ModifyCloudNativeAPIGatewayConsumer" not in _ops(fake)


def test_description_drift_updates_consumer(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient(consumers=[_consumer(description="old notes")]))
    _base(description="new notes")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"]["Description"] == "new notes"
    assert fake.consumers["consumer-1"]["Description"] == "new notes"
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayConsumerList",
        "DescribeCloudNativeAPIGatewayConsumer",
        "ModifyCloudNativeAPIGatewayConsumer",
        "DescribeCloudNativeAPIGatewayConsumerList",
        "DescribeCloudNativeAPIGatewayConsumer",
    ]


def test_priority_drift_updates_consumer(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient(consumers=[_consumer(priority="Low")]))
    _base(priority="High")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"]["Priority"] == "High"
    assert fake.consumers["consumer-1"]["Priority"] == "High"


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient(consumers=[_consumer(priority="Low")]))
    _base(priority="High", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer"] == {"Name": NAME, "Priority": "High", "Description": None}
    assert "diff" in result
    assert fake.consumers["consumer-1"]["Priority"] == "Low"
    assert "ModifyCloudNativeAPIGatewayConsumer" not in _ops(fake)


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_invalid_priority_choice_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeConsumerClient())
    _base(priority="Urgent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "priority" in exc.value.args[0]["msg"]
    assert fake.consumers == {}


def test_duplicate_name_match_requires_consumer_id(monkeypatch):
    class DuplicateClient(object):
        def DescribeCloudNativeAPIGatewayConsumerList(self, request):
            values = [FakeResource(_consumer("consumer-1", name="dup")), FakeResource(_consumer("consumer-2", name="dup"))]
            return SimpleNamespace(Result=SimpleNamespace(Consumers=values, TotalCount=2), RequestId="req-fake")

    _make_module(monkeypatch, DuplicateClient())
    _base(name="dup")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway consumers matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayConsumerList(self, request):
            raise Boom("tse endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tse endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_consumer.py)
# ---------------------------------------------------------------------------


class _Value(object):
    pass


class _ConsumerModels(object):
    CreateCloudNativeAPIGatewayConsumerRequest = _Value
    ModifyCloudNativeAPIGatewayConsumerRequest = _Value
    DeleteCloudNativeAPIGatewayConsumerRequest = _Value


def test_consumer_create_request_uses_stable_identity_and_priority():
    p = {"gateway_id": "g1", "name": "mobile", "priority": "High", "description": "app"}
    request = mod.create_request(_ConsumerModels, p)
    assert request.GatewayId == "g1"
    assert request.Name == "mobile"
    assert request.Priority == "High"
    assert request.Description == "app"


def test_consumer_create_request_defaults_priority_to_medium():
    p = {"gateway_id": "g1", "name": "mobile", "description": "app"}
    request = mod.create_request(_ConsumerModels, p)
    assert request.Priority == "Medium"


def test_consumer_update_request_carries_existing_id():
    p = {"gateway_id": "g1", "name": "mobile", "priority": "Low", "description": "notes"}
    request = mod.update_request(_ConsumerModels, p, {"ConsumerId": "consumer-9"})
    assert request.GatewayId == "g1"
    assert request.ConsumerId == "consumer-9"
    assert request.Name == "mobile"
    assert request.Priority == "Low"
    assert request.Description == "notes"


def test_consumer_delete_request_maps_existing_id():
    p = {"gateway_id": "g1"}
    request = mod.delete_request(_ConsumerModels, p, {"ConsumerId": "consumer-9"})
    assert request.GatewayId == "g1"
    assert request.ConsumerId == "consumer-9"
