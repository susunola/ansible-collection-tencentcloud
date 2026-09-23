"""Unit tests for the tem_application_deployment write module.

``tem_application_deployment`` declaratively deploys a named TEM version
and skips redeploying when the active application already carries the
requested configuration. Real deploys run an async ``wait_for_task`` poll
that the fake converges on immediately.

Scenario matrix:

* no-drift (active version + configuration match) idempotence
* version-name drift and configuration drift trigger deploys
* force_redeploy bypasses the match shortcut
* wait=False returns the immediate describe snapshot
* check-mode dry run
* configuration must not override deployment identity fields
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tem_application_deployment as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

APP_ID = "app-abc123"
ENV_ID = "en-abc123"
VERSION = "v2026.08.30"

CONFIG = {
    "InitPodNum": 2,
    "CpuSpec": 1,
    "MemorySpec": 2,
    "DeployMode": "IMAGE",
    "ImgRepo": "ccr.ccs.tencentyun.com/example/order:v2026.08.30",
    "SecurityGroupIds": ["sg-abc123"],
}

DEPLOYMENT = {
    "DeployVersion": VERSION,
    "VersionId": "ver-1001",
    "UnderDeploying": False,
}
DEPLOYMENT.update(copy.deepcopy(CONFIG))


def _deployment(**overrides):
    item = copy.deepcopy(DEPLOYMENT)
    item.update(overrides)
    return item


def _dep_args(**overrides):
    params = {
        "application_id": APP_ID,
        "environment_id": ENV_ID,
        "deploy_version": VERSION,
        "configuration": copy.deepcopy(CONFIG),
    }
    params.update(overrides)
    return module_args(**params)


class FakeTemClient(object):
    """In-memory TEM client holding the active deployment per application."""

    def __init__(self, deployments=None):
        self.deployments = {
            (app, env): copy.deepcopy(state)
            for (app, env), state in (deployments or {}).items()
        }
        self.calls = []
        self._next = 2000

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeApplicationInfo(self, request):
        self._record("DescribeApplicationInfo", request)
        state = self.deployments.get((request.ApplicationId, request.EnvironmentId))
        return SimpleNamespace(Result=FakeResource(dict(state)) if state else None)

    def DeployApplication(self, request):
        self._record("DeployApplication", request)
        self._next += 1
        state = copy.deepcopy(request.__dict__)
        state["VersionId"] = "ver-%04d" % self._next
        state["UnderDeploying"] = False
        self.deployments[(request.ApplicationId, request.EnvironmentId)] = state
        return SimpleNamespace(Result=state["VersionId"])


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TemClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotence and guards
# ---------------------------------------------------------------------------


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeTemClient(deployments={(APP_ID, ENV_ID): _deployment()})
    _make_module(monkeypatch, fake)
    _dep_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment"]["VersionId"] == "ver-1001"
    assert result["version_id"] == "ver-1001"
    ops = [c for c, unused in fake.calls]
    assert "DeployApplication" not in ops


def test_configuration_must_not_override_identity(monkeypatch):
    fake = FakeTemClient(deployments={})
    _make_module(monkeypatch, fake)
    _dep_args(configuration=dict(CONFIG, DeployVersion="nope"))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "must not override deployment identity fields" in payload["msg"]
    assert "DeployVersion" in payload["fields"]


# ---------------------------------------------------------------------------
# deploy flows
# ---------------------------------------------------------------------------


def test_version_name_drift_deploys(monkeypatch):
    fake = FakeTemClient(deployments={(APP_ID, ENV_ID): _deployment()})
    _make_module(monkeypatch, fake)
    _dep_args(deploy_version="v2026.09.01")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["DeployVersion"] == "v2026.09.01"
    assert result["version_id"].startswith("ver-")
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeApplicationInfo"
    assert "DeployApplication" in ops


def test_configuration_drift_deploys(monkeypatch):
    fake = FakeTemClient(deployments={(APP_ID, ENV_ID): _deployment()})
    _make_module(monkeypatch, fake)
    drifted = dict(CONFIG, CpuSpec=2, MemorySpec=4)
    _dep_args(configuration=drifted)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["CpuSpec"] == 2
    assert result["deployment"]["MemorySpec"] == 4


def test_force_redeploy_skips_match(monkeypatch):
    fake = FakeTemClient(deployments={(APP_ID, ENV_ID): _deployment()})
    _make_module(monkeypatch, fake)
    _dep_args(force_redeploy=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "DeployApplication" in ops


def test_deploy_without_wait_returns_snapshot(monkeypatch):
    fake = FakeTemClient(deployments={})
    _make_module(monkeypatch, fake)
    _dep_args(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["DeployVersion"] == VERSION
    assert result["version_id"].startswith("ver-")


def test_deploy_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient(deployments={})
    _make_module(monkeypatch, fake)
    _dep_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["DeployVersion"] == VERSION
    assert result["version_id"] is None
    assert "DeployApplication" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeApplicationInfo(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _dep_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
