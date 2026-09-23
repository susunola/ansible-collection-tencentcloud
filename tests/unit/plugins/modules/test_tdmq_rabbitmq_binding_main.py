"""Unit tests for the tdmq_rabbitmq_binding write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
delete operations mutate a RabbitMQ-binding store so post-write describes
converge immediately.

Scenario matrix:

* absent on a missing binding, looked up by full attribute tuple or by
  ``binding_id`` (idempotent no-op)
* absent with a matching binding (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the binding already exists — bindings are immutable, so a
  present run never issues a Modify
* ``binding_id`` lookup wins over attribute mismatch (immutable identity)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rabbitmq_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BINDING = {
    "BindingId": 1001,
    "Source": "orders",
    "DestinationType": "queue",
    "Destination": "order-workers",
    "RoutingKey": "orders.created",
}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {
        "instance_id": "amqp-abc",
        "virtual_host": "production",
        "source_exchange": "orders",
        "destination_type": "queue",
        "destination": "order-workers",
        "routing_key": "orders.created",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small RabbitMQ-binding store."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(t) for t in (bindings or [])]
        self.calls = []
        self._next = 1000

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRabbitMQBindings(self, request):
        self._record("DescribeRabbitMQBindings", request)
        return SimpleNamespace(
            BindingInfoList=[FakeResource(t) for t in self.bindings], TotalCount=len(self.bindings)
        )

    def CreateRabbitMQBinding(self, request):
        self._record("CreateRabbitMQBinding", request)
        self._next += 1
        self.bindings.append(
            {
                "BindingId": self._next,
                "Source": getattr(request, "Source", None),
                "DestinationType": getattr(request, "DestinationType", None),
                "Destination": getattr(request, "Destination", None),
                "RoutingKey": getattr(request, "RoutingKey", None) or "",
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQBinding(self, request):
        self._record("DeleteRabbitMQBinding", request)
        binding_id = getattr(request, "BindingId", None)
        self.bindings = [t for t in self.bindings if t.get("BindingId") != binding_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_attributes_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQBindings"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="absent",
        instance_id="amqp-abc",
        virtual_host="production",
        binding_id=9999,
        source_exchange="orders",
        destination_type="queue",
        destination="order-workers",
        routing_key="orders.created",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["BindingId"] == 1001
    assert len(fake.bindings) == 1
    assert "DeleteRabbitMQBinding" not in [c for c, unused in fake.calls]


def test_absent_deletes_binding_by_attributes(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQBinding" in ops


def test_absent_deletes_binding_by_id(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="absent", binding_id=1001)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.bindings == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQBinding" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_binding(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["Source"] == "orders"
    assert result["binding"]["Destination"] == "order-workers"
    assert result["binding"]["RoutingKey"] == "orders.created"
    assert len(fake.bindings) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQBindings"
    assert "CreateRabbitMQBinding" in ops


def test_create_exchange_to_exchange_binding(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(
        state="present",
        source_exchange="orders",
        destination_type="exchange",
        destination="orders-backup",
        routing_key="",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["DestinationType"] == "exchange"
    assert result["binding"]["Destination"] == "orders-backup"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(bindings=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    assert "CreateRabbitMQBinding" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-binding flows (immutable: present never issues a Modify)
# ---------------------------------------------------------------------------


def test_existing_binding_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["BindingId"] == 1001
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeRabbitMQBindings"]


def test_binding_id_identity_wins_over_attribute_mismatch(monkeypatch):
    # A binding_id match short-circuits attribute comparison, so a present
    # run cannot rename or reshape an existing immutable binding.
    fake = FakeTdmqClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _config(state="present", binding_id=1001, routing_key="different.key")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["RoutingKey"] == "orders.created"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQBindings(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
