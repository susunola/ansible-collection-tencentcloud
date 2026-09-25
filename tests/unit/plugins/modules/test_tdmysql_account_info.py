# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the tdmysql_account_info read module.

The module lists every account on an instance, or narrows to the single
account identified by an exact ``username``/``host`` pair. Being exact is the
point of the pair, so it is asserted in both directions: a host that only
prefix-matches must not be silently reported as the account the caller asked
for, and a pair that matches more than one row must fail instead of picking
one. Exact mode also makes a second, optional API call for the account's
global privileges; the tests pin that the call happens only for a unique
match, that the payload carries the privileges sorted, and that the privilege
request is scoped to the whole account rather than one object.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_account_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcd1234"

ACCOUNTS = [
    {"UserName": "reporting", "Host": "10.%", "Description": "Read-only reporting account"},
    {"UserName": "reporting", "Host": "%", "Description": "Read-only reporting account"},
    {"UserName": "app", "Host": "%", "Description": "Application account"},
]

PRIVILEGES = ["UPDATE", "SELECT", "INSERT"]


class FakeTdmysqlClient(object):
    """Records every call and returns canned TDSQL MySQL responses."""

    def __init__(self, accounts=None, privileges=None):
        self.accounts = [dict(item) for item in (accounts if accounts is not None else ACCOUNTS)]
        self.privileges = list(privileges if privileges is not None else PRIVILEGES)
        self.calls = []

    def DescribeUsers(self, request):
        self.calls.append(("DescribeUsers", request))
        return FakeResource({"Users": [FakeResource(item) for item in self.accounts],
                             "RequestId": "req-users"})

    def DescribeUserPrivileges(self, request):
        self.calls.append(("DescribeUserPrivileges", request))
        return FakeResource({"Privileges": list(self.privileges), "RequestId": "req-privileges"})

    def operations(self):
        return [name for name, _request in self.calls]


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# listing every account
# ---------------------------------------------------------------------------

def test_listing_returns_every_account(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert [(item["UserName"], item["Host"]) for item in result["accounts"]] == [
        ("reporting", "10.%"), ("reporting", "%"), ("app", "%"),
    ]
    assert result["request_id"] == "req-users"
    assert client.operations() == ["DescribeUsers"]


def test_listing_sends_the_instance_id(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.InstanceId == INSTANCE_ID


def test_listing_an_instance_with_no_accounts_is_empty(monkeypatch):
    client = FakeTdmysqlClient(accounts=[])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["accounts"] == []
    assert result["request_id"] == "req-users"


def test_listing_every_account_never_fetches_privileges(monkeypatch):
    """The privilege call belongs to exact mode only. Listing all accounts
    with the default ``include_global_privileges=true`` must still issue the
    one list request."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, include_global_privileges=True)
    result = run(mod.run_module)

    assert client.operations() == ["DescribeUsers"]
    assert all("GlobalPrivileges" not in item for item in result["accounts"])


# ---------------------------------------------------------------------------
# the exact username and host pair
# ---------------------------------------------------------------------------

def test_exact_pair_selects_one_account(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="10.%",
                include_global_privileges=False)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert [(item["UserName"], item["Host"]) for item in result["accounts"]] == [("reporting", "10.%")]
    assert client.operations() == ["DescribeUsers"]


def test_exact_pair_disambiguates_a_shared_username(monkeypatch):
    """Two accounts share the username; the host is what makes the pair
    exact, so only the one whose host matches is returned."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="%",
                include_global_privileges=False)
    result = run(mod.run_module)

    assert [(item["UserName"], item["Host"]) for item in result["accounts"]] == [("reporting", "%")]


def test_exact_pair_matches_the_host_exactly(monkeypatch):
    """A host that merely shares a prefix with a stored host is not the
    requested account: the comparison is on the whole value."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="10.0.0.%")
    result = run(mod.run_module)

    assert result["accounts"] == []
    assert client.operations() == ["DescribeUsers"]


def test_exact_pair_matching_multiple_accounts_fails(monkeypatch):
    duplicate = {"UserName": "reporting", "Host": "%", "Description": "duplicate"}
    client = FakeTdmysqlClient(accounts=[dict(duplicate), dict(duplicate)])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="%")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple TDSQL MySQL accounts matched the exact username and host"
    assert "accounts" not in payload
    # The ambiguity is detected before the privilege fetch.
    assert client.operations() == ["DescribeUsers"]


# ---------------------------------------------------------------------------
# global privileges for the exact account
# ---------------------------------------------------------------------------

def test_exact_mode_fetches_the_global_privileges(monkeypatch):
    client = FakeTdmysqlClient(privileges=["UPDATE", "SELECT", "INSERT"])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="10.%")
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["accounts"][0]["GlobalPrivileges"] == ["INSERT", "SELECT", "UPDATE"]
    assert result["request_id"] == "req-privileges"
    assert client.operations() == ["DescribeUsers", "DescribeUserPrivileges"]


def test_privilege_request_scopes_the_whole_account(monkeypatch):
    """DescribeUserPrivileges is asked for global privileges, so the object
    coordinates are wildcards rather than one database or table."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="10.%")
    run(mod.run_module)
    request = client.calls[1][1]
    assert request.InstanceId == INSTANCE_ID
    assert request.UserName == "reporting"
    assert request.Host == "10.%"
    assert (request.DbName, request.ObjectType, request.Object, request.ColName) == ("*", "*", "*", "*")


def test_include_global_privileges_false_skips_the_fetch(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="10.%",
                include_global_privileges=False)
    result = run(mod.run_module)

    assert client.operations() == ["DescribeUsers"]
    assert result["request_id"] == "req-users"
    assert "GlobalPrivileges" not in result["accounts"][0]


def test_exact_mode_without_a_match_does_not_fetch_privileges(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, username="reporting", host="nope.example.com")
    result = run(mod.run_module)

    assert result["accounts"] == []
    assert client.operations() == ["DescribeUsers"]


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

def test_instance_id_is_required(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id" in exc.value.args[0]["msg"]
    assert client.calls == []


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_sdk_error_is_surfaced(monkeypatch):
    _wire(monkeypatch, _BoomClient())
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "service exploded" in payload["error"]
    assert payload["error_kind"] == "other"
