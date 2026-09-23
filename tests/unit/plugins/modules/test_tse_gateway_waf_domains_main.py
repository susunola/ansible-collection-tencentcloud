"""Unit tests for the tse_gateway_waf_domains write module.

Drives ``run_module()`` against an in-memory fake TSE client whose
create / delete domain calls mutate a registered-domain set so post-write
describes converge immediately.

Domain-set semantics:

* ``state=present`` adds the listed domains; with ``purge_unlisted`` it also
  deletes registered domains that were not listed.
* ``state=absent`` deletes exactly the listed domains out of the registered
  set (the binding-removal style used by the waf_domains family).

Scenario matrix:

* argument guards (empty list, duplicate domains, purge with absent)
* present: no-op, add-only, purge-only, add+purge, check-mode dry run
* absent: no-op when nothing registered, remove a subset, check mode
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_waf_domains as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_waf_domains import request
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

REGISTERED = ["api.example.com", "www.example.com"]


def _registered(*domains):
    return sorted(set(domains))


def _domains_args(**overrides):
    params = {
        "gateway_id": "gateway-1001",
        "domains": ["api.example.com"],
        "state": "present",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client holding the gateway's registered WAF domain set."""

    def __init__(self, domains=None):
        self.domains = sorted(set(domains or []))
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWafDomains(self, request):
        self._record("DescribeWafDomains", request)
        return SimpleNamespace(Result=SimpleNamespace(Domains=list(self.domains)), RequestId="req-fake")

    def CreateWafDomains(self, request):
        self._record("CreateWafDomains", request)
        self.domains = sorted(set(self.domains) | set(getattr(request, "Domains", None) or []))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteWafDomains(self, request):
        self._record("DeleteWafDomains", request)
        self.domains = sorted(set(self.domains) - set(getattr(request, "Domains", None) or []))
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# argument guards
# ---------------------------------------------------------------------------


def test_empty_domains_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _domains_args(domains=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domains must contain at least one entry" in exc.value.args[0]["msg"]


def test_duplicate_domains_fail(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _domains_args(domains=["api.example.com", "api.example.com"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domains must not contain duplicates" in exc.value.args[0]["msg"]


def test_purge_unlisted_with_absent_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _domains_args(state="absent", purge_unlisted=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge_unlisted is only valid with state=present" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(domains=REGISTERED)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_domains"] == sorted(REGISTERED)
    assert "CreateWafDomains" not in _names(fake)
    assert "DeleteWafDomains" not in _names(fake)


def test_present_adds_domains(monkeypatch):
    fake = FakeTseClient(domains=["api.example.com"])
    _make_module(monkeypatch, fake)
    _domains_args(domains=["api.example.com", "docs.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_domains"] == sorted(["api.example.com", "docs.example.com"])
    assert result["added_domains"] == ["docs.example.com"]
    assert result["removed_domains"] == []
    assert fake.domains == sorted(["api.example.com", "docs.example.com"])
    assert "CreateWafDomains" in _names(fake)


def test_present_purge_removes_unlisted(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(domains=["api.example.com"], purge_unlisted=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_domains"] == ["api.example.com"]
    assert result["added_domains"] == []
    assert result["removed_domains"] == ["www.example.com"]
    assert fake.domains == ["api.example.com"]
    assert "DeleteWafDomains" in _names(fake)


def test_present_adds_and_purges(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(domains=["api.example.com", "docs.example.com"], purge_unlisted=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_domains"] == sorted(["api.example.com", "docs.example.com"])
    assert result["added_domains"] == ["docs.example.com"]
    assert result["removed_domains"] == ["www.example.com"]
    ops = _names(fake)
    assert "CreateWafDomains" in ops
    assert "DeleteWafDomains" in ops


def test_present_purge_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(domains=REGISTERED, purge_unlisted=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_domains"] == sorted(REGISTERED)


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(domains=["api.example.com"])
    _make_module(monkeypatch, fake)
    _domains_args(_ansible_check_mode=True, domains=["api.example.com", "docs.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["added_domains"] == ["docs.example.com"]
    assert result["waf_domains"] == sorted(["api.example.com", "docs.example.com"])
    assert fake.domains == ["api.example.com"]
    assert "CreateWafDomains" not in _names(fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(state="absent", domains=["ghost.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_domains"] == sorted(REGISTERED)
    assert "DeleteWafDomains" not in _names(fake)


def test_absent_removes_subset_of_registered(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(state="absent", domains=["api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_domains"] == ["www.example.com"]
    assert result["added_domains"] == []
    assert result["removed_domains"] == ["api.example.com"]
    assert fake.domains == ["www.example.com"]
    assert "DeleteWafDomains" in _names(fake)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(domains=REGISTERED)
    _make_module(monkeypatch, fake)
    _domains_args(_ansible_check_mode=True, state="absent", domains=["api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_domains"] == ["www.example.com"]
    assert fake.domains == sorted(REGISTERED)
    assert "DeleteWafDomains" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWafDomains(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _domains_args(domains=["api.example.com"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


class _Value(object):
    pass


def test_legacy_domain_request_maps_delta():
    value = request(_Value, {"gateway_id": "g1"}, ["api.example.com"])
    assert value.GatewayId == "g1"
    assert value.Domains == ["api.example.com"]
