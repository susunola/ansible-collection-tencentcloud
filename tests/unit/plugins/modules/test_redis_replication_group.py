"""Unit tests for the redis_replication_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Redis client that
mutates a replication-group store keyed by group name, so the module's
post-write ``DescribeReplicationGroup`` refetch observes the new state
immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the group already exists
* absent when missing (no-op)
* remove when present (real Remove + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Remove call)
* missing instance_id on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import redis_replication_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _group(gid, name, remark=""):
    return FakeResource({"GroupId": str(gid), "GroupName": name, "Remark": remark, "InstanceCount": 1})


class FakeRedisClient(object):
    """In-memory Redis client mutating a replication-group store."""

    def __init__(self, groups=None):
        self.groups = list(groups or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeReplicationGroup(self, request):
        self._record("DescribeReplicationGroup", request)
        key = getattr(request, "SearchKey", None)
        if key:
            matched = [g for g in self.groups if key in g.GroupName]
        else:
            matched = list(self.groups)
        return SimpleNamespace(Groups=[FakeResource(dict(g._data)) for g in matched],
                               TotalCount=len(matched), RequestId="req-fake")

    def CreateReplicationGroup(self, request):
        self._record("CreateReplicationGroup", request)
        self._seq += 1
        item = _group(self._seq, getattr(request, "GroupName", ""), getattr(request, "Remark", ""))
        self.groups.append(item)
        return SimpleNamespace(GroupId=item.GroupId, TaskId=self._seq, RequestId="req-fake")

    def RemoveReplicationGroup(self, request):
        self._record("RemoveReplicationGroup", request)
        gid = getattr(request, "GroupId", None)
        self.groups = [g for g in self.groups if g.GroupId != gid]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_redis", lambda: (models or FakeModels(), SimpleNamespace(RedisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / remove flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeRedisClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", instance_id="crs-abc", remark="ha", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["group_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeReplicationGroup"
    assert "CreateReplicationGroup" in ops
    assert "RemoveReplicationGroup" not in ops
    created = [r for c, r in fake.calls if c == "CreateReplicationGroup"][0]
    assert created.GroupName == "app-cache-ha"
    assert created.InstanceId == "crs-abc"


def test_remove_when_present(monkeypatch):
    fake = FakeRedisClient(groups=[_group(1, "app-cache-ha")])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "RemoveReplicationGroup" in [c for c, unused in fake.calls]
    assert "CreateReplicationGroup" not in [c for c, unused in fake.calls]
    assert fake.groups == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeRedisClient(groups=[_group(1, "app-cache-ha")])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", instance_id="crs-abc", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeReplicationGroup"]
    assert "CreateReplicationGroup" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeRedisClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "RemoveReplicationGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", instance_id="crs-abc", state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateReplicationGroup" not in [c for c, unused in fake.calls]
    assert fake.groups == []


def test_remove_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(groups=[_group(1, "app-cache-ha")])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "RemoveReplicationGroup" not in [c for c, unused in fake.calls]
    assert len(fake.groups) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_instance_id_on_present_fails(monkeypatch):
    fake = FakeRedisClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if instance_id to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeRedisClient(groups=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateReplicationGroup = _raise_error
    _make_module(monkeypatch, fake)
    module_args(group_name="app-cache-ha", instance_id="crs-abc", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
