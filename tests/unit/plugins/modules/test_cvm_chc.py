"""Unit tests for the cvm_chc write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import pytest
from ansible_collections.susunola.tencentcloud.plugins.modules.cvm_chc import (
    _configure_vpc,
    _remove_assist,
    _remove_deploy,
    _rename,
    _set_network_mode,
    build_describe_request,
    find_host,
    run_module,
)


class FakeFilter(object):
    """Mimics the Tencent SDK Filter model: zero-arg constructor."""

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeNetwork(object):
    def __init__(self):
        self.VpcId = None
        self.SubnetId = None


class FakeModels(object):
    Filter = FakeFilter
    DescribeChcHostsRequest = FakeRequest
    ConfigureChcAssistVpcRequest = FakeRequest
    ModifyChcAttributeRequest = FakeRequest
    RemoveChcAssistVpcRequest = FakeRequest
    RemoveChcDeployVpcRequest = FakeRequest
    ModifyChcNetworkModeRequest = FakeRequest
    VirtualPrivateCloud = FakeNetwork


class FakeHost(object):
    def __init__(self, chc_id, name, bmc_vpc=None, deploy_vpc=None):
        self.ChcId = chc_id
        self.InstanceName = name
        self.BmcVirtualPrivateCloud = bmc_vpc
        self.DeployVirtualPrivateCloud = deploy_vpc
        self.BmcSecurityGroupIds = None
        self.DeploySecurityGroupIds = None
        self.NetworkMode = None

    def _serialize(self, allow_none=True):
        return {
            "ChcId": self.ChcId,
            "InstanceName": self.InstanceName,
            "BmcVirtualPrivateCloud": self.BmcVirtualPrivateCloud,
            "DeployVirtualPrivateCloud": self.DeployVirtualPrivateCloud,
            "BmcSecurityGroupIds": self.BmcSecurityGroupIds,
            "DeploySecurityGroupIds": self.DeploySecurityGroupIds,
            "NetworkMode": self.NetworkMode,
        }


class FakeResponse(object):
    def __init__(self, hosts):
        self.ChcHostSet = hosts


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeChcHosts(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ConfigureChcAssistVpc(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyChcAttribute(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def RemoveChcAssistVpc(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def RemoveChcDeployVpc(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyChcNetworkMode(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self, params=None, check_mode=False, supports_check_mode=None, argument_spec=None):
        if params is None:
            params = {}
            for key, spec in (argument_spec or {}).items():
                if "default" in spec:
                    params[key] = spec["default"]
        self.params = params
        self.check_mode = check_mode
        self.result = {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AssertionError("unexpected fail_json: %s" % (kwargs,))

    def exit_json(self, **kwargs):
        self.result = kwargs
        raise SystemExit(0)

    def require_sdk(self):
        pass

    def create_client(self, client_cls, endpoint):
        return FakeClient(FakeResponse([]))


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "chc-123", None)
    assert request.ChcIds == ["chc-123"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "chc-prod-01")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["chc-prod-01"]
    assert not hasattr(request, "ChcIds") or request.ChcIds is None


def test_find_host_returns_first_match():
    client = FakeClient(FakeResponse([FakeHost("chc-1", "chc-prod-01")]))
    module = FakeModule()
    host = find_host(module, client, FakeModels, None, "chc-prod-01")
    assert host["ChcId"] == "chc-1"
    assert len(client.calls) == 1


def test_find_host_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_host(module, client, FakeModels, "chc-9", None) is None


def test_find_host_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_host(module, client, FakeModels, "chc-9", None) is None


def test_configure_vpc_sends_bmc_and_deploy():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _configure_vpc(module, client, FakeModels, "chc-1", {
        "bmc_vpc_id": "vpc-a",
        "bmc_subnet_id": "subnet-a",
        "bmc_security_group_ids": ["sg-1"],
        "deploy_vpc_id": "vpc-b",
        "deploy_subnet_id": "subnet-b",
        "deploy_security_group_ids": ["sg-2"],
    })
    request = client.calls[-1]
    assert request.ChcIds == ["chc-1"]
    assert request.BmcVirtualPrivateCloud.VpcId == "vpc-a"
    assert request.BmcVirtualPrivateCloud.SubnetId == "subnet-a"
    assert request.BmcSecurityGroupIds == ["sg-1"]
    assert request.DeployVirtualPrivateCloud.VpcId == "vpc-b"
    assert request.DeployVirtualPrivateCloud.SubnetId == "subnet-b"
    assert request.DeploySecurityGroupIds == ["sg-2"]


def test_configure_vpc_omits_unset_networks():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _configure_vpc(module, client, FakeModels, "chc-1", {
        "bmc_vpc_id": "vpc-a",
        "bmc_subnet_id": "subnet-a",
        "bmc_security_group_ids": None,
        "deploy_vpc_id": None,
        "deploy_subnet_id": None,
        "deploy_security_group_ids": None,
    })
    request = client.calls[-1]
    assert request.BmcVirtualPrivateCloud.VpcId == "vpc-a"
    assert not hasattr(request, "BmcSecurityGroupIds")
    assert not hasattr(request, "DeployVirtualPrivateCloud")
    assert not hasattr(request, "DeploySecurityGroupIds")


def test_configure_vpc_with_only_subnet_builds_network():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _configure_vpc(module, client, FakeModels, "chc-1", {
        "bmc_vpc_id": None,
        "bmc_subnet_id": None,
        "bmc_security_group_ids": None,
        "deploy_vpc_id": None,
        "deploy_subnet_id": "subnet-b",
        "deploy_security_group_ids": None,
    })
    request = client.calls[-1]
    assert request.DeployVirtualPrivateCloud.VpcId is None
    assert request.DeployVirtualPrivateCloud.SubnetId == "subnet-b"


def test_rename_sends_chc_ids_and_name():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _rename(module, client, FakeModels, "chc-1", "chc-prod-02")
    request = client.calls[-1]
    assert request.ChcIds == ["chc-1"]
    assert request.InstanceName == "chc-prod-02"


def test_remove_assist_sends_chc_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _remove_assist(module, client, FakeModels, "chc-1")
    assert client.calls[-1].ChcIds == ["chc-1"]


def test_remove_deploy_sends_chc_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _remove_deploy(module, client, FakeModels, "chc-1")
    assert client.calls[-1].ChcIds == ["chc-1"]


def test_set_network_mode_sends_chc_ids_and_mode():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _set_network_mode(module, client, FakeModels, "chc-1", "BUSINESS")
    request = client.calls[-1]
    assert request.ChcIds == ["chc-1"]
    assert request.NetworkMode == "BUSINESS"


class _FakeCvmClientModule(object):
    CvmClient = object


def _run_with_host(monkeypatch, params, host, check_mode=False):
    """Drive run_module with the given host as the described CHC server."""
    import ansible_collections.susunola.tencentcloud.plugins.modules.cvm_chc as mod

    params.setdefault("state", "present")
    params.setdefault("chc_id", "chc-1")
    params.setdefault("name", None)
    params.setdefault("bmc_vpc_id", None)
    params.setdefault("bmc_subnet_id", None)
    params.setdefault("bmc_security_group_ids", None)
    params.setdefault("deploy_vpc_id", None)
    params.setdefault("deploy_subnet_id", None)
    params.setdefault("deploy_security_group_ids", None)
    params.setdefault("network_mode", None)
    client = FakeClient(FakeResponse([host]))
    module = FakeModule(params=params, check_mode=check_mode)
    monkeypatch.setattr(mod, "TencentCloudModule", lambda argument_spec=None, supports_check_mode=None: module)
    monkeypatch.setattr(mod, "_load_cvm", lambda: (FakeModels, _FakeCvmClientModule))
    monkeypatch.setattr(module, "create_client", lambda cls, ep: client)
    with pytest.raises(SystemExit):
        run_module()
    return client


def test_run_module_switches_network_mode_when_drifted(monkeypatch):
    host = FakeHost("chc-1", "chc-prod-01")
    host.NetworkMode = "DEPLOY"
    client = _run_with_host(monkeypatch, {"network_mode": "BUSINESS"}, host)
    mode_calls = [c for c in client.calls if hasattr(c, "NetworkMode")]
    assert len(mode_calls) == 1
    assert mode_calls[0].NetworkMode == "BUSINESS"


def test_run_module_keeps_network_mode_when_matching(monkeypatch):
    host = FakeHost("chc-1", "chc-prod-01")
    host.NetworkMode = "BUSINESS"
    client = _run_with_host(monkeypatch, {"network_mode": "BUSINESS"}, host)
    assert not any(hasattr(c, "NetworkMode") for c in client.calls)


def test_run_module_check_mode_network_mode(monkeypatch):
    host = FakeHost("chc-1", "chc-prod-01")
    host.NetworkMode = "DEPLOY"
    client = _run_with_host(monkeypatch, {"network_mode": "BUSINESS"}, host, check_mode=True)
    assert not any(hasattr(c, "NetworkMode") for c in client.calls)
