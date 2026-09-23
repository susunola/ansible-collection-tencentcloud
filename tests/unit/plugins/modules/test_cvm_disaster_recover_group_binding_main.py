"""Unit tests for the cvm_disaster_recover_group_binding write module.

Drives ``run_module()`` against an in-memory fake CVM client whose
bind/unbind operations mutate an instance -> placement-group store so
post-write describes converge immediately.

Scenario matrix:

* absent on an instance already outside the target group (idempotent no-op)
* absent on a bound instance (check-mode dry run, real unbind)
* present on an already-bound instance (idempotent no-op)
* binding an ungrouped instance (happy path, check mode)
* moving between groups requires force_migrate; without it the module fails
* the instance-not-found guard and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_disaster_recover_group_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "ins-123456",
    "DisasterRecoverGroupId": "ps-abcdef",
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _group_args(**overrides):
    params = {"state": "present", "instance_id": "ins-123456", "group_id": "ps-abcdef", "force_migrate": False}
    params.update(overrides)
    return module_args(**params)


class FakeCvmClient(object):
    """In-memory CVM client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, instance_id):
        for item in self.instances:
            if item.get("InstanceId") == instance_id:
                return item
        return None

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        ids = list(getattr(request, "InstanceIds", None) or [])
        values = [t for t in self.instances if t.get("InstanceId") in ids]
        return SimpleNamespace(InstanceSet=[FakeResource(copy.deepcopy(t)) for t in values])

    def ModifyInstancesDisasterRecoverGroup(self, request):
        self._record("ModifyInstancesDisasterRecoverGroup", request)
        item = self._by_id((getattr(request, "InstanceIds", None) or [None])[0])
        if item is not None:
            item["DisasterRecoverGroupId"] = getattr(request, "DisasterRecoverGroupId", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteInstancesDisasterRecoverGroups(self, request):
        self._record("DeleteInstancesDisasterRecoverGroups", request)
        instance_id = (getattr(request, "InstanceIds", None) or [None])[0]
        group_ids = list(getattr(request, "DisasterRecoverGroupIds", None) or [])
        item = self._by_id(instance_id)
        if item is not None and item.get("DisasterRecoverGroupId") in group_ids:
            item["DisasterRecoverGroupId"] = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CvmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unbound_instance_is_idempotent(monkeypatch):
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId=None)])
    _make_module(monkeypatch, fake)
    _group_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert [c for c, unused in fake.calls] == ["DescribeInstances"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "ins-123456", "GroupIds": ["ps-abcdef"]}
    assert fake.instances[0]["DisasterRecoverGroupId"] == "ps-abcdef"
    assert "DeleteInstancesDisasterRecoverGroups" not in [c for c, unused in fake.calls]


def test_absent_unbinds_instance(monkeypatch):
    fake = FakeCvmClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _group_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.instances[0]["DisasterRecoverGroupId"] is None
    assert "DeleteInstancesDisasterRecoverGroups" in [c for c, unused in fake.calls]


def test_absent_to_a_different_group_is_idempotent(monkeypatch):
    # Unbinding from the wrong group must not touch an instance bound to ps-other.
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId="ps-other")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ins-123456", group_id="ps-abcdef")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert fake.instances[0]["DisasterRecoverGroupId"] == "ps-other"


# ---------------------------------------------------------------------------
# binding flows
# ---------------------------------------------------------------------------


def test_present_already_bound_is_idempotent(monkeypatch):
    fake = FakeCvmClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] == {"InstanceId": "ins-123456", "GroupIds": ["ps-abcdef"]}
    assert "ModifyInstancesDisasterRecoverGroup" not in [c for c, unused in fake.calls]


def test_present_binds_ungrouped_instance(monkeypatch):
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId=None)])
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "ins-123456", "GroupIds": ["ps-abcdef"]}
    ops = [c for c, unused in fake.calls]
    assert "ModifyInstancesDisasterRecoverGroup" in ops
    assert ops[-1] == "DescribeInstances"


def test_present_bind_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId=None)])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "ins-123456", "GroupIds": []}
    assert "diff" in result
    assert fake.instances[0]["DisasterRecoverGroupId"] is None
    assert "ModifyInstancesDisasterRecoverGroup" not in [c for c, unused in fake.calls]


def test_present_move_without_force_fails(monkeypatch):
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId="ps-other")])
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "force_migrate=true" in payload["msg"]
    assert payload["current_group_ids"] == ["ps-other"]


def test_present_move_with_force_migrates(monkeypatch):
    fake = FakeCvmClient(instances=[_instance(DisasterRecoverGroupId="ps-other")])
    _make_module(monkeypatch, fake)
    _group_args(force_migrate=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "ins-123456", "GroupIds": ["ps-abcdef"]}
    assert fake.instances[0]["DisasterRecoverGroupId"] == "ps-abcdef"
    assert "ModifyInstancesDisasterRecoverGroup" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_missing_instance_fails(monkeypatch):
    fake = FakeCvmClient(instances=[])
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CVM instance was not found"
    assert payload["instance_id"] == "ins-123456"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_bind_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstances(self, request):
            return SimpleNamespace(InstanceSet=[FakeResource(copy.deepcopy(_instance(DisasterRecoverGroupId=None)))])

        def ModifyInstancesDisasterRecoverGroup(self, request):
            raise Boom("bind refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "bind refused" in payload["error"]
