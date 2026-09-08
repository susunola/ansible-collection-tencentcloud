"""Unit tests for the tse_sre_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
write operations mutate the registry-engine store, so the module's custom
``_wait`` loop converges on the first poll.

Scenario matrix:

* argument validation (missing instance_id and name)
* absent on a missing engine (idempotent) / check-mode dry run / real delete
* creation when missing (missing creation parameters, the Apollo
  environment requirement, check mode, real create with internet access)
* no-op when nothing drifts
* immutable drift failure
* internet-access reconciliation (enable and in check mode)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "ins-8b0a1c2d",
    "Name": "production-nacos",
    "Type": "nacos",
    "Edition": "STANDARD",
    "SpecId": "spec-1",
    "Replica": 3,
    "VpcId": "vpc-1",
    "SubnetId": "subnet-1",
    "StorageType": "CLOUD_SSD",
    "StorageCapacity": 50,
    "Status": "running",
    "EnableInternet": False,
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "production-nacos"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a registry-engine store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _find(self, instance_id):
        for item in self.instances:
            if item.get("InstanceId") == instance_id:
                return item
        return None

    def DescribeSREInstances(self, request):
        self.calls.append("DescribeSREInstances")
        return SimpleNamespace(Content=[FakeResource(t) for t in self.instances], TotalCount=len(self.instances), RequestId="req-fake")

    def CreateEngine(self, request):
        self.calls.append("CreateEngine")
        self._next += 1
        item = {
            "InstanceId": "ins-new-%03d" % self._next,
            "Name": getattr(request, "EngineName", None),
            "Type": getattr(request, "EngineType", None),
            "Edition": getattr(request, "EngineProductVersion", None),
            "SpecId": getattr(request, "EngineResourceSpec", None),
            "Replica": getattr(request, "EngineNodeNum", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "StorageType": getattr(request, "StorageType", None),
            "StorageCapacity": getattr(request, "StorageCapacity", None),
            "Status": "running",
            "EnableInternet": False,
        }
        self.instances.append(item)
        return SimpleNamespace(InstanceId=item["InstanceId"], RequestId="req-fake")

    def UpdateEngineInternetAccess(self, request):
        self.calls.append("UpdateEngineInternetAccess")
        item = self._find(getattr(request, "InstanceId", None))
        if item is not None:
            item["EnableInternet"] = getattr(request, "EnableClientInternetAccess", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEngine(self, request):
        self.calls.append("DeleteEngine")
        self.instances = [t for t in self.instances if t.get("InstanceId") != getattr(request, "InstanceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_instance_id_or_name_required(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_engine_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_deletes_engine(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances == []
    ops = list(fake.calls)
    assert "DeleteEngine" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.instances) == 1
    assert "DeleteEngine" not in fake.calls


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(name="new-engine")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "engine_version" in payload["missing"]


def test_apollo_engine_requires_environments(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(name="apollo-prod", engine_type="apollo", engine_version="1.8.0", product_version="STANDARD")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "apollo_environments is required" in exc.value.args[0]["msg"]


def test_create_engine(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        engine_type="nacos",
        engine_version="2.4.3",
        product_version="STANDARD",
        resource_spec="spec-1",
        node_count=3,
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        storage_type="CLOUD_SSD",
        storage_capacity=50,
        internet_access=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"].startswith("ins-new-")
    assert result["instance"]["Name"] == "production-nacos"
    assert result["instance"]["Status"] == "running"
    assert len(fake.instances) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeSREInstances"
    assert "CreateEngine" in ops


def test_create_engine_with_internet_access(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        engine_type="nacos",
        engine_version="2.4.3",
        product_version="STANDARD",
        resource_spec="spec-1",
        node_count=3,
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        internet_access=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["EnableInternet"] is True
    ops = list(fake.calls)
    assert "CreateEngine" in ops
    assert "UpdateEngineInternetAccess" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        engine_type="nacos",
        engine_version="2.4.3",
        product_version="STANDARD",
        resource_spec="spec-1",
        node_count=3,
        vpc_id="vpc-1",
        subnet_id="subnet-1",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Name"] == "production-nacos"
    assert fake.instances == []
    assert "CreateEngine" not in fake.calls


# ---------------------------------------------------------------------------
# existing-engine flows
# ---------------------------------------------------------------------------


def test_existing_engine_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(name="production-nacos")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "ins-8b0a1c2d"


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(instance_id="ins-8b0a1c2d", name="renamed", engine_type="zookeeper")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "identity, topology, network and storage are immutable" in payload["msg"]
    assert "Type" in payload["immutable_drift"]


def test_enable_internet_access(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(instance_id="ins-8b0a1c2d", internet_access=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["EnableInternet"] is True
    ops = list(fake.calls)
    assert "UpdateEngineInternetAccess" in ops


def test_internet_access_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, instance_id="ins-8b0a1c2d", internet_access=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["EnableInternet"] is False
    assert "UpdateEngineInternetAccess" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(instances=[_instance(), _instance(InstanceId="ins-dup")])
    _make_module(monkeypatch, fake)
    _base(name="production-nacos")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE engines matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSREInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(name="production-nacos")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
