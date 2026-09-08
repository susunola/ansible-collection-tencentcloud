"""Unit tests for the privatelink_endpoint_service write module
(run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client
whose write operations mutate the endpoint-service store, so the module's
post-write ``find_service`` refetch and waiters converge immediately.

Scenario matrix:

* absent on a missing service (idempotent no-op)
* absent with a matching service (check-mode dry run and the real delete)
* creation when missing (required-parameter guard, check mode, happy path)
* no-op when nothing drifts
* drift updates by service ID and check-mode dry runs
* the multiple-match guard and the ``Tencent Cloud API request failed``
  failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import privatelink_endpoint_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVICE = {
    "EndPointServiceId": "vpcsvc-abc123",
    "ServiceName": "internal-api",
    "VpcId": "vpc-abc",
    "ServiceInstanceId": "lb-abc",
    "AutoAcceptFlag": True,
    "IpAddressType": "IPv4",
}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating a small endpoint-service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeVpcEndPointService(self, request):
        self._record("DescribeVpcEndPointService", request)
        service_ids = getattr(request, "EndPointServiceIds", None) or []
        matches = []
        if service_ids:
            matches = [dict(t) for t in self.services if t.get("EndPointServiceId") in service_ids]
        else:
            filters = getattr(request, "Filters", None) or []
            name = None
            for item in filters:
                if item.Name == "end-point-service-name":
                    name = item.Values[0]
            matches = [dict(t) for t in self.services if t.get("ServiceName") == name]
        return SimpleNamespace(EndPointServiceSet=[FakeResource(t) for t in matches], TotalCount=len(matches))

    def CreateVpcEndPointService(self, request):
        self._record("CreateVpcEndPointService", request)
        self._next += 1
        item = {
            "EndPointServiceId": "vpcsvc-new-%03d" % self._next,
            "ServiceName": getattr(request, "EndPointServiceName", None),
            "VpcId": getattr(request, "VpcId", None),
            "ServiceInstanceId": getattr(request, "ServiceInstanceId", None),
            "AutoAcceptFlag": getattr(request, "AutoAcceptFlag", None),
            "IpAddressType": getattr(request, "IpAddressType", None),
        }
        self.services.append(item)
        return SimpleNamespace(EndPointService=FakeResource({"EndPointServiceId": item["EndPointServiceId"]}), RequestId="req-fake")

    def ModifyVpcEndPointServiceAttribute(self, request):
        self._record("ModifyVpcEndPointServiceAttribute", request)
        for item in self.services:
            if item.get("EndPointServiceId") == getattr(request, "EndPointServiceId", None):
                item["ServiceName"] = getattr(request, "EndPointServiceName", None)
                item["VpcId"] = getattr(request, "VpcId", None)
                item["ServiceInstanceId"] = getattr(request, "ServiceInstanceId", None)
                item["AutoAcceptFlag"] = getattr(request, "AutoAcceptFlag", None)
                item["IpAddressType"] = getattr(request, "IpAddressType", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteVpcEndPointService(self, request):
        self._record("DeleteVpcEndPointService", request)
        self.services = [t for t in self.services if t.get("EndPointServiceId") != getattr(request, "EndPointServiceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_service_is_idempotent(monkeypatch):
    fake = FakeVpcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint_service"] is None
    assert _ops(fake) == ["DescribeVpcEndPointService"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", endpoint_service_id="vpcsvc-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"]["ServiceName"] == "internal-api"
    assert len(fake.services) == 1
    assert "DeleteVpcEndPointService" not in _ops(fake)


def test_absent_deletes_service(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="absent", endpoint_service_id="vpcsvc-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"] is None
    assert fake.services == []
    ops = _ops(fake)
    assert "DeleteVpcEndPointService" in ops
    delete_request = [r for c, r in fake.calls if c == "DeleteVpcEndPointService"][0]
    assert delete_request.EndPointServiceId == "vpcsvc-abc123"
    assert delete_request.IpAddressType == "IPv4"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeVpcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="internal-api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"].startswith("Required when creating:")
    assert "vpc_id" in payload["msg"]
    assert "service_instance_id" in payload["msg"]


def test_create_service(monkeypatch):
    fake = FakeVpcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="internal-api", vpc_id="vpc-abc", service_instance_id="lb-abc", auto_accept=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"]["ServiceName"] == "internal-api"
    assert result["endpoint_service"]["EndPointServiceId"].startswith("vpcsvc-new-")
    assert len(fake.services) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeVpcEndPointService"
    assert "CreateVpcEndPointService" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="internal-api", vpc_id="vpc-abc", service_instance_id="lb-abc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"] is None
    assert fake.services == []
    assert "CreateVpcEndPointService" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_existing_service_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", endpoint_service_id="vpcsvc-abc123", name="internal-api", vpc_id="vpc-abc", service_instance_id="lb-abc", auto_accept=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint_service"]["EndPointServiceId"] == "vpcsvc-abc123"
    assert "ModifyVpcEndPointServiceAttribute" not in _ops(fake)


def test_auto_accept_drift_updates(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        endpoint_service_id="vpcsvc-abc123",
        name="internal-api",
        vpc_id="vpc-abc",
        service_instance_id="lb-abc",
        auto_accept=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"]["AutoAcceptFlag"] is False
    ops = _ops(fake)
    assert "ModifyVpcEndPointServiceAttribute" in ops
    modify_request = [r for c, r in fake.calls if c == "ModifyVpcEndPointServiceAttribute"][0]
    assert modify_request.AutoAcceptFlag is False


def test_rename_service_updates(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", endpoint_service_id="vpcsvc-abc123", name="renamed-api", vpc_id="vpc-abc", service_instance_id="lb-abc", auto_accept=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint_service"]["ServiceName"] == "renamed-api"
    assert fake.services[0]["ServiceName"] == "renamed-api"
    assert "ModifyVpcEndPointServiceAttribute" in _ops(fake)


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        endpoint_service_id="vpcsvc-abc123",
        name="renamed-api",
        vpc_id="vpc-abc",
        service_instance_id="lb-abc",
        auto_accept=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.services[0]["ServiceName"] == "internal-api"
    assert fake.services[0]["AutoAcceptFlag"] is True
    assert "ModifyVpcEndPointServiceAttribute" not in _ops(fake)


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeVpcClient(services=[_service(), _service(EndPointServiceId="vpcsvc-dup2")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="internal-api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple endpoint services have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeVpcEndPointService(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="internal-api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
