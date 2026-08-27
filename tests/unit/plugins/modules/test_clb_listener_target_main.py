"""Main-path unit tests for the clb_listener_target module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import clb_listener_target
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BASE_ARGS = dict(load_balancer_id="lb-xxxxxxxx", listener_id="lbl-xxxxxxxx")


class FakeClbClient(object):
    def __init__(self, backends=None):
        self.backends = list(backends or [])
        self.RegisterTargets = MagicMock(side_effect=self._register)
        self.DeregisterTargets = MagicMock(side_effect=self._deregister)
        self.DescribeTaskStatus = MagicMock(
            return_value=SimpleNamespace(Status=0, Message=None, LoadBalancerIds=[]))

    @staticmethod
    def _request_key(target):
        backend = getattr(target, "InstanceId", None) or getattr(target, "EniIp", None)
        return (backend, target.Port)

    @staticmethod
    def _backend_key(backend):
        return (backend["InstanceId"] or (backend["PrivateIpAddresses"] or [None])[0],
                backend["Port"])

    def DescribeTargets(self, request):
        return SimpleNamespace(Listeners=[SimpleNamespace(
            ListenerId=request.ListenerIds[0],
            Targets=[FakeResource(b) for b in self.backends],
            Rules=[],
        )])

    def _register(self, request):
        for target in request.Targets:
            key = self._request_key(target)
            self.backends = [b for b in self.backends if self._backend_key(b) != key]
            self.backends.append({
                "InstanceId": getattr(target, "InstanceId", None),
                "PrivateIpAddresses": (
                    [target.EniIp] if getattr(target, "EniIp", None) else []),
                "Port": target.Port,
                "Weight": getattr(target, "Weight", None),
            })
        return SimpleNamespace(RequestId="req-register")

    def _deregister(self, request):
        keys = {self._request_key(t) for t in request.Targets}
        self.backends = [b for b in self.backends if self._backend_key(b) not in keys]
        return SimpleNamespace(RequestId="req-deregister")


@pytest.fixture
def client(monkeypatch):
    fake = FakeClbClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        clb_listener_target, "_load_clb",
        lambda: (FakeModels(), SimpleNamespace(ClbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def _backend(instance_id=None, eni_ip=None, port=8080, weight=10):
    return {
        "InstanceId": instance_id,
        "PrivateIpAddresses": [eni_ip] if eni_ip else [],
        "Port": port,
        "Weight": weight,
    }


def test_register_missing_target_reports_changed(client):
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 20}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    client.RegisterTargets.assert_called_once()
    client.DescribeTaskStatus.assert_called_once()
    assert result["targets"] == [{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 20}]
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.backends.append(_backend(instance_id="ins-aaaaaaaa"))
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is False
    client.RegisterTargets.assert_not_called()
    client.DeregisterTargets.assert_not_called()


def test_purge_deregisters_unlisted_targets(client):
    client.backends.append(_backend(instance_id="ins-aaaaaaaa"))
    client.backends.append(_backend(instance_id="ins-surplus1"))
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    client.RegisterTargets.assert_not_called()
    client.DeregisterTargets.assert_called_once()
    request = client.DeregisterTargets.call_args[0][0]
    assert request.Targets[0].InstanceId == "ins-surplus1"
    assert [b["InstanceId"] for b in client.backends] == ["ins-aaaaaaaa"]


def test_purge_false_keeps_unlisted_targets(client):
    client.backends.append(_backend(instance_id="ins-surplus1"))
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                purge=False, **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    client.RegisterTargets.assert_called_once()
    client.DeregisterTargets.assert_not_called()
    assert len(client.backends) == 2


def test_weight_drift_reregisters_target(client):
    client.backends.append(_backend(instance_id="ins-aaaaaaaa", weight=10))
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 50}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    client.RegisterTargets.assert_called_once()
    request = client.RegisterTargets.call_args[0][0]
    assert request.Targets[0].Weight == 50
    assert client.backends[0]["Weight"] == 50


def test_eni_target_registered_by_ip(client):
    module_args(targets=[{"eni_ip": "10.0.1.15", "port": 8080, "weight": 10}], **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    request = client.RegisterTargets.call_args[0][0]
    assert request.Targets[0].EniIp == "10.0.1.15"
    assert not hasattr(request.Targets[0], "InstanceId")


def test_absent_deregisters_listed_targets(client):
    client.backends.append(_backend(instance_id="ins-aaaaaaaa"))
    module_args(state="absent",
                targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    client.DeregisterTargets.assert_called_once()
    assert client.backends == []


def test_absent_on_unregistered_targets_is_unchanged(client):
    module_args(state="absent",
                targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is False
    client.DeregisterTargets.assert_not_called()


def test_check_mode_makes_no_sdk_writes(client):
    client.backends.append(_backend(instance_id="ins-surplus1"))
    module_args(targets=[{"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10}],
                _ansible_check_mode=True, **BASE_ARGS)
    result = run(clb_listener_target.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["diff"]["after"]["targets"] == [
        {"instance_id": "ins-aaaaaaaa", "port": 8080, "weight": 10},
    ]
    client.RegisterTargets.assert_not_called()
    client.DeregisterTargets.assert_not_called()


def test_target_without_backend_fails(client):
    module_args(targets=[{"port": 8080}], **BASE_ARGS)
    with pytest.raises(SystemExit) as excinfo:
        run(clb_listener_target.run_module)
    payload = excinfo.value.args[0]
    assert payload["failed"] is True
    assert "instance_id" in payload["msg"]
    client.RegisterTargets.assert_not_called()
