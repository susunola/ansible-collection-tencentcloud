"""Unit tests for the cvm_chc write module (``run_module`` flows).

``test_cvm_chc.py`` covers the request builders against a recording client.
This file drives ``run_module`` itself, because the ``idempotent`` attribute
is a claim about what a second run does, and only running it twice can check
that.

CHC servers are physically delivered, so the module never creates one: the
present path converges an existing host and fails when the host is missing.
That makes the converge paths the whole of the surface worth testing twice.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_chc as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


class FakeRequest(object):
    pass


class FakeFilter(object):
    def __init__(self):
        self.Name = None
        self.Values = None


class FakeNetwork(object):
    def __init__(self, vpc_id=None, subnet_id=None):
        self.VpcId = vpc_id
        self.SubnetId = subnet_id


class ChcModels(FakeModels):
    DescribeChcHostsRequest = FakeRequest
    ModifyChcAttributeRequest = FakeRequest
    ModifyChcNetworkModeRequest = FakeRequest
    ConfigureChcAssistVpcRequest = FakeRequest
    RemoveChcAssistVpcRequest = FakeRequest
    RemoveChcDeployVpcRequest = FakeRequest
    Filter = FakeFilter
    VirtualPrivateCloud = FakeNetwork


class FakeHost(object):
    def __init__(self, chc_id, name, network_mode=None):
        self.ChcId = chc_id
        self.InstanceName = name
        self.BmcVirtualPrivateCloud = None
        self.DeployVirtualPrivateCloud = None
        self.BmcSecurityGroupIds = None
        self.DeploySecurityGroupIds = None
        self.NetworkMode = network_mode

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


class FakeChcStore(object):
    """The CHC host store, used as the SDK client."""

    _WRITES = ("ModifyChcAttribute", "ModifyChcNetworkMode", "ConfigureChcAssistVpc",
               "RemoveChcAssistVpc", "RemoveChcDeployVpc")

    def __init__(self, hosts=()):
        self.hosts = list(hosts)
        self.calls = []

    def DescribeChcHosts(self, request):
        self.calls.append("DescribeChcHosts")
        wanted = set(getattr(request, "ChcIds", None) or [])
        if wanted:
            return FakeResponse([h for h in self.hosts if h.ChcId in wanted])
        return FakeResponse(list(self.hosts))

    def ModifyChcAttribute(self, request):
        self.calls.append("ModifyChcAttribute")
        for host in self.hosts:
            if host.ChcId in (request.ChcIds or []):
                host.InstanceName = request.InstanceName

    def ModifyChcNetworkMode(self, request):
        self.calls.append("ModifyChcNetworkMode")
        for host in self.hosts:
            if host.ChcId in (request.ChcIds or []):
                host.NetworkMode = request.NetworkMode

    def ConfigureChcAssistVpc(self, request):
        self.calls.append("ConfigureChcAssistVpc")

    def RemoveChcAssistVpc(self, request):
        self.calls.append("RemoveChcAssistVpc")
        for host in self.hosts:
            if host.ChcId in (request.ChcIds or []):
                host.BmcVirtualPrivateCloud = None
                host.BmcSecurityGroupIds = None

    def RemoveChcDeployVpc(self, request):
        self.calls.append("RemoveChcDeployVpc")
        for host in self.hosts:
            if host.ChcId in (request.ChcIds or []):
                host.DeployVirtualPrivateCloud = None
                host.DeploySecurityGroupIds = None

    @property
    def writes(self):
        return [c for c in self.calls if c in self._WRITES]


def _make_module(monkeypatch, store):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cvm",
                        lambda: (ChcModels(), SimpleNamespace(CvmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: store)
    return store


def _args(**extra):
    base = {"chc_id": "chc-1", "name": "host"}
    base.update(extra)
    module_args(**base)


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_present_twice_is_a_no_op(monkeypatch):
    """The claim the attribute makes, checked by running the module twice."""
    store = FakeChcStore([FakeHost("chc-1", "host")])
    _make_module(monkeypatch, store)

    _args()
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "CHC server is up to date"

    _args()
    second = run(mod.run_module)
    assert second["changed"] is False
    assert second["msg"] == "CHC server is up to date"
    assert store.writes == []


def test_rename_then_second_run_converges(monkeypatch):
    store = FakeChcStore([FakeHost("chc-1", "old-name")])
    _make_module(monkeypatch, store)

    _args(name="host")
    first = run(mod.run_module)
    assert first["changed"] is True
    assert first["msg"] == "CHC server renamed"
    assert store.writes == ["ModifyChcAttribute"]

    store.calls = []
    _args(name="host")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_network_mode_switch_converges_once(monkeypatch):
    store = FakeChcStore([FakeHost("chc-1", "host", network_mode="DEPLOY")])
    _make_module(monkeypatch, store)

    _args(network_mode="BUSINESS")
    first = run(mod.run_module)
    assert first["changed"] is True
    assert first["msg"] == "CHC network mode switched"

    store.calls = []
    _args(network_mode="BUSINESS")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_absent_without_network_config_is_a_no_op(monkeypatch):
    store = FakeChcStore([FakeHost("chc-1", "host")])
    _make_module(monkeypatch, store)

    _args(state="absent")
    first = run(mod.run_module)
    assert first["changed"] is False
    assert first["msg"] == "CHC server has no network configuration"

    _args(state="absent")
    second = run(mod.run_module)
    assert second["changed"] is False
    assert store.writes == []


def test_missing_host_fails_rather_than_creating(monkeypatch):
    """CHC servers are physically delivered; the module must not pretend to create one."""
    store = FakeChcStore([])
    _make_module(monkeypatch, store)

    _args()
    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)
    assert "physically delivered" in failure.value.args[0]["msg"]
    assert store.writes == []


def test_check_mode_does_not_write(monkeypatch):
    store = FakeChcStore([FakeHost("chc-1", "host", network_mode="DEPLOY")])
    _make_module(monkeypatch, store)

    _args(network_mode="BUSINESS", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would switch" in result["msg"]
    assert store.writes == []
