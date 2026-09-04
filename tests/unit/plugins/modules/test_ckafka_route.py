"""Unit tests for the ckafka_route write module (helpers + run_module).

Creates and deletes CKafka access routes. A route is looked up through
DescribeRoute by RouteId or by the VipType/AccessType/VpcId/Subnet
identity fields. Every comparable field is immutable on an existing
route — any drift fails instead of updating; the only remedy is delete
and recreate. VPC routes demand vpc_id + subnet_id and public routes
demand public_bandwidth, which must be a multiple of 3.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_route as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _route(**overrides):
    """API-shaped route dict; fresh copy per call."""
    item = {
        "RouteId": 101,
        "VipType": 3,
        "AccessType": 0,
        "VpcId": "vpc-1",
        "Subnet": "subnet-1",
        "Note": "",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "ckafka-abc",
        "route_id": None,
        "network_type": 3,
        "access_type": 0,
        "vpc_id": None,
        "subnet_id": None,
        "public_bandwidth": None,
        "note": "",
        "security_group_ids": [],
        "ip_whitelist": [],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCkafkaClient(object):
    """In-memory CkafkaClient stand-in storing route dicts.

    DescribeRoute returns Result.Routers filtered by RouteId when given;
    CreateRoute synthesizes sequential RouteIds from the request fields
    (SubnetId maps to the API's Subnet key); DeleteRoute removes by id.
    """

    def __init__(self, routes=None):
        self.routes = [dict(r) for r in (routes or [])]
        self.calls = []
        self._seq = 1001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeRoute(self, request):
        self._record("DescribeRoute", request)
        route_id = getattr(request, "RouteId", None)
        values = self.routes
        if route_id is not None:
            values = [r for r in values if r["RouteId"] == route_id]
        return SimpleNamespace(
            Result=SimpleNamespace(Routers=[FakeResource(dict(r)) for r in values]),
            RequestId="req-fake",
        )

    def CreateRoute(self, request):
        self._record("CreateRoute", request)
        stored = {
            "RouteId": self._seq,
            "VipType": request.VipType,
            "AccessType": request.AccessType,
            "VpcId": getattr(request, "VpcId", None),
            "Subnet": getattr(request, "SubnetId", None),
            "Note": getattr(request, "Note", ""),
        }
        self._seq += 1
        self.routes.append(stored)
        return SimpleNamespace(RouteId=stored["RouteId"], RequestId="req-fake")

    def DeleteRoute(self, request):
        self._record("DeleteRoute", request)
        self.routes = [r for r in self.routes if r["RouteId"] != request.RouteId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_instance_and_route():
    request = mod.describe_request(FakeModels(), "ckafka-abc", 101)
    assert request.InstanceId == "ckafka-abc"
    assert request.RouteId == 101


def test_describe_request_instance_only():
    request = mod.describe_request(FakeModels(), "ckafka-abc")
    assert request.InstanceId == "ckafka-abc"
    assert request.RouteId is None


def test_create_request_carries_all_fields():
    request = mod.create_request(
        FakeModels(),
        _params(vpc_id="vpc-1", subnet_id="subnet-1", note="prod", security_group_ids=["sg-1"], ip_whitelist=["1.2.3.4"]),
    )
    assert request.InstanceId == "ckafka-abc"
    assert request.VipType == 3
    assert request.AccessType == 0
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.PublicNetwork is None
    assert request.Note == "prod"
    assert request.SecurityGroupIds == ["sg-1"]
    assert request.IpWhitelist == ["1.2.3.4"]


def test_create_request_public_route_fields():
    request = mod.create_request(FakeModels(), _params(network_type=1, public_bandwidth=3))
    assert request.VipType == 1
    assert request.PublicNetwork == 3
    assert request.VpcId is None
    assert request.SubnetId is None


def test_delete_request_carries_route_id():
    request = mod.delete_request(FakeModels(), "ckafka-abc", 101)
    assert request.InstanceId == "ckafka-abc"
    assert request.RouteId == 101


def test_comparable_selects_five_keys():
    value = mod.comparable(_route())
    assert value == {
        "VipType": 3,
        "AccessType": 0,
        "VpcId": "vpc-1",
        "Subnet": "subnet-1",
        "Note": "",
    }


def test_comparable_normalizes_absent_identity():
    value = mod.comparable({"VipType": 1, "Note": None})
    assert value == {"VipType": 1, "AccessType": None, "VpcId": None, "Subnet": None, "Note": ""}


def test_desired_matches_module_params():
    assert mod.desired(_params(vpc_id="vpc-1", subnet_id="subnet-1", note="x")) == {
        "VipType": 3,
        "AccessType": 0,
        "VpcId": "vpc-1",
        "Subnet": "subnet-1",
        "Note": "x",
    }


def test_find_by_route_id(monkeypatch):
    fake = FakeCkafkaClient([_route(), _route(RouteId=102, VipType=1)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(route_id=102))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RouteId"] == 102


def test_find_by_identity_fields(monkeypatch):
    fake = FakeCkafkaClient([_route(RouteId=102, VipType=1), _route()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(route_id=None, vpc_id="vpc-1", subnet_id="subnet-1"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RouteId"] == 101


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCkafkaClient([_route(VipType=1)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(route_id=None, vpc_id="vpc-9", subnet_id="subnet-9"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_vpc_route_requires_vpc_and_subnet(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "vpc_id and subnet_id are required for VPC routes" in payload["msg"]


def test_public_route_requires_bandwidth(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, network_type=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "public_bandwidth is required for public routes" in payload["msg"]


def test_bandwidth_must_be_multiple_of_three(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, network_type=1, public_bandwidth=4)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "public_bandwidth must be a multiple of 3" in payload["msg"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", route_id=999)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"] is None
    assert [c[0] for c in fake.calls] == ["DescribeRoute"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", route_id=101, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["RouteId"] == 101
    assert [c[0] for c in fake.calls] == ["DescribeRoute"]


def test_absent_deletes_route(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", route_id=101)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert [c[0] for c in fake.calls] == ["DescribeRoute", "DeleteRoute"]
    assert fake.calls[1][1].RouteId == 101
    assert fake.routes == []


def test_present_noop_matching_identity(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, vpc_id="vpc-1", subnet_id="subnet-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"]["RouteId"] == 101
    assert [c[0] for c in fake.calls] == ["DescribeRoute"]


def test_present_noop_via_route_id(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(route_id=101, vpc_id="vpc-1", subnet_id="subnet-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"]["RouteId"] == 101


def test_present_check_mode_create_reports_target(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, vpc_id="vpc-1", subnet_id="subnet-1", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["VipType"] == 3
    assert result["diff"]["after"]["VpcId"] == "vpc-1"
    assert [c[0] for c in fake.calls] == ["DescribeRoute"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, vpc_id="vpc-1", subnet_id="subnet-1", note="orders", security_group_ids=["sg-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["RouteId"] == 1001
    assert result["route"]["VipType"] == 3
    assert [c[0] for c in fake.calls] == ["DescribeRoute", "CreateRoute", "DescribeRoute"]
    created = fake.calls[1][1]
    assert created.InstanceId == "ckafka-abc"
    assert created.VipType == 3
    assert created.VpcId == "vpc-1"
    assert created.SubnetId == "subnet-1"
    assert created.Note == "orders"
    assert created.SecurityGroupIds == ["sg-1"]
    assert created.IpWhitelist == []


def test_present_create_public_route_with_bandwidth(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, network_type=1, public_bandwidth=6, ip_whitelist=["1.2.3.4"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["RouteId"] == 1001
    assert result["route"]["VipType"] == 1
    assert [c[0] for c in fake.calls] == ["DescribeRoute", "CreateRoute", "DescribeRoute"]
    assert fake.calls[1][1].PublicNetwork == 6
    assert fake.calls[1][1].IpWhitelist == ["1.2.3.4"]
    assert fake.calls[1][1].VpcId is None


def test_present_immutable_note_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(route_id=None, vpc_id="vpc-1", subnet_id="subnet-1", note="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing CKafka route" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"Note": {"before": "", "after": "renamed"}}
    assert [c[0] for c in fake.calls] == ["DescribeRoute"]


def test_present_immutable_vpc_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_route()])
    _make_module(monkeypatch, fake)
    _run_args(route_id=101, vpc_id="vpc-2", subnet_id="subnet-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {
        "VpcId": {"before": "vpc-1", "after": "vpc-2"}
    }


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", route_id=101)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
