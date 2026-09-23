"""Unit tests for the tcb_http_service_route write module (run_module flows).

``tcb_http_service_route`` manages an HTTP service domain and its route
configuration inside a CloudBase environment. The desired config is an SDK
shaped ``domain_config`` dict (carrying ``Routes`` etc.); drift detection
uses a recursive ``contains`` over the serialized current domain.

Scenario matrix:

* absent on a missing domain / existing domain (check-mode, real delete)
* present requires domain_config and a matching Domain field
* present no-drift idempotence (nested Routes payload)
* create / update (real, check mode)
* ambiguous multi-domain guard and blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcb_http_service_route as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = "api.example.com"

DOMAIN_CONFIG = {
    "Domain": DOMAIN,
    "Protocol": "https",
    "Routes": [
        {"Path": "/api", "UpstreamResourceType": "cloudrun", "UpstreamResourceName": "backend"},
    ],
}


def _config(**overrides):
    item = copy.deepcopy(DOMAIN_CONFIG)
    item.update(overrides)
    return item


def _d_args(**overrides):
    params = {"env_id": "env-abc123", "domain": DOMAIN}
    params.update(overrides)
    return module_args(**params)


class FakeTcbClient(object):
    """In-memory CloudBase client mutating a domain-route store."""

    def __init__(self, domains=None):
        self.domains = [copy.deepcopy(d) for d in (domains or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeHTTPServiceRoute(self, request):
        self._record("DescribeHTTPServiceRoute", request)
        return SimpleNamespace(
            Domains=[FakeResource(dict(d)) for d in self.domains],
            TotalCount=len(self.domains),
        )

    def CreateHTTPServiceRoute(self, request):
        self._record("CreateHTTPServiceRoute", request)
        self.domains.append(copy.deepcopy(request.Domain.__dict__))
        return SimpleNamespace()

    def ModifyHTTPServiceRoute(self, request):
        self._record("ModifyHTTPServiceRoute", request)
        value = copy.deepcopy(request.Domain.__dict__)
        self.domains = [d for d in self.domains if d.get("Domain") != value.get("Domain")]
        self.domains.append(value)
        return SimpleNamespace()

    def DeleteHTTPServiceRoute(self, request):
        self._record("DeleteHTTPServiceRoute", request)
        self.domains = [d for d in self.domains if d.get("Domain") != request.Domain]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_domain_is_idempotent(monkeypatch):
    fake = FakeTcbClient(domains=[])
    _make_module(monkeypatch, fake)
    _d_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"] is None
    assert [c for c, unused in fake.calls] == ["DescribeHTTPServiceRoute"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient(domains=[_config()])
    _make_module(monkeypatch, fake)
    _d_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert len(fake.domains) == 1
    assert "DeleteHTTPServiceRoute" not in [c for c, unused in fake.calls]


def test_absent_deletes_domain_route(monkeypatch):
    fake = FakeTcbClient(domains=[_config()])
    _make_module(monkeypatch, fake)
    _d_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert fake.domains == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteHTTPServiceRoute" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_requires_domain_config(monkeypatch):
    fake = FakeTcbClient(domains=[])
    _make_module(monkeypatch, fake)
    _d_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain_config is required" in exc.value.args[0]["msg"]


def test_domain_config_must_match_domain(monkeypatch):
    fake = FakeTcbClient(domains=[])
    _make_module(monkeypatch, fake)
    _d_args(state="present", domain_config=_config(Domain="other.example.com"))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain_config.Domain must match domain" in exc.value.args[0]["msg"]


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTcbClient(domains=[_config()])
    _make_module(monkeypatch, fake)
    _d_args(state="present", domain_config=_config())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"]["Domain"] == DOMAIN
    ops = [c for c, unused in fake.calls]
    assert "CreateHTTPServiceRoute" not in ops
    assert "ModifyHTTPServiceRoute" not in ops


def test_present_creates_route(monkeypatch):
    fake = FakeTcbClient(domains=[])
    _make_module(monkeypatch, fake)
    _d_args(state="present", domain_config=_config())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Domain"] == DOMAIN
    assert result["route"]["Routes"][0]["Path"] == "/api"
    assert len(fake.domains) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeHTTPServiceRoute"
    assert "CreateHTTPServiceRoute" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient(domains=[])
    _make_module(monkeypatch, fake)
    _d_args(_ansible_check_mode=True, state="present", domain_config=_config())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Domain"] == DOMAIN
    assert fake.domains == []
    assert "CreateHTTPServiceRoute" not in [c for c, unused in fake.calls]


def test_route_drift_updates_domain(monkeypatch):
    fake = FakeTcbClient(domains=[_config()])
    _make_module(monkeypatch, fake)
    drifted = _config(Protocol="http", Routes=[{"Path": "/v2", "UpstreamResourceType": "cloudrun", "UpstreamResourceName": "backend-v2"}])
    _d_args(state="present", domain_config=drifted)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Protocol"] == "http"
    assert len(fake.domains) == 1
    ops = [c for c, unused in fake.calls]
    assert "ModifyHTTPServiceRoute" in ops


def test_present_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient(domains=[_config()])
    _make_module(monkeypatch, fake)
    _d_args(_ansible_check_mode=True, state="present", domain_config=_config(Protocol="http"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Protocol"] == "http"
    assert fake.domains[0]["Protocol"] == "https"
    assert "ModifyHTTPServiceRoute" not in [c for c, unused in fake.calls]


def test_multiple_matching_domains_fail(monkeypatch):
    fake = FakeTcbClient(domains=[_config(), _config(Routes=[])])
    _make_module(monkeypatch, fake)
    _d_args(state="present", domain_config=_config())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CloudBase HTTP service domains" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeHTTPServiceRoute(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _d_args(state="present", domain_config=_config())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
