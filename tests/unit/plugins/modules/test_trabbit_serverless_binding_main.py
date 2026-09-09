"""Unit tests for the trabbit_serverless_binding write module.

``trabbit_serverless_binding`` creates and deletes RabbitMQ Serverless
exchange bindings. Bindings are immutable: a binding is looked up either
by its integer ``binding_id`` or by its full identity (source exchange,
destination type, destination and routing key), and any existing match
short-circuits with no change.

Scenario matrix:

* absent on a missing binding / existing binding (check-mode, real delete)
* present identity no-op (matched by binding_id or by identity fields)
* create (real, check mode)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "amqp-abc123"
VIRTUAL_HOST = "production"

BINDING = {
    "BindingId": 501,
    "InstanceId": INSTANCE_ID,
    "VirtualHost": VIRTUAL_HOST,
    "Source": "orders",
    "DestinationType": "queue",
    "Destination": "order-workers",
    "RoutingKey": "orders.created",
}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _b_args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "virtual_host": VIRTUAL_HOST,
        "source_exchange": "orders",
        "destination_type": "queue",
        "destination": "order-workers",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTrabbitClient(object):
    """In-memory RabbitMQ Serverless client mutating a binding store."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(b) for b in (bindings or [])]
        self.calls = []
        self._next = 500

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRabbitMQServerlessBindings(self, request):
        self._record("DescribeRabbitMQServerlessBindings", request)
        matches = [b for b in self.bindings if b["VirtualHost"] == request.VirtualHost]
        return SimpleNamespace(
            BindingInfoList=[FakeResource(dict(b)) for b in matches],
            TotalCount=len(matches),
        )

    def CreateRabbitMQServerlessBinding(self, request):
        self._record("CreateRabbitMQServerlessBinding", request)
        self._next += 1
        self.bindings.append({
            "BindingId": self._next,
            "InstanceId": request.InstanceId,
            "VirtualHost": request.VirtualHost,
            "Source": request.Source,
            "DestinationType": request.DestinationType,
            "Destination": request.Destination,
            "RoutingKey": getattr(request, "RoutingKey", "") or "",
        })
        return SimpleNamespace()

    def DeleteRabbitMQServerlessBinding(self, request):
        self._record("DeleteRabbitMQServerlessBinding", request)
        self.bindings = [
            b for b in self.bindings
            if not (b["VirtualHost"] == request.VirtualHost and b["BindingId"] == request.BindingId)
        ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_binding_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQServerlessBindings"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(_ansible_check_mode=True, state="absent", routing_key="orders.created")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["BindingId"] == 501
    assert len(fake.bindings) == 1
    assert "DeleteRabbitMQServerlessBinding" not in [c for c, unused in fake.calls]


def test_absent_deletes_binding_by_id(monkeypatch):
    fake = FakeTrabbitClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(state="absent", binding_id=501)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQServerlessBinding" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_existing_by_identity_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(state="present", routing_key="orders.created")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["BindingId"] == 501
    ops = [c for c, unused in fake.calls]
    assert "CreateRabbitMQServerlessBinding" not in ops


def test_present_existing_by_binding_id_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _b_args(state="present", binding_id=501)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["BindingId"] == 501


def test_present_creates_binding(monkeypatch):
    fake = FakeTrabbitClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(state="present", routing_key="orders.created")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["Destination"] == "order-workers"
    assert result["binding"]["RoutingKey"] == "orders.created"
    assert len(fake.bindings) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQServerlessBindings"
    assert "CreateRabbitMQServerlessBinding" in ops


def test_present_exchange_destination_flow(monkeypatch):
    fake = FakeTrabbitClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(
        state="present",
        destination_type="exchange",
        destination="orders-fanout",
        routing_key="",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["DestinationType"] == "exchange"
    assert result["binding"]["Destination"] == "orders-fanout"


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(bindings=[])
    _make_module(monkeypatch, fake)
    _b_args(_ansible_check_mode=True, state="present", routing_key="orders.created")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.bindings == []
    assert "CreateRabbitMQServerlessBinding" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQServerlessBindings(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _b_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
