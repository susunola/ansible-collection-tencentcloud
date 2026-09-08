"""Unit tests for the tsf_microservice write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSF client
whose write operations mutate the microservice store, so the post-write
describe refetch converges immediately.

Scenario matrix:

* absent on a missing microservice (idempotent) / real delete / delete by
  microservice_id / check-mode dry run / SDK-rejected delete
* creation when missing (check mode, real create)
* no-op when nothing drifts
* description update and check-mode update
* immutable drift on namespace/name
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_microservice as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAMESPACE_ID = "namespace-8b0a1c2d"

MICROSERVICE = {
    "MicroserviceId": "ms-8b0a1c2d",
    "NamespaceId": NAMESPACE_ID,
    "MicroserviceName": "orders",
    "MicroserviceDesc": "Order service",
}


def _microservice(**overrides):
    item = copy.deepcopy(MICROSERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"namespace_id": NAMESPACE_ID, "name": "orders"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client mutating a microservice store."""

    def __init__(self, microservices=None):
        self.microservices = [copy.deepcopy(t) for t in (microservices or [])]
        self.calls = []
        self._next = 0

    def _copy(self, request):
        return {k: v for k, v in dict(getattr(request, "__dict__", {})).items() if not k.startswith("_")}

    def DescribeMicroservices(self, request):
        self.calls.append("DescribeMicroservices")
        ids = getattr(request, "MicroserviceIdList", None)
        names = getattr(request, "MicroserviceNameList", None)
        if ids:
            # Microservice IDs are globally unique; the ID lookup ignores the
            # namespace so a microservice can be found even when its
            # namespace identity is drifting in the requested parameters.
            matched = [t for t in self.microservices if t.get("MicroserviceId") in ids]
        else:
            matched = [
                t
                for t in self.microservices
                if t.get("NamespaceId") == getattr(request, "NamespaceId", None) and t.get("MicroserviceName") in (names or [])
            ]
        return SimpleNamespace(Result=SimpleNamespace(Content=[FakeResource(t) for t in matched]), RequestId="req-fake")

    def CreateMicroserviceWithDetailResp(self, request):
        self.calls.append("CreateMicroserviceWithDetailResp")
        self._next += 1
        item = self._copy(request)
        item["MicroserviceId"] = "ms-new-%03d" % self._next
        self.microservices.append(item)
        return SimpleNamespace(Result=item["MicroserviceId"], RequestId="req-fake")

    def ModifyMicroservice(self, request):
        self.calls.append("ModifyMicroservice")
        for item in self.microservices:
            if item.get("MicroserviceId") == getattr(request, "MicroserviceId", None):
                desc = getattr(request, "MicroserviceDesc", None)
                if desc is not None:
                    item["MicroserviceDesc"] = desc
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteMicroservice(self, request):
        self.calls.append("DeleteMicroservice")
        self.microservices = [t for t in self.microservices if t.get("MicroserviceId") != getattr(request, "MicroserviceId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_microservice_is_idempotent(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["microservice"] is None
    assert list(fake.calls) == ["DescribeMicroservices"]


def test_absent_deletes_microservice(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.microservices == []
    assert "DeleteMicroservice" in fake.calls


def test_absent_deletes_by_microservice_id(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice(MicroserviceId="ms-explicit")])
    _make_module(monkeypatch, fake)
    _base(state="absent", microservice_id="ms-explicit", name="does-not-matter")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.microservices == []
    assert "DeleteMicroservice" in fake.calls


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.microservices) == 1
    assert "DeleteMicroservice" not in fake.calls


def test_absent_sdk_rejected_delete_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteMicroservice(self, request):
            self.calls.append("DeleteMicroservice")
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF microservice deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_microservice(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(name="billing", description="Billing service")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["microservice"]["MicroserviceId"].startswith("ms-new-")
    assert result["microservice"]["MicroserviceName"] == "billing"
    assert result["microservice"]["NamespaceId"] == NAMESPACE_ID
    assert len(fake.microservices) == 1
    assert "CreateMicroserviceWithDetailResp" in fake.calls


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, name="billing", description="Billing service")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["microservice"] == {"NamespaceId": NAMESPACE_ID, "MicroserviceName": "billing", "MicroserviceDesc": "Billing service"}
    assert fake.microservices == []
    assert "CreateMicroserviceWithDetailResp" not in fake.calls


# ---------------------------------------------------------------------------
# existing-microservice flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(description="Order service")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["microservice"]["MicroserviceId"] == "ms-8b0a1c2d"
    assert "ModifyMicroservice" not in fake.calls


def test_update_description(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(description="Renamed order service")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["microservice"]["MicroserviceDesc"] == "Renamed order service"
    assert fake.microservices[0]["MicroserviceDesc"] == "Renamed order service"
    assert "ModifyMicroservice" in fake.calls


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, description="Renamed order service")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "ModifyMicroservice" not in fake.calls
    assert fake.microservices[0]["MicroserviceDesc"] == "Order service"


def test_update_sdk_rejected_modify_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def ModifyMicroservice(self, request):
            self.calls.append("ModifyMicroservice")
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(description="Renamed order service")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF microservice update" in exc.value.args[0]["msg"]


def test_immutable_namespace_drift_fails(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(microservice_id="ms-8b0a1c2d", namespace_id="namespace-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "NamespaceId" in payload["immutable_changes"]


def test_immutable_name_drift_fails(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice()])
    _make_module(monkeypatch, fake)
    _base(microservice_id="ms-8b0a1c2d", name="renamed-orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "MicroserviceName" in payload["immutable_changes"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTsfClient(microservices=[_microservice(), _microservice(MicroserviceId="ms-dup")])
    _make_module(monkeypatch, fake)
    _base(name="orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF microservices matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMicroservices(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(name="orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
