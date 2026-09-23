"""Unit tests for the tke_cluster_authentication write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TKE client whose modify
operation mutates an authentication-options store so post-write describes
converge immediately. Service-account and OIDC options are toggled as
opaque SDK-shaped dicts.

Scenario matrix:

* matching options are idempotent
* service-account and OIDC drift each trigger a modify
* empty remote options versus requested options drift
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_authentication as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "cls-1234"

SERVICE_ACCOUNTS = {
    "UseTKEDefault": True,
    "AutoCreateDiscoveryAnonymousAuth": True,
}

OIDC = {
    "AutoCreateOIDCConfig": True,
    "AutoCreateClientId": ["kubernetes"],
    "AutoInstallPodIdentityWebhookAddon": True,
}


def _auth(service_accounts=None, oidc=None):
    return {
        "ServiceAccounts": copy.deepcopy(service_accounts if service_accounts is not None else SERVICE_ACCOUNTS),
        "OIDCConfig": copy.deepcopy(oidc if oidc is not None else OIDC),
    }


def _args(service_accounts=None, oidc=None):
    return module_args(
        cluster_id=CLUSTER_ID,
        service_accounts=copy.deepcopy(service_accounts if service_accounts is not None else SERVICE_ACCOUNTS),
        oidc=copy.deepcopy(oidc if oidc is not None else OIDC),
    )


class FakeTkeClient(object):
    """In-memory TKE client holding one cluster's authentication options."""

    def __init__(self, service_accounts=None, oidc=None):
        self.service_accounts = copy.deepcopy(service_accounts)
        self.oidc = copy.deepcopy(oidc)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterAuthenticationOptions(self, request):
        self._record("DescribeClusterAuthenticationOptions", request)
        return SimpleNamespace(
            ServiceAccounts=FakeResource(self.service_accounts) if self.service_accounts is not None else None,
            OIDCConfig=FakeResource(self.oidc) if self.oidc is not None else None,
        )

    def ModifyClusterAuthenticationOptions(self, request):
        self._record("ModifyClusterAuthenticationOptions", request)
        sa = getattr(request, "ServiceAccounts", None)
        oidc = getattr(request, "OIDCConfig", None)
        self.service_accounts = dict(vars(sa)) if sa is not None else None
        self.oidc = dict(vars(oidc)) if oidc is not None else None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeTkeClient(service_accounts=SERVICE_ACCOUNTS, oidc=OIDC)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["authentication"]["ServiceAccounts"] == SERVICE_ACCOUNTS
    assert result["authentication"]["OIDCConfig"] == OIDC
    assert [c for c, unused in fake.calls] == ["DescribeClusterAuthenticationOptions"]


def test_service_account_drift_triggers_modify(monkeypatch):
    fake = FakeTkeClient(service_accounts=SERVICE_ACCOUNTS, oidc=OIDC)
    _make_module(monkeypatch, fake)
    _args(service_accounts={"UseTKEDefault": True, "AutoCreateDiscoveryAnonymousAuth": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authentication"]["ServiceAccounts"] == {"UseTKEDefault": True, "AutoCreateDiscoveryAnonymousAuth": False}
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterAuthenticationOptions" in ops
    modify_call = [r for c, r in fake.calls if c == "ModifyClusterAuthenticationOptions"][0]
    assert modify_call.ClusterId == CLUSTER_ID
    assert vars(modify_call.ServiceAccounts) == {"UseTKEDefault": True, "AutoCreateDiscoveryAnonymousAuth": False}
    assert vars(modify_call.OIDCConfig) == OIDC


def test_oidc_drift_triggers_modify(monkeypatch):
    fake = FakeTkeClient(service_accounts=SERVICE_ACCOUNTS, oidc=OIDC)
    _make_module(monkeypatch, fake)
    _args(oidc={"AutoCreateOIDCConfig": False, "AutoCreateClientId": ["kubernetes", "tke"], "AutoInstallPodIdentityWebhookAddon": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authentication"]["OIDCConfig"]["AutoCreateOIDCConfig"] is False
    assert result["authentication"]["OIDCConfig"]["AutoCreateClientId"] == ["kubernetes", "tke"]


def test_empty_remote_options_drift(monkeypatch):
    # API reports no options yet: both sub-objects resolve to {}.
    fake = FakeTkeClient(service_accounts=None, oidc=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authentication"]["ServiceAccounts"] == SERVICE_ACCOUNTS
    assert result["authentication"]["OIDCConfig"] == OIDC


def test_all_empty_options_is_idempotent(monkeypatch):
    fake = FakeTkeClient(service_accounts={}, oidc={})
    _make_module(monkeypatch, fake)
    _args(service_accounts={}, oidc={})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["authentication"] == {"ServiceAccounts": {}, "OIDCConfig": {}}


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(service_accounts=SERVICE_ACCOUNTS, oidc=OIDC)
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        cluster_id=CLUSTER_ID,
        service_accounts={"UseTKEDefault": False, "AutoCreateDiscoveryAnonymousAuth": False},
        oidc=OIDC,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.service_accounts == SERVICE_ACCOUNTS
    assert not [c for c, unused in fake.calls if c != "DescribeClusterAuthenticationOptions"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusterAuthenticationOptions(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
