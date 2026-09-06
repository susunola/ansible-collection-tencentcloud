"""Unit tests for the eb_connection write module (helpers + run_module).

Creates, updates and deletes EventBridge connections on a given event
bus. A connection is looked up through ListConnections: when
``connection_id`` is given it matches by ConnectionId, otherwise the
full list is scanned for ``name``. Type and ConnectionDescription are
immutable on an existing connection; Enable / Description / name drift
become UpdateConnection. Creation requires name + connection_type +
connection_description. UpdateConnection deliberately carries
``ConnectionName`` (which may be None) but never the immutable fields.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eb_connection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeRequest,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _connection(**overrides):
    """API-shaped connection dict; fresh copy per call."""
    item = {
        "ConnectionId": "conn-1001",
        "ConnectionName": "kafka-orders",
        "Type": "ckafka",
        "ConnectionDescription": {
            "ResourceDescription": '{"InstanceId":"ckafka-xxxx","TopicName":"orders"}'
        },
        "Enable": True,
        "Description": "",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "event_bus_id": "eb-l8q2xxxx",
        "connection_id": None,
        "name": "kafka-orders",
        "connection_type": "ckafka",
        "connection_description": {
            "ResourceDescription": '{"InstanceId":"ckafka-xxxx","TopicName":"orders"}'
        },
        "enabled": True,
        "description": "",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


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


class _JsonModel(object):
    """Model whose from_json_string stores the parsed JSON payload.

    The module builds ``ConnectionDescription`` payloads with
    ``cls().from_json_string(json.dumps(value))``, so the model class
    must offer a no-arg constructor and that ingestion method.
    """

    def __init__(self):
        self.payload = None

    def from_json_string(self, raw):
        self.payload = json.loads(raw)


class FakeEbModels(FakeModels):
    """FakeModels whose ConnectionDescription can ingest a JSON payload."""

    def __getattr__(self, name):
        if name == "ConnectionDescription":
            return _JsonModel
        return type(name, (FakeRequest,), {})


class FakeEbClient(object):
    """In-memory EbClient stand-in storing connection dicts.

    ListConnections returns the whole list (the module scans it
    client-side); CreateConnection synthesizes sequential ConnectionIds;
    UpdateConnection rewrites ConnectionName when present plus Enable and
    Description; DeleteConnection removes by ConnectionId.
    """

    def __init__(self, connections=None):
        self.connections = [dict(c) for c in (connections or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListConnections(self, request):
        self._record("ListConnections", request)
        return SimpleNamespace(
            Connections=[FakeResource(dict(c)) for c in self.connections],
            RequestId="req-fake",
        )

    def CreateConnection(self, request):
        self._record("CreateConnection", request)
        description = getattr(request, "ConnectionDescription", None)
        stored = {
            "ConnectionId": "conn-%04d" % self._seq,
            "ConnectionName": request.ConnectionName,
            "Type": request.Type,
            "ConnectionDescription": description.payload if description is not None else None,
            "Enable": getattr(request, "Enable", None),
            "Description": getattr(request, "Description", ""),
        }
        self._seq += 1
        self.connections.append(stored)
        return SimpleNamespace(ConnectionId=stored["ConnectionId"], RequestId="req-fake")

    def UpdateConnection(self, request):
        self._record("UpdateConnection", request)
        for stored in self.connections:
            if stored["ConnectionId"] == request.ConnectionId:
                if getattr(request, "ConnectionName", None) is not None:
                    stored["ConnectionName"] = request.ConnectionName
                stored["Enable"] = getattr(request, "Enable", None)
                stored["Description"] = getattr(request, "Description", "")
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConnection(self, request):
        self._record("DeleteConnection", request)
        self.connections = [c for c in self.connections if c["ConnectionId"] != request.ConnectionId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeEbModels(), SimpleNamespace(EbClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_list_request_sets_bus_offset_limit():
    request = mod.list_request(FakeEbModels(), _params())
    assert request.EventBusId == "eb-l8q2xxxx"
    assert request.Offset == 0
    assert request.Limit == 100


def test_create_request_carries_all_fields():
    request = mod.create_request(FakeEbModels(), _params())
    assert request.EventBusId == "eb-l8q2xxxx"
    assert request.ConnectionName == "kafka-orders"
    assert request.Type == "ckafka"
    assert isinstance(request.ConnectionDescription, _JsonModel)
    assert request.ConnectionDescription.payload == {
        "ResourceDescription": '{"InstanceId":"ckafka-xxxx","TopicName":"orders"}'
    }
    assert request.Enable is True
    assert request.Description == ""


def test_create_request_without_description_is_none():
    request = mod.create_request(FakeEbModels(), _params(connection_description=None))
    assert request.ConnectionDescription is None


def test_update_request_carries_id_name_enable_description():
    request = mod.update_request(FakeEbModels(), _params(), "conn-1001")
    assert request.EventBusId == "eb-l8q2xxxx"
    assert request.ConnectionId == "conn-1001"
    assert request.ConnectionName == "kafka-orders"
    assert request.Enable is True
    assert request.Description == ""
    assert not hasattr(request, "Type")
    assert not hasattr(request, "ConnectionDescription")


def test_update_request_allows_missing_name():
    request = mod.update_request(FakeEbModels(), _params(name=None), "conn-1001")
    assert request.ConnectionId == "conn-1001"
    assert request.ConnectionName is None
    assert request.Enable is True


def test_delete_request_carries_id():
    request = mod.delete_request(FakeEbModels(), _params(), "conn-1001")
    assert request.EventBusId == "eb-l8q2xxxx"
    assert request.ConnectionId == "conn-1001"


def test_model_none_returns_none():
    assert mod._model(FakeEbModels().ConnectionDescription, None) is None


def test_model_parses_json_payload():
    value = {"ResourceDescription": "{}"}
    item = mod._model(FakeEbModels().ConnectionDescription, value)
    assert isinstance(item, _JsonModel)
    assert item.payload == value


def test_find_by_connection_id(monkeypatch):
    fake = FakeEbClient([_connection(), _connection(ConnectionId="conn-1002", ConnectionName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(connection_id="conn-1002", name=None))
    value = mod.find(module, fake, FakeEbModels(), module.params)
    assert value["ConnectionId"] == "conn-1002"
    assert value["ConnectionName"] == "other"


def test_find_by_name(monkeypatch):
    fake = FakeEbClient([_connection(), _connection(ConnectionId="conn-1002", ConnectionName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(connection_id=None, name="kafka-orders"))
    value = mod.find(module, fake, FakeEbModels(), module.params)
    assert value["ConnectionId"] == "conn-1001"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeEbClient([_connection(ConnectionName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(connection_id=None, name="missing"))
    assert mod.find(module, fake, FakeEbModels(), module.params) is None


def test_find_multiple_name_matches_fail(monkeypatch):
    fake = FakeEbClient([_connection(), _connection(ConnectionId="conn-1002")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(connection_id=None, name="kafka-orders"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeEbModels(), module.params)
    assert "Multiple EventBridge connections matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", connection_id="conn-ghost", name=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"] is None
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", connection_id="conn-1001", name=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_absent_deletes_connection(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", connection_id="conn-1001", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    assert [c[0] for c in fake.calls] == ["ListConnections", "DeleteConnection"]
    assert fake.calls[1][1].ConnectionId == "conn-1001"
    assert fake.connections == []


def test_create_requires_all_creation_params(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-ghost", name=None, connection_type=None, connection_description=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["name", "connection_type", "connection_description"]


def test_create_requires_remaining_creation_params(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-ghost", name="kafka-orders", connection_type=None, connection_description=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["missing"] == ["connection_type", "connection_description"]


def test_present_check_mode_create_reports_target(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(connection_id=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["ConnectionName"] == "kafka-orders"
    assert result["connection"]["Type"] == "ckafka"
    assert result["connection"]["Enable"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["ConnectionName"] == "kafka-orders"
    assert result["diff"]["after"]["Type"] == "ckafka"
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(connection_id=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["ConnectionId"] == "conn-2001"
    assert result["connection"]["ConnectionName"] == "kafka-orders"
    assert result["connection"]["Enable"] is True
    assert [c[0] for c in fake.calls] == ["ListConnections", "CreateConnection", "ListConnections"]
    created = fake.calls[1][1]
    assert created.ConnectionName == "kafka-orders"
    assert created.Type == "ckafka"
    assert created.Enable is True
    assert created.Description == ""
    assert created.ConnectionDescription.payload["ResourceDescription"].startswith('{"InstanceId"')


def test_present_noop(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name=None, connection_type=None, connection_description=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"]["ConnectionId"] == "conn-1001"
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_present_enabled_drift_triggers_update(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name=None, connection_type=None, connection_description=None, enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["Enable"] is False
    assert [c[0] for c in fake.calls] == ["ListConnections", "UpdateConnection", "ListConnections"]
    assert fake.calls[1][1].Enable is False
    assert fake.calls[1][1].ConnectionName is None


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name=None, connection_type=None, connection_description=None, description="orders topic")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["Description"] == "orders topic"
    assert fake.calls[1][1].Description == "orders topic"


def test_present_name_drift_via_connection_id(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name="orders-v2", connection_type=None, connection_description=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["ConnectionName"] == "orders-v2"
    assert fake.calls[1][1].ConnectionName == "orders-v2"
    assert fake.calls[1][1].ConnectionId == "conn-1001"


def test_present_check_mode_update_reports_diff(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name="orders-v2", connection_type=None, connection_description=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["ConnectionName"] == "kafka-orders"
    assert result["diff"]["after"]["ConnectionName"] == "orders-v2"
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_present_immutable_type_drift_fails(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name=None, connection_type="http", connection_description=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {
        "Type": {"before": "ckafka", "after": "http"}
    }
    assert [c[0] for c in fake.calls] == ["ListConnections"]


def test_present_immutable_description_drift_fails(monkeypatch):
    fake = FakeEbClient([_connection()])
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-1001", name=None, connection_type=None, connection_description={"ResourceDescription": "{}"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"]["ConnectionDescription"]["after"] == {"ResourceDescription": "{}"}
    assert payload["immutable_changes"]["ConnectionDescription"]["before"]["ResourceDescription"].startswith('{"InstanceId"')


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(connection_id="conn-ghost", name=None, connection_type=None, connection_description=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.main)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", connection_id="conn-ghost", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
