"""Unit tests for the api_gateway_service_release write module (run_module flows).

Drives ``run_module()`` against an in-memory fake API Gateway client whose
release / unrelease operations mutate a service-environment release store so
post-write describes converge immediately.

A release is "present" only when the environment carries ``Status == 1``, so
unreleasing flips the status and reads back as absent.

Scenario matrix:

* absent on an already-unreleased environment (idempotent no-op)
* absent with a live release (check-mode dry run, real unrelease)
* releasing an unreleased environment (happy path with describe read-back,
  check mode)
* present when the environment is already released (idempotent no-op)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_service_release as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RELEASE = {
    "ServiceId": "service-abc",
    "EnvironmentName": "release",
    "Status": 1,
    "ReleaseDesc": "Managed by Ansible",
    "ReleaseVersion": "20260901-abc",
}


def _release(**overrides):
    item = copy.deepcopy(RELEASE)
    item.update(overrides)
    return item


def _env_args(**overrides):
    params = {"service_id": "service-abc", "environment": "release"}
    params.update(overrides)
    return module_args(**params)


class FakeApigatewayClient(object):
    """In-memory API Gateway client mutating a service release store."""

    def __init__(self, releases=None):
        self.releases = [copy.deepcopy(t) for t in (releases or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeServiceEnvironmentList(self, request):
        self._record("DescribeServiceEnvironmentList", request)
        return SimpleNamespace(
            Result=SimpleNamespace(
                EnvironmentList=[FakeResource(t) for t in self.releases if t.get("ServiceId") == getattr(request, "ServiceId", None)]
            )
        )

    def ReleaseService(self, request):
        self._record("ReleaseService", request)
        self.releases = [
            t for t in self.releases
            if not (t.get("ServiceId") == getattr(request, "ServiceId", None)
                    and t.get("EnvironmentName") == getattr(request, "EnvironmentName", None))
        ]
        self.releases.append({
            "ServiceId": getattr(request, "ServiceId", None),
            "EnvironmentName": getattr(request, "EnvironmentName", None),
            "Status": 1,
            "ReleaseDesc": getattr(request, "ReleaseDesc", None),
            "ReleaseVersion": "20260901-xyz",
        })
        return SimpleNamespace(RequestId="req-fake")

    def UnReleaseService(self, request):
        self._record("UnReleaseService", request)
        for item in self.releases:
            if item.get("ServiceId") == getattr(request, "ServiceId", None) and item.get("EnvironmentName") == getattr(request, "EnvironmentName", None):
                item["Status"] = 0
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_release_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(releases=[])
    _make_module(monkeypatch, fake)
    _env_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"] is None
    assert _names(fake) == ["DescribeServiceEnvironmentList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _env_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["EnvironmentName"] == "release"
    assert fake.releases[0]["Status"] == 1
    assert "UnReleaseService" not in _names(fake)


def test_absent_unreleases_environment(monkeypatch):
    fake = FakeApigatewayClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _env_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"] is None
    assert fake.releases[0]["Status"] == 0
    assert "UnReleaseService" in _names(fake)


# ---------------------------------------------------------------------------
# release (present) flows
# ---------------------------------------------------------------------------


def test_release_when_not_released(monkeypatch):
    fake = FakeApigatewayClient(releases=[_release(Status=0)])
    _make_module(monkeypatch, fake)
    _env_args(state="present", description="production cutover")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["EnvironmentName"] == "release"
    assert result["release"]["Status"] == 1
    ops = _names(fake)
    assert ops[0] == "DescribeServiceEnvironmentList"
    assert "ReleaseService" in ops
    assert ops[-1] == "DescribeServiceEnvironmentList"


def test_release_missing_environment(monkeypatch):
    fake = FakeApigatewayClient(releases=[])
    _make_module(monkeypatch, fake)
    _env_args(state="present", environment="test")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["EnvironmentName"] == "test"
    assert len(fake.releases) == 1


def test_release_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(releases=[])
    _make_module(monkeypatch, fake)
    _env_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.releases == []
    assert "ReleaseService" not in _names(fake)


def test_present_already_released_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _env_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"]["Status"] == 1
    assert "ReleaseService" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeServiceEnvironmentList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _env_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
