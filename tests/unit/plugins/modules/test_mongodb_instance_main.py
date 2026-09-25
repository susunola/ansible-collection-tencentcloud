"""Unit tests for the mongodb_instance write module (``run_module`` flows).

``test_mongodb_instance.py`` covers the request builders against a recording
client.  This file drives ``run_module`` itself, because the ``idempotent``
attribute is a claim about what a second run does, and only running it twice
can check that.

The fake client is the instance store: ``DescribeDBInstances`` answers from it
and the create/rename/isolate calls update it, so a run observes what the
previous run wrote.  ``SearchKey`` is a fuzzy server-side filter, so the store
returns every instance and lets the module's shared resolver do the exact
matching it is written to do.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mongodb_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


class FakeRequest(object):
    pass


class FakeTag(object):
    def __init__(self):
        self.TagKey = None
        self.TagValue = None


class MongoDBModels(FakeModels):
    DescribeDBInstancesRequest = FakeRequest
    CreateDBInstanceRequest = FakeRequest
    CreateDBInstanceHourRequest = FakeRequest
    RenameInstanceRequest = FakeRequest
    IsolateDBInstanceRequest = FakeRequest
    TagInfo = FakeTag


class FakeInstance(object):
    def __init__(self, instance_id, name):
        self.InstanceId = instance_id
        self.InstanceName = name

    def _serialize(self, allow_none=True):
        return {"InstanceId": self.InstanceId, "InstanceName": self.InstanceName}


class FakeResponse(object):
    def __init__(self, instances):
        self.InstanceDetails = instances


class FakeCreateResponse(object):
    def __init__(self, instance_ids):
        self.InstanceIds = instance_ids


class FakeMongoDBStore(object):
    """The MongoDB instance store, used as the SDK client."""

    _WRITES = ("CreateDBInstance", "CreateDBInstanceHour", "RenameInstance",
               "IsolateDBInstance")

    def __init__(self, instances=()):
        self.instances = list(instances)
        self.calls = []
        self._next_id = 1

    def DescribeDBInstances(self, request):
        self.calls.append("DescribeDBInstances")
        return FakeResponse(list(self.instances))

    def CreateDBInstance(self, request):
        self.calls.append("CreateDBInstance")
        return self._add(request)

    def CreateDBInstanceHour(self, request):
        self.calls.append("CreateDBInstanceHour")
        return self._add(request)

    def _add(self, request):
        instance_id = "cmgo-auto%d" % self._next_id
        self._next_id += 1
        self.instances.append(FakeInstance(instance_id, request.InstanceName))
        return FakeCreateResponse([instance_id])

    def RenameInstance(self, request):
        self.calls.append("RenameInstance")
        for item in self.instances:
            if item.InstanceId == request.InstanceId:
                item.InstanceName = request.NewName

    def IsolateDBInstance(self, request):
        self.calls.append("IsolateDBInstance")
        self.instances = [i for i in self.instances if i.InstanceId != request.InstanceId]

    @property
    def writes(self):
        return [c for c in self.calls if c in self._WRITES]


def _make_module(monkeypatch, store):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_mongodb",
                        lambda: (MongoDBModels(), SimpleNamespace(MongodbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: store)
    return store


def _args(**extra):
    base = {"instance_id": "cmgo-1", "name": "mongo"}
    base.update(extra)
    module_args(**base)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_present_twice_is_a_no_op(monkeypatch):
    """The claim the attribute makes, checked by running the module twice."""
    store = FakeMongoDBStore([FakeInstance("cmgo-1", "mongo")])
    _make_module(monkeypatch, store)

    _args()
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "MongoDB instance is up to date"

    _args()
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "MongoDB instance is up to date"
    assert store.writes == []


def test_absent_twice_is_a_no_op(monkeypatch):
    store = FakeMongoDBStore([])
    _make_module(monkeypatch, store)

    _args(state="absent")
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "MongoDB instance already absent"

    _args(state="absent")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_rename_then_second_run_converges(monkeypatch):
    """A drifted name is corrected once; the run after that writes nothing."""
    store = FakeMongoDBStore([FakeInstance("cmgo-1", "old-name")])
    _make_module(monkeypatch, store)

    _args(name="mongo")
    first = run(mod.run_module)
    assert first["changed"] is True
    assert first["msg"] == "MongoDB instance renamed"
    assert store.writes == ["RenameInstance"]

    store.calls = []
    _args(name="mongo")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "MongoDB instance is up to date"
    assert store.writes == []


def test_check_mode_does_not_write(monkeypatch):
    store = FakeMongoDBStore([FakeInstance("cmgo-1", "old-name")])
    _make_module(monkeypatch, store)

    _args(name="mongo", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would rename" in result["msg"]
    assert store.writes == []
