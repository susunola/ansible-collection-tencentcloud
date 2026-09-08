"""Unit tests for the cdn_domain write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CDN client
whose write operations mutate the domain store, so the module's post-write
``find_domain`` refetch and the status waiter converge immediately.

Scenario matrix:

* absent on a missing domain (idempotent no-op)
* absent with a matching online domain (stop, wait, delete) and check mode
* absent on an already offline domain (delete without stop)
* running/stopped state transitions including check mode and no-ops
* creation when missing (required-parameter guard, check mode, happy path)
* no-op when nothing drifts and update when drift exists (plus check mode)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdn_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = {
    "Domain": "cdn.example.com",
    "Status": "online",
    "ServiceType": "web",
    "ProjectId": 0,
    "Area": "mainland",
    "Origin": {
        "Origins": ["origin.example.com"],
        "OriginType": "domain",
        "OriginPullProtocol": "http",
        "BackupOrigins": [],
    },
}


def _domain(**overrides):
    item = copy.deepcopy(DOMAIN)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeCdnClient(object):
    """In-memory CDN client mutating a small domain store."""

    def __init__(self, domains=None):
        self.domains = [copy.deepcopy(t) for t in (domains or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, domain):
        for item in self.domains:
            if item.get("Domain") == domain:
                return item
        return None

    def _matching(self, request):
        filters = getattr(request, "Filters", None) or []
        for item in filters:
            if item.Name == "domain":
                return item.Value[0]
        return None

    def DescribeDomains(self, request):
        self._record("DescribeDomains", request)
        domain = self._matching(request)
        matches = [dict(t) for t in self.domains if t.get("Domain") == domain]
        return SimpleNamespace(Domains=[FakeResource(t) for t in matches])

    def AddCdnDomain(self, request):
        self._record("AddCdnDomain", request)
        self._next += 1
        origin = getattr(request, "Origin", None)
        item = {
            "Domain": getattr(request, "Domain", None),
            "Status": "online",
            "ServiceType": getattr(request, "ServiceType", None),
            "ProjectId": getattr(request, "ProjectId", None),
            "Area": getattr(request, "Area", None),
            "Origin": {
                "Origins": getattr(origin, "Origins", None),
                "OriginType": getattr(origin, "OriginType", None),
                "OriginPullProtocol": getattr(origin, "OriginPullProtocol", None),
                "BackupOrigins": getattr(origin, "BackupOrigins", None) or [],
            },
        }
        self.domains.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateDomainConfig(self, request):
        self._record("UpdateDomainConfig", request)
        item = self._find(getattr(request, "Domain", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        if getattr(request, "ServiceType", None) is not None:
            item["ServiceType"] = request.ServiceType
        if getattr(request, "ProjectId", None) is not None:
            item["ProjectId"] = request.ProjectId
        if getattr(request, "Area", None) is not None:
            item["Area"] = request.Area
        origin = getattr(request, "Origin", None)
        if origin is not None:
            existing = item.setdefault("Origin", {})
            for attr in ("Origins", "OriginType", "OriginPullProtocol", "BackupOrigins"):
                if getattr(origin, attr, None) is not None:
                    existing[attr] = getattr(origin, attr)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCdnDomain(self, request):
        self._record("DeleteCdnDomain", request)
        self.domains = [t for t in self.domains if t.get("Domain") != getattr(request, "Domain", None)]
        return SimpleNamespace(RequestId="req-fake")

    def StartCdnDomain(self, request):
        self._record("StartCdnDomain", request)
        item = self._find(getattr(request, "Domain", None))
        if item is not None:
            item["Status"] = "online"
        return SimpleNamespace(RequestId="req-fake")

    def StopCdnDomain(self, request):
        self._record("StopCdnDomain", request)
        item = self._find(getattr(request, "Domain", None))
        if item is not None:
            item["Status"] = "offline"
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cdn", lambda: (models or FakeModels(), SimpleNamespace(CdnClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_domain_is_idempotent(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="ghost.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert _ops(fake) == ["DescribeDomains"]


def test_domain_is_required(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain is required" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdnClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.domains) == 1
    assert "DeleteCdnDomain" not in _ops(fake)
    assert "StopCdnDomain" not in _ops(fake)


def test_absent_online_domain_stops_then_deletes(monkeypatch):
    fake = FakeCdnClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"] is None
    assert fake.domains == []
    ops = _ops(fake)
    assert "StopCdnDomain" in ops
    assert "DeleteCdnDomain" in ops
    assert ops.index("StopCdnDomain") < ops.index("DeleteCdnDomain")


def test_absent_offline_domain_deletes_without_stop(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.domains == []
    ops = _ops(fake)
    assert "StopCdnDomain" not in ops
    assert "DeleteCdnDomain" in ops


# ---------------------------------------------------------------------------
# running / stopped state transitions
# ---------------------------------------------------------------------------


def test_running_on_missing_domain_fails(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(state="running", domain="cdn.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "use state=present" in exc.value.args[0]["msg"]


def test_running_already_online_is_idempotent(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="online")])
    _make_module(monkeypatch, fake)
    _base(state="running", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "StartCdnDomain" not in _ops(fake)


def test_running_starts_offline_domain(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(state="running", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    # the module reports the pre-write snapshot it fetched before starting
    assert result["domain"]["Status"] == "offline"
    assert "StartCdnDomain" in _ops(fake)


def test_running_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="running", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Status"] == "offline"
    assert "StartCdnDomain" not in _ops(fake)


def test_stopped_already_offline_is_idempotent(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="offline")])
    _make_module(monkeypatch, fake)
    _base(state="stopped", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "StopCdnDomain" not in _ops(fake)


def test_stopped_stops_online_domain(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="online")])
    _make_module(monkeypatch, fake)
    _base(state="stopped", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    # the module reports the pre-write snapshot it fetched before stopping
    assert result["domain"]["Status"] == "online"
    assert "StopCdnDomain" in _ops(fake)


def test_stopped_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdnClient(domains=[_domain(Status="online")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="stopped", domain="cdn.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "StopCdnDomain" not in _ops(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_add_parameters(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(state="present", domain="cdn.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "required when adding" in payload["msg"]
    for key in ("service_type", "origins", "origin_type"):
        assert key in payload["msg"]


def test_create_domain(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        domain="cdn.example.com",
        service_type="web",
        origins=["origin.example.com"],
        origin_type="domain",
        origin_protocol="http",
        project_id=100,
        area="global",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Domain"] == "cdn.example.com"
    assert result["domain"]["Status"] == "online"
    assert result["domain"]["ProjectId"] == 100
    assert result["domain"]["Area"] == "global"
    assert result["domain"]["Origin"]["Origins"] == ["origin.example.com"]
    assert len(fake.domains) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeDomains"
    assert "AddCdnDomain" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdnClient(domains=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        domain="cdn.example.com",
        service_type="web",
        origins=["origin.example.com"],
        origin_type="domain",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.domains == []
    assert "AddCdnDomain" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-domain flows
# ---------------------------------------------------------------------------


def test_existing_domain_no_drift_is_idempotent(monkeypatch):
    fake = FakeCdnClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        domain="cdn.example.com",
        service_type="web",
        origins=["origin.example.com"],
        origin_type="domain",
        origin_protocol="http",
        project_id=0,
        area="mainland",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domain"]["Domain"] == "cdn.example.com"
    assert "UpdateDomainConfig" not in _ops(fake)


def test_existing_domain_drift_updates(monkeypatch):
    fake = FakeCdnClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        domain="cdn.example.com",
        service_type="download",
        origins=["origin2.example.com"],
        origin_type="domain",
        origin_protocol="http",
        project_id=0,
        area="mainland",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["ServiceType"] == "download"
    assert result["domain"]["Origin"]["Origins"] == ["origin2.example.com"]
    assert "UpdateDomainConfig" in _ops(fake)


def test_existing_domain_check_mode_dry_run(monkeypatch):
    fake = FakeCdnClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        domain="cdn.example.com",
        service_type="download",
        origins=["origin.example.com"],
        origin_type="domain",
        origin_protocol="http",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.domains[0]["ServiceType"] == "web"
    assert "UpdateDomainConfig" not in _ops(fake)


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDomains(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", domain="cdn.example.com", service_type="web", origins=["x"], origin_type="domain")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
