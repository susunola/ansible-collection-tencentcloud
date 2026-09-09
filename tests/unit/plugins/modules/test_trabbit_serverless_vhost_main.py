"""Unit tests for the trabbit_serverless_vhost write module (run_module flows).

The module creates, renames-less-updates (description) and deletes RabbitMQ
Serverless virtual hosts keyed by their ``name``. Mirror-queue policy is
immutable on an existing vhost, and message tracing is write-only: the
service never returns the current value, so ``apply_trace`` forces an
explicit ``TraceFlag`` update even when everything else matches.

Scenario matrix:

* absent on a missing vhost is an idempotent no-op
* absent with a matching vhost (check-mode dry run, real delete)
* creation when missing (with and without check mode) carries ``TraceFlag``
* no-op when the vhost already matches; description drift drives a modify
* mirror-queue policy is immutable on existing vhosts
* ``apply_trace`` requires ``trace_enabled`` and forces a trace update
* ``find`` pages through the describe results to locate the vhost
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_vhost as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "amqp-abc123"

VHOST = {
    "InstanceId": INSTANCE_ID,
    "VirtualHost": "production",
    "Description": "Production workloads",
    "MirrorQueuePolicyFlag": True,
    "TraceFlag": False,
}


def _vhost(**overrides):
    item = copy.deepcopy(VHOST)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "name": "production", "description": "Production workloads"}
    params.update(overrides)
    return module_args(**params)


class FakeTrabbitClient(object):
    """In-memory RabbitMQ Serverless client mutating a virtual-host store."""

    def __init__(self, vhosts=None, page_size=100):
        self.vhosts = [copy.deepcopy(t) for t in (vhosts or [])]
        self.calls = []
        self.page_size = page_size

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRabbitMQServerlessVirtualHost(self, request):
        self._record("DescribeRabbitMQServerlessVirtualHost", request)
        offset = getattr(request, "Offset", None) or 0
        limit = getattr(request, "Limit", None) or 100
        instance_id = getattr(request, "InstanceId", None)
        matching = [v for v in self.vhosts if v.get("InstanceId") == instance_id]
        page = matching[offset : offset + min(limit, self.page_size)]
        return SimpleNamespace(VirtualHostList=[FakeResource(v) for v in page], TotalCount=len(matching))

    def _index(self, request):
        instance_id = getattr(request, "InstanceId", None)
        virtual_host = getattr(request, "VirtualHost", None)
        for i, v in enumerate(self.vhosts):
            if v.get("InstanceId") == instance_id and v.get("VirtualHost") == virtual_host:
                return i
        return None

    def CreateRabbitMQServerlessVirtualHost(self, request):
        self._record("CreateRabbitMQServerlessVirtualHost", request)
        self.vhosts.append(
            {
                "InstanceId": getattr(request, "InstanceId", None),
                "VirtualHost": getattr(request, "VirtualHost", None),
                "Description": getattr(request, "Description", None) or "",
                "MirrorQueuePolicyFlag": getattr(request, "MirrorQueuePolicyFlag", True),
                "TraceFlag": getattr(request, "TraceFlag", None),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQServerlessVirtualHost(self, request):
        self._record("ModifyRabbitMQServerlessVirtualHost", request)
        index = self._index(request)
        if index is not None:
            self.vhosts[index]["Description"] = getattr(request, "Description", self.vhosts[index].get("Description"))
            trace = getattr(request, "TraceFlag", None)
            if trace is not None:
                self.vhosts[index]["TraceFlag"] = trace
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQServerlessVirtualHost(self, request):
        self._record("DeleteRabbitMQServerlessVirtualHost", request)
        instance_id = getattr(request, "InstanceId", None)
        virtual_host = getattr(request, "VirtualHost", None)
        self.vhosts = [
            v
            for v in self.vhosts
            if not (v.get("InstanceId") == instance_id and v.get("VirtualHost") == virtual_host)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-vhost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["virtual_host"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQServerlessVirtualHost"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert len(fake.vhosts) == 1
    assert "DeleteRabbitMQServerlessVirtualHost" not in [c for c, unused in fake.calls]


def test_absent_deletes_vhost(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"] is None
    assert fake.vhosts == []
    assert "DeleteRabbitMQServerlessVirtualHost" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_vhost_carries_trace_flag(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _args(trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert result["virtual_host"]["Description"] == "Production workloads"
    assert result["virtual_host"]["MirrorQueuePolicyFlag"] is True
    assert len(fake.vhosts) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQServerlessVirtualHost"
    assert "CreateRabbitMQServerlessVirtualHost" in ops
    assert ops[-1] == "DescribeRabbitMQServerlessVirtualHost"
    create_call = dict((name, request) for name, request in fake.calls)["CreateRabbitMQServerlessVirtualHost"]
    assert create_call.TraceFlag is True


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["virtual_host"] is None
    assert fake.vhosts == []
    assert "CreateRabbitMQServerlessVirtualHost" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-vhost flows
# ---------------------------------------------------------------------------


def test_existing_vhost_no_drift_is_idempotent(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["virtual_host"]["VirtualHost"] == "production"
    assert "ModifyRabbitMQServerlessVirtualHost" not in [c for c, unused in fake.calls]


def test_description_drift_modifies(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args(description="Renamed production workloads")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["virtual_host"]["Description"] == "Renamed production workloads"
    assert fake.vhosts[0]["Description"] == "Renamed production workloads"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQServerlessVirtualHost" in ops
    modify_call = dict((name, request) for name, request in fake.calls)["ModifyRabbitMQServerlessVirtualHost"]
    assert modify_call.Description == "Renamed production workloads"


def test_mirror_queue_policy_is_immutable(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args(mirror_queue_policy=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert "MirrorQueuePolicyFlag" in payload["immutable_changes"]
    assert "ModifyRabbitMQServerlessVirtualHost" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# trace flows
# ---------------------------------------------------------------------------


def test_apply_trace_requires_trace_enabled(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[])
    _make_module(monkeypatch, fake)
    _args(apply_trace=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "trace_enabled" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_apply_trace_forces_trace_update_when_matching(monkeypatch):
    fake = FakeTrabbitClient(vhosts=[_vhost()])
    _make_module(monkeypatch, fake)
    _args(apply_trace=True, trace_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.vhosts[0]["TraceFlag"] is True
    modify_call = dict((name, request) for name, request in fake.calls)["ModifyRabbitMQServerlessVirtualHost"]
    assert modify_call.TraceFlag is True


# ---------------------------------------------------------------------------
# lookup pagination
# ---------------------------------------------------------------------------


def test_find_pages_to_locate_vhost(monkeypatch):
    fake = FakeTrabbitClient(
        vhosts=[_vhost(VirtualHost="sales"), _vhost(VirtualHost="marketing"), _vhost()], page_size=2
    )
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["virtual_host"]["VirtualHost"] == "production"
    describe_calls = [c for c, unused in fake.calls if c == "DescribeRabbitMQServerlessVirtualHost"]
    assert len(describe_calls) == 2


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQServerlessVirtualHost(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
