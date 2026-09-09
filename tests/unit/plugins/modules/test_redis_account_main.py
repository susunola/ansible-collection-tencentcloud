"""Unit tests for the redis_account write module (run_module flows).

Manages a named Redis account with ``present``/``absent`` lifecycle.
``password`` is optional and ``no_log``: it is only required for creation or
when ``rotate_password=true``. Presence is determined by matching
``AccountName`` in ``DescribeInstanceAccount``; updates go through
``ModifyInstanceAccount`` (password included only for explicit rotation),
creation through ``CreateInstanceAccount`` and removal through
``DeleteInstanceAccount``.

Scenario matrix:

* absent on a missing account is idempotent
* absent with an existing account deletes (check mode is a dry run)
* creation when missing, with the password guard
* no-op when the account matches (no password rotation requested)
* privilege/readonly-policy/remark drift triggers a modify without a password
* ``rotate_password=true`` forces a modify carrying the new password
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import redis_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCOUNT = {
    "InstanceId": "crs-abc123",
    "AccountName": "application",
    "Privilege": "rw",
    "ReadonlyPolicy": ["master"],
    "Remark": "",
    "AccountPassword": "old-secret",
}


def _account(**overrides):
    item = copy.deepcopy(ACCOUNT)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "instance_id": "crs-abc123",
        "name": "application",
        "privilege": "rw",
        "readonly_policy": ["master"],
        "remark": "",
        "encrypt_password": False,
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class FakeRedisClient(object):
    """In-memory Redis client storing named accounts for one instance."""

    def __init__(self, accounts=None):
        self.accounts = [copy.deepcopy(a) for a in (accounts or [])]
        self.calls = []

    def _by_name(self, name):
        for item in self.accounts:
            if item.get("AccountName") == name:
                return item
        return None

    def DescribeInstanceAccount(self, request):
        self.calls.append(("DescribeInstanceAccount", request))
        return SimpleNamespace(Accounts=[FakeResource(a) for a in self.accounts], Total=len(self.accounts))

    def CreateInstanceAccount(self, request):
        self.calls.append(("CreateInstanceAccount", request))
        item = {
            "InstanceId": request.InstanceId,
            "AccountName": request.AccountName,
            "AccountPassword": request.AccountPassword,
            "Privilege": request.Privilege,
            "ReadonlyPolicy": list(request.ReadonlyPolicy or []),
            "Remark": request.Remark,
            "EncryptPassword": request.EncryptPassword,
        }
        self.accounts.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyInstanceAccount(self, request):
        self.calls.append(("ModifyInstanceAccount", request))
        item = self._by_name(request.AccountName)
        if item is not None:
            if request.AccountPassword is not None:
                item["AccountPassword"] = request.AccountPassword
            item["Privilege"] = request.Privilege
            item["ReadonlyPolicy"] = list(request.ReadonlyPolicy or [])
            item["Remark"] = request.Remark
        return SimpleNamespace(RequestId="req-fake")

    def DeleteInstanceAccount(self, request):
        self.calls.append(("DeleteInstanceAccount", request))
        self.accounts = [a for a in self.accounts if a.get("AccountName") != request.AccountName]
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(RedisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_account_is_idempotent(monkeypatch):
    fake = FakeRedisClient(accounts=[])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert [name for name, unused in fake.calls] == ["DescribeInstanceAccount"]


def test_absent_deletes_account(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeInstanceAccount", "DeleteInstanceAccount"]


def test_absent_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountName"] == "application"  # current shown as preview
    assert len(fake.accounts) == 1
    assert "DeleteInstanceAccount" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_account(monkeypatch):
    fake = FakeRedisClient(accounts=[])
    _make_module(monkeypatch, fake)
    _run_args(password="new-secret", remark="billing app")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountName"] == "application"
    assert result["account"]["Remark"] == "billing app"
    assert len(fake.accounts) == 1
    assert fake.accounts[0]["AccountPassword"] == "new-secret"
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeInstanceAccount"
    assert "CreateInstanceAccount" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(accounts=[])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, password="new-secret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    assert "CreateInstanceAccount" not in [name for name, unused in fake.calls]


def test_create_without_password_fails(monkeypatch):
    fake = FakeRedisClient(accounts=[])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-account flows
# ---------------------------------------------------------------------------


def test_existing_account_no_drift_is_idempotent(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["Privilege"] == "rw"
    assert "ModifyInstanceAccount" not in [name for name, unused in fake.calls]


def test_privilege_drift_modifies_without_password(monkeypatch):
    fake = FakeRedisClient(accounts=[_account(Privilege="r")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Privilege"] == "rw"
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeInstanceAccount", "ModifyInstanceAccount", "DescribeInstanceAccount"]
    modify = [request for name, request in fake.calls if name == "ModifyInstanceAccount"][0]
    assert modify.AccountPassword is None
    assert modify.Privilege == "rw"


def test_readonly_policy_drift_modifies(monkeypatch):
    fake = FakeRedisClient(accounts=[_account(ReadonlyPolicy=["master", "replica"])])
    _make_module(monkeypatch, fake)
    _run_args(readonly_policy=["master"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["ReadonlyPolicy"] == ["master"]


def test_rotate_password_forces_modify(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args(password="rotated-secret", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [name for name, unused in fake.calls]
    assert "ModifyInstanceAccount" in ops
    modify = [request for name, request in fake.calls if name == "ModifyInstanceAccount"][0]
    assert modify.AccountPassword == "rotated-secret"
    assert fake.accounts[0]["AccountPassword"] == "rotated-secret"


def test_rotate_password_without_password_fails(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeRedisClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["account"]["AccountName"] == "application"
