"""Unit tests for the ckafka_user write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CKafka client whose user
store is mutated by create / password rotation / delete so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing user (idempotent no-op)
* absent with a matching user (check-mode dry run, real delete)
* creation when missing (happy path, check mode, password-required guard)
* no-op for an existing user without ``rotate_password``
* explicit password rotation via ``ModifyPassword`` when ``rotate_password``
  is set
* rotation argument validation before any SDK call
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_user as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {"Name": "producer"}


def _user(**overrides):
    item = copy.deepcopy(USER)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "instance_id": "ckafka-abcdef12",
        "name": "producer",
        "password": "secret-password",
        "rotate_password": False,
        "current_password": None,
    }
    params.update(overrides)
    return module_args(**params)


class FakeCkafkaClient(object):
    """In-memory CKafka client mutating a small user store."""

    def __init__(self, users=None):
        self.users = [copy.deepcopy(t) for t in (users or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUser(self, request):
        self._record("DescribeUser", request)
        return SimpleNamespace(
            Result=SimpleNamespace(
                Users=[FakeResource(t) for t in self.users if t.get("Name") == getattr(request, "SearchWord", None)],
                TotalCount=len([t for t in self.users if t.get("Name") == getattr(request, "SearchWord", None)]),
            )
        )

    def CreateUser(self, request):
        self._record("CreateUser", request)
        self.users.append({"Name": request.Name})
        return SimpleNamespace(RequestId="req-fake")

    def ModifyPassword(self, request):
        self._record("ModifyPassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteUser(self, request):
        self._record("DeleteUser", request)
        self.users = [t for t in self.users if t.get("Name") != request.Name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_user_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(users=[])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"] is None
    assert [c for c, unused in fake.calls] == ["DescribeUser"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Name"] == "producer"
    assert len(fake.users) == 1
    assert "DeleteUser" not in [c for c, unused in fake.calls]


def test_absent_deletes_user(monkeypatch):
    fake = FakeCkafkaClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert fake.users == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUser" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_user(monkeypatch):
    fake = FakeCkafkaClient(users=[])
    _make_module(monkeypatch, fake)
    _args(state="present", password="secret-password")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Name"] == "producer"
    assert len(fake.users) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeUser"
    assert "CreateUser" in ops


def test_create_requires_password(monkeypatch):
    fake = FakeCkafkaClient(users=[])
    _make_module(monkeypatch, fake)
    _args(state="present", password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating a CKafka user" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(users=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", password="secret-password")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert fake.users == []
    assert "CreateUser" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-user flows
# ---------------------------------------------------------------------------


def test_existing_user_no_rotation_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _args(state="present", password="ignored-password")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"]["Name"] == "producer"
    assert "ModifyPassword" not in [c for c, unused in fake.calls]


def test_rotate_password_modifies_password(monkeypatch):
    fake = FakeCkafkaClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _args(state="present", rotate_password=True, current_password="old-password", password="new-password")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Name"] == "producer"
    assert "ModifyPassword" in [c for c, unused in fake.calls]
    rotate_call = dict((name, request) for name, request in fake.calls)["ModifyPassword"]
    assert rotate_call.Password == "old-password"
    assert rotate_call.PasswordNew == "new-password"


def test_rotate_password_without_credentials_fails(monkeypatch):
    fake = FakeCkafkaClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _args(state="present", rotate_password=True, password=None, current_password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "password and current_password are required when rotate_password=true"
    assert fake.calls == []


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUser(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present", password="secret-password")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
