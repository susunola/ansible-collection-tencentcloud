"""Unit tests for the cdwdoris_cooldown_policy write module (run_module flows).

The module creates or updates a named hot/cold tiering policy; the service
exposes no standalone policy deletion, so the lifecycle is present-only with
drift updates. The fake CDW Doris client mutates a policy store so the
post-write describe refetch converges immediately.

Scenario matrix:

* argument validation (missing instance/name, no cooldown field,
  mutually exclusive TTL and datetime)
* no-op when the policy already matches
* creation flows (real and check-mode dry run)
* drift updates drive ``ModifyCoolDownPolicy``
* multiple-match and blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_cooldown_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwdoris-xxxxxxxx"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "name": "archive-after-30-days", "cooldown_ttl": "30 DAY"}
    params.update(overrides)
    return module_args(**params)


class FakeCdwdorisClient(object):
    """In-memory CDW Doris client mutating a cooldown-policy store."""

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCoolDownPolicies(self, request):
        self._record("DescribeCoolDownPolicies", request)
        return SimpleNamespace(List=[FakeResource(p) for p in self.policies], ErrorMsg=None)

    def CreateCoolDownPolicy(self, request):
        self._record("CreateCoolDownPolicy", request)
        item = {"PolicyName": getattr(request, "PolicyName", None)}
        if getattr(request, "CoolDownTtl", None) is not None:
            item["CooldownTtl"] = request.CoolDownTtl
        if getattr(request, "CoolDownDatetime", None) is not None:
            item["CooldownDatetime"] = request.CoolDownDatetime
        self.policies.append(item)
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")

    def ModifyCoolDownPolicy(self, request):
        self._record("ModifyCoolDownPolicy", request)
        for policy in self.policies:
            if policy.get("PolicyName") == getattr(request, "PolicyName", None):
                if getattr(request, "CoolDownTtl", None) is not None:
                    policy["CooldownTtl"] = request.CoolDownTtl
                if getattr(request, "CoolDownDatetime", None) is not None:
                    policy["CooldownDatetime"] = request.CoolDownDatetime
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwdorisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_cooldown_field_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, name="archive")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_ttl_and_datetime_mutually_exclusive_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(cooldown_ttl="30 DAY", cooldown_datetime="2026-12-31 00:00:00")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_policy_matches(monkeypatch):
    fake = FakeCdwdorisClient(policies=[{"PolicyName": "archive-after-30-days", "CooldownTtl": "30 DAY"}])
    _make_module(monkeypatch, fake)
    _args(cooldown_ttl="30 DAY")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["PolicyName"] == "archive-after-30-days"
    assert [c for c, unused in fake.calls] == ["DescribeCoolDownPolicies"]


def test_create_policy(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(cooldown_ttl="30 DAY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["CooldownTtl"] == "30 DAY"
    assert len(fake.policies) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateCoolDownPolicy" in ops
    assert "ModifyCoolDownPolicy" not in ops


def test_create_datetime_policy(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, name="archive-after-30-days", cooldown_datetime="2026-12-31 00:00:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["CooldownDatetime"] == "2026-12-31 00:00:00"
    assert "CooldownTtl" not in result["policy"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, cooldown_ttl="30 DAY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] == {"PolicyName": "archive-after-30-days", "CooldownTtl": "30 DAY"}
    assert fake.policies == []
    assert "CreateCoolDownPolicy" not in [c for c, unused in fake.calls]


def test_ttl_drift_updates_policy(monkeypatch):
    fake = FakeCdwdorisClient(policies=[{"PolicyName": "archive-after-30-days", "CooldownTtl": "30 DAY"}])
    _make_module(monkeypatch, fake)
    _args(cooldown_ttl="60 DAY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["CooldownTtl"] == "60 DAY"
    update_call = next((c, r) for c, r in fake.calls if c == "ModifyCoolDownPolicy")
    assert getattr(update_call[1], "PolicyName") == "archive-after-30-days"
    assert getattr(update_call[1], "CoolDownTtl") == "60 DAY"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeCdwdorisClient(
        policies=[
            {"PolicyName": "dup", "CooldownTtl": "30 DAY"},
            {"PolicyName": "dup", "CooldownTtl": "60 DAY"},
        ]
    )
    _make_module(monkeypatch, fake)
    _args(name="dup", cooldown_ttl="90 DAY")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Doris cooldown policies matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCoolDownPolicies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(cooldown_ttl="30 DAY")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwdoris_cooldown_policy.py)
# ---------------------------------------------------------------------------


def test_desired_ttl_policy_uses_read_model_field_names():
    assert mod.desired({"name": "archive", "cooldown_ttl": "30 DAY", "cooldown_datetime": None}) == {
        "PolicyName": "archive",
        "CooldownTtl": "30 DAY",
    }


def test_desired_datetime_policy():
    assert mod.desired({"name": "year-end", "cooldown_ttl": None, "cooldown_datetime": "2026-12-31 00:00:00"}) == {
        "PolicyName": "year-end",
        "CooldownDatetime": "2026-12-31 00:00:00",
    }
