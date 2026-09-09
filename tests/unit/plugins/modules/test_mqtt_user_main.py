"""Unit tests for the mqtt_user write module (run_module flows).

``mqtt_user`` manages MQTT username/password identities: passwords are
write-only (required at creation, never read back) and remark is the only
mutable field. The fake MQTT client stores users without passwords.

Scenario matrix:

* absent on a missing user / present create requires password (real, check)
* present no-drift idempotence, remark drift update
* absent on an existing user (check-mode dry run, real delete)
* duplicate username guard and blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mqtt_user as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {
    "InstanceId": "mqtt-abc123",
    "Username": "application",
    "Remark": "Application account",
}


def _user(**overrides):
    item = copy.deepcopy(USER)
    item.update(overrides)
    return item


def _u_args(**overrides):
    params = {"instance_id": "mqtt-abc123", "username": "application"}
    params.update(overrides)
    return module_args(**params)


class FakeMqttClient(object):
    """In-memory MQTT client mutating a password-less user store."""

    def __init__(self, users=None):
        self.users = [copy.deepcopy(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUserList(self, request):
        self._record("DescribeUserList", request)
        return SimpleNamespace(Data=[FakeResource(dict(u)) for u in self.users])

    def CreateUser(self, request):
        self._record("CreateUser", request)
        self.users.append({
            "InstanceId": request.InstanceId,
            "Username": request.Username,
            "Remark": getattr(request, "Remark", "") or "",
        })
        return SimpleNamespace()

    def ModifyUser(self, request):
        self._record("ModifyUser", request)
        for user in self.users:
            if user["InstanceId"] == request.InstanceId and user["Username"] == request.Username:
                user["Remark"] = getattr(request, "Remark", "") or ""
        return SimpleNamespace()

    def DeleteUser(self, request):
        self._record("DeleteUser", request)
        self.users = [
            u for u in self.users
            if not (u["InstanceId"] == request.InstanceId and u["Username"] == request.Username)
        ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MqttClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_user_is_idempotent(monkeypatch):
    fake = FakeMqttClient(users=[])
    _make_module(monkeypatch, fake)
    _u_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"] is None
    assert [c for c, unused in fake.calls] == ["DescribeUserList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _u_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert len(fake.users) == 1
    assert "DeleteUser" not in [c for c, unused in fake.calls]


def test_absent_deletes_user(monkeypatch):
    fake = FakeMqttClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _u_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert fake.users == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUser" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_requires_password_when_creating(monkeypatch):
    fake = FakeMqttClient(users=[])
    _make_module(monkeypatch, fake)
    _u_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required" in exc.value.args[0]["msg"]


def test_present_creates_user(monkeypatch):
    fake = FakeMqttClient(users=[])
    _make_module(monkeypatch, fake)
    _u_args(state="present", password="s3cret", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Username"] == "application"
    assert result["user"]["Remark"] == "Application account"
    assert len(fake.users) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeUserList"
    assert "CreateUser" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient(users=[])
    _make_module(monkeypatch, fake)
    _u_args(_ansible_check_mode=True, state="present", password="s3cret", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Username"] == "application"
    assert fake.users == []
    assert "CreateUser" not in [c for c, unused in fake.calls]


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeMqttClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _u_args(state="present", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"]["Username"] == "application"
    assert "ModifyUser" not in [c for c, unused in fake.calls]


def test_remark_drift_modifies_user(monkeypatch):
    fake = FakeMqttClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _u_args(state="present", remark="Updated remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Remark"] == "Updated remark"
    assert fake.users[0]["Remark"] == "Updated remark"
    ops = [c for c, unused in fake.calls]
    assert "ModifyUser" in ops


def test_multiple_matching_users_fails(monkeypatch):
    fake = FakeMqttClient(users=[_user(), _user(Remark="Duplicate account")])
    _make_module(monkeypatch, fake)
    _u_args(state="present", remark="Application account")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple MQTT users" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUserList(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _u_args(state="present", password="s3cret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
