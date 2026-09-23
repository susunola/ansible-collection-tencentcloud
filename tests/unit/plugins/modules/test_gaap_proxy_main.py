"""Unit tests for the gaap_proxy write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake GAAP client
whose write operations mutate the proxy store, so the module's post-write
``find_proxy`` refetch and the state waiters return immediately.

Scenario matrix:

* absent on a missing proxy (idempotent no-op)
* absent with a matching proxy (check-mode dry run and real destroy)
* the running/stopped lifecycle on missing and existing proxies, including
  check-mode dry runs
* creation when missing (with/without the mandatory creation parameters,
  check mode)
* rename of an existing proxy
* no-op when nothing drifts
* the multi-match guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gaap_proxy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PROXY = {
    "ProxyId": "proxy-aaaaaaaa",
    "ProxyName": "prod-gaap",
    "Status": "running",
    "AccessRegion": "ap-guangzhou",
    "RealServerRegion": "ap-hongkong",
    "Bandwidth": 20,
    "Concurrent": 2,
}


def _proxy(**overrides):
    item = copy.deepcopy(PROXY)
    item.update(overrides)
    return item


def _base(**overrides):
    # proxy_id and name are alternatives; start from the name and let
    # lifecycle tests pass a proxy_id when the identity requires it.
    params = {"name": "prod-gaap"}
    params.update(overrides)
    return module_args(**params)


class FakeGaapClient(object):
    """In-memory GAAP client mutating a proxy store."""

    def __init__(self, proxies=None):
        self.proxies = [copy.deepcopy(t) for t in (proxies or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeProxies(self, request):
        self._record("DescribeProxies", request)
        return SimpleNamespace(
            ProxySet=[FakeResource(dict(t)) for t in self.proxies],
            TotalCount=len(self.proxies),
        )

    def CreateProxy(self, request):
        self._record("CreateProxy", request)
        self.proxies.append({
            "ProxyId": "proxy-new%04d" % (len(self.proxies) + 1),
            "ProxyName": request.ProxyName,
            "Status": "running",
            "AccessRegion": request.AccessRegion,
            "RealServerRegion": request.RealServerRegion,
            "Bandwidth": request.Bandwidth,
            "Concurrent": request.Concurrent,
        })
        return SimpleNamespace(ProxyId=self.proxies[-1]["ProxyId"], RequestId="req-fake")

    def ModifyProxiesAttribute(self, request):
        self._record("ModifyProxiesAttribute", request)
        ids = list(getattr(request, "ProxyIds", None) or [])
        for item in self.proxies:
            if item.get("ProxyId") in ids:
                item["ProxyName"] = request.ProxyName
        return SimpleNamespace(RequestId="req-fake")

    def OpenProxies(self, request):
        self._record("OpenProxies", request)
        ids = list(getattr(request, "ProxyIds", None) or [])
        for item in self.proxies:
            if item.get("ProxyId") in ids:
                item["Status"] = "running"
        return SimpleNamespace(RequestId="req-fake")

    def CloseProxies(self, request):
        self._record("CloseProxies", request)
        ids = list(getattr(request, "ProxyIds", None) or [])
        for item in self.proxies:
            if item.get("ProxyId") in ids:
                item["Status"] = "closed"
        return SimpleNamespace(RequestId="req-fake")

    def DestroyProxies(self, request):
        self._record("DestroyProxies", request)
        ids = list(getattr(request, "ProxyIds", None) or [])
        self.proxies = [t for t in self.proxies if t.get("ProxyId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_gaap", lambda: (models or FakeModels(), SimpleNamespace(GaapClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_proxy_is_idempotent(monkeypatch):
    fake = FakeGaapClient(proxies=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-proxy")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c for c, unused in fake.calls] == ["DescribeProxies"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DestroyProxies" not in [c for c, unused in fake.calls]


def test_absent_destroys_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"] is None
    assert fake.proxies == []
    ops = [c for c, unused in fake.calls]
    assert "DestroyProxies" in ops


# ---------------------------------------------------------------------------
# running / stopped flows
# ---------------------------------------------------------------------------


def test_running_requires_existing_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[])
    _make_module(monkeypatch, fake)
    _base(state="running", name="ghost-proxy")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "use state=present to create it" in exc.value.args[0]["msg"]


def test_running_already_running_is_idempotent(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "OpenProxies" not in [c for c, unused in fake.calls]


def test_running_opens_closed_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy(Status="closed")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"]["Status"] == "running"
    ops = [c for c, unused in fake.calls]
    assert "OpenProxies" in ops


def test_running_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy(Status="closed")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"]["Status"] == "closed"
    assert "OpenProxies" not in [c for c, unused in fake.calls]


def test_stopped_already_closed_is_idempotent(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy(Status="closed")])
    _make_module(monkeypatch, fake)
    _base(state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "CloseProxies" not in [c for c, unused in fake.calls]


def test_stopped_closes_running_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"]["Status"] == "closed"
    ops = [c for c, unused in fake.calls]
    assert "CloseProxies" in ops


def test_stopped_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"]["Status"] == "running"
    assert "CloseProxies" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeGaapClient(proxies=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "is required when creating a GAAP proxy" in exc.value.args[0]["msg"]


def test_create_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="prod-gaap",
        access_region="ap-guangzhou",
        real_server_region="ap-hongkong",
        bandwidth=20,
        concurrent=2,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    proxy = result["proxy"]
    assert proxy["ProxyName"] == "prod-gaap"
    assert proxy["Bandwidth"] == 20
    assert proxy["Status"] == "running"
    assert len(fake.proxies) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeProxies"
    assert "CreateProxy" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(proxies=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="prod-gaap",
        access_region="ap-guangzhou",
        real_server_region="ap-hongkong",
        bandwidth=20,
        concurrent=2,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.proxies == []
    assert "CreateProxy" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-proxy flows
# ---------------------------------------------------------------------------


def test_existing_proxy_no_drift_is_idempotent(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-gaap")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["proxy"]["ProxyId"] == "proxy-aaaaaaaa"


def test_rename_proxy(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    module_args(state="present", proxy_id="proxy-aaaaaaaa", name="prod-gaap-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["proxy"]["ProxyName"] == "prod-gaap-v2"
    ops = [c for c, unused in fake.calls]
    assert "ModifyProxiesAttribute" in ops


def test_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", proxy_id="proxy-aaaaaaaa", name="prod-gaap-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.proxies[0]["ProxyName"] == "prod-gaap"
    assert "ModifyProxiesAttribute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeGaapClient(proxies=[_proxy(), _proxy(ProxyId="proxy-bbbbbbbb")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-gaap")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple GAAP proxies have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeProxies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-gaap")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
