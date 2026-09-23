"""Unit tests for the tse_governance_alias write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TSE client whose create /
modify / delete alias operations mutate the alias store so post-write
describe/wait polls converge on the first attempt.

Scenario matrix:

* absent on a missing alias (idempotent no-op)
* absent with a matching alias (check-mode dry run, real delete)
* creation when missing (service/namespace required guard, happy path,
  check mode)
* no-op when the alias already targets the desired service/namespace
* retarget / comment drift updates
* the ``Result is not True`` guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_alias as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeRequest,
    FakeResource,
    module_args,
    run,
)


class CachedModels(object):
    """Models stand-in with STABLE per-name classes.

    ``tse_governance_alias.write_request`` picks the request shape with a
    class-identity test (``cls in (models.CreateGovernanceAliasRequest,
    ...)``), which the stateless ``FakeModels`` defeats by minting a new
    class on every attribute access. Caching one class per name keeps
    identity and constructor behaviour intact.
    """

    def __init__(self):
        self._classes = {}

    def __getattr__(self, name):
        cls = self._classes.get(name)
        if cls is None:
            cls = type(name, (FakeRequest,), {})
            self._classes[name] = cls
        return cls


INSTANCE = "ins-abc"

ALIAS = {
    "Alias": "orders-api",
    "AliasNamespace": "shared",
    "Service": "orders",
    "Namespace": "production",
    "Comment": "alias comment",
}


def _alias(**overrides):
    item = copy.deepcopy(ALIAS)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "instance_id": INSTANCE,
        "alias": "orders-api",
        "alias_namespace": "shared",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE governance client mutating an alias store."""

    def __init__(self, aliases=None, result=True):
        self.aliases = [copy.deepcopy(t) for t in (aliases or [])]
        self.result = result
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGovernanceAliases(self, request):
        self._record("DescribeGovernanceAliases", request)
        alias = getattr(request, "Alias", None)
        alias_namespace = getattr(request, "AliasNamespace", None)
        matches = [
            t for t in self.aliases
            if t.get("Alias") == alias and t.get("AliasNamespace") == alias_namespace
        ]
        return SimpleNamespace(
            Content=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateGovernanceAlias(self, request):
        self._record("CreateGovernanceAlias", request)
        data = dict(getattr(request, "__dict__", {}) or {})
        payload = dict(data)
        payload.pop("InstanceId", None)
        payload.pop("RequestId", None)
        self.aliases = [t for t in self.aliases if not (t.get("Alias") == payload.get("Alias") and t.get("AliasNamespace") == payload.get("AliasNamespace"))]
        self.aliases.append(payload)
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def ModifyGovernanceAlias(self, request):
        self._record("ModifyGovernanceAlias", request)
        data = dict(getattr(request, "__dict__", {}) or {})
        payload = dict(data)
        payload.pop("InstanceId", None)
        payload.pop("RequestId", None)
        for item in self.aliases:
            if item.get("Alias") == payload.get("Alias") and item.get("AliasNamespace") == payload.get("AliasNamespace"):
                for key, value in payload.items():
                    if value is not None:
                        item[key] = value
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def DeleteGovernanceAliases(self, request):
        self._record("DeleteGovernanceAliases", request)
        aliases = list(getattr(request, "GovernanceAliases", None) or [])
        if aliases:
            data = dict(getattr(aliases[0], "__dict__", {}) or {})
            self.aliases = [
                t for t in self.aliases
                if not (t.get("Alias") == data.get("Alias") and t.get("AliasNamespace") == data.get("AliasNamespace"))
            ]
        return SimpleNamespace(Result=self.result, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    models = models or CachedModels()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models, SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_alias_is_idempotent(monkeypatch):
    fake = FakeTseClient(aliases=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", alias="ghost-api")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alias_info"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGovernanceAliases"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(aliases=[_alias()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"] is None
    assert len(fake.aliases) == 1
    assert "DeleteGovernanceAliases" not in [c for c, unused in fake.calls]


def test_absent_deletes_alias(monkeypatch):
    fake = FakeTseClient(aliases=[_alias()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"] is None
    assert fake.aliases == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteGovernanceAliases" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_service_and_namespace(monkeypatch):
    fake = FakeTseClient(aliases=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["service", "namespace"]


def test_create_alias(monkeypatch):
    fake = FakeTseClient(aliases=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        service="orders",
        namespace="production",
        comment="alias comment",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"]["Alias"] == "orders-api"
    assert result["alias_info"]["Service"] == "orders"
    assert result["alias_info"]["Namespace"] == "production"
    assert len(fake.aliases) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGovernanceAliases"
    assert "CreateGovernanceAlias" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(aliases=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", service="orders", namespace="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"]["Service"] == "orders"
    assert fake.aliases == []
    assert "CreateGovernanceAlias" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-alias flows
# ---------------------------------------------------------------------------


def test_existing_alias_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(aliases=[_alias()])
    _make_module(monkeypatch, fake)
    _base(state="present", service="orders", namespace="production", comment="alias comment")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alias_info"]["Alias"] == "orders-api"
    assert "ModifyGovernanceAlias" not in [c for c, unused in fake.calls]


def test_retarget_service_drift(monkeypatch):
    fake = FakeTseClient(aliases=[_alias()])
    _make_module(monkeypatch, fake)
    _base(state="present", service="checkout", namespace="production", comment="alias comment")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"]["Service"] == "checkout"
    ops = [c for c, unused in fake.calls]
    assert "ModifyGovernanceAlias" in ops


def test_comment_drift_updates(monkeypatch):
    fake = FakeTseClient(aliases=[_alias()])
    _make_module(monkeypatch, fake)
    _base(state="present", service="orders", namespace="production", comment="new comment")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias_info"]["Comment"] == "new comment"
    ops = [c for c, unused in fake.calls]
    assert "ModifyGovernanceAlias" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(aliases=[_alias(), _alias(Service="duplicate")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE governance aliases matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_unsuccessful_result_fails(monkeypatch):
    fake = FakeTseClient(aliases=[], result=False)
    _make_module(monkeypatch, fake)
    _base(state="present", service="orders", namespace="production")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "unsuccessful result" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceAliases(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_governance_alias.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    def from_json_string(self, raw):
        self.raw = raw


class LegacyDeleteValue(object):
    pass


class LegacyModels(object):
    CreateGovernanceAliasRequest = LegacyValue
    ModifyGovernanceAliasRequest = LegacyValue
    DeleteGovernanceAliasesRequest = LegacyDeleteValue
    GovernanceAlias = LegacyValue


def test_governance_alias_requests_map_full_lifecycle():
    p = {"instance_id": "ins1", "alias": "orders-api", "alias_namespace": "shared", "service": "orders", "namespace": "production", "comment": "stable"}
    target = mod.desired(p)
    assert json.loads(mod.write_request(LegacyModels.CreateGovernanceAliasRequest, LegacyModels, p, target).raw)["Service"] == "orders"
    delete = mod.write_request(LegacyModels.DeleteGovernanceAliasesRequest, LegacyModels, p, target)
    assert delete.InstanceId == "ins1" and json.loads(delete.GovernanceAliases[0].raw)["AliasNamespace"] == "shared"


def test_governance_alias_update_preserves_unspecified_fields():
    p = {"alias": "orders-api", "alias_namespace": "shared", "service": None, "namespace": None, "comment": "new"}
    assert mod.desired(p, {"Service": "orders", "Namespace": "production", "Comment": "old"}) == {
        "Alias": "orders-api",
        "AliasNamespace": "shared",
        "Service": "orders",
        "Namespace": "production",
        "Comment": "new",
    }
