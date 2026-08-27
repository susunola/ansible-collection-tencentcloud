"""Unit tests for the clb_listener_target write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules.clb_listener_target import (
    _matches,
    build_describe_request,
    build_targets,
    find_targets,
    normalize_desired_target,
    reconcile_targets,
)


class FakeTarget(object):
    """Mimics the SDK Target model: zero-arg constructor, attribute assignment."""

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Target = FakeTarget
    DescribeTargetsRequest = FakeRequest
    RegisterTargetsRequest = FakeRequest
    DeregisterTargetsRequest = FakeRequest


class FakeBackend(object):
    def __init__(self, instance_id=None, private_ips=None, port=80, weight=10):
        self.InstanceId = instance_id
        self.PrivateIpAddresses = private_ips or []
        self.Port = port
        self.Weight = weight

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "PrivateIpAddresses": list(self.PrivateIpAddresses),
            "Port": self.Port,
            "Weight": self.Weight,
        }


class FakeRule(object):
    def __init__(self, location_id, targets):
        self.LocationId = location_id
        self.Targets = targets


class FakeListenerBackend(object):
    def __init__(self, listener_id, targets, rules=None):
        self.ListenerId = listener_id
        self.Targets = targets
        self.Rules = rules or []


class FakeResponse(object):
    def __init__(self, listeners):
        self.Listeners = listeners


class FakeClient(object):
    def __init__(self, response):
        self.response = response
        self.calls = []

    def DescribeTargets(self, request):
        self.calls.append(request)
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request():
    request = build_describe_request(FakeModels, "lb-1", "lbl-1")
    assert request.LoadBalancerId == "lb-1"
    assert request.ListenerIds == ["lbl-1"]


def test_find_targets_layer4():
    client = FakeClient(FakeResponse([
        FakeListenerBackend("lbl-other", [FakeBackend(instance_id="ins-x", port=80)]),
        FakeListenerBackend("lbl-1", [FakeBackend(instance_id="ins-a", port=8080)]),
    ]))
    module = FakeModule()
    targets = find_targets(module, client, FakeModels, "lb-1", "lbl-1", None)
    assert targets == [{
        "instance_id": "ins-a", "private_ips": [], "port": 8080, "weight": 10,
    }]


def test_find_targets_by_location_id():
    client = FakeClient(FakeResponse([
        FakeListenerBackend("lbl-1", [], rules=[
            FakeRule("loc-1", [FakeBackend(instance_id="ins-a", port=443)]),
            FakeRule("loc-2", [FakeBackend(instance_id="ins-b", port=443)]),
        ]),
    ]))
    module = FakeModule()
    targets = find_targets(module, client, FakeModels, "lb-1", "lbl-1", "loc-2")
    assert [t["instance_id"] for t in targets] == ["ins-b"]


def test_find_targets_unknown_listener_returns_empty():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_targets(module, client, FakeModels, "lb-1", "lbl-1", None) == []


def test_normalize_desired_target_requires_exactly_one_backend():
    with pytest.raises(ValueError):
        normalize_desired_target({"port": 80})
    with pytest.raises(ValueError):
        normalize_desired_target({"instance_id": "ins-a", "eni_ip": "10.0.0.1", "port": 80})
    target = normalize_desired_target({"eni_ip": "10.0.0.1", "port": 80})
    assert target == {"instance_id": None, "eni_ip": "10.0.0.1", "port": 80, "weight": 10}


def test_matches_by_instance_id():
    desired = {"instance_id": "ins-a", "eni_ip": None, "port": 80, "weight": 10}
    assert _matches(desired, {"instance_id": "ins-a", "private_ips": [], "port": 80})
    assert not _matches(desired, {"instance_id": "ins-a", "private_ips": [], "port": 81})
    assert not _matches(desired, {"instance_id": "ins-b", "private_ips": [], "port": 80})


def test_matches_by_eni_ip():
    desired = {"instance_id": None, "eni_ip": "10.0.0.1", "port": 80, "weight": 10}
    assert _matches(desired, {"instance_id": None, "private_ips": ["10.0.0.1"], "port": 80})
    assert not _matches(desired, {"instance_id": None, "private_ips": ["10.0.0.2"], "port": 80})


def test_reconcile_registers_missing_and_deregisters_surplus():
    desired = [
        {"instance_id": "ins-a", "eni_ip": None, "port": 80, "weight": 10},
        {"instance_id": "ins-b", "eni_ip": None, "port": 80, "weight": 10},
    ]
    current = [
        {"instance_id": "ins-a", "private_ips": [], "port": 80, "weight": 10},
        {"instance_id": "ins-c", "private_ips": [], "port": 80, "weight": 10},
    ]
    to_register, to_deregister = reconcile_targets(desired, current, purge=True)
    assert [t["instance_id"] for t in to_register] == ["ins-b"]
    assert [t["instance_id"] for t in to_deregister] == ["ins-c"]


def test_reconcile_purge_false_never_deregisters():
    desired = []
    current = [{"instance_id": "ins-a", "private_ips": [], "port": 80, "weight": 10}]
    to_register, to_deregister = reconcile_targets(desired, current, purge=False)
    assert to_register == []
    assert to_deregister == []


def test_reconcile_reregisters_on_weight_drift():
    desired = [{"instance_id": "ins-a", "eni_ip": None, "port": 80, "weight": 50}]
    current = [{"instance_id": "ins-a", "private_ips": [], "port": 80, "weight": 10}]
    to_register, to_deregister = reconcile_targets(desired, current, purge=True)
    assert [t["weight"] for t in to_register] == [50]
    assert to_deregister == []


def test_reconcile_idempotent_when_matching():
    desired = [{"instance_id": "ins-a", "eni_ip": None, "port": 80, "weight": 10}]
    current = [{"instance_id": "ins-a", "private_ips": [], "port": 80, "weight": 10}]
    to_register, to_deregister = reconcile_targets(desired, current, purge=True)
    assert to_register == []
    assert to_deregister == []


def test_build_targets_by_instance_id():
    targets = build_targets(FakeModels, [
        {"instance_id": "ins-a", "eni_ip": None, "port": 8080, "weight": 20},
    ])
    assert targets[0].InstanceId == "ins-a"
    assert targets[0].Port == 8080
    assert targets[0].Weight == 20
    assert not hasattr(targets[0], "EniIp")


def test_build_targets_by_eni_ip():
    targets = build_targets(FakeModels, [
        {"instance_id": None, "eni_ip": "10.0.0.1", "port": 8080, "weight": 10},
    ])
    assert targets[0].EniIp == "10.0.0.1"
    assert not hasattr(targets[0], "InstanceId")


def test_build_targets_deregister_falls_back_to_reported_private_ip():
    """Purged ENI targets are deregistered by their reported private IP."""
    targets = build_targets(FakeModels, [
        {"instance_id": None, "private_ips": ["10.0.0.9"], "port": 80, "weight": 10},
    ])
    assert targets[0].EniIp == "10.0.0.9"
