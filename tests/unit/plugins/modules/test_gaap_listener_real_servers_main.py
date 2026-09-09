"""Unit tests for the gaap_listener_real_servers write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake GAAP client
whose ``BindListenerRealServers`` replaces the listener binding store, so the
post-write ``DescribeListenerRealServers`` refetch returns the new set. The
module has no create/delete lifecycle: it atomically replaces a TCP/UDP
listener's whole origin-binding set, and an empty set simply unbinds every
origin (covered as the "remove all" case).

Scenario matrix:

* argument validation (missing listener_id, incomplete binding entries)
* idempotent no-op when bindings already match (health status noise ignored)
* check-mode dry run reports the replacement without writing
* real replacement binds the whole desired set with captured request fields
* unbinding every origin through an empty set
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_gaap_listener_real_servers.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gaap_listener_real_servers as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LISTENER_ID = "listener-aaaaaaaa"
BINDINGS = [{"RealServerId": "rs-a", "RealServerIP": "10.0.0.1", "RealServerPort": 3306, "RealServerWeight": 10}]


def _binding(**overrides):
    item = copy.deepcopy(BINDINGS[0])
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "listener_id": LISTENER_ID,
        "real_servers": [
            {"real_server_id": "rs-a", "address": "10.0.0.1", "port": 3306, "weight": 10},
        ],
    }
    params.update(overrides)
    return module_args(**params)


class FakeGaapClient(object):
    """In-memory GAAP client mutating per-listener binding stores."""

    def __init__(self, bindings=None):
        self.bindings = {LISTENER_ID: [copy.deepcopy(t) for t in (bindings or [])]}
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeListenerRealServers(self, request):
        self._record("DescribeListenerRealServers", request)
        return SimpleNamespace(
            BindRealServerSet=[FakeResource(dict(t)) for t in self.bindings.get(request.ListenerId, [])],
            RequestId="req-fake",
        )

    def BindListenerRealServers(self, request):
        self._record("BindListenerRealServers", request)
        entries = []
        for item in request.RealServerBindSet:
            entries.append({k: copy.deepcopy(v) for k, v in vars(item).items() if not k.startswith("_")})
        self.bindings[request.ListenerId] = entries
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(GaapClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_missing_listener_id_fails(monkeypatch):
    fake = FakeGaapClient(bindings=[])
    _make_module(monkeypatch, fake)
    module_args(real_servers=[{"real_server_id": "rs-a", "address": "10.0.0.1", "port": 3306}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "listener_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_binding_entry_requires_port(monkeypatch):
    fake = FakeGaapClient(bindings=[])
    _make_module(monkeypatch, fake)
    module_args(
        listener_id=LISTENER_ID,
        real_servers=[{"real_server_id": "rs-a", "address": "10.0.0.1"}],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "port" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_bindings_already_match_is_idempotent(monkeypatch):
    fake = FakeGaapClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["real_servers"] == mod.canonical(_base()["real_servers"])
    assert [name for name, unused in fake.calls] == ["DescribeListenerRealServers"]


# ---------------------------------------------------------------------------
# replacement flows
# ---------------------------------------------------------------------------


def test_replacement_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    desired = [
        {"real_server_id": "rs-a", "address": "10.0.0.1", "port": 3306, "weight": 10},
        {"real_server_id": "rs-b", "address": "10.0.0.2", "port": 3306, "weight": 1},
    ]
    _base(_ansible_check_mode=True, real_servers=desired)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_servers"] == mod.canonical(desired)
    assert fake.bindings[LISTENER_ID] == [_binding()]
    assert "BindListenerRealServers" not in [name for name, unused in fake.calls]


def test_replacement_binds_desired_set(monkeypatch):
    fake = FakeGaapClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    desired = [
        {"real_server_id": "rs-b", "address": "10.0.0.2", "port": 3306, "weight": 1},
        {"real_server_id": "rs-a", "address": "10.0.0.1", "port": 3306, "weight": 10},
    ]
    _base(real_servers=desired)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_servers"] == mod.canonical(desired)
    request = _find_call(fake, "BindListenerRealServers")
    assert request.ListenerId == LISTENER_ID
    bound = sorted(
        [{k: v for k, v in vars(item).items() if not k.startswith("_")} for item in request.RealServerBindSet],
        key=lambda value: value["RealServerId"],
    )
    assert [item["RealServerId"] for item in bound] == ["rs-a", "rs-b"]
    assert bound[0]["RealServerWeight"] == 10
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeListenerRealServers"
    assert ops[-1] == "DescribeListenerRealServers"  # post-bind refetch


def test_empty_set_unbinds_every_origin(monkeypatch):
    fake = FakeGaapClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _base(real_servers=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_servers"] == []
    assert fake.bindings[LISTENER_ID] == []
    request = _find_call(fake, "BindListenerRealServers")
    assert request.RealServerBindSet == []


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeListenerRealServers(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_gaap_listener_real_servers.py)
# ---------------------------------------------------------------------------


def test_canonical_maps_and_sorts_desired_bindings():
    result = mod.canonical([
        {"real_server_id": "rs-b", "address": "10.0.0.2", "port": 80},
        {"real_server_id": "rs-a", "address": "10.0.0.1", "port": 80, "weight": 10, "failover_role": "master"},
    ])
    assert [item["RealServerId"] for item in result] == ["rs-a", "rs-b"]
    assert result[0]["RealServerWeight"] == 10
    assert result[0]["RealServerFailoverRole"] == "master"
    assert result[1]["RealServerWeight"] == 1
    assert result[1]["RealServerFailoverRole"] is None


def test_canonical_ignores_health_status_fields():
    current = mod.canonical([{
        "RealServerId": "rs-a", "RealServerIP": "10.0.0.1", "RealServerPort": 80,
        "RealServerWeight": 1, "RealServerStatus": 0,
    }])
    desired = mod.canonical([{"real_server_id": "rs-a", "address": "10.0.0.1", "port": 80}])
    assert current == desired
