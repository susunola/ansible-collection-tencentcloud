"""Unit tests for the trabbit_serverless_exchange write module.

Creates, updates and destroys RabbitMQ Serverless exchanges while
protecting immutable routing semantics (ExchangeType / Durable /
AutoDelete / Internal). Lookup first lists exchanges to confirm the name
exists, then fetches the detail record whose serialization excludes
``RequestId``. ``Remark`` and ``AlternateExchange`` are the only mutable
fields, so an update always carries exactly those two. The fake client
stores detail dicts and derives the list presence from the same store,
so a post-write refetch converges.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_exchange as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _exchange(**overrides):
    """API-shaped exchange detail dict isolated from the shared constant."""
    item = {
        "ExchangeName": "orders",
        "VirtualHost": "production",
        "ExchangeType": "direct",
        "Remark": "",
        "Durable": True,
        "AutoDelete": False,
        "Internal": False,
        "AlternateExchange": "",
        "RequestId": "req-fake",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "amqp-abc",
        "virtual_host": "production",
        "name": "orders",
        "exchange_type": None,
        "remark": "",
        "durable": None,
        "auto_delete": None,
        "internal": None,
        "alternate_exchange": "",
        "delayed_exchange_type": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeTrabbitClient(object):
    """In-memory TrabbitClient stand-in storing exchange detail dicts.

    Describe lists every stored exchange (each item exposes
    ``ExchangeName``); the detail operation returns the stored dict as a
    :class:`FakeResource` so the module's ``_serialize`` + ``RequestId``
    pop round-trips. Create seeds a fresh detail from the request and the
    mutable Modify operation updates Remark / AlternateExchange in place.
    """

    def __init__(self, exchanges=None):
        self.exchanges = {}
        for value in exchanges or []:
            self.exchanges[value["ExchangeName"]] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeRabbitMQServerlessExchanges(self, request):
        self._record("DescribeRabbitMQServerlessExchanges", request)
        return SimpleNamespace(
            ExchangeInfoList=[SimpleNamespace(ExchangeName=name) for name in self.exchanges],
            RequestId="req-fake",
        )

    def DescribeRabbitMQServerlessExchangeDetail(self, request):
        self._record("DescribeRabbitMQServerlessExchangeDetail", request)
        return FakeResource(dict(self.exchanges.get(request.ExchangeName, {"ExchangeName": request.ExchangeName})))

    def CreateRabbitMQServerlessExchange(self, request):
        self._record("CreateRabbitMQServerlessExchange", request)
        self.exchanges[request.ExchangeName] = {
            "ExchangeName": request.ExchangeName,
            "VirtualHost": request.VirtualHost,
            "ExchangeType": request.ExchangeType,
            "Remark": request.Remark,
            "Durable": request.Durable,
            "AutoDelete": request.AutoDelete,
            "Internal": request.Internal,
            "AlternateExchange": request.AlternateExchange,
            "RequestId": "req-fake",
        }
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQServerlessExchange(self, request):
        self._record("ModifyRabbitMQServerlessExchange", request)
        stored = self.exchanges.get(request.ExchangeName)
        if stored is not None:
            stored["Remark"] = request.Remark
            stored["AlternateExchange"] = request.AlternateExchange
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQServerlessExchange(self, request):
        self._record("DeleteRabbitMQServerlessExchange", request)
        self.exchanges.pop(request.ExchangeName, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=25)
    assert request.InstanceId == "amqp-abc"
    assert request.VirtualHost == "production"
    assert request.ExchangeName == "orders"
    assert request.Offset == 25
    assert request.Limit == 100


def test_detail_request_fields():
    request = mod.detail_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-abc"
    assert request.VirtualHost == "production"
    assert request.ExchangeName == "orders"


def test_create_request_defaults():
    request = mod.create_request(FakeModels(), _params())
    assert request.ExchangeType == "direct"
    assert request.Remark == ""
    assert request.Durable is True
    assert request.AutoDelete is False
    assert request.Internal is False
    assert request.AlternateExchange == ""
    assert request.DelayedExchangeType is None


def test_create_request_maps_explicit_values():
    request = mod.create_request(
        FakeModels(),
        _params(exchange_type="x-delayed-message", remark="orders-fanout", durable=False, auto_delete=True, internal=True, alternate_exchange="dlx", delayed_exchange_type="topic"),
    )
    assert request.ExchangeType == "x-delayed-message"
    assert request.Remark == "orders-fanout"
    assert request.Durable is False
    assert request.AutoDelete is True
    assert request.Internal is True
    assert request.AlternateExchange == "dlx"
    assert request.DelayedExchangeType == "topic"


def test_update_request_carries_only_mutable_fields():
    request = mod.update_request(FakeModels(), _params(remark="new-remark", alternate_exchange="alt-x", exchange_type="topic"))
    assert request.InstanceId == "amqp-abc"
    assert request.VirtualHost == "production"
    assert request.ExchangeName == "orders"
    assert request.Remark == "new-remark"
    assert request.AlternateExchange == "alt-x"
    assert not hasattr(request, "ExchangeType")
    assert not hasattr(request, "Durable")


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-abc"
    assert request.VirtualHost == "production"
    assert request.ExchangeName == "orders"


def test_comparable_maps_all_fields():
    value = mod.comparable(_exchange(Remark="note", Durable=1, AlternateExchange="dlx"))
    assert value == {
        "ExchangeName": "orders",
        "VirtualHost": "production",
        "ExchangeType": "direct",
        "Remark": "note",
        "Durable": True,
        "AutoDelete": False,
        "Internal": False,
        "AlternateExchange": "dlx",
    }


def test_comparable_normalises_missing_values():
    value = mod.comparable({"ExchangeName": "x"})
    assert value["Remark"] == ""
    assert value["Durable"] is False
    assert value["AutoDelete"] is False
    assert value["AlternateExchange"] == ""


def test_desired_defaults_from_creation_values():
    target = mod.desired(_params())
    assert target["ExchangeType"] == "direct"
    assert target["Durable"] is True
    assert target["AutoDelete"] is False
    assert target["Internal"] is False
    assert target["Remark"] == ""
    assert target["AlternateExchange"] == ""


def test_desired_merges_current_when_params_omitted():
    target = mod.desired(_params(exchange_type=None, durable=None), _exchange(ExchangeType="topic", Durable=False, AutoDelete=True, Internal=True))
    assert target["ExchangeType"] == "topic"
    assert target["Durable"] is False
    assert target["AutoDelete"] is True
    assert target["Internal"] is True


def test_desired_prefers_explicit_params():
    target = mod.desired(_params(exchange_type="fanout", durable=True, auto_delete=True, internal=True), _exchange(ExchangeType="topic", Durable=False))
    assert target["ExchangeType"] == "fanout"
    assert target["Durable"] is True
    assert target["AutoDelete"] is True


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_returns_detail_without_request_id(monkeypatch):
    fake = FakeTrabbitClient([_exchange()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ExchangeName"] == "orders"
    assert value["ExchangeType"] == "direct"
    assert "RequestId" not in value
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQServerlessExchanges", "DescribeRabbitMQServerlessExchangeDetail"]


def test_find_absent_exchange_returns_none(monkeypatch):
    fake = FakeTrabbitClient([_exchange(ExchangeName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQServerlessExchanges"]  # no detail call


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_exchange(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    exchange = result["exchange"]
    assert exchange["ExchangeName"] == "orders"
    assert exchange["ExchangeType"] == "direct"
    assert exchange["Durable"] is True
    create = [c for c in fake.calls if c[0] == "CreateRabbitMQServerlessExchange"][0][1]
    assert create.ExchangeType == "direct"
    assert create.Durable is True
    assert "ModifyRabbitMQServerlessExchange" not in [c[0] for c in fake.calls]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTrabbitClient([_exchange()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exchange"]["ExchangeName"] == "orders"
    assert not any("CreateRabbitMQServerlessExchange" == c[0] or "ModifyRabbitMQServerlessExchange" == c[0] for c in fake.calls)


def test_present_remark_drift_triggers_update(monkeypatch):
    fake = FakeTrabbitClient([_exchange(Remark="old-note")])
    _make_module(monkeypatch, fake)
    _run_args(remark="new-note")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"]["Remark"] == "new-note"
    modify = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessExchange"][0][1]
    assert modify.Remark == "new-note"
    assert not any("CreateRabbitMQServerlessExchange" == c[0] for c in fake.calls)
    assert [c[0] for c in fake.calls].count("DescribeRabbitMQServerlessExchangeDetail") == 2  # find + refetch


def test_present_alternate_exchange_drift_triggers_update(monkeypatch):
    fake = FakeTrabbitClient([_exchange(AlternateExchange="old-dlx")])
    _make_module(monkeypatch, fake)
    _run_args(alternate_exchange="dlx-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"]["AlternateExchange"] == "dlx-v2"
    modify = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessExchange"][0][1]
    assert modify.AlternateExchange == "dlx-v2"
    assert modify.Remark == ""


def test_present_type_immutable_fails(monkeypatch):
    fake = FakeTrabbitClient([_exchange(ExchangeType="direct")])
    _make_module(monkeypatch, fake)
    _run_args(exchange_type="topic")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"ExchangeType": {"before": "direct", "after": "topic"}}
    assert not any("ModifyRabbitMQServerlessExchange" == c[0] for c in fake.calls)


def test_present_durable_immutable_fails(monkeypatch):
    fake = FakeTrabbitClient([_exchange(Durable=True)])
    _make_module(monkeypatch, fake)
    _run_args(durable=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {"Durable": {"before": True, "after": False}}


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"] is None  # no refetch in check mode
    assert not any("CreateRabbitMQServerlessExchange" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient([_exchange(Remark="old")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(remark="new").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"]["Remark"] == "old"  # pre-change reported
    assert not any("ModifyRabbitMQServerlessExchange" == c[0] for c in fake.calls)


def test_check_mode_immutable_drift_still_fails(monkeypatch):
    fake = FakeTrabbitClient([_exchange()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(exchange_type="topic").items() if v is not None})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Immutable fields cannot be changed" in exc.value.args[0]["msg"]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTrabbitClient([_exchange(ExchangeName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exchange"] is None
    assert not any("DeleteRabbitMQServerlessExchange" == c[0] for c in fake.calls)


def test_absent_deletes_exchange(monkeypatch):
    fake = FakeTrabbitClient([_exchange()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteRabbitMQServerlessExchange"][0][1]
    assert delete.InstanceId == "amqp-abc"
    assert delete.VirtualHost == "production"
    assert delete.ExchangeName == "orders"
    assert fake.exchanges == {}


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient([_exchange()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exchange"]["ExchangeName"] == "orders"  # pre-change detail reported
    assert not any("DeleteRabbitMQServerlessExchange" == c[0] for c in fake.calls)
    assert len(fake.exchanges) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
