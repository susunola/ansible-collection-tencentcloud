"""Unit tests for the scf_custom_domain write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SCF client that
mutates a domain-name keyed store, so the module's post-write
``ListCustomDomains`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the domain already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_custom_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _domain(name, protocol="HTTP"):
    return FakeResource({"Domain": name, "Protocol": protocol})


class FakeScfClient(object):
    """In-memory SCF client mutating a custom-domain store keyed by domain."""

    def __init__(self, domains=None):
        self.domains = list(domains or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def ListCustomDomains(self, request):
        self._record("ListCustomDomains", request)
        return SimpleNamespace(
            Domains=[FakeResource(dict(t._data)) for t in self.domains],
            Total=len(self.domains),
            RequestId="req-fake",
        )

    def CreateCustomDomain(self, request):
        self._record("CreateCustomDomain", request)
        self.domains.append(_domain(getattr(request, "Domain", ""), getattr(request, "Protocol", "HTTP")))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCustomDomain(self, request):
        self._record("DeleteCustomDomain", request)
        target = getattr(request, "Domain", "")
        self.domains = [t for t in self.domains if t.Domain != target]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_scf", lambda: (models or FakeModels(), SimpleNamespace(ScfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeScfClient(domains=[])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", protocol="HTTPS", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"] == "functions.example.com"
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListCustomDomains"
    assert "CreateCustomDomain" in ops
    assert "DeleteCustomDomain" not in ops
    created = [r for c, r in fake.calls if c == "CreateCustomDomain"][0]
    assert created.Domain == "functions.example.com"
    assert created.Protocol == "HTTPS"


def test_delete_when_present(monkeypatch):
    fake = FakeScfClient(domains=[_domain("functions.example.com")])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteCustomDomain" in ops
    assert "CreateCustomDomain" not in ops
    assert fake.domains == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeScfClient(domains=[_domain("functions.example.com")])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    ops = [c for c, unused in fake.calls]
    assert ops == ["ListCustomDomains"]
    assert "CreateCustomDomain" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeScfClient(domains=[])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteCustomDomain" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient(domains=[])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateCustomDomain" not in [c for c, unused in fake.calls]
    assert fake.domains == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient(domains=[_domain("functions.example.com")])
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteCustomDomain" not in [c for c, unused in fake.calls]
    assert len(fake.domains) == 1


# ---------------------------------------------------------------------------
# error path
# ---------------------------------------------------------------------------


def test_sdk_failure_fails(monkeypatch):
    fake = FakeScfClient(domains=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateCustomDomain = _raise_error
    _make_module(monkeypatch, fake)
    module_args(domain="functions.example.com", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
