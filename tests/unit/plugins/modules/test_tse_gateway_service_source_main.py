"""Unit tests for the tse_gateway_service_source write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TSE client whose write
operations mutate the service-source store so post-write find/waiters
converge on the first poll.

Scenario matrix:

* absent on a missing source (idempotent no-op), matched by id or by name
* absent with a matching source (check-mode dry run, real delete)
* creation when missing (happy path, check mode, missing creation params)
* no-op when nothing drifts
* drift updates (source_info change, rotate_credentials)
* immutable source_type guard
* the ``Result is not True`` guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_service_source as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SOURCE = {
    "SourceID": "nacos-123",
    "SourceName": "customer-nacos",
    "SourceType": "Customer-Nacos",
    "SourceInfo": {
        "Addresses": ["10.0.0.20:8848"],
        "VpcInfo": {"VpcID": "vpc-abc", "SubnetID": "subnet-abc"},
        "Auth": {"Username": "gateway-reader", "Password": "sekrit"},
    },
}


def _source(**overrides):
    item = copy.deepcopy(SOURCE)
    item.update(overrides)
    return item


def _id_args(**overrides):
    params = {"gateway_id": "gateway-abc", "source_id": "nacos-123"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"gateway_id": "gateway-abc", "source_name": "customer-nacos"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a small service-source store."""

    def __init__(self, sources=None, result=True):
        self.sources = [copy.deepcopy(t) for t in (sources or [])]
        self.result = result
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeNativeGatewayServiceSources(self, request):
        self._record("DescribeNativeGatewayServiceSources", request)
        return SimpleNamespace(List=[FakeResource(t) for t in self.sources])

    def _mutate(self, request, source_id):
        for item in self.sources:
            if item.get("SourceID") == source_id:
                for attr in ("SourceName", "SourceInfo", "SourceType"):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[attr] = value
                return True
        return False

    def CreateNativeGatewayServiceSource(self, request):
        self._record("CreateNativeGatewayServiceSource", request)
        self._next += 1
        item = {
            "SourceID": getattr(request, "SourceID", None) or "source-new-%03d" % self._next,
            "SourceName": getattr(request, "SourceName", None),
            "SourceType": getattr(request, "SourceType", None),
        }
        if getattr(request, "SourceInfo", None) is not None:
            item["SourceInfo"] = getattr(request, "SourceInfo")
        self.sources.append(item)
        return SimpleNamespace(Result=self.result, SourceID=item["SourceID"], RequestId="req-fake")

    def ModifyNativeGatewayServiceSource(self, request):
        self._record("ModifyNativeGatewayServiceSource", request)
        self._mutate(request, getattr(request, "SourceID", None))
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def DeleteNativeGatewayServiceSource(self, request):
        self._record("DeleteNativeGatewayServiceSource", request)
        source_id = getattr(request, "SourceID", None)
        self.sources = [t for t in self.sources if t.get("SourceID") != source_id]
        return SimpleNamespace(Result=self.result, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", source_id="ghost-source")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["source"] is None
    assert [c for c, unused in fake.calls] == ["DescribeNativeGatewayServiceSources"]


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", source_name="ghost-source")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["source"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"] is None
    assert len(fake.sources) == 1
    assert "DeleteNativeGatewayServiceSource" not in [c for c, unused in fake.calls]


def test_absent_deletes_source(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"] is None
    assert fake.sources == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteNativeGatewayServiceSource" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", source_type="Customer-Nacos")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "source_id" in payload["missing"]


def test_create_source(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    _id_args(
        state="present",
        source_id="nacos-123",
        source_name="customer-nacos",
        source_type="Customer-Nacos",
        source_info={
            "Addresses": ["10.0.0.20:8848"],
            "VpcInfo": {"VpcID": "vpc-abc", "SubnetID": "subnet-abc"},
            "Auth": {"Username": "gateway-reader", "Password": "sekrit"},
        },
        waiter_timeout=60,
        waiter_delay=1,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"]["SourceID"] == "nacos-123"
    assert result["source"]["SourceType"] == "Customer-Nacos"
    assert len(fake.sources) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateNativeGatewayServiceSource" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        source_id="nacos-123",
        source_name="customer-nacos",
        source_type="Customer-Nacos",
        source_info={"Addresses": ["10.0.0.20:8848"]},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"]["SourceType"] == "Customer-Nacos"
    assert fake.sources == []
    assert "CreateNativeGatewayServiceSource" not in [c for c, unused in fake.calls]


def test_create_without_source_name_allowed_for_private_dns(monkeypatch):
    fake = FakeTseClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        gateway_id="gateway-abc",
        source_name="pdns-source",
        source_type="PrivateDNS",
        source_info={"DnsId": "dns-abc"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"]["SourceType"] == "PrivateDNS"


# ---------------------------------------------------------------------------
# existing-source flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", source_name="customer-nacos", source_type="Customer-Nacos")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["source"]["SourceID"] == "nacos-123"
    assert "ModifyNativeGatewayServiceSource" not in [c for c, unused in fake.calls]


def test_update_source_info_drift(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _id_args(
        state="present",
        source_name="customer-nacos",
        source_info={"Addresses": ["10.0.0.99:8848"]},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["source"]["SourceInfo"]["Addresses"] == ["10.0.0.99:8848"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyNativeGatewayServiceSource" in ops


def test_rotate_credentials_forces_update(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", source_name="customer-nacos", rotate_credentials=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ModifyNativeGatewayServiceSource" in ops


def test_source_type_is_immutable(monkeypatch):
    fake = FakeTseClient(sources=[_source()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", source_type="TSE-Nacos")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert payload["current_type"] == "Customer-Nacos"
    assert payload["desired_type"] == "TSE-Nacos"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(sources=[_source(), _source(SourceID="nacos-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify source_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_unsuccessful_result_fails(monkeypatch):
    fake = FakeTseClient(sources=[], result=False)
    _make_module(monkeypatch, fake)
    _id_args(
        state="present",
        source_id="nacos-123",
        source_name="customer-nacos",
        source_type="Customer-Nacos",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "unsuccessful result" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNativeGatewayServiceSources(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_service_source.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    def from_json_string(self, raw):
        self.raw = raw


class LegacyModels(object):
    CreateNativeGatewayServiceSourceRequest = LegacyValue
    ModifyNativeGatewayServiceSourceRequest = LegacyValue
    DeleteNativeGatewayServiceSourceRequest = LegacyValue


def test_service_source_requests_map_full_lifecycle():
    p = {
        "gateway_id": "g1",
        "source_id": "nacos-1",
        "source_name": "registry",
        "source_type": "Customer-Nacos",
        "source_info": {
            "Addresses": ["10.0.0.2:8848"],
            "Auth": {"Username": "reader", "Password": "secret"},
        },
    }
    assert json.loads(mod.create_request(LegacyModels, p).raw)["GatewayID"] == "g1"
    current = {"SourceID": "nacos-1", "SourceName": "old", "SourceInfo": {}}
    assert json.loads(mod.update_request(LegacyModels, p, current).raw)["SourceName"] == "registry"
    without_info = dict(p, source_info=None)
    assert "SourceInfo" not in json.loads(mod.update_request(LegacyModels, without_info, current).raw)
    assert json.loads(mod.delete_request(LegacyModels, p, "nacos-1").raw)["SourceID"] == "nacos-1"


def test_service_source_comparison_removes_write_only_credentials():
    value = {"SourceInfo": {"Addresses": ["10.0.0.2:8848"], "Auth": {"Username": "reader", "Password": "secret", "AccessToken": "token"}}}
    assert mod.readable(value) == {"SourceInfo": {"Addresses": ["10.0.0.2:8848"], "Auth": {"Username": "reader"}}}
    p = {"source_name": "registry", "source_type": "Customer-Nacos", "source_info": value["SourceInfo"]}
    assert mod.desired(p)["SourceInfo"]["Auth"] == {"Username": "reader"}
