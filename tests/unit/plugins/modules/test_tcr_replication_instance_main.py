"""Unit tests for the tcr_replication_instance write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake TCR client
whose create/delete operations mutate a replication-instance store, so the
post-write ``DescribeReplicationInstances`` refetch used by the waiter
converges immediately.

Scenario matrix:

* present with an already-running instance (idempotent no-op)
* creation when the destination region has no instance yet (check mode and
  real create)
* absent without an instance (idempotent) / check-mode delete / real delete
* argument validation before any SDK call (missing region fields, bad state)
* blanket ``sdk_error_payload`` failure path
* waiter never-converges (stuck creating) and failed-state failures
* legacy helper regression tests (folded from test_tcr_replication_instance.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_replication_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

REGISTRY_ID = "tcr-source-abc"
REGION_ID = 1
REGION_NAME = "ap-shanghai"


def _base(**overrides):
    params = {
        "state": "present",
        "registry_id": REGISTRY_ID,
        "replication_region_id": REGION_ID,
        "replication_region_name": REGION_NAME,
        "sync_tag": False,
    }
    params.update(overrides)
    return module_args(**params)


def _running_item():
    return {
        "ReplicationRegistryId": "tcr-repl-1",
        "ReplicationRegionId": REGION_ID,
        "ReplicationRegionName": REGION_NAME,
        "Status": "Running",
    }


class FakeTcrClient(object):
    """In-memory TCR client holding the replication instances of a registry."""

    def __init__(self, items=None, create_status="Running", delete_noop=False):
        self.items = [copy.deepcopy(item) for item in (items or [])]
        self.create_status = create_status
        self.delete_noop = delete_noop
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeReplicationInstances(self, request):
        self._record("DescribeReplicationInstances", request)
        assert request.RegistryId == REGISTRY_ID
        return SimpleNamespace(
            ReplicationRegistries=[FakeResource(item) for item in self.items],
            RequestId="req-fake",
        )

    def CreateReplicationInstance(self, request):
        self._record("CreateReplicationInstance", request)
        self.last_request = request
        self.items.append(
            {
                "ReplicationRegistryId": "tcr-repl-%s" % request.ReplicationRegionId,
                "ReplicationRegionId": request.ReplicationRegionId,
                "ReplicationRegionName": request.ReplicationRegionName,
                "Status": self.create_status,
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteReplicationInstance(self, request):
        self._record("DeleteReplicationInstance", request)
        self.last_request = request
        if not self.delete_noop:
            self.items = [
                item
                for item in self.items
                if item["ReplicationRegistryId"] != request.ReplicationRegistryId
                or item["ReplicationRegionId"] != request.ReplicationRegionId
            ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tcr", lambda: (FakeModels(), SimpleNamespace(TcrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_running_instance_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient(items=[_running_item()]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["replication_instance"]["Status"] == "Running"
    assert _names(fake) == ["DescribeReplicationInstances"]


def test_present_creates_instance_when_absent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_instance"]["ReplicationRegionName"] == REGION_NAME
    assert result["replication_instance"]["Status"] == "Running"
    assert len(fake.items) == 1
    request = _find_call(fake, "CreateReplicationInstance")
    assert request.RegistryId == REGISTRY_ID
    assert request.ReplicationRegionId == REGION_ID
    assert request.ReplicationRegionName == REGION_NAME
    assert _names(fake) == [
        "DescribeReplicationInstances",
        "CreateReplicationInstance",
        "DescribeReplicationInstances",
    ]


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_instance"] is None
    assert "diff" in result
    assert fake.items == []
    assert _names(fake) == ["DescribeReplicationInstances"]


def test_present_waiter_times_out_when_create_never_converges(monkeypatch):
    _make_module(monkeypatch, FakeTcrClient(create_status="Creating"))
    _base(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for TCR replication instance convergence" in payload["msg"]
    assert payload["expected"]["ReplicationRegionId"] == REGION_ID
    assert payload["replication_instance"]["Status"] == "Creating"


def test_present_waiter_fails_when_instance_enters_failed_state(monkeypatch):
    _make_module(monkeypatch, FakeTcrClient(create_status="Failed"))
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "entered a failed state" in payload["msg"]
    assert payload["replication_instance"]["Status"] == "Failed"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_instance_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["replication_instance"] is None
    assert _names(fake) == ["DescribeReplicationInstances"]


def test_absent_delete_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient(items=[_running_item()]))
    _base(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_instance"]["ReplicationRegistryId"] == "tcr-repl-1"
    assert len(fake.items) == 1
    assert "DeleteReplicationInstance" not in _names(fake)


def test_absent_deletes_existing_instance(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient(items=[_running_item()]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_instance"] is None
    assert fake.items == []
    request = _find_call(fake, "DeleteReplicationInstance")
    assert request.RegistryId == REGISTRY_ID
    assert request.ReplicationRegistryId == "tcr-repl-1"
    assert request.ReplicationRegionId == REGION_ID
    assert _names(fake) == [
        "DescribeReplicationInstances",
        "DeleteReplicationInstance",
        "DescribeReplicationInstances",
    ]


def test_absent_waiter_times_out_when_delete_does_not_converge(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient(items=[_running_item()], delete_noop=True))
    _base(state="absent", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for TCR replication instance convergence" in payload["msg"]
    assert payload["expected"] == "absent"
    assert len(fake.items) == 1


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_replication_region_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    module_args(registry_id=REGISTRY_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "replication_region_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_registry_id_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    module_args(replication_region_id=REGION_ID, replication_region_name=REGION_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "registry_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_invalid_state_choice_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcrClient())
    _base(state="flapping")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "flapping" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeReplicationInstances(self, request):
            raise Boom("tcr endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tcr endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcr_replication_instance.py)
# ---------------------------------------------------------------------------


def test_request_builders_populate_payload_fields():
    models = FakeModels()
    describe = mod.build_describe_request(models, "tcr-x")
    assert describe.RegistryId == "tcr-x"
    assert describe.Limit == 100
    assert describe.Offset == 0
    create = mod.build_create_request(models, {"registry_id": "tcr-x", "replication_region_id": 1, "replication_region_name": "ap-shanghai", "sync_tag": True})
    assert create.RegistryId == "tcr-x"
    assert create.ReplicationRegionId == 1
    assert create.SyncTag is True
    delete = mod.build_delete_request(models, "tcr-x", "tcr-y", 1)
    assert delete.RegistryId == "tcr-x"
    assert delete.ReplicationRegistryId == "tcr-y"
    assert delete.ReplicationRegionId == 1


def test_find_replication_matches_by_region_id():
    item = FakeResource({"ReplicationRegionId": 1, "ReplicationRegistryId": "tcr-repl-1", "Status": "Running"})
    assert mod._find([item], 1)["Status"] == "Running"
    assert mod._find([item], 2) is None
