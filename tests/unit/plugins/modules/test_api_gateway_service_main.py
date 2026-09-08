"""Unit tests for the api_gateway_service write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake API Gateway
client whose write operations mutate the service store, so the module's
post-write ``find_service`` refetch and the converged-state waiter return
immediately.

Scenario matrix:

* absent on a missing service (idempotent no-op)
* absent with a matching service (check-mode dry run and real delete)
* creation when missing (with/without the required name, check mode)
* no-op when nothing drifts
* drift updates on the mutable service attributes
* the multi-match guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVICE = {
    "ServiceId": "service-abc123",
    "ServiceName": "order-api",
    "ServiceDesc": "Order service APIs",
    "Protocol": "http&https",
    "NetTypes": ["OUTER"],
    "Status": "active",
}


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.ServiceNotFound"

    def get_request_id(self):
        return None


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    # service_id and name are alternatives (required_one_of); start from the
    # name and let update tests pass a service_id when they need it.
    params = {"name": "order-api"}
    params.update(overrides)
    return module_args(**params)


class FakeApigatewayClient(object):
    """In-memory API Gateway client mutating a service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeService(self, request):
        self._record("DescribeService", request)
        for item in self.services:
            if item.get("ServiceId") == request.ServiceId:
                return SimpleNamespace(Result=FakeResource(dict(item)), RequestId="req-fake")
        raise NotFoundError()

    def DescribeServicesStatus(self, request):
        self._record("DescribeServicesStatus", request)
        return SimpleNamespace(
            Result=SimpleNamespace(
                ServiceSet=[FakeResource(dict(t)) for t in self.services],
                TotalCount=len(self.services),
            ),
            RequestId="req-fake",
        )

    def CreateService(self, request):
        self._record("CreateService", request)
        service_id = "service-new%04d" % (len(self.services) + 1)
        self.services.append({
            "ServiceId": service_id,
            "ServiceName": request.ServiceName,
            "ServiceDesc": request.ServiceDesc,
            "Protocol": request.Protocol,
            "NetTypes": list(request.NetTypes or []),
            "Status": "active",
        })
        return SimpleNamespace(ServiceId=service_id, RequestId="req-fake")

    def ModifyService(self, request):
        self._record("ModifyService", request)
        for item in self.services:
            if item.get("ServiceId") == request.ServiceId:
                item["ServiceName"] = request.ServiceName
                item["ServiceDesc"] = request.ServiceDesc
                item["Protocol"] = request.Protocol
                item["NetTypes"] = list(request.NetTypes or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteService(self, request):
        self._record("DeleteService", request)
        self.services = [t for t in self.services if t.get("ServiceId") != request.ServiceId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_api_gateway", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_service_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", service_id="service-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert [c for c, unused in fake.calls] == ["DescribeService"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceId"] == "service-abc123"
    assert "DeleteService" not in [c for c, unused in fake.calls]


def test_absent_deletes_service(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert fake.services == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteService" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeApigatewayClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", service_id="service-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating" in exc.value.args[0]["msg"]


def test_create_service(monkeypatch):
    fake = FakeApigatewayClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api", protocol="http&https", network_types=["OUTER"], description="Order service APIs")
    result = run(mod.run_module)
    assert result["changed"] is True
    service = result["service"]
    assert service["ServiceName"] == "order-api"
    assert service["ServiceDesc"] == "Order service APIs"
    assert service["NetTypes"] == ["OUTER"]
    assert len(fake.services) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeServicesStatus"
    assert "CreateService" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(services=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="order-api", protocol="https")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert fake.services == []
    assert "CreateService" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_existing_service_no_drift_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api", protocol="http&https", network_types=["OUTER"], description="Order service APIs")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["ServiceId"] == "service-abc123"


def test_update_description_drift(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api", protocol="http&https", network_types=["OUTER"], description="Renamed service APIs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceDesc"] == "Renamed service APIs"
    ops = [c for c, unused in fake.calls]
    assert "ModifyService" in ops


def test_update_network_types(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api", protocol="http&https", network_types=["INNER", "OUTER"], description="Order service APIs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(result["service"]["NetTypes"]) == ["INNER", "OUTER"]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="order-api", description="Renamed service APIs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceDesc"] == "Order service APIs"
    assert "ModifyService" not in [c for c, unused in fake.calls]


def test_identify_by_service_id_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(services=[_service()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        service_id="service-abc123",
        name="order-api",
        protocol="http&https",
        network_types=["OUTER"],
        description="Order service APIs",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c for c, unused in fake.calls] == ["DescribeService"]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeApigatewayClient(services=[_service(), _service(ServiceId="service-dup999")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api", protocol="http&https")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple API Gateway services have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeServicesStatus(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="order-api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
