"""Unit tests for the cdwpg_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CDWPG client
whose writes mutate the instance store so the describe-based waiters converge
on the first poll.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (check-mode dry run and the real destroy
  that waits for the instance to disappear)
* creation when missing (missing creation parameters, check-mode dry run and
  the happy path with waiting)
* no-op when nothing drifts
* rename drift update (with waiting)
* the multiple-match guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwpg-8b0a1c2d"

INSTANCE = {
    "InstanceId": INSTANCE_ID,
    "InstanceName": "analytics-pg",
    "Zone": "ap-guangzhou-3",
    "Status": 2,
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _resources():
    return [
        {"SpecName": "S_4_16_H", "Count": 2, "Type": "cn"},
        {"SpecName": "S_8_32_H", "Count": 3, "Type": "dn"},
    ]


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state) must not be pre-filled with
    # None; ``name``/``instance_id`` are a required_one_of pair so a helper
    # always supplies exactly one of them.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "analytics-pg"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"instance_id": INSTANCE_ID}
    params.update(overrides)
    return module_args(**params)


class FakeCdwpgClient(object):
    """In-memory CDWPG client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, request):
        wanted_id = getattr(request, "SearchInstanceId", None)
        wanted_name = getattr(request, "SearchInstanceName", None)
        for item in self.instances:
            item_id = item.get("InstanceId") or item.get("InstanceID")
            if wanted_id and item_id == wanted_id:
                return item
            if wanted_name and item.get("InstanceName") == wanted_name:
                return item
        return None

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        wanted_id = getattr(request, "SearchInstanceId", None)
        wanted_name = getattr(request, "SearchInstanceName", None)

        def matched(item):
            item_id = item.get("InstanceId") or item.get("InstanceID")
            if wanted_id:
                return item_id == wanted_id
            if wanted_name:
                return item.get("InstanceName") == wanted_name
            return True

        page = [dict(t) for t in self.instances if matched(t)]
        return SimpleNamespace(InstancesList=[FakeResource(t) for t in page], TotalCount=len(page))

    def DescribeInstanceState(self, request):
        self._record("DescribeInstanceState", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                return SimpleNamespace(InstanceState=item.get("InstanceState", "Serving"), FlowMsg=None)
        return SimpleNamespace(InstanceState="Serving", FlowMsg=None)

    def CreateInstanceByApi(self, request):
        self._record("CreateInstanceByApi", request)
        item = {
            "InstanceId": "cdwpg-new-%d" % (len(self.instances) + 1),
            "InstanceName": getattr(request, "InstanceName", None),
            "Zone": getattr(request, "Zone", None),
            "InstanceState": "Serving",
            "Status": 2,
        }
        self.instances.append(item)
        return SimpleNamespace(InstanceId=item["InstanceId"], ErrorMsg=None, RequestId="req-fake")

    def ModifyInstance(self, request):
        self._record("ModifyInstance", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                item["InstanceName"] = getattr(request, "InstanceName", None)
        return SimpleNamespace(RequestId="req-fake")

    def DestroyInstanceByApi(self, request):
        self._record("DestroyInstanceByApi", request)
        self.instances = [t for t in self.instances if t.get("InstanceId") != getattr(request, "InstanceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeCdwpgClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert len(fake.instances) == 1
    assert "DestroyInstanceByApi" not in [c for c, unused in fake.calls]


def test_absent_destroys_and_waits(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    assert "DestroyInstanceByApi" in [c for c, unused in fake.calls]


def test_absent_by_id_destroys(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeCdwpgClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="new-pg")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "resources" in payload["missing"]


def test_create_instance(monkeypatch):
    fake = FakeCdwpgClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        name="analytics-pg",
        zone="ap-guangzhou-3",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        charge_properties={"ChargeType": "POSTPAID_BY_HOUR"},
        admin_password="hunter2-secret",
        resources=_resources(),
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "analytics-pg"
    assert result["instance"]["InstanceState"] == "Serving"
    assert len(fake.instances) == 1
    assert fake.instances[0]["InstanceName"] == "analytics-pg"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeInstances"
    assert "CreateInstanceByApi" in ops
    assert "DescribeInstanceState" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwpgClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        name="analytics-pg",
        zone="ap-guangzhou-3",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        charge_properties={"ChargeType": "POSTPAID_BY_HOUR"},
        admin_password="hunter2-secret",
        resources=_resources(),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] == {"InstanceName": "analytics-pg", "Zone": "ap-guangzhou-3", "Version": None}
    assert fake.instances == []
    assert "CreateInstanceByApi" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == INSTANCE_ID


def test_rename_instance(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance(InstanceName="old-name")])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-pg", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "renamed-pg"
    ops = [c for c, unused in fake.calls]
    assert "ModifyInstance" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeCdwpgClient(instances=[_instance(), _instance(InstanceId="cdwpg-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CDW PostgreSQL instances matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
