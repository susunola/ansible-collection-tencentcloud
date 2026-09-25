"""Unit tests for the tcr_instance write module (``run_module`` flows).

``test_tcr_instance.py`` covers the request builders against a recording
client.  This file drives ``run_module`` itself, because the ``idempotent``
attribute is a claim about what a second run does, and only running it twice
can check that.

The fake client is the registry store: ``DescribeInstances`` answers from it
and create/update/delete keep it in step, so a run observes what the previous
run wrote.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


class FakeRequest(object):
    pass


class FakePrepaid(object):
    def __init__(self):
        self.Period = None
        self.RenewFlag = None


class FakeTag(object):
    def __init__(self):
        self.Key = None
        self.Value = None


class FakeTagSpecification(object):
    def __init__(self):
        self.ResourceType = None
        self.Tags = None


class TcrModels(FakeModels):
    DescribeInstancesRequest = FakeRequest
    CreateInstanceRequest = FakeRequest
    ModifyInstanceRequest = FakeRequest
    DeleteInstanceRequest = FakeRequest
    RegistryChargePrepaid = FakePrepaid
    Tag = FakeTag
    TagSpecification = FakeTagSpecification


class FakeInstance(object):
    def __init__(self, registry_id, name, protection=False):
        self.RegistryId = registry_id
        self.RegistryName = name
        self.DeletionProtection = protection

    def _serialize(self, allow_none=True):
        return {
            "RegistryId": self.RegistryId,
            "RegistryName": self.RegistryName,
            "DeletionProtection": self.DeletionProtection,
        }


class FakeResponse(object):
    def __init__(self, registries):
        self.Registries = registries


class FakeCreateResponse(object):
    def __init__(self, registry_ids):
        self.RegistryIds = registry_ids


class FakeTcrStore(object):
    """The TCR registry store, used as the SDK client."""

    _WRITES = ("CreateInstance", "ModifyInstance", "DeleteInstance")

    def __init__(self, registries=()):
        self.registries = list(registries)
        self.calls = []
        self._next_id = 1

    def DescribeInstances(self, request):
        self.calls.append("DescribeInstances")
        if getattr(request, "Registryids", None):
            wanted = set(request.Registryids)
            return FakeResponse([r for r in self.registries if r.RegistryId in wanted])
        if getattr(request, "RegistryName", None):
            return FakeResponse([r for r in self.registries
                                 if r.RegistryName == request.RegistryName])
        return FakeResponse(list(self.registries))

    def CreateInstance(self, request):
        self.calls.append("CreateInstance")
        registry_id = "tcr-auto%d" % self._next_id
        self._next_id += 1
        self.registries.append(
            FakeInstance(registry_id, request.RegistryName,
                         bool(getattr(request, "DeletionProtection", False))))
        return FakeCreateResponse([registry_id])

    def ModifyInstance(self, request):
        self.calls.append("ModifyInstance")
        for item in self.registries:
            if item.RegistryId == request.RegistryId:
                if getattr(request, "DeletionProtection", None) is not None:
                    item.DeletionProtection = request.DeletionProtection

    def DeleteInstance(self, request):
        self.calls.append("DeleteInstance")
        self.registries = [r for r in self.registries if r.RegistryId != request.RegistryId]

    @property
    def writes(self):
        return [c for c in self.calls if c in self._WRITES]


def _make_module(monkeypatch, store):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tcr",
                        lambda: (TcrModels(), SimpleNamespace(TcrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: store)
    return store


def _args(**extra):
    base = {"registry_id": "tcr-1", "name": "registry"}
    base.update(extra)
    module_args(**base)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_present_twice_is_a_no_op(monkeypatch):
    """The claim the attribute makes, checked by running the module twice."""
    store = FakeTcrStore([FakeInstance("tcr-1", "registry")])
    _make_module(monkeypatch, store)

    _args()
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "TCR instance is up to date"

    _args()
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "TCR instance is up to date"
    assert store.writes == []


def test_absent_twice_is_a_no_op(monkeypatch):
    store = FakeTcrStore([])
    _make_module(monkeypatch, store)

    _args(state="absent")
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "TCR instance already absent"

    _args(state="absent")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_deletion_protection_drift_converges_once(monkeypatch):
    """A drifted flag is corrected once; the run after that writes nothing."""
    store = FakeTcrStore([FakeInstance("tcr-1", "registry", protection=False)])
    _make_module(monkeypatch, store)

    _args(deletion_protection=True)
    first = run(mod.run_module)
    assert first["changed"] is True
    assert first["msg"] == "TCR deletion protection updated"
    assert store.writes == ["ModifyInstance"]
    assert store.registries[0].DeletionProtection is True

    store.calls = []
    _args(deletion_protection=True)
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "TCR instance is up to date"
    assert store.writes == []


def test_check_mode_does_not_write(monkeypatch):
    store = FakeTcrStore([FakeInstance("tcr-1", "registry", protection=False)])
    _make_module(monkeypatch, store)

    _args(deletion_protection=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert store.writes == []
