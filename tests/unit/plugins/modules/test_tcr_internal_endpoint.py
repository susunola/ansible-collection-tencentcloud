"""Read-based lifecycle tests for TCR private VPC access links."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_internal_endpoint as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class FakeTcrClient(object):
    def __init__(self, links=None):
        self.links = list(links or [])
        self.calls = []

    def DescribeInternalEndpoints(self, request):
        self.calls.append(("DescribeInternalEndpoints", request))
        return SimpleNamespace(AccessVpcSet=[FakeResource(item) for item in self.links],
                               TotalCount=len(self.links))

    def ManageInternalEndpoint(self, request):
        self.calls.append(("ManageInternalEndpoint", request))
        if request.Operation == "Create":
            self.links.append({"VpcId": request.VpcId, "SubnetId": request.SubnetId,
                               "Status": "Creating", "AccessIp": "10.0.0.2"})
        else:
            self.links = [item for item in self.links
                          if not (item["VpcId"] == request.VpcId and item["SubnetId"] == request.SubnetId)]
        return SimpleNamespace(RegistryId=request.RegistryId)


def setup(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tcr", lambda: (FakeModels(), SimpleNamespace(TcrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


def args(**overrides):
    values = {"registry_id": "tcr-abc", "vpc_id": "vpc-abc", "subnet_id": "subnet-abc",
              "waiter_timeout": 0, "waiter_delay": 0}
    values.update(overrides)
    return module_args(**values)


def test_create_and_refetch(monkeypatch):
    fake = FakeTcrClient()
    setup(monkeypatch, fake)
    args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["VpcId"] == "vpc-abc"
    write = [request for name, request in fake.calls if name == "ManageInternalEndpoint"][0]
    assert (write.Operation, write.VpcId, write.SubnetId) == ("Create", "vpc-abc", "subnet-abc")


def test_existing_link_is_noop(monkeypatch):
    fake = FakeTcrClient([{"VpcId": "vpc-abc", "SubnetId": "subnet-abc"}])
    setup(monkeypatch, fake)
    args()
    assert run(mod.run_module)["changed"] is False
    assert all(name != "ManageInternalEndpoint" for name, unused in fake.calls)


def test_different_subnet_conflicts_without_write(monkeypatch):
    fake = FakeTcrClient([{"VpcId": "vpc-abc", "SubnetId": "subnet-other"}])
    setup(monkeypatch, fake)
    args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "another subnet" in exc.value.args[0]["msg"]
    assert all(name != "ManageInternalEndpoint" for name, unused in fake.calls)


def test_delete_exact_link(monkeypatch):
    fake = FakeTcrClient([{"VpcId": "vpc-abc", "SubnetId": "subnet-abc"}])
    setup(monkeypatch, fake)
    args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"] is None
    assert fake.links == []


def test_check_mode_does_not_write(monkeypatch):
    fake = FakeTcrClient()
    setup(monkeypatch, fake)
    args(_ansible_check_mode=True)
    assert run(mod.run_module)["changed"] is True
    assert fake.links == []


def test_incomplete_read_fails_closed(monkeypatch):
    fake = FakeTcrClient()
    fake.DescribeInternalEndpoints = lambda request: SimpleNamespace(AccessVpcSet=[], TotalCount=1)
    setup(monkeypatch, fake)
    args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)
