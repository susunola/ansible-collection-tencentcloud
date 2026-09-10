"""Unit tests for the tdcpg_account write module (run_module flows).

``run_module()`` reconciles an existing TDSQL-C PostgreSQL account's
description and performs explicitly requested password rotation. It is
driven end to end against an in-memory fake client whose write operations
mutate an account store, so the post-write ``DescribeAccounts`` refetch
converges immediately.

Scenario matrix:

* idempotent no-op when the description already matches and no rotation is
  requested
* description drift update (check mode and real update)
* explicit password rotation with a converged description
* combined description drift plus rotation
* argument validation before any SDK call (missing required password,
  description over 256 chars)
* missing account and blanket ``sdk_error_payload`` failure paths
* legacy helper regression tests (folded from test_tdcpg_account.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdcpg_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "tdcpg-cluster-abc"
ACCOUNT_NAME = "root"


def _base(**overrides):
    params = {
        "cluster_id": CLUSTER_ID,
        "account_name": ACCOUNT_NAME,
        "description": "Platform administrator",
        "rotate_password": False,
    }
    params.update(overrides)
    return module_args(**params)


def _account(description="Platform administrator"):
    return {"AccountName": ACCOUNT_NAME, "AccountDescription": description, "ClusterId": CLUSTER_ID}


class FakeTdcpgClient(object):
    """In-memory TDSQL-C PostgreSQL client holding one account per cluster."""

    def __init__(self, account=None):
        self.account = copy.deepcopy(account) if account is not None else None
        self.calls = []
        self.last_request = None
        self.last_password_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        assert request.ClusterId == CLUSTER_ID
        account_set = [FakeResource(self.account)] if self.account is not None else []
        return SimpleNamespace(AccountSet=account_set, RequestId="req-fake")

    def ModifyAccountDescription(self, request):
        self._record("ModifyAccountDescription", request)
        self.last_request = request
        if self.account is not None:
            self.account["AccountDescription"] = request.AccountDescription
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        self.last_password_request = request
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdcpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_converged_description_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account()))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["AccountDescription"] == "Platform administrator"
    assert "password_rotated" not in result
    assert _names(fake) == ["DescribeAccounts"]


def test_omitted_description_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account("custom label")))
    _base(description=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["AccountDescription"] == "custom label"
    assert _names(fake) == ["DescribeAccounts"]


# ---------------------------------------------------------------------------
# description drift flows
# ---------------------------------------------------------------------------


def test_description_drift_updates_account(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account("old label")))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountDescription"] == "Platform administrator"
    assert fake.account["AccountDescription"] == "Platform administrator"
    assert fake.last_request.AccountDescription == "Platform administrator"
    assert fake.last_request.AccountName == ACCOUNT_NAME
    assert _names(fake) == ["DescribeAccounts", "ModifyAccountDescription", "DescribeAccounts"]


def test_description_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account("old label")))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountDescription"] == "Platform administrator"
    assert "diff" in result
    assert fake.account["AccountDescription"] == "old label"
    assert _names(fake) == ["DescribeAccounts"]


# ---------------------------------------------------------------------------
# password rotation flows
# ---------------------------------------------------------------------------


def test_rotate_password_forces_change_when_converged(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account()))
    _base(password="n3w-s3cret", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["password_rotated"] is True
    assert result["account"]["AccountDescription"] == "Platform administrator"
    assert fake.last_password_request.AccountName == ACCOUNT_NAME
    assert fake.last_password_request.AccountPassword == "n3w-s3cret"
    assert _names(fake) == ["DescribeAccounts", "ResetAccountPassword", "DescribeAccounts"]


def test_rotate_password_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account()))
    _base(password="n3w-s3cret", rotate_password=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["password_rotated"] is True
    assert "ResetAccountPassword" not in _names(fake)


def test_description_drift_and_rotation_combined(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account("old label")))
    _base(password="n3w-s3cret", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["password_rotated"] is True
    assert fake.account["AccountDescription"] == "Platform administrator"
    assert fake.last_request.AccountDescription == "Platform administrator"
    assert fake.last_password_request.AccountPassword == "n3w-s3cret"
    assert _names(fake) == [
        "DescribeAccounts",
        "ModifyAccountDescription",
        "ResetAccountPassword",
        "DescribeAccounts",
    ]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_rotate_password_requires_password(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account()))
    _base(rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_description_too_long_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient(account=_account()))
    _base(description="x" * 257)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "description must not exceed 256" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_account_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "account was not found" in payload["msg"]
    assert payload["account_name"] == ACCOUNT_NAME
    assert _names(fake) == ["DescribeAccounts"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccounts(self, request):
            raise Boom("tdcpg endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tdcpg endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdcpg_account.py)
# ---------------------------------------------------------------------------


def test_account_requests_map_identity_and_secret():
    p = {"cluster_id": "c1", "account_name": "root", "description": "admin", "password": "secret"}
    description = mod.description_request(FakeModels(), p)
    assert description.ClusterId == "c1"
    assert description.AccountName == "root"
    assert description.AccountDescription == "admin"
    password = mod.password_request(FakeModels(), p)
    assert password.ClusterId == "c1"
    assert password.AccountName == "root"
    assert password.AccountPassword == "secret"
