"""Unit tests for the network_interface write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/network_interface.py`` with an in-memory fake VPC client
whose write operations mutate the interface store, so the module's post-write
``find_interface`` refetch converges immediately. Interfaces can be matched
by ``network_interface_id`` (single fetch) or by ``name`` (+ optional
``subnet_id``) — both lookup paths are exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import network_interface as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INTERFACE = {
    "NetworkInterfaceId": "eni-8b0a1c2d",
    "NetworkInterfaceName": "eni-prod",
    "VpcId": "vpc-8b0a1c2d",
    "SubnetId": "subnet-8b0a1c2d",
    "NetworkInterfaceDescription": "production",
    "GroupSet": ["sg-8b0a1c2d"],
}

WRITE_OPS = (
    "CreateNetworkInterface",
    "ModifyNetworkInterfaceAttribute",
    "DeleteNetworkInterface",
)


def _interface(**overrides):
    """Return an interface fixture isolated from the shared constant."""
    interface = copy.deepcopy(INTERFACE)
    interface.update(overrides)
    return interface


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "network_interface_id": None,
        "name": None,
        "vpc_id": None,
        "subnet_id": None,
        "description": None,
        "security_group_ids": [],
        "secondary_private_ip_count": None,
        "tags": {},
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
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


class FakeVpcClient(object):
    """In-memory VPC client that mutates a small ENI store."""

    def __init__(self, interfaces=None):
        self.interfaces = [copy.deepcopy(i) for i in (interfaces or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeNetworkInterfaces(self, request):
        self._record("DescribeNetworkInterfaces", request)
        ids = getattr(request, "NetworkInterfaceIds", None)
        items = self.interfaces
        if ids:
            items = [i for i in items if i.get("NetworkInterfaceId") in ids]
        return SimpleNamespace(NetworkInterfaceSet=[FakeResource(dict(i)) for i in items])

    def CreateNetworkInterface(self, request):
        self._record("CreateNetworkInterface", request)
        interface = {
            "NetworkInterfaceId": "eni-fake-001",
            "NetworkInterfaceName": request.NetworkInterfaceName,
            "VpcId": request.VpcId,
            "SubnetId": request.SubnetId,
        }
        if hasattr(request, "NetworkInterfaceDescription"):
            interface["NetworkInterfaceDescription"] = request.NetworkInterfaceDescription
        if hasattr(request, "SecurityGroupIds"):
            interface["GroupSet"] = list(request.SecurityGroupIds)
        self.interfaces.append(interface)
        return SimpleNamespace(NetworkInterfaceId="eni-fake-001")

    def ModifyNetworkInterfaceAttribute(self, request):
        self._record("ModifyNetworkInterfaceAttribute", request)
        for interface in self.interfaces:
            if interface["NetworkInterfaceId"] != request.NetworkInterfaceId:
                continue
            if getattr(request, "NetworkInterfaceName", None):
                interface["NetworkInterfaceName"] = request.NetworkInterfaceName
            if hasattr(request, "NetworkInterfaceDescription"):
                interface["NetworkInterfaceDescription"] = request.NetworkInterfaceDescription
            if hasattr(request, "SecurityGroupIds"):
                interface["GroupSet"] = list(request.SecurityGroupIds)
        return SimpleNamespace()

    def DeleteNetworkInterface(self, request):
        self._record("DeleteNetworkInterface", request)
        self.interfaces = [
            i for i in self.interfaces if i["NetworkInterfaceId"] != request.NetworkInterfaceId
        ]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        '_load_vpc',
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_build_describe_request_by_id_sets_limit_and_filter():
    request = mod.build_describe_request(FakeModels(), "eni-8b0a1c2d", None, None)
    assert request.Limit == 100
    assert request.NetworkInterfaceIds == ["eni-8b0a1c2d"]


def test_build_describe_request_without_id_omits_filter():
    request = mod.build_describe_request(FakeModels(), None, "subnet-8b0a1c2d", "eni-prod")
    assert request.Limit == 100
    assert not hasattr(request, "NetworkInterfaceIds")


def test_find_interface_by_id_returns_serialized_item():
    module = FakeModule()
    client = FakeVpcClient(interfaces=[_interface(), _interface(NetworkInterfaceId="eni-2", NetworkInterfaceName="eni-other")])
    found = mod.find_interface(module, client, FakeModels(), "eni-8b0a1c2d", None, None)
    assert found["NetworkInterfaceId"] == "eni-8b0a1c2d"
    assert found["NetworkInterfaceName"] == "eni-prod"


def test_find_interface_by_id_missing_returns_none():
    module = FakeModule()
    client = FakeVpcClient()
    assert mod.find_interface(module, client, FakeModels(), "eni-8b0a1c2d", None, None) is None


def test_find_interface_by_name_and_subnet():
    module = FakeModule()
    client = FakeVpcClient(
        interfaces=[
            _interface(NetworkInterfaceId="eni-1", NetworkInterfaceName="eni-other", SubnetId="subnet-9"),
            _interface(),
        ]
    )
    found = mod.find_interface(module, client, FakeModels(), None, "subnet-8b0a1c2d", "eni-prod")
    assert found["NetworkInterfaceId"] == "eni-8b0a1c2d"


def test_find_interface_by_name_ignores_other_subnet():
    module = FakeModule()
    client = FakeVpcClient(interfaces=[_interface(SubnetId="subnet-9")])
    assert mod.find_interface(module, client, FakeModels(), None, "subnet-8b0a1c2d", "eni-prod") is None


def test_find_interface_by_name_without_subnet_matches_any():
    module = FakeModule()
    client = FakeVpcClient(interfaces=[_interface(SubnetId="subnet-9")])
    found = mod.find_interface(module, client, FakeModels(), None, None, "eni-prod")
    assert found["NetworkInterfaceId"] == "eni-8b0a1c2d"


def test_build_create_request_sets_required_fields():
    request = mod.build_create_request(
        FakeModels(),
        _params(name="eni-prod", vpc_id="vpc-8b0a1c2d", subnet_id="subnet-8b0a1c2d"),
    )
    assert request.VpcId == "vpc-8b0a1c2d"
    assert request.NetworkInterfaceName == "eni-prod"
    assert request.SubnetId == "subnet-8b0a1c2d"
    assert not hasattr(request, "NetworkInterfaceDescription")
    assert not hasattr(request, "SecurityGroupIds")
    assert not hasattr(request, "Tags")


def test_build_create_request_sets_optional_fields():
    request = mod.build_create_request(
        FakeModels(),
        _params(
            name="eni-prod",
            vpc_id="vpc-8b0a1c2d",
            subnet_id="subnet-8b0a1c2d",
            description="prod desc",
            security_group_ids=["sg-8b0a1c2d"],
            secondary_private_ip_count=3,
            tags={"env": "prod"},
        ),
    )
    assert request.NetworkInterfaceDescription == "prod desc"
    assert request.SecurityGroupIds == ["sg-8b0a1c2d"]
    assert request.SecondaryPrivateIpAddressCount == 3
    assert [(tag.Key, tag.Value) for tag in request.Tags] == [("env", "prod")]


def test_build_tags_sorts_by_key():
    tags = mod._build_tags(FakeModels(), {"b": "2", "a": "1"})
    assert [(tag.Key, tag.Value) for tag in tags] == [("a", "1"), ("b", "2")]


def test_create_issues_create_call(monkeypatch):
    module = FakeModule()
    client = FakeVpcClient()
    monkeypatch.setattr(
        mod,
        "build_create_request",
        lambda models, params: SimpleNamespace(
            NetworkInterfaceName="eni-prod",
            VpcId="vpc-8b0a1c2d",
            SubnetId="subnet-8b0a1c2d",
        ),
    )
    result = mod._create(module, client, FakeModels(), _params(name="eni-prod", vpc_id="vpc-8b0a1c2d", subnet_id="subnet-8b0a1c2d"))
    assert len(module.sdk_calls) == 1
    assert module.sdk_calls[0][0] == client.CreateNetworkInterface
    assert result == "eni-fake-001"


def test_update_sets_supplied_fields():
    module = FakeModule()
    client = FakeVpcClient()
    mod._update(
        module,
        client,
        FakeModels(),
        _params(name="eni-prod", description="new desc", security_group_ids=["sg-2"]),
        "eni-8b0a1c2d",
    )
    assert len(module.sdk_calls) == 1
    request = module.sdk_calls[0][1]
    assert request.NetworkInterfaceId == "eni-8b0a1c2d"
    assert request.NetworkInterfaceName == "eni-prod"
    assert request.NetworkInterfaceDescription == "new desc"
    assert request.SecurityGroupIds == ["sg-2"]


def test_delete_sets_interface_id():
    module = FakeModule()
    client = FakeVpcClient()
    mod._delete(module, client, FakeModels(), "eni-8b0a1c2d")
    assert len(module.sdk_calls) == 1
    assert module.sdk_calls[0][1].NetworkInterfaceId == "eni-8b0a1c2d"


def test_stringify_coerces_values():
    assert mod._stringify([1, "sg-2", None]) == ["1", "sg-2", "None"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_identifier_required(client):
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "network_interface_id or name is required" in exc.value.args[0]["msg"]


def test_absent_missing_interface_is_unchanged(client):
    _run_args(state="absent", name="eni-prod")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_interface(client):
    client.interfaces = [_interface()]
    _run_args(state="absent", name="eni-prod")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "deleted" in result["msg"]
    assert result["network_interface"] is None
    assert any(name == "DeleteNetworkInterface" for name, request in client.calls)
    assert client.interfaces == []
    delete_request = next(request for name, request in client.calls if name == "DeleteNetworkInterface")
    assert delete_request.NetworkInterfaceId == "eni-8b0a1c2d"


def test_present_create_missing_vpc_and_subnet_fails(client):
    _run_args(name="eni-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "is required when creating" in payload["msg"]
    assert "vpc_id" in payload["msg"]
    assert "subnet_id" in payload["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_creates_interface(client):
    _run_args(
        name="eni-prod",
        vpc_id="vpc-8b0a1c2d",
        subnet_id="subnet-8b0a1c2d",
        description="prod desc",
        security_group_ids=["sg-8b0a1c2d"],
        secondary_private_ip_count=2,
        tags={"env": "prod"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "created" in result["msg"]
    assert result["network_interface"]["NetworkInterfaceName"] == "eni-prod"
    assert len(client.interfaces) == 1
    create_request = next(request for name, request in client.calls if name == "CreateNetworkInterface")
    assert create_request.VpcId == "vpc-8b0a1c2d"
    assert create_request.SubnetId == "subnet-8b0a1c2d"
    assert create_request.NetworkInterfaceDescription == "prod desc"
    assert create_request.SecurityGroupIds == ["sg-8b0a1c2d"]
    assert create_request.SecondaryPrivateIpAddressCount == 2


def test_present_existing_is_up_to_date(client):
    client.interfaces = [_interface()]
    _run_args(network_interface_id="eni-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert result["network_interface"]["NetworkInterfaceName"] == "eni-prod"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_description(client):
    client.interfaces = [_interface(NetworkInterfaceDescription="stale")]
    _run_args(network_interface_id="eni-8b0a1c2d", description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert any(name == "ModifyNetworkInterfaceAttribute" for name, request in client.calls)
    assert client.interfaces[0]["NetworkInterfaceDescription"] == "production"
    update_request = next(request for name, request in client.calls if name == "ModifyNetworkInterfaceAttribute")
    assert update_request.NetworkInterfaceDescription == "production"


def test_present_updates_name(client):
    client.interfaces = [_interface(NetworkInterfaceName="eni-stale")]
    _run_args(network_interface_id="eni-8b0a1c2d", name="eni-prod")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert client.interfaces[0]["NetworkInterfaceName"] == "eni-prod"
    update_request = next(request for name, request in client.calls if name == "ModifyNetworkInterfaceAttribute")
    assert update_request.NetworkInterfaceName == "eni-prod"


def test_present_updates_security_groups(client):
    client.interfaces = [_interface(GroupSet=["sg-old"])]
    _run_args(network_interface_id="eni-8b0a1c2d", security_group_ids=["sg-new", "sg-8b0a1c2d"])
    result = run(mod.run_module)
    assert result["changed"] is True
    update_request = next(request for name, request in client.calls if name == "ModifyNetworkInterfaceAttribute")
    assert sorted(update_request.SecurityGroupIds) == ["sg-8b0a1c2d", "sg-new"]
    assert sorted(client.interfaces[0]["GroupSet"]) == ["sg-8b0a1c2d", "sg-new"]


def test_check_mode_create_makes_no_writes(client):
    _run_args(name="eni-prod", vpc_id="vpc-8b0a1c2d", subnet_id="subnet-8b0a1c2d", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert client.interfaces == []
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_update_makes_no_writes(client):
    client.interfaces = [_interface(NetworkInterfaceDescription="stale")]
    _run_args(network_interface_id="eni-8b0a1c2d", description="production", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert result["diff"]["before"]["NetworkInterfaceDescription"] == "stale"
    assert result["diff"]["after"]["NetworkInterfaceDescription"] == "production"
    assert client.interfaces[0]["NetworkInterfaceDescription"] == "stale"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_delete_makes_no_writes(client):
    client.interfaces = [_interface()]
    _run_args(state="absent", name="eni-prod", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete" in result["msg"]
    assert len(client.interfaces) == 1
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("vpc api exploded")

    client.DescribeNetworkInterfaces = boom
    _run_args(name="eni-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "vpc api exploded"
    assert payload["error_code"] is None
