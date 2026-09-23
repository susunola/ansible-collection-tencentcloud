"""Unit tests for the cam_oidc_provider write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CAM OIDC client whose
create / update / delete operations mutate an OIDC-provider store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing provider (idempotent no-op)
* absent with a matching provider (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the provider already matches (name/url/client-ids/key/description)
* client-id list order invariance and description/URL drift updates
* rename-by-name-alone creates a separate provider, the
  zero-Status-acts-absent branch, a not-found describe and the blanket SDK
  failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_oidc_provider as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PROVIDER = {
    "Name": "ci-workloads",
    "IdentityUrl": "https://token.actions.githubusercontent.com",
    "ClientId": ["sts.tencentcloudapi.com"],
    "IdentityKey": "dGVzdC1wdWJsaWMta2V5",
    "Description": "CI workload identity",
    "Status": 1,
}


def _provider(**overrides):
    item = copy.deepcopy(PROVIDER)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "name": "ci-workloads",
        "identity_url": "https://token.actions.githubusercontent.com",
        "client_ids": ["sts.tencentcloudapi.com"],
        "identity_key": "dGVzdC1wdWJsaWMta2V5",
        "description": "CI workload identity",
    }
    params.update(overrides)
    return module_args(**params)


def _not_found():
    class NotFound(Exception):
        def get_code(self):
            return "ResourceNotFound.CamOidcProvider"

        def get_request_id(self):
            return "req-1"

    return NotFound("oidc provider not found")


class FakeCamClient(object):
    """In-memory CAM OIDC client mutating a small provider store."""

    def __init__(self, providers=None):
        self.providers = [copy.deepcopy(t) for t in (providers or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.providers:
            if item.get("Name") == name:
                return item
        return None

    def DescribeOIDCConfig(self, request):
        self._record("DescribeOIDCConfig", request)
        item = self._by_name(getattr(request, "Name", None))
        if item is None:
            raise _not_found()
        return FakeResource(copy.deepcopy(item))

    def CreateOIDCConfig(self, request):
        self._record("CreateOIDCConfig", request)
        item = {
            "Name": getattr(request, "Name", None),
            "IdentityUrl": getattr(request, "IdentityUrl", None),
            "ClientId": list(getattr(request, "ClientId", None) or []),
            "IdentityKey": getattr(request, "IdentityKey", None),
            "Description": getattr(request, "Description", None) or "",
            "Status": 1,
        }
        self.providers.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateOIDCConfig(self, request):
        self._record("UpdateOIDCConfig", request)
        item = self._by_name(getattr(request, "Name", None))
        if item is not None:
            item["IdentityUrl"] = getattr(request, "IdentityUrl", item.get("IdentityUrl"))
            item["ClientId"] = list(getattr(request, "ClientId", None) or [])
            item["IdentityKey"] = getattr(request, "IdentityKey", item.get("IdentityKey"))
            item["Description"] = getattr(request, "Description", item.get("Description"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteOIDCConfig(self, request):
        self._record("DeleteOIDCConfig", request)
        name = getattr(request, "Name", None)
        self.providers = [t for t in self.providers if t.get("Name") != name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CamClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_provider_is_idempotent(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-provider")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["oidc_provider"] is None
    assert [c for c, unused in fake.calls] == ["DescribeOIDCConfig"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="ci-workloads")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"]["Name"] == "ci-workloads"
    assert len(fake.providers) == 1
    assert "DeleteOIDCConfig" not in [c for c, unused in fake.calls]


def test_absent_deletes_provider(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ci-workloads")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"] is None
    assert fake.providers == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteOIDCConfig" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_provider(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"]["Name"] == "ci-workloads"
    assert result["oidc_provider"]["ClientId"] == ["sts.tencentcloudapi.com"]
    assert len(fake.providers) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeOIDCConfig"
    assert "CreateOIDCConfig" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"] is None
    assert "diff" in result
    assert fake.providers == []
    assert "CreateOIDCConfig" not in [c for c, unused in fake.calls]


def test_rename_by_name_alone_creates_new_provider(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(name="renamed-provider")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"]["Name"] == "renamed-provider"
    assert [p["Name"] for p in fake.providers] == ["ci-workloads", "renamed-provider"]


def test_zero_status_is_treated_as_absent(monkeypatch):
    # DescribeOIDCConfig returns the record but Status==0 means the provider
    # is disabled/not usable, so the module acts as if it were absent.
    fake = FakeCamClient(providers=[_provider(Status=0)])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateOIDCConfig" in [c for c, unused in fake.calls]
    assert [p["Status"] for p in fake.providers if p["Name"] == "ci-workloads"] == [0, 1]


# ---------------------------------------------------------------------------
# existing-provider flows
# ---------------------------------------------------------------------------


def test_existing_provider_no_drift_is_idempotent(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["oidc_provider"]["Name"] == "ci-workloads"
    assert "UpdateOIDCConfig" not in [c for c, unused in fake.calls]


def test_client_ids_order_invariance_is_idempotent(monkeypatch):
    fake = FakeCamClient(providers=[_provider(ClientId=["sts.tencentcloudapi.com", "other.example.com"])])
    _make_module(monkeypatch, fake)
    _present_args(client_ids=["other.example.com", "sts.tencentcloudapi.com"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "UpdateOIDCConfig" not in [c for c, unused in fake.calls]


def test_description_drift_updates(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(description="Updated description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"]["Description"] == "Updated description"
    assert "UpdateOIDCConfig" in [c for c, unused in fake.calls]


def test_identity_url_drift_updates(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(identity_url="https://token.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["oidc_provider"]["IdentityUrl"] == "https://token.example.com"
    ops = [c for c, unused in fake.calls]
    assert "UpdateOIDCConfig" in ops
    assert ops[-1] == "DescribeOIDCConfig"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeOIDCConfig(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_delete_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeOIDCConfig(self, request):
            return FakeResource(copy.deepcopy(_provider()))

        def DeleteOIDCConfig(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ci-workloads")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
