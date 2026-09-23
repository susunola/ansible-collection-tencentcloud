"""Unit tests for the trabbit_serverless_permission write module.

``trabbit_serverless_permission`` reconciles a user's configure / write /
read regex permissions for a RabbitMQ Serverless virtual host. The API
upserts through ``ModifyRabbitMQServerlessPermission`` (used both to
create a missing permission and to change regexps); delete removes it.

Scenario matrix:

* absent on a missing permission / existing permission (check, real delete)
* present no-drift idempotence
* create via modify (real, check mode)
* regexp drift update (real, check mode)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_permission as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "amqp-abc123"
USER = "application"
VIRTUAL_HOST = "production"

PERMISSION = {
    "InstanceId": INSTANCE_ID,
    "User": USER,
    "VirtualHost": VIRTUAL_HOST,
    "ConfigRegexp": "^orders\\.",
    "WriteRegexp": "^orders\\.",
    "ReadRegexp": "^orders\\.",
}


def _permission(**overrides):
    item = copy.deepcopy(PERMISSION)
    item.update(overrides)
    return item


def _p_args(**overrides):
    params = {"instance_id": INSTANCE_ID, "user": USER, "virtual_host": VIRTUAL_HOST}
    params.update(overrides)
    return module_args(**params)


class FakeTrabbitClient(object):
    """In-memory RabbitMQ Serverless client storing virtual-host permissions."""

    def __init__(self, permissions=None):
        self.permissions = [copy.deepcopy(p) for p in (permissions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRabbitMQServerlessPermission(self, request):
        self._record("DescribeRabbitMQServerlessPermission", request)
        return SimpleNamespace(
            RabbitMQPermissionList=[FakeResource(dict(p)) for p in self.permissions],
        )

    def ModifyRabbitMQServerlessPermission(self, request):
        self._record("ModifyRabbitMQServerlessPermission", request)
        self.permissions = [
            p for p in self.permissions
            if not (p["User"] == request.User and p["VirtualHost"] == request.VirtualHost)
        ]
        self.permissions.append({
            "InstanceId": request.InstanceId,
            "User": request.User,
            "VirtualHost": request.VirtualHost,
            "ConfigRegexp": request.ConfigRegexp,
            "WriteRegexp": request.WriteRegexp,
            "ReadRegexp": request.ReadRegexp,
        })
        return SimpleNamespace()

    def DeleteRabbitMQServerlessPermission(self, request):
        self._record("DeleteRabbitMQServerlessPermission", request)
        self.permissions = [
            p for p in self.permissions
            if not (p["User"] == request.User and p["VirtualHost"] == request.VirtualHost)
        ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_permission_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(permissions=[])
    _make_module(monkeypatch, fake)
    _p_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQServerlessPermission"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _p_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["User"] == USER
    assert len(fake.permissions) == 1
    assert "DeleteRabbitMQServerlessPermission" not in [c for c, unused in fake.calls]


def test_absent_deletes_permission(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _p_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"] is None
    assert fake.permissions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQServerlessPermission" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _p_args(state="present", configure_regex="^orders\\.", write_regex="^orders\\.", read_regex="^orders\\.")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"]["User"] == USER
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQServerlessPermission" not in ops


def test_present_default_regex_no_drift_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission(
        ConfigRegexp=".*", WriteRegexp=".*", ReadRegexp=".*",
    )])
    _make_module(monkeypatch, fake)
    _p_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False


def test_present_creates_via_modify(monkeypatch):
    fake = FakeTrabbitClient(permissions=[])
    _make_module(monkeypatch, fake)
    _p_args(state="present", configure_regex="^orders\\.", write_regex="^orders\\.", read_regex="^orders\\.")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["User"] == USER
    assert result["permission"]["ConfigRegexp"] == "^orders\\."
    assert len(fake.permissions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQServerlessPermission"
    assert "ModifyRabbitMQServerlessPermission" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(permissions=[])
    _make_module(monkeypatch, fake)
    _p_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.permissions == []
    assert "ModifyRabbitMQServerlessPermission" not in [c for c, unused in fake.calls]


def test_regexp_drift_updates_permission(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _p_args(state="present", configure_regex="^orders\\.", write_regex="^invoices\\.", read_regex="^orders\\.")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["WriteRegexp"] == "^invoices\\."
    assert fake.permissions[0]["WriteRegexp"] == "^invoices\\."
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQServerlessPermission" in ops


def test_regexp_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _p_args(_ansible_check_mode=True, state="present", configure_regex="^orders\\.", write_regex="^invoices\\.", read_regex="^orders\\.")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["WriteRegexp"] == "^orders\\."
    assert fake.permissions[0]["WriteRegexp"] == "^orders\\."
    assert "ModifyRabbitMQServerlessPermission" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQServerlessPermission(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _p_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
