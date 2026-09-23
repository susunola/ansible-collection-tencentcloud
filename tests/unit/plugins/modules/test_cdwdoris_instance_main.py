"""Unit tests for the cdwdoris_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CDW Doris
client whose write operations mutate the instance store, so the module's
post-write ``find`` and ``wait_present`` convergence are immediate.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (check-mode dry run and the real
  destroy-and-wait path)
* creation when missing (required-parameter guard, check mode, happy path)
* no-op when nothing drifts
* rename drift (with ``instance_id``), check mode and wait
* the multiple-match guard and the ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "doris-abc123",
    "InstanceName": "doris-a",
    "Zone": "ap-guangzhou-3",
    "Version": "2.1",
}

CREATE_ARGS = {
    "name": "doris-a",
    "zone": "ap-guangzhou-3",
    "fe_spec": {"SpecName": "S_4_16_H", "Count": 3, "DiskSize": 100},
    "be_spec": {"SpecName": "S_8_32_H", "Count": 3, "DiskSize": 500},
    "vpc_id": "vpc-abc",
    "subnet_id": "subnet-abc",
    "product_version": "2.1",
    "charge_properties": {"ChargeType": "POSTPAID_BY_HOUR"},
    "admin_password": "S3cret-pass",
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeCdwdorisClient(object):
    """In-memory CDW Doris client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        search_id = getattr(request, "SearchInstanceId", None)
        search_name = getattr(request, "SearchInstanceName", None)
        matches = []
        for item in self.instances:
            if search_id and item.get("InstanceId") == search_id:
                matches.append(dict(item))
            elif not search_id and search_name and item.get("InstanceName") == search_name:
                matches.append(dict(item))
        return SimpleNamespace(InstancesList=[FakeResource(t) for t in matches], TotalCount=len(matches))

    def DescribeInstanceState(self, request):
        self._record("DescribeInstanceState", request)
        return SimpleNamespace(InstanceState="Serving", FlowMsg=None)

    def CreateInstanceNew(self, request):
        self._record("CreateInstanceNew", request)
        self._next += 1
        item = {
            "InstanceId": "doris-new-%03d" % self._next,
            "InstanceName": getattr(request, "InstanceName", None),
            "Zone": getattr(request, "Zone", None),
            "Version": getattr(request, "ProductVersion", None),
        }
        self.instances.append(item)
        return SimpleNamespace(InstanceId=item["InstanceId"], ErrorMsg=None, RequestId="req-fake")

    def ModifyInstance(self, request):
        self._record("ModifyInstance", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                item["InstanceName"] = getattr(request, "InstanceName", None)
        return SimpleNamespace(RequestId="req-fake")

    def DestroyInstance(self, request):
        self._record("DestroyInstance", request)
        self.instances = [t for t in self.instances if t.get("InstanceId") != getattr(request, "InstanceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwdorisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeCdwdorisClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert _ops(fake) == ["DescribeInstances"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", instance_id="doris-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.instances) == 1
    assert "DestroyInstance" not in _ops(fake)


def test_absent_destroys_instance_and_waits(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="absent", instance_id="doris-abc123", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    ops = _ops(fake)
    assert ops[0] == "DescribeInstances"
    assert "DestroyInstance" in ops
    destroy_request = [r for c, r in fake.calls if c == "DestroyInstance"][0]
    assert destroy_request.InstanceId == "doris-abc123"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeCdwdorisClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="doris-b")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert set(payload["missing"]) == {"zone", "fe_spec", "be_spec", "vpc_id", "subnet_id", "product_version", "charge_properties", "admin_password"}


def test_create_instance(monkeypatch):
    fake = FakeCdwdorisClient(instances=[])
    _make_module(monkeypatch, fake)
    args = dict(CREATE_ARGS)
    args["state"] = "present"
    _base(**args)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "doris-a"
    assert result["instance"]["InstanceId"].startswith("doris-new-")
    assert len(fake.instances) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeInstances"
    assert "CreateInstanceNew" in ops
    assert "DescribeInstanceState" in ops


def test_create_with_wait_disabled(monkeypatch):
    fake = FakeCdwdorisClient(instances=[])
    _make_module(monkeypatch, fake)
    args = dict(CREATE_ARGS)
    args.update(state="present", wait=False)
    _base(**args)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"].startswith("doris-new-")
    assert "DescribeInstanceState" not in _ops(fake)


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient(instances=[])
    _make_module(monkeypatch, fake)
    args = dict(CREATE_ARGS)
    args["state"] = "present"
    _base(_ansible_check_mode=True, **args)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "doris-a"
    assert fake.instances == []
    assert "CreateInstanceNew" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="doris-abc123", name="doris-a")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "doris-abc123"
    assert "ModifyInstance" not in _ops(fake)


def test_rename_instance(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="doris-abc123", name="doris-b", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "doris-b"
    assert fake.instances[0]["InstanceName"] == "doris-b"
    ops = _ops(fake)
    assert "ModifyInstance" in ops
    modify_request = [r for c, r in fake.calls if c == "ModifyInstance"][0]
    assert modify_request.InstanceId == "doris-abc123"
    assert modify_request.InstanceName == "doris-b"


def test_rename_instance_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", instance_id="doris-abc123", name="doris-b")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "doris-b"
    assert fake.instances[0]["InstanceName"] == "doris-a"
    assert "ModifyInstance" not in _ops(fake)


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeCdwdorisClient(instances=[_instance(), _instance(InstanceId="doris-dup2")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="doris-a")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CDW Doris instances matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="doris-a")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
