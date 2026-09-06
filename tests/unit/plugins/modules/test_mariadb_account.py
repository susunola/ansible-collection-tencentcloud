"""Unit tests for the mariadb_account write module (helpers + run_module).

Creates and deletes TencentDB for MariaDB accounts, updates the
description and explicitly rotates passwords. An account is identified by
instance_id + username + host (host defaults to ``%`` and an API-side
empty host compares equal to it). ReadOnly/DelayThresh/SlaveConst/
MaxUserConnections are immutable once the account exists; description
drift becomes ModifyAccountDescription and ``rotate_password`` triggers
ResetAccountPassword. Password is required on a real create but check
mode never validates it (no write happens).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mariadb_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _account(**overrides):
    """API-shaped account dict; fresh copy per call."""
    item = {
        "InstanceId": "tdsql-abc",
        "UserName": "app",
        "Host": "%",
        "Description": "Application account",
        "ReadOnly": 0,
        "DelayThresh": 10,
        "SlaveConst": 0,
        "MaxUserConnections": 0,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "tdsql-abc",
        "username": "app",
        "host": "%",
        "password": None,
        "rotate_password": False,
        "description": "",
        "read_only": 0,
        "delay_threshold": 10,
        "sticky_replica": False,
        "max_user_connections": 0,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeMariadbClient(object):
    """In-memory MariadbClient stand-in storing account dicts.

    DescribeAccounts returns every account of the requested instance;
    Create/Delete/Modify-description address accounts by
    instance_id + username + host, mirroring the module's identity.
    ResetAccountPassword is recorded but stores nothing (the API never
    returns passwords).
    """

    def __init__(self, accounts=None):
        self.accounts = [dict(a) for a in (accounts or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _find_stored(self, request, include_user=True):
        for stored in self.accounts:
            if stored["InstanceId"] != request.InstanceId:
                continue
            if include_user and stored["UserName"] != request.UserName:
                continue
            if include_user and (stored["Host"] or "%") != getattr(request, "Host", "%"):
                continue
            return stored
        return None

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        users = [FakeResource(dict(a)) for a in self.accounts if a["InstanceId"] == request.InstanceId]
        return SimpleNamespace(Users=users, RequestId="req-fake")

    def CreateAccount(self, request):
        self._record("CreateAccount", request)
        self.accounts.append(
            {
                "InstanceId": request.InstanceId,
                "UserName": request.UserName,
                "Host": request.Host,
                "Description": request.Description,
                "ReadOnly": request.ReadOnly,
                "DelayThresh": request.DelayThresh,
                "SlaveConst": request.SlaveConst,
                "MaxUserConnections": request.MaxUserConnections,
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountDescription(self, request):
        self._record("ModifyAccountDescription", request)
        stored = self._find_stored(request)
        if stored is not None:
            stored["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccount(self, request):
        self._record("DeleteAccount", request)
        stored = self._find_stored(request)
        if stored is not None:
            self.accounts.remove(stored)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MariadbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_instance_id():
    request = mod.describe_request(FakeModels(), "tdsql-abc")
    assert request.InstanceId == "tdsql-abc"


def test_create_request_carries_all_fields():
    request = mod.create_request(
        FakeModels(),
        _params(
            host="10.0.0.0/8",
            password="secret",
            description="ETL",
            read_only=2,
            delay_threshold=15,
            sticky_replica=True,
            max_user_connections=100,
        ),
    )
    assert request.InstanceId == "tdsql-abc"
    assert request.UserName == "app"
    assert request.Host == "10.0.0.0/8"
    assert request.Password == "secret"
    assert request.Description == "ETL"
    assert request.ReadOnly == 2
    assert request.DelayThresh == 15
    assert request.SlaveConst == 1
    assert request.MaxUserConnections == 100


def test_description_request_fields():
    request = mod.description_request(FakeModels(), _params(description="new"))
    assert request.InstanceId == "tdsql-abc"
    assert request.UserName == "app"
    assert request.Host == "%"
    assert request.Description == "new"


def test_password_request_fields():
    request = mod.password_request(FakeModels(), _params(password="newsecret"))
    assert request.InstanceId == "tdsql-abc"
    assert request.UserName == "app"
    assert request.Host == "%"
    assert request.Password == "newsecret"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "tdsql-abc"
    assert request.UserName == "app"
    assert request.Host == "%"


def test_desired_maps_params():
    value = mod.desired(_params(sticky_replica=True, max_user_connections=50))
    assert value == {
        "UserName": "app",
        "Host": "%",
        "Description": "",
        "ReadOnly": 0,
        "DelayThresh": 10,
        "SlaveConst": 1,
        "MaxUserConnections": 50,
    }


def test_comparable_selects_seven_keys():
    value = mod.comparable(_account())
    assert set(value.keys()) == {
        "UserName",
        "Host",
        "Description",
        "ReadOnly",
        "DelayThresh",
        "SlaveConst",
        "MaxUserConnections",
    }
    assert value["Description"] == "Application account"


def test_find_matches_username_and_host(monkeypatch):
    fake = FakeMariadbClient([_account(), _account(UserName="other", Description="x")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["UserName"] == "app"
    assert value["Description"] == "Application account"


def test_find_ignores_other_instances(monkeypatch):
    fake = FakeMariadbClient([_account(InstanceId="tdsql-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_host_default_matches_empty_host(monkeypatch):
    # The API can report Host as empty; the module treats it as '%'.
    fake = FakeMariadbClient([_account(Host="")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value is not None


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMariadbClient([_account(Host="10.0.0.0/8")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_rotate_password_without_password_fails():
    _run_args(rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_absent_check_mode_delete_reports_current(monkeypatch):
    fake = FakeMariadbClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["UserName"] == "app"
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_absent_deletes_account(monkeypatch):
    fake = FakeMariadbClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert [c[0] for c in fake.calls] == ["DescribeAccounts", "DeleteAccount"]
    assert fake.calls[1][1].UserName == "app"
    assert fake.calls[1][1].Host == "%"
    assert fake.accounts == []


def test_present_noop(monkeypatch):
    fake = FakeMariadbClient([_account(Description="")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["UserName"] == "app"
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_present_check_mode_create_does_not_require_password(monkeypatch):
    # Check mode never writes, so the create-time password check is skipped.
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_present_real_create_requires_password(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]


def test_present_create_with_password(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args(password="secret", description="ETL")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "ETL"
    assert [c[0] for c in fake.calls] == ["DescribeAccounts", "CreateAccount", "DescribeAccounts"]
    assert fake.calls[1][1].Password == "secret"
    assert fake.calls[1][1].Description == "ETL"


def test_present_description_drift_updates_description(monkeypatch):
    fake = FakeMariadbClient([_account(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(password="secret", description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "new"
    assert [c[0] for c in fake.calls] == [
        "DescribeAccounts",
        "ModifyAccountDescription",
        "DescribeAccounts",
    ]
    assert fake.calls[1][1].Description == "new"


def test_present_rotate_password_only(monkeypatch):
    fake = FakeMariadbClient([_account(Description="")])
    _make_module(monkeypatch, fake)
    _run_args(password="newsecret", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [c[0] for c in fake.calls] == [
        "DescribeAccounts",
        "ResetAccountPassword",
        "DescribeAccounts",
    ]
    assert fake.calls[1][1].Password == "newsecret"


def test_present_rotate_password_with_description_drift(monkeypatch):
    fake = FakeMariadbClient([_account(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(password="newsecret", rotate_password=True, description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [c[0] for c in fake.calls] == [
        "DescribeAccounts",
        "ModifyAccountDescription",
        "ResetAccountPassword",
        "DescribeAccounts",
    ]


def test_present_immutable_read_only_drift_fails(monkeypatch):
    fake = FakeMariadbClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(password="secret", read_only=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"ReadOnly": {"before": 0, "after": 1}}
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_present_immutable_max_user_connections_drift_fails(monkeypatch):
    fake = FakeMariadbClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(password="secret", max_user_connections=50)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {
        "MaxUserConnections": {"before": 0, "after": 50}
    }


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMariadbClient([_account(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(password="secret", description="new", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "old"
    assert [c[0] for c in fake.calls] == ["DescribeAccounts"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
