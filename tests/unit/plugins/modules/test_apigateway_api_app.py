"""Unit tests for the apigateway_api_app write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake API Gateway client
that mutates an app-name keyed store, so the module's post-write
``DescribeApiAppsStatus`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the app already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import apigateway_api_app as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _app(api_app_id, api_app_name, api_app_desc=""):
    return FakeResource({"ApiAppId": api_app_id, "ApiAppName": api_app_name, "ApiAppDesc": api_app_desc})


class FakeApiGatewayClient(object):
    """In-memory API Gateway client mutating an app store keyed by app name."""

    def __init__(self, apps=None):
        self.apps = list(apps or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeApiAppsStatus(self, request):
        self._record("DescribeApiAppsStatus", request)
        return SimpleNamespace(
            Result=SimpleNamespace(ApiAppSet=[FakeResource(dict(t._data)) for t in self.apps]),
            RequestId="req-fake",
        )

    def CreateApiApp(self, request):
        self._record("CreateApiApp", request)
        api_app_id = "app-%d" % (len(self.apps) + 1)
        self.apps.append(_app(api_app_id, getattr(request, "ApiAppName", ""), getattr(request, "ApiAppDesc", "")))
        return SimpleNamespace(ApiAppId=api_app_id, RequestId="req-fake")

    def DeleteApiApp(self, request):
        self._record("DeleteApiApp", request)
        target = getattr(request, "ApiAppId", "")
        self.apps = [t for t in self.apps if t.ApiAppId != target]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_apigateway", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeApiGatewayClient(apps=[])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", api_app_desc="Mobile client credentials", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["api_app_name"] == "mobile-client"
    assert result["api_app_id"].startswith("app-")
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeApiAppsStatus"
    assert "CreateApiApp" in ops
    assert "DeleteApiApp" not in ops
    created = [r for c, r in fake.calls if c == "CreateApiApp"][0]
    assert created.ApiAppName == "mobile-client"
    assert created.ApiAppDesc == "Mobile client credentials"


def test_delete_when_present(monkeypatch):
    fake = FakeApiGatewayClient(apps=[_app("app-1", "mobile-client")])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteApiApp" in ops
    assert "CreateApiApp" not in ops
    assert fake.apps == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeApiGatewayClient(apps=[_app("app-1", "mobile-client")])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["api_app_id"] == "app-1"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeApiAppsStatus"]
    assert "CreateApiApp" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeApiGatewayClient(apps=[])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteApiApp" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApiGatewayClient(apps=[])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateApiApp" not in [c for c, unused in fake.calls]
    assert fake.apps == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeApiGatewayClient(apps=[_app("app-1", "mobile-client")])
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteApiApp" not in [c for c, unused in fake.calls]
    assert len(fake.apps) == 1


# ---------------------------------------------------------------------------
# error path
# ---------------------------------------------------------------------------


def test_sdk_failure_fails(monkeypatch):
    fake = FakeApiGatewayClient(apps=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateApiApp = _raise_error
    _make_module(monkeypatch, fake)
    module_args(api_app_name="mobile-client", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
