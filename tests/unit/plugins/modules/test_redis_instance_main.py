"""Unit tests for the redis_instance write module (``run_module`` flows).

``test_redis_instance.py`` covers the request builders against a recording
client.  This file drives ``run_module`` itself, because the ``idempotent``
attribute is a claim about what a second run does, and only running it twice
can check that.

The fake client is the instance store: ``DescribeInstances`` answers from it
and ``CreateInstances`` adds to it, so a run observes what the previous run
wrote.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import redis_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


class FakeRequest(object):
    pass


class FakeResourceTag(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class RedisModels(FakeModels):
    DescribeInstancesRequest = FakeRequest
    CreateInstancesRequest = FakeRequest
    ModifyInstanceRequest = FakeRequest
    DestroyPostpaidInstanceRequest = FakeRequest
    DestroyPrepaidInstanceRequest = FakeRequest
    ResourceTag = FakeResourceTag


class FakeInstance(object):
    def __init__(self, instance_id, name, status=2, billing_mode="POSTPAID"):
        self.InstanceId = instance_id
        self.InstanceName = name
        self.Status = status
        self.BillingMode = billing_mode
        self.RedisShardSize = 4096
        self.ZoneId = 100003

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "Status": self.Status,
            "BillingMode": self.BillingMode,
            "RedisShardSize": self.RedisShardSize,
            "ZoneId": self.ZoneId,
        }


class FakeDescribeResponse(object):
    def __init__(self, instances):
        self.InstanceSet = instances


class FakeCreateResponse(object):
    def __init__(self, instance_ids):
        self.InstanceIds = instance_ids


class FakeRedisStore(object):
    """The Redis instance store, used as the SDK client.

    Status 2 is "running", which is what ``_wait_status`` polls for, so a
    created instance is immediately observable as converged.
    """

    _WRITES = ("CreateInstances", "ModifyInstance", "DestroyPostpaidInstance",
               "DestroyPrepaidInstance")

    def __init__(self, instances=()):
        self.instances = list(instances)
        self.calls = []
        self._next_id = 1

    def DescribeInstances(self, request):
        self.calls.append("DescribeInstances")
        wanted_ids = set(getattr(request, "InstanceIds", None) or [])
        wanted_names = set(getattr(request, "InstanceName", None) and
                           [request.InstanceName] or [])
        if not wanted_ids and not wanted_names:
            return FakeDescribeResponse(list(self.instances))
        return FakeDescribeResponse([
            item for item in self.instances
            if item.InstanceId in wanted_ids or item.InstanceName in wanted_names
        ])

    def CreateInstances(self, request):
        self.calls.append("CreateInstances")
        instance_id = "crs-auto%d" % self._next_id
        self._next_id += 1
        self.instances.append(FakeInstance(instance_id, request.InstanceName))
        return FakeCreateResponse([instance_id])

    def ModifyInstance(self, request):
        self.calls.append("ModifyInstance")
        for item in self.instances:
            if item.InstanceId == request.InstanceId:
                item.InstanceName = request.InstanceName

    def DestroyPostpaidInstance(self, request):
        self.calls.append("DestroyPostpaidInstance")
        self.instances = [i for i in self.instances if i.InstanceId != request.InstanceId]

    def DestroyPrepaidInstance(self, request):
        self.calls.append("DestroyPrepaidInstance")
        self.instances = [i for i in self.instances if i.InstanceId != request.InstanceId]

    @property
    def writes(self):
        return [c for c in self.calls if c in self._WRITES]


def _make_module(monkeypatch, store):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_redis",
                        lambda: (RedisModels(), SimpleNamespace(RedisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: store)
    return store


def _args(**extra):
    base = {"instance_id": "crs-1", "name": "cache"}
    base.update(extra)
    module_args(**base)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_present_twice_is_a_no_op(monkeypatch):
    """The claim the attribute makes, checked by running the module twice."""
    store = FakeRedisStore([FakeInstance("crs-1", "cache")])
    _make_module(monkeypatch, store)

    _args()
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "Redis instance is up to date"

    _args()
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "Redis instance is up to date"
    assert store.writes == []


def test_absent_twice_is_a_no_op(monkeypatch):
    store = FakeRedisStore([])
    _make_module(monkeypatch, store)

    _args(state="absent")
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "Redis instance already absent"

    _args(state="absent")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_rename_then_second_run_converges(monkeypatch):
    """A drifted name is corrected once; the run after that writes nothing."""
    store = FakeRedisStore([FakeInstance("crs-1", "old-name")])
    _make_module(monkeypatch, store)

    _args(name="cache")
    first = run(mod.run_module)
    assert first["changed"] is True
    assert first["msg"] == "Redis instance renamed"
    assert store.writes == ["ModifyInstance"]

    store.calls = []
    _args(name="cache")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "Redis instance is up to date"
    assert store.writes == []


def test_check_mode_does_not_write(monkeypatch):
    store = FakeRedisStore([FakeInstance("crs-1", "old-name")])
    _make_module(monkeypatch, store)

    _args(name="cache", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would rename" in result["msg"]
    assert store.writes == []
