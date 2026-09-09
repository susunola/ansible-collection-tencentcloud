"""Unit tests for the tdmq_rabbitmq_vhost write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a RabbitMQ-virtual-host store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing virtual host (idempotent no-op)
* absent with a matching virtual host (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the virtual host already matches (description/trace)
* description / trace drift updates through ModifyRabbitMQVirtualHost
* immutable ``mirror_queue_policy`` drift guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rabbitmq_vhost as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VHOST = {
    "VirtualHost": "production",
    "Description": "Production workloads",
    "TraceFlag": True,
    "MirrorQueuePolicyFlag": True,
}


def _vhost(**overrides):
    item = copy.deepcopy(VHOST)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"instance_id": "amqp-abc", "name": "production"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small RabbitMQ-virtual-host store."""

    def __init__(self, vhosts=None):
        self.vhosts = [copy.deepcopy(t) for t in (vhosts or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.vhosts:
            if item.get("VirtualHost") == name:
                return item
        return None

    def DescribeRabbitMQVirtualHost(self, request):
        self._record("DescribeRabbitMQVirtualHost", request)
        return SimpleNamespace(VirtualHostList=[FakeResource(t) for t in self.vhosts], TotalCount=len(self.vhosts))

    def CreateRabbitMQVirtualHost(self, request):
        self._record("CreateRabbitMQVirtualHost", request)
        self.vhosts.append(
            {
                "VirtualHost": getattr(request, "VirtualHost", None),
                "Description": getattr(request, "Description", None) or "",
                "TraceFlag": bool(getattr(request, "TraceFlag", None)),
                "MirrorQueuePolicyFlag": bool(getattr(request, "MirrorQueuePolicyFlag", None)),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQVirtualHost(self, request):
        self._record("ModifyRabbitMQVirtualHost", request)
        item = self._by_name(getattr(request, "VirtualHost", None))
        if item is not None:
            item["Description"] = getattr(request, "Description", item.get("Description"))
            item["TraceFlag"] = bool(getattr(request, "TraceFlag", item.get("TraceFlag")))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQVirtualHost(self, request):
        self._record("DeleteRabbitMQVirtualHost", request)
        self.vhosts = [t for t in self.vhosts if t.get("VirtualHost") != getattr(request, "VirtualHost", None)]
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
    fake = FakeTdmqClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["virtual_host"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQVirtualHost"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert len(fake.vhosts) == 1
    assert "DeleteRabbitMQVirtualHost" not in [c for c, unused in fake.calls]


def test_absent_deletes_vhost(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"] is None
    assert fake.vhosts == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQVirtualHost" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_vhost(monkeypatch):
    fake = FakeTdmqClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _config(state="present", description="Production workloads", trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert result["virtual_host"]["TraceFlag"] is True
    assert result["virtual_host"]["MirrorQueuePolicyFlag"] is True
    assert len(fake.vhosts) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQVirtualHost"
    assert "CreateRabbitMQVirtualHost" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", description="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"] is None
    assert fake.vhosts == []
    assert "CreateRabbitMQVirtualHost" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-vhost flows
# ---------------------------------------------------------------------------


def test_existing_vhost_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _config(state="present", description="Production workloads", trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert "ModifyRabbitMQVirtualHost" not in [c for c, unused in fake.calls]


def test_description_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost(Description="Stale description")])
    _make_module(monkeypatch, fake)
    _config(state="present", description="Production workloads", trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["Description"] == "Production workloads"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQVirtualHost" in ops


def test_trace_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost(TraceFlag=False)])
    _make_module(monkeypatch, fake)
    _config(state="present", description="Production workloads", trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["TraceFlag"] is True


def test_mirror_queue_policy_drift_is_immutable(monkeypatch):
    fake = FakeTdmqClient(vhosts=[_vhost(MirrorQueuePolicyFlag=False)])
    _make_module(monkeypatch, fake)
    _config(state="present", description="Production workloads", trace_enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing RabbitMQ virtual host" in payload["msg"]
    assert payload["immutable_changes"]["MirrorQueuePolicyFlag"]["after"] is True


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQVirtualHost(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
