"""Unit tests for the tdmq_rabbitmq_permission write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose modify /
delete operations mutate a RabbitMQ virtual-host permission store so
post-write describes converge immediately. Note the module has no create
operation: ``present`` converges through ModifyRabbitMQPermission (the API
upserts), so the store fake upserts as well.

Scenario matrix:

* absent on a missing permission (idempotent no-op)
* absent with a matching permission (check-mode dry run, real delete)
* present when missing converges through Modify (upsert, happy path)
* no-op when the regex trio already matches
* configure/write/read regex drift triggers ModifyRabbitMQPermission
* check-mode dry run for an absent-then-present permission
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rabbitmq_permission as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PERMISSION = {
    "User": "application",
    "VirtualHost": "production",
    "ConfigRegexp": "^orders\\.",
    "WriteRegexp": "^orders\\.",
    "ReadRegexp": "^orders\\.",
}


def _permission(**overrides):
    item = copy.deepcopy(PERMISSION)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"instance_id": "amqp-abc", "user": "application", "virtual_host": "production"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a RabbitMQ vhost permission store."""

    def __init__(self, permissions=None):
        self.permissions = [copy.deepcopy(t) for t in (permissions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRabbitMQPermission(self, request):
        self._record("DescribeRabbitMQPermission", request)
        return SimpleNamespace(
            RabbitMQPermissionList=[FakeResource(t) for t in self.permissions],
            TotalCount=len(self.permissions),
        )

    def ModifyRabbitMQPermission(self, request):
        self._record("ModifyRabbitMQPermission", request)
        user = getattr(request, "User", None)
        vhost = getattr(request, "VirtualHost", None)
        for item in self.permissions:
            if item.get("User") == user and item.get("VirtualHost") == vhost:
                item["ConfigRegexp"] = getattr(request, "ConfigRegexp", item.get("ConfigRegexp"))
                item["WriteRegexp"] = getattr(request, "WriteRegexp", item.get("WriteRegexp"))
                item["ReadRegexp"] = getattr(request, "ReadRegexp", item.get("ReadRegexp"))
                return SimpleNamespace(RequestId="req-fake")
        self.permissions.append(
            {
                "User": user,
                "VirtualHost": vhost,
                "ConfigRegexp": getattr(request, "ConfigRegexp", None),
                "WriteRegexp": getattr(request, "WriteRegexp", None),
                "ReadRegexp": getattr(request, "ReadRegexp", None),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQPermission(self, request):
        self._record("DeleteRabbitMQPermission", request)
        user = getattr(request, "User", None)
        vhost = getattr(request, "VirtualHost", None)
        self.permissions = [
            t for t in self.permissions if not (t.get("User") == user and t.get("VirtualHost") == vhost)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQPermission"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["User"] == "application"
    assert len(fake.permissions) == 1
    assert "DeleteRabbitMQPermission" not in [c for c, unused in fake.calls]


def test_absent_deletes_permission(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"] is None
    assert fake.permissions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQPermission" in ops


# ---------------------------------------------------------------------------
# present flows (Modify-only; the API upserts)
# ---------------------------------------------------------------------------


def test_present_missing_converges_via_modify(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(
        state="present",
        configure_regex="^orders\\.",
        write_regex="^orders\\.",
        read_regex="^orders\\.",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["User"] == "application"
    assert result["permission"]["ConfigRegexp"] == "^orders\\."
    assert len(fake.permissions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQPermission"
    assert "ModifyRabbitMQPermission" in ops


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(permissions=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", configure_regex="^custom\\.")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"] is None
    assert fake.permissions == []
    assert "ModifyRabbitMQPermission" not in [c for c, unused in fake.calls]


def test_existing_permission_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission()])
    _make_module(monkeypatch, fake)
    _config(
        state="present",
        configure_regex="^orders\\.",
        write_regex="^orders\\.",
        read_regex="^orders\\.",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission"]["User"] == "application"
    assert "ModifyRabbitMQPermission" not in [c for c, unused in fake.calls]


def test_read_regex_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(permissions=[_permission(ReadRegexp=".*")])
    _make_module(monkeypatch, fake)
    _config(
        state="present",
        configure_regex="^orders\\.",
        write_regex="^orders\\.",
        read_regex="^orders\\.",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission"]["ReadRegexp"] == "^orders\\."
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQPermission" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQPermission(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
