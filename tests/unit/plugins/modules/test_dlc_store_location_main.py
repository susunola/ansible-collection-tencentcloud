"""Unit tests for the dlc_store_location write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client
whose ``CreateStoreLocation``/``ModifyAdvancedStoreLocation`` mutate the
store-location settings, so the module's post-write ``read`` refetches and
``wait_config`` converge on the first poll.

Scenario matrix:

* pre-SDK cosn:// and advanced-location validation
* base location immutable-drift failure
* base initialization (happy path, check mode)
* no-drift idempotency, advanced-drift modify (enable / disable / check mode)
* waiter timeout when a modify never becomes readable
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_store_location as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

BASE = "cosn://analytics-results/"
ADVANCED = "cosn://analytics-results/advanced/"


class FakeDlcStoreLocationClient(object):
    """In-memory DLC store-location client."""

    def __init__(self, base="", advanced_enable=0, advanced_location="", modify_stores=True):
        self.base = base
        self.advanced = {
            "Enable": advanced_enable,
            "StoreLocation": advanced_location,
            "HasLakeFs": False,
            "LakeFsStatus": "",
            "BucketType": "",
        }
        self.calls = []
        self.modify_stores = modify_stores

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _advanced_response(self):
        return SimpleNamespace(**self.advanced)

    def DescribeStoreLocation(self, request):
        self._record("DescribeStoreLocation", request)
        return SimpleNamespace(StoreLocation=self.base, RequestId="req-fake")

    def DescribeAdvancedStoreLocation(self, request):
        self._record("DescribeAdvancedStoreLocation", request)
        return self._advanced_response()

    def CreateStoreLocation(self, request):
        self._record("CreateStoreLocation", request)
        self.base = request.StoreLocation
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAdvancedStoreLocation(self, request):
        self._record("ModifyAdvancedStoreLocation", request)
        if self.modify_stores:
            self.advanced["Enable"] = request.Enable
            self.advanced["StoreLocation"] = request.StoreLocation
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _args(**overrides):
    params = {"store_location": BASE}
    params.update(overrides)
    return module_args(**params)


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_store_location_must_be_cosn(monkeypatch):
    fake = FakeDlcStoreLocationClient()
    _make_module(monkeypatch, fake)
    _args(store_location="s3://bucket/results/")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "store_location must use a cosn:// path" in exc.value.args[0]["msg"]


def test_advanced_store_location_must_be_cosn(monkeypatch):
    fake = FakeDlcStoreLocationClient()
    _make_module(monkeypatch, fake)
    _args(advanced_store_location="s3://bucket/advanced/")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "advanced_store_location must use a cosn:// path" in exc.value.args[0]["msg"]


def test_advanced_enabled_requires_advanced_location(monkeypatch):
    fake = FakeDlcStoreLocationClient()
    _make_module(monkeypatch, fake)
    _args(advanced_enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "advanced_store_location is required when advanced_enabled=true" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# base location flows
# ---------------------------------------------------------------------------


def test_base_store_location_is_immutable(monkeypatch):
    fake = FakeDlcStoreLocationClient(base=BASE, advanced_enable=0, advanced_location="")
    _make_module(monkeypatch, fake)
    _args(store_location="cosn://other-bucket/")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable after initialization" in payload["msg"]
    assert payload["immutable_drift"]["StoreLocation"] == (BASE, "cosn://other-bucket/")


def test_initialize_store_location(monkeypatch):
    fake = FakeDlcStoreLocationClient()
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["store_location_config"]["StoreLocation"] == BASE
    assert fake.base == BASE
    assert "CreateStoreLocation" in _ops(fake)


def test_initialize_store_location_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcStoreLocationClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["store_location_config"]["StoreLocation"] == BASE
    assert fake.base == ""
    assert "CreateStoreLocation" not in _ops(fake)


# ---------------------------------------------------------------------------
# advanced setting flows
# ---------------------------------------------------------------------------


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcStoreLocationClient(base=BASE, advanced_enable=1, advanced_location=ADVANCED)
    _make_module(monkeypatch, fake)
    _args(advanced_enabled=True, advanced_store_location=ADVANCED)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["store_location_config"]["AdvancedEnabled"] is True
    ops = _ops(fake)
    assert "CreateStoreLocation" not in ops
    assert "ModifyAdvancedStoreLocation" not in ops


def test_advanced_drift_enables_storage(monkeypatch):
    fake = FakeDlcStoreLocationClient(base=BASE, advanced_enable=0, advanced_location="")
    _make_module(monkeypatch, fake)
    _args(advanced_enabled=True, advanced_store_location=ADVANCED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["store_location_config"]["AdvancedEnabled"] is True
    assert result["store_location_config"]["AdvancedStoreLocation"] == ADVANCED
    assert fake.advanced["Enable"] == 1
    assert fake.advanced["StoreLocation"] == ADVANCED
    assert "ModifyAdvancedStoreLocation" in _ops(fake)


def test_advanced_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcStoreLocationClient(base=BASE, advanced_enable=0, advanced_location="")
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, advanced_enabled=True, advanced_store_location=ADVANCED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["store_location_config"]["AdvancedEnabled"] is True
    assert fake.advanced["Enable"] == 0
    assert "ModifyAdvancedStoreLocation" not in _ops(fake)


def test_advanced_drift_disables_storage(monkeypatch):
    fake = FakeDlcStoreLocationClient(base=BASE, advanced_enable=1, advanced_location=ADVANCED)
    _make_module(monkeypatch, fake)
    _args(advanced_enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["store_location_config"]["AdvancedEnabled"] is False
    assert fake.advanced["Enable"] == 0
    assert "ModifyAdvancedStoreLocation" in _ops(fake)


def test_modify_wait_timeout_when_unreadable(monkeypatch):
    fake = FakeDlcStoreLocationClient(
        base=BASE, advanced_enable=0, advanced_location="", modify_stores=False
    )
    _make_module(monkeypatch, fake)
    _args(advanced_enabled=True, advanced_store_location=ADVANCED, waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Timed out waiting for resource state"
    assert payload["expected_states"] == ["ready"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeStoreLocation(self, request):
            raise Boom("catalog unavailable")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "catalog unavailable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_store_location.py)
# ---------------------------------------------------------------------------


class LegacyRequest(object):
    pass


class LegacyModels(object):
    CreateStoreLocationRequest = ModifyAdvancedStoreLocationRequest = LegacyRequest


def test_base_and_advanced_requests_are_explicit():
    create = mod.create_request(LegacyModels, "cosn://results/")
    modify = mod.modify_request(LegacyModels, True, "cosn://advanced/")
    assert create.StoreLocation == "cosn://results/"
    assert modify.Enable == 1 and modify.StoreLocation == "cosn://advanced/"


def test_advanced_drift_does_not_treat_read_only_fields_as_managed():
    p = {"store_location": "cosn://results/", "advanced_enabled": True, "advanced_store_location": "cosn://advanced/"}
    current = {"StoreLocation": "cosn://results/", "AdvancedEnabled": False, "AdvancedStoreLocation": "", "HasLakeFs": True}
    assert mod.advanced_drift(p, current) == {"AdvancedEnabled": (False, True), "AdvancedStoreLocation": ("", "cosn://advanced/")}
    assert mod.desired(p, current)["HasLakeFs"] is True
