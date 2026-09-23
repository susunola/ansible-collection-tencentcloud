"""Unit tests for the gaap_real_server write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake GAAP client
whose register/rename/remove operations mutate the real-server store, so the
module's paginated ``find`` refetch returns freshly written state. Real
servers are reusable origins with a real create (register), rename update and
explicit delete lifecycle, keyed by real_server_id or exact address.

Scenario matrix:

* register when absent (check mode and real ``AddRealServers`` with captured
  request fields)
* register requires address+name; argument validation needs an identity
* idempotent no-op when the existing server already carries the name
* rename drift drives ``ModifyRealServerName``
* absent flows (missing no-op, ``allow_shared_delete`` guard, check-mode dry
  run, real removal)
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_gaap_real_server.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gaap_real_server as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVER = {
    "RealServerId": "rs-aaaaaaaa",
    "RealServerIP": "10.0.1.10",
    "RealServerName": "orders-primary",
    "ProjectId": 0,
}


def _server(**overrides):
    item = copy.deepcopy(SERVER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"address": "10.0.1.10", "name": "orders-primary"}
    params.update(overrides)
    return module_args(**params)


class FakeGaapClient(object):
    """In-memory GAAP client mutating a reusable real-server store."""

    def __init__(self, servers=None):
        self.servers = [copy.deepcopy(t) for t in (servers or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRealServers(self, request):
        self._record("DescribeRealServers", request)
        return SimpleNamespace(
            RealServerSet=[FakeResource(dict(t)) for t in self.servers],
            TotalCount=len(self.servers),
            RequestId="req-fake",
        )

    def AddRealServers(self, request):
        self._record("AddRealServers", request)
        self._next += 1
        server_id = "rs-new-%04d" % self._next
        self.servers.append({
            "RealServerId": server_id,
            "RealServerIP": request.RealServerIP[0],
            "RealServerName": request.RealServerName,
            "ProjectId": request.ProjectId,
        })
        return SimpleNamespace(RealServerSet=[SimpleNamespace(RealServerId=server_id)], RequestId="req-fake")

    def ModifyRealServerName(self, request):
        self._record("ModifyRealServerName", request)
        for item in self.servers:
            if item.get("RealServerId") == request.RealServerId:
                item["RealServerName"] = request.RealServerName
        return SimpleNamespace(RequestId="req-fake")

    def RemoveRealServers(self, request):
        self._record("RemoveRealServers", request)
        ids = list(getattr(request, "RealServerIds", None) or [])
        self.servers = [t for t in self.servers if t.get("RealServerId") not in ids]
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


def test_missing_identity_fails(monkeypatch):
    fake = FakeGaapClient()
    _make_module(monkeypatch, fake)
    module_args(name="orphan")  # neither real_server_id nor address
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


def test_register_requires_address_and_name(monkeypatch):
    fake = FakeGaapClient()
    _make_module(monkeypatch, fake)
    module_args(real_server_id="rs-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "address and name are required" in exc.value.args[0]["msg"]
    assert fake.calls and [name for name, unused in fake.calls][0] == "DescribeRealServers"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_register_real_server(monkeypatch):
    fake = FakeGaapClient(servers=[])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"]["RealServerId"].startswith("rs-new-")
    assert result["real_server"]["RealServerIP"] == "10.0.1.10"
    assert result["real_server"]["RealServerName"] == "orders-primary"
    assert len(fake.servers) == 1
    request = _find_call(fake, "AddRealServers")
    assert request.ProjectId == 0
    assert request.RealServerIP == ["10.0.1.10"]
    assert request.RealServerName == "orders-primary"


def test_register_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(servers=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"] == {"RealServerIP": "10.0.1.10", "RealServerName": "orders-primary", "ProjectId": 0}
    assert fake.servers == []
    assert "AddRealServers" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-server flows
# ---------------------------------------------------------------------------


def test_existing_server_no_drift_is_idempotent(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["real_server"]["RealServerId"] == "rs-aaaaaaaa"
    assert [name for name, unused in fake.calls] == ["DescribeRealServers"]


def test_existing_server_without_name_is_idempotent(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(name=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["real_server"]["RealServerName"] == "orders-primary"


def test_rename_drift_updates_server(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(name="orders-primary-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"]["RealServerName"] == "orders-primary-v2"
    request = _find_call(fake, "ModifyRealServerName")
    assert request.RealServerId == "rs-aaaaaaaa"
    assert request.RealServerName == "orders-primary-v2"


def test_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, name="orders-primary-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"] == {"RealServerName": "orders-primary-v2"}
    assert fake.servers[0]["RealServerName"] == "orders-primary"
    assert "ModifyRealServerName" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_server_is_idempotent(monkeypatch):
    fake = FakeGaapClient(servers=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", address="10.0.9.9")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["real_server"] is None


def test_absent_requires_allow_shared_delete(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_shared_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_shared_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"]["RealServerId"] == "rs-aaaaaaaa"
    assert len(fake.servers) == 1
    assert "RemoveRealServers" not in [name for name, unused in fake.calls]


def test_absent_removes_real_server(monkeypatch):
    fake = FakeGaapClient(servers=[_server()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_shared_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["real_server"] is None
    assert fake.servers == []
    request = _find_call(fake, "RemoveRealServers")
    assert request.RealServerIds == ["rs-aaaaaaaa"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRealServers(self, request):
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
# legacy helper regression tests (folded from test_gaap_real_server.py)
# ---------------------------------------------------------------------------


class _Item(object):
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return self.value


class _Response(object):
    def __init__(self, values):
        self.RealServerSet = [_Item(v) for v in values]
        self.TotalCount = len(values)


class _Models(object):
    class DescribeRealServersRequest(object):
        pass


class _Client(object):
    def __init__(self, values):
        self.values = values

    def DescribeRealServers(self, request):
        return _Response(self.values)


class _Module(object):
    def sdk_call(self, method, request):
        return method(request)

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


def test_find_real_server_matches_exact_address():
    values = [{"RealServerId": "rs-old", "RealServerIP": "10.0.1.100"}, {"RealServerId": "rs-1", "RealServerIP": "10.0.1.10"}]
    assert mod.find(_Module(), _Client(values), _Models, address="10.0.1.10")["RealServerId"] == "rs-1"


def test_find_real_server_matches_explicit_id():
    values = [{"RealServerId": "rs-1", "RealServerIP": "10.0.1.10"}]
    assert mod.find(_Module(), _Client(values), _Models, real_server_id="rs-1")["RealServerIP"] == "10.0.1.10"


def test_find_real_server_returns_none_when_absent():
    assert mod.find(_Module(), _Client([{"RealServerId": "rs-1", "RealServerIP": "10.0.1.10"}]), _Models, address="10.0.9.9") is None
