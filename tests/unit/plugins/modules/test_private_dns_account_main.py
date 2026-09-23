"""Unit tests for the private_dns_account write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake Private DNS
client whose create/delete operations mutate a relationship store, so the
post-write ``DescribePrivateDNSAccountList`` refetch used by the waiter
converges immediately.

Scenario matrix:

* absent on a missing relationship (idempotent) / check-mode delete / real
  delete with post-delete waiter refetch
* present on a missing relationship (check mode and real create)
* idempotent no-op when a matching UIN already exists
* in-place account-name drift is rejected (must delete first)
* multiple matches for the same UIN fail before any mutation
* waiter timeout surfaces as a module failure (delete never converges)
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_private_dns_account.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import private_dns_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

UIN = "100000000001"
ACCOUNT = "consumer@example.com"


def _binding(**overrides):
    item = {"Uin": UIN, "Account": ACCOUNT}
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"uin": UIN, "account": ACCOUNT}
    params.update(overrides)
    return module_args(**params)


class FakePrivatednsClient(object):
    """In-memory Private DNS client mutating a cross-account store."""

    def __init__(self, accounts=None, delete_noop=False):
        self.accounts = [copy.deepcopy(d) for d in (accounts or [])]
        self.delete_noop = delete_noop
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrivateDNSAccountList(self, request):
        self._record("DescribePrivateDNSAccountList", request)
        start = int(request.Offset)
        page = self.accounts[start:start + int(request.Limit)]
        return SimpleNamespace(
            AccountSet=[FakeResource(dict(item)) for item in page],
            TotalCount=len(self.accounts),
            RequestId="req-fake",
        )

    def CreatePrivateDNSAccount(self, request):
        self._record("CreatePrivateDNSAccount", request)
        self._next += 1
        self.accounts.append({"Uin": request.Account.Uin, "Account": request.Account.Account})
        return SimpleNamespace(RequestId="req-fake")

    def DeletePrivateDNSAccount(self, request):
        self._record("DeletePrivateDNSAccount", request)
        if not self.delete_noop:
            self.accounts = [item for item in self.accounts if str(item["Uin"]) != str(request.Account.Uin)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(PrivatednsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_relationship_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account_binding"] is None
    assert [name for name, unused in fake.calls] == ["DescribePrivateDNSAccountList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient(accounts=[_binding()]))
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_binding"] == _binding()
    assert len(fake.accounts) == 1
    assert "DeletePrivateDNSAccount" not in [name for name, unused in fake.calls]


def test_absent_deletes_relationship(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient(accounts=[_binding()]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_binding"] is None
    assert fake.accounts == []
    request = _find_call(fake, "DeletePrivateDNSAccount")
    assert request.Account.Uin == UIN
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribePrivateDNSAccountList", "DeletePrivateDNSAccount", "DescribePrivateDNSAccountList"]


def test_absent_waiter_times_out_when_delete_does_not_converge(monkeypatch):
    _make_module(monkeypatch, FakePrivatednsClient(accounts=[_binding()], delete_noop=True))
    _base(state="absent", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting" in payload["msg"]
    assert payload["uin"] == UIN


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_idempotent_when_relationship_exists(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient(accounts=[_binding()]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account_binding"] == _binding()
    assert [name for name, unused in fake.calls] == ["DescribePrivateDNSAccountList"]


def test_present_account_name_drift_is_rejected(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient(accounts=[_binding(Account="old@example.com")]))
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be updated in place" in exc.value.args[0]["msg"]
    assert len(fake.accounts) == 1


def test_present_create_relationship(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_binding"] == _binding()
    assert len(fake.accounts) == 1
    request = _find_call(fake, "CreatePrivateDNSAccount")
    assert request.Account.Uin == UIN
    assert request.Account.Account == ACCOUNT
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribePrivateDNSAccountList"
    assert ops[-1] == "DescribePrivateDNSAccountList"  # post-write waiter refetch


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_binding"] == _binding()  # desired projection
    assert fake.accounts == []
    assert "CreatePrivateDNSAccount" not in [name for name, unused in fake.calls]


def test_present_multiple_matches_fail(monkeypatch):
    _make_module(
        monkeypatch,
        FakePrivatednsClient(accounts=[_binding(), _binding(Account="other@example.com")]),
    )
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Private DNS account relationships" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = _make_module(monkeypatch, FakePrivatednsClient())
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "uin" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrivateDNSAccountList(self, request):
            raise Boom("privatedns unavailable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "privatedns unavailable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_private_dns_account.py)
# ---------------------------------------------------------------------------


def test_account_object_and_mutation_request_preserve_uin():
    value = mod.mutation_request(FakeModels(), "CreatePrivateDNSAccountRequest", UIN, ACCOUNT)
    assert value.Account.Uin == UIN
    assert value.Account.Account == ACCOUNT
    assert mod.account_object(FakeModels(), "1", "a").Uin == "1"


def test_list_request_is_bounded():
    value = mod.list_request(FakeModels(), 200)
    assert (value.Offset, value.Limit) == (200, 100)
