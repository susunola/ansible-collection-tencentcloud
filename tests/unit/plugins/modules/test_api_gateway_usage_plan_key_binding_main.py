"""Unit tests for the api_gateway_usage_plan_key_binding write module.

Drives ``run_module()`` against an in-memory fake API Gateway client whose
bind / unbind operations mutate the usage plan's key-binding list so
post-write describes converge immediately.

Scenario matrix:

* absent on a plan that does not bind the key (idempotent no-op)
* absent unbinds one key out of a plan's multi-key binding list
* absent with a live binding (check-mode dry run, real unbind)
* present bind of an unbound key (happy path, check mode)
* present when the key is already bound (idempotent no-op)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_usage_plan_key_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BINDING = {
    "UsagePlanId": "usagePlan-1001",
    "AccessKeyId": "AKID-1001",
}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _bind_args(**overrides):
    params = {"usage_plan_id": "usagePlan-1001", "access_key_id": "AKID-1001"}
    params.update(overrides)
    return module_args(**params)


class FakeApigatewayClient(object):
    """In-memory client mutating one usage plan's key-binding list."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(t) for t in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUsagePlanSecretIds(self, request):
        self._record("DescribeUsagePlanSecretIds", request)
        plan_id = getattr(request, "UsagePlanId", None)
        return SimpleNamespace(
            Result=SimpleNamespace(AccessKeyList=[FakeResource(t) for t in self.bindings if t.get("UsagePlanId") == plan_id])
        )

    def BindSecretIds(self, request):
        self._record("BindSecretIds", request)
        plan_id = getattr(request, "UsagePlanId", None)
        for key_id in getattr(request, "AccessKeyIds", None) or []:
            self.bindings.append({"UsagePlanId": plan_id, "AccessKeyId": key_id})
        return SimpleNamespace(RequestId="req-fake")

    def UnBindSecretIds(self, request):
        self._record("UnBindSecretIds", request)
        plan_id = getattr(request, "UsagePlanId", None)
        key_ids = set(getattr(request, "AccessKeyIds", None) or [])
        self.bindings = [
            t for t in self.bindings
            if not (t.get("UsagePlanId") == plan_id and t.get("AccessKeyId") in key_ids)
        ]
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


def test_absent_missing_binding_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert _names(fake) == ["DescribeUsagePlanSecretIds"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.bindings) == 1
    assert "UnBindSecretIds" not in _names(fake)


def test_absent_unbinds_key(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    assert "UnBindSecretIds" in _names(fake)


def test_absent_removes_single_key_from_list(monkeypatch):
    # The plan binds two keys; absent must remove only the requested key.
    fake = FakeApigatewayClient(bindings=[_binding(), _binding(AccessKeyId="AKID-1002")])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [b["AccessKeyId"] for b in fake.bindings] == ["AKID-1002"]


# ---------------------------------------------------------------------------
# present (bind) flows
# ---------------------------------------------------------------------------


def test_present_binds_unbound_key(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"UsagePlanId": "usagePlan-1001", "AccessKeyId": "AKID-1001"}
    assert len(fake.bindings) == 1
    assert "BindSecretIds" in _names(fake)


def test_present_bind_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["AccessKeyId"] == "AKID-1001"
    assert fake.bindings == []
    assert "BindSecretIds" not in _names(fake)


def test_present_already_bound_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["UsagePlanId"] == "usagePlan-1001"
    assert "BindSecretIds" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsagePlanSecretIds(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
