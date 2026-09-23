"""Unit tests for the privatelink_endpoint write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client whose
write operations mutate the endpoint store, so the post-write waiter
converges on its first poll.

Scenario matrix:

* absent on a missing endpoint (idempotent no-op)
* absent with a matching endpoint (check-mode dry run and the real delete)
* creation when missing (missing creation parameters, check-mode dry run and
  the happy path)
* no-op when nothing drifts
* drift update (name / security groups) with check-mode preview
* argument-spec validation guards (choice violations, missing endpoint_id/name)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import privatelink_endpoint as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENDPOINT_ID = "vpce-8b0a1c2d"

ENDPOINT = {
    "EndPointId": ENDPOINT_ID,
    "EndPointName": "internal-api-client",
    "VpcId": "vpc-abc",
    "SubnetId": "subnet-abc",
    "EndPointServiceId": "vpcsvc-xyz",
    "GroupSet": [{"SecurityGroupId": "sg-1"}],
    "IpAddressType": "IPv4",
}


def _endpoint(**overrides):
    item = copy.deepcopy(ENDPOINT)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, ip_address_type) must not be
    # pre-filled with None. endpoint_id/name are a required_one_of pair.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "internal-api-client"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"endpoint_id": ENDPOINT_ID}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating a small PrivateLink endpoint store."""

    def __init__(self, endpoints=None):
        self.endpoints = [copy.deepcopy(t) for t in (endpoints or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeVpcEndPoint(self, request):
        self._record("DescribeVpcEndPoint", request)
        ids = list(getattr(request, "EndPointId", None) or [])
        filters = {getattr(f, "Name", None): list(getattr(f, "Values", None) or []) for f in (getattr(request, "Filters", None) or [])}
        matched = []
        for item in self.endpoints:
            if ids and item.get("EndPointId") not in ids:
                continue
            if filters.get("end-point-name") and item.get("EndPointName") not in filters["end-point-name"]:
                continue
            if filters.get("vpc-id") and item.get("VpcId") not in filters["vpc-id"]:
                continue
            matched.append(dict(item))
        return SimpleNamespace(EndPointSet=[FakeResource(t) for t in matched], TotalCount=len(matched))

    def CreateVpcEndPoint(self, request):
        self._record("CreateVpcEndPoint", request)
        item = {
            "EndPointId": "vpce-new-%d" % (len(self.endpoints) + 1),
            "EndPointName": getattr(request, "EndPointName", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "EndPointServiceId": getattr(request, "EndPointServiceId", None),
            "IpAddressType": getattr(request, "IpAddressType", None),
        }
        group = getattr(request, "SecurityGroupId", None)
        item["GroupSet"] = [{"SecurityGroupId": group}] if group else []
        self.endpoints.append(item)
        return SimpleNamespace(EndPoint=SimpleNamespace(EndPointId=item["EndPointId"]), RequestId="req-fake")

    def ModifyVpcEndPointAttribute(self, request):
        self._record("ModifyVpcEndPointAttribute", request)
        for item in self.endpoints:
            if item.get("EndPointId") == getattr(request, "EndPointId", None):
                item["EndPointName"] = getattr(request, "EndPointName", None)
                item["IpAddressType"] = getattr(request, "IpAddressType", None)
                groups = getattr(request, "SecurityGroupIds", None)
                if groups is not None:
                    item["GroupSet"] = [{"SecurityGroupId": g} for g in groups]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteVpcEndPoint(self, request):
        self._record("DeleteVpcEndPoint", request)
        self.endpoints = [t for t in self.endpoints if t.get("EndPointId") != getattr(request, "EndPointId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_endpoint_is_idempotent(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-endpoint")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"] is None
    assert [c for c, unused in fake.calls] == ["DescribeVpcEndPoint"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete PrivateLink endpoint"
    assert len(fake.endpoints) == 1
    assert "DeleteVpcEndPoint" not in [c for c, unused in fake.calls]


def test_absent_deletes_endpoint(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "PrivateLink endpoint deleted"
    assert result["endpoint"] is None
    assert fake.endpoints == []
    assert "DeleteVpcEndPoint" in [c for c, unused in fake.calls]


def test_absent_by_id_deletes_endpoint(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.endpoints == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="new-ep", vpc_id="vpc-abc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Required when creating" in payload["msg"]
    assert "subnet_id" in payload["msg"]
    assert "endpoint_service_id" in payload["msg"]


def test_create_endpoint(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        endpoint_service_id="vpcsvc-xyz",
        security_group_ids=["sg-1"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "PrivateLink endpoint created"
    assert result["endpoint"]["EndPointName"] == "internal-api-client"
    assert len(fake.endpoints) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeVpcEndPoint"
    assert "CreateVpcEndPoint" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        endpoint_service_id="vpcsvc-xyz",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create PrivateLink endpoint"
    assert fake.endpoints == []
    assert "CreateVpcEndPoint" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-endpoint flows
# ---------------------------------------------------------------------------


def test_existing_endpoint_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", security_group_ids=["sg-1"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "PrivateLink endpoint is up to date"
    assert result["endpoint"]["EndPointId"] == ENDPOINT_ID


def test_update_endpoint_name(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint(EndPointName="old-name", GroupSet=[])])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-ep", security_group_ids=["sg-2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "PrivateLink endpoint updated"
    assert result["endpoint"]["EndPointName"] == "renamed-ep"
    assert [g["SecurityGroupId"] for g in result["endpoint"]["GroupSet"]] == ["sg-2"]
    assert "ModifyVpcEndPointAttribute" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint(EndPointName="old-name")])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update PrivateLink endpoint"
    assert fake.endpoints[0]["EndPointName"] == "old-name"
    assert "ModifyVpcEndPointAttribute" not in [c for c, unused in fake.calls]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeVpcClient(endpoints=[_endpoint(), _endpoint(EndPointId="vpce-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple endpoints have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_requires_endpoint_id_or_name(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _base(state="present", vpc_id="vpc-abc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "endpoint_id" in exc.value.args[0]["msg"]
    assert "name" in exc.value.args[0]["msg"]


def test_invalid_ip_address_type_fails_argument_spec(monkeypatch):
    fake = FakeVpcClient(endpoints=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", ip_address_type="IPV4")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ip_address_type" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeVpcEndPoint(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_privatelink_endpoint.py)
# ---------------------------------------------------------------------------


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "api-client",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "endpoint_service_id": "vpcsvc-1",
        "endpoint_vip": None,
        "security_group_ids": ["sg-1"],
        "ip_address_type": "IPv4",
        "tags": {"env": "prod"},
    }
    create = mod.build_create_request(models, params)
    assert create.EndPointServiceId == "vpcsvc-1"
    assert create.SecurityGroupId == "sg-1"
    update = mod.build_update_request(models, "vpce-1", params)
    assert update.SecurityGroupIds == ["sg-1"]
    assert mod.build_delete_request(models, "vpce-1", "IPv4").EndPointId == "vpce-1"
