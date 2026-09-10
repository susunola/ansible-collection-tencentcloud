"""Unit tests for the tcb_auth_domain write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake TCB client
whose create/delete operations mutate an auth-domain store, so the
post-write ``DescribeAuthDomains`` refetch used by the waiter converges
immediately.

Scenario matrix:

* absent on a missing domain (idempotent) / SYSTEM-domain delete guard /
  check-mode delete / real delete with post-delete waiter refetch
* present on a missing domain (check mode and real create)
* idempotent no-op when the domain already exists
* multiple matching domains fail before any mutation
* waiter timeout surfaces as a module failure (delete never converges)
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tcb_auth_domain.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcb_auth_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENV_ID = "env-abcdefgh"
DOMAIN = "app.example.com"


def _domain(**overrides):
    item = {"Id": "domain-0001", "Domain": DOMAIN, "Type": "USER"}
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"env_id": ENV_ID, "domain": DOMAIN}
    params.update(overrides)
    return module_args(**params)


class FakeTcbClient(object):
    """In-memory TCB client mutating an environment-scoped auth-domain store."""

    def __init__(self, domains=None, delete_noop=False):
        self.domains = [copy.deepcopy(d) for d in (domains or [])]
        self.delete_noop = delete_noop
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAuthDomains(self, request):
        self._record("DescribeAuthDomains", request)
        return SimpleNamespace(
            Domains=[FakeResource(dict(item)) for item in self.domains],
            RequestId="req-fake",
        )

    def CreateAuthDomain(self, request):
        self._record("CreateAuthDomain", request)
        for domain in request.Domains:
            self._next += 1
            self.domains.append({"Id": "domain-%04d" % self._next, "Domain": domain, "Type": "USER"})
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAuthDomain(self, request):
        self._record("DeleteAuthDomain", request)
        if not self.delete_noop:
            doomed = set(request.DomainIds)
            self.domains = [item for item in self.domains if item["Id"] not in doomed]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_domain_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["auth_domain"] is None
    assert [name for name, unused in fake.calls] == ["DescribeAuthDomains"]


def test_absent_system_domain_cannot_be_deleted(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient(domains=[_domain(Type="SYSTEM")]))
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be deleted" in exc.value.args[0]["msg"]
    assert len(fake.domains) == 1


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient(domains=[_domain()]))
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_domain"] == _domain()
    assert len(fake.domains) == 1
    assert "DeleteAuthDomain" not in [name for name, unused in fake.calls]


def test_absent_deletes_domain(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient(domains=[_domain()]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_domain"] is None
    assert fake.domains == []
    request = _find_call(fake, "DeleteAuthDomain")
    assert request.EnvId == ENV_ID
    assert request.DomainIds == ["domain-0001"]
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeAuthDomains", "DeleteAuthDomain", "DescribeAuthDomains"]


def test_absent_waiter_times_out_when_delete_does_not_converge(monkeypatch):
    _make_module(monkeypatch, FakeTcbClient(domains=[_domain()], delete_noop=True))
    _base(state="absent", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting" in payload["msg"]
    assert payload["domain"] == DOMAIN


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_idempotent_when_domain_exists(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient(domains=[_domain()]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["auth_domain"] == _domain()
    assert [name for name, unused in fake.calls] == ["DescribeAuthDomains"]


def test_present_create_domain(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_domain"]["Domain"] == DOMAIN
    assert result["auth_domain"]["Type"] == "USER"
    assert len(fake.domains) == 1
    request = _find_call(fake, "CreateAuthDomain")
    assert request.EnvId == ENV_ID
    assert request.Domains == [DOMAIN]
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeAuthDomains"
    assert ops[-1] == "DescribeAuthDomains"  # post-write waiter refetch


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_domain"] == {"Domain": DOMAIN, "Type": "USER"}  # desired projection
    assert fake.domains == []
    assert "CreateAuthDomain" not in [name for name, unused in fake.calls]


def test_present_multiple_matching_domains_fail(monkeypatch):
    _make_module(
        monkeypatch,
        FakeTcbClient(domains=[_domain(), _domain(Id="domain-0002")]),
    )
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CloudBase authentication domains" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcbClient())
    module_args(domain=DOMAIN)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "env_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAuthDomains(self, request):
            raise Boom("tcb down")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tcb down" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcb_auth_domain.py)
# ---------------------------------------------------------------------------


def test_auth_domain_requests_are_environment_scoped():
    assert mod.describe_request(FakeModels(), "env-1").EnvId == "env-1"
    create = mod.create_request(FakeModels(), "env-1", "app.example.com")
    assert create.EnvId == "env-1"
    assert create.Domains == ["app.example.com"]
    delete = mod.delete_request(FakeModels(), "env-1", "domain-1")
    assert delete.EnvId == "env-1"
    assert delete.DomainIds == ["domain-1"]
