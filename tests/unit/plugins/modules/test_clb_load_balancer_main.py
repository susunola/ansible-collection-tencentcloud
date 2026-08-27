"""Main-path unit tests for the clb_load_balancer module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_load_balancer
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LOAD_BALANCER = {
    "LoadBalancerId": "lb-existing1",
    "LoadBalancerName": "web-lb",
    "LoadBalancerType": "OPEN",
    "VpcId": "vpc-existing1",
    "SubnetId": None,
    "Status": 1,
    "Tags": [],
    "NetworkAttributes": {
        "InternetChargeType": "TRAFFIC_POSTPAID_BY_HOUR",
        "InternetMaxBandwidthOut": 10,
    },
}

CREATE_ARGS = dict(
    state="present",
    name="web-lb",
    load_balancer_type="OPEN",
    vpc_id="vpc-existing1",
)


class FakeClbClient(object):
    def __init__(self, load_balancers=None):
        self.load_balancers = list(load_balancers or [])
        self.CreateLoadBalancer = MagicMock(side_effect=self._create)
        self.DeleteLoadBalancer = MagicMock(side_effect=self._delete)
        self.ModifyLoadBalancerAttributes = MagicMock(side_effect=self._modify)
        self.DescribeTaskStatus = MagicMock(
            return_value=SimpleNamespace(Status=0, Message=None, LoadBalancerIds=[]))

    def DescribeLoadBalancers(self, request):
        matched = self.load_balancers
        ids = getattr(request, "LoadBalancerIds", None)
        if ids:
            matched = [lb for lb in matched if lb["LoadBalancerId"] in ids]
        else:
            name = getattr(request, "LoadBalancerName", None)
            vpc_id = getattr(request, "VpcId", None)
            if name:
                # The API matches names fuzzily, like the real service.
                matched = [lb for lb in matched if name in lb["LoadBalancerName"]]
            if vpc_id:
                matched = [lb for lb in matched if lb["VpcId"] == vpc_id]
        return SimpleNamespace(LoadBalancerSet=[FakeResource(lb) for lb in matched])

    def _create(self, request):
        lb = {
            "LoadBalancerId": "lb-new000001",
            "LoadBalancerName": request.LoadBalancerName,
            "LoadBalancerType": getattr(request, "LoadBalancerType", "OPEN"),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "Status": 1,
            "Tags": [
                {"TagKey": tag.TagKey, "TagValue": tag.TagValue}
                for tag in (getattr(request, "Tags", None) or [])
            ],
            "NetworkAttributes": {},
        }
        self.load_balancers.append(lb)
        return SimpleNamespace(LoadBalancerIds=[lb["LoadBalancerId"]], RequestId="req-create")

    def _delete(self, request):
        self.load_balancers = [
            lb for lb in self.load_balancers
            if lb["LoadBalancerId"] not in request.LoadBalancerIds
        ]
        return SimpleNamespace(RequestId="req-delete")

    def _modify(self, request):
        for lb in self.load_balancers:
            if lb["LoadBalancerId"] != request.LoadBalancerId:
                continue
            if getattr(request, "LoadBalancerName", None):
                lb["LoadBalancerName"] = request.LoadBalancerName
            charge_info = getattr(request, "InternetChargeInfo", None)
            if charge_info is not None:
                lb["NetworkAttributes"] = {
                    "InternetChargeType": getattr(charge_info, "InternetChargeType", None),
                    "InternetMaxBandwidthOut": getattr(charge_info, "InternetMaxBandwidthOut", None),
                }
        return SimpleNamespace(RequestId="req-modify")


class FakeTagClient(object):
    def __init__(self, load_balancer):
        self.load_balancer = load_balancer
        self.AttachResourcesTag = MagicMock(side_effect=self._attach)
        self.DetachResourcesTag = MagicMock(side_effect=self._detach)

    def _attach(self, request):
        tags = self.load_balancer["Tags"]
        tags[:] = [t for t in tags if t["TagKey"] != request.TagKey]
        tags.append({"TagKey": request.TagKey, "TagValue": request.TagValue})

    def _detach(self, request):
        tags = self.load_balancer["Tags"]
        tags[:] = [t for t in tags if t["TagKey"] != request.TagKey]


@pytest.fixture
def client(monkeypatch):
    fake = FakeClbClient()
    clients = {"clb.tencentcloudapi.com": fake}
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        clb_load_balancer, "_load_clb",
        lambda: (FakeModels(), SimpleNamespace(ClbClient=object)),
    )
    monkeypatch.setattr(
        clb_load_balancer, "_load_tag",
        lambda: (FakeModels(), SimpleNamespace(TagClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: clients.setdefault(
            endpoint, FakeTagClient(fake.load_balancers[-1] if fake.load_balancers else {})),
    )
    return fake


def test_create_reports_changed(client):
    module_args(**CREATE_ARGS)
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["LoadBalancerId"] == "lb-new000001"
    assert result["load_balancer"]["LoadBalancerName"] == "web-lb"
    client.CreateLoadBalancer.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.load_balancers.append(dict(LOAD_BALANCER))
    module_args(**CREATE_ARGS)
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is False
    assert result["load_balancer"]["LoadBalancerId"] == "lb-existing1"
    client.CreateLoadBalancer.assert_not_called()
    client.ModifyLoadBalancerAttributes.assert_not_called()


def test_absent_deletes_existing_load_balancer(client):
    client.load_balancers.append(dict(LOAD_BALANCER))
    module_args(state="absent", name="web-lb")
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    client.DeleteLoadBalancer.assert_called_once()
    assert client.load_balancers == []


def test_absent_on_missing_load_balancer_is_unchanged(client):
    module_args(state="absent", name="web-lb")
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is False
    client.DeleteLoadBalancer.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(_ansible_check_mode=True, **CREATE_ARGS)
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateLoadBalancer.assert_not_called()
    client.DeleteLoadBalancer.assert_not_called()
    client.ModifyLoadBalancerAttributes.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(_ansible_diff=True, **CREATE_ARGS)
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["LoadBalancerName"] == "web-lb"
    client.CreateLoadBalancer.assert_called_once()


def test_rename_updates_attributes(client):
    client.load_balancers.append(dict(LOAD_BALANCER))
    module_args(state="present", load_balancer_id="lb-existing1", name="renamed-lb")
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert client.load_balancers[0]["LoadBalancerName"] == "renamed-lb"
    client.ModifyLoadBalancerAttributes.assert_called_once()
    client.DescribeTaskStatus.assert_called_once()


def test_internet_charge_change_updates_attributes(client):
    client.load_balancers.append(dict(LOAD_BALANCER))
    module_args(
        state="present", load_balancer_id="lb-existing1", name="web-lb",
        internet_max_bandwidth_out=50,
    )
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert client.load_balancers[0]["NetworkAttributes"]["InternetMaxBandwidthOut"] == 50
    client.ModifyLoadBalancerAttributes.assert_called_once()


def test_immutable_drift_fails(client):
    client.load_balancers.append(dict(LOAD_BALANCER))
    module_args(
        state="present", load_balancer_id="lb-existing1", name="web-lb",
        load_balancer_type="INTERNAL",
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(clb_load_balancer.run_module)
    payload = excinfo.value.args[0]
    assert "load_balancer_type" in payload["msg"]
    client.CreateLoadBalancer.assert_not_called()


def test_tags_are_reconciled(client):
    lb = dict(LOAD_BALANCER)
    lb["Tags"] = [{"TagKey": "legacy", "TagValue": "x"}]
    client.load_balancers.append(lb)
    module_args(state="present", load_balancer_id="lb-existing1", name="web-lb",
                tags={"env": "prod"})
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert client.load_balancers[0]["Tags"] == [{"TagKey": "env", "TagValue": "prod"}]
    client.ModifyLoadBalancerAttributes.assert_not_called()


def test_create_waits_for_running_state(client, monkeypatch):
    """The waiter polls DescribeLoadBalancers until Status becomes 1."""
    original_create = client._create

    def create_pending(request):
        response = original_create(request)
        client.load_balancers[-1]["Status"] = 0
        return response

    client.CreateLoadBalancer = MagicMock(side_effect=create_pending)

    def flip_status(self, request):
        for lb in self.load_balancers:
            lb["Status"] = 1
        return SimpleNamespace(LoadBalancerSet=[FakeResource(lb) for lb in self.load_balancers])

    monkeypatch.setattr(FakeClbClient, "DescribeLoadBalancers", flip_status)
    module_args(**CREATE_ARGS)
    result = run(clb_load_balancer.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["Status"] == 1
