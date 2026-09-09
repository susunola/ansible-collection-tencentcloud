"""Unit tests for the tse_gateway_model_api_group_auth write module.

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
consumer-group-authorization mutations mutate the scope store, so the module's
post-mutation ``current`` readback converges immediately.

Scenario matrix:

* present with every requested group already authorized (idempotent no-op)
* present granting one missing group (real add and check-mode preview)
* name-based resolution of the Model API and the consumer groups
* unknown model-api / consumer-group names and an unknown Model API id
* absent with no intersection (no-op), real revoke and check-mode preview
* validation guards (missing identities, mutual exclusivity, 1..10 entry
  bound, duplicate entries)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_model_api_group_auth as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _base(**overrides):
    params = {"gateway_id": "gateway-x"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a small Model API scope store."""

    def __init__(self, apis=None, groups=None, scopes=None):
        self.apis = [copy.deepcopy(t) for t in (
            apis if apis is not None else [{"Id": "api-1001", "Name": "chat-completions"}]
        )]
        self.groups = [copy.deepcopy(t) for t in (
            groups if groups is not None else [
                {"ConsumerGroupId": "group-2001", "Name": "trusted-clients"},
                {"ConsumerGroupId": "group-2002", "Name": "partner-clients"},
            ]
        )]
        self.scopes = [copy.deepcopy(t) for t in (scopes or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCloudNativeAPIGatewayLLMModelAPIs(self, request):
        self._record("DescribeCloudNativeAPIGatewayLLMModelAPIs", request)
        return SimpleNamespace(
            Result=SimpleNamespace(DataList=[FakeResource(dict(a)) for a in self.apis], TotalCount=len(self.apis))
        )

    def DescribeCloudNativeAPIGatewayConsumerGroupList(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumerGroupList", request)
        return SimpleNamespace(
            Result=SimpleNamespace(ConsumerGroups=[FakeResource(dict(g)) for g in self.groups], TotalCount=len(self.groups))
        )

    def DescribeCloudNativeAPIGatewayLLMModelAPI(self, request):
        self._record("DescribeCloudNativeAPIGatewayLLMModelAPI", request)
        api = next((a for a in self.apis if a.get("Id") == getattr(request, "ModelAPIId", None)), None)
        if api is None:
            return SimpleNamespace(Result=None)
        return SimpleNamespace(
            Result=FakeResource({"ConsumerGroupModelScopes": [dict(s) for s in self.scopes]})
        )

    def _mutate(self, name, request):
        self._record(name, request)
        ids = set(getattr(request, "ConsumerGroupIds", None) or [])
        if name == "AddCloudNativeAPIGatewayConsumerGroupAuth":
            for group_id in ids:
                if group_id not in [s.get("PrincipalId") for s in self.scopes]:
                    self.scopes.append({"PrincipalId": group_id})
        else:
            self.scopes = [s for s in self.scopes if s.get("PrincipalId") not in ids]
        return SimpleNamespace(RequestId="req-fake")

    def AddCloudNativeAPIGatewayConsumerGroupAuth(self, request):
        return self._mutate("AddCloudNativeAPIGatewayConsumerGroupAuth", request)

    def RemoveCloudNativeAPIGatewayConsumerGroupAuth(self, request):
        return self._mutate("RemoveCloudNativeAPIGatewayConsumerGroupAuth", request)


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_all_authorized_is_idempotent(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", consumer_group_ids=["group-2001"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["authorization"]["ModelAPIId"] == "api-1001"
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2001"]
    ops = [c for c, unused in fake.calls]
    assert "AddCloudNativeAPIGatewayConsumerGroupAuth" not in ops


def test_present_grants_missing_group(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", consumer_group_ids=["group-2001", "group-2002"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authorization"]["ModelAPIId"] == "api-1001"
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2001", "group-2002"]
    assert result["authorization"]["AffectedConsumerGroupIds"] == ["group-2002"]
    ops = [c for c, unused in fake.calls]
    assert "AddCloudNativeAPIGatewayConsumerGroupAuth" in ops
    add_call = fake.calls[[c for c, unused in fake.calls].index("AddCloudNativeAPIGatewayConsumerGroupAuth")][1]
    assert add_call.ResourceType == "ModelAPI"
    assert add_call.ConsumerGroupIds == ["group-2002"]


def test_present_check_mode_previews_grant(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        model_api_id="api-1001",
        consumer_group_ids=["group-2001", "group-2002"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2001", "group-2002"]
    assert result["authorization"]["AffectedConsumerGroupIds"] == ["group-2002"]
    assert [s.get("PrincipalId") for s in fake.scopes] == ["group-2001"]
    assert "AddCloudNativeAPIGatewayConsumerGroupAuth" not in [c for c, unused in fake.calls]


def test_present_resolves_api_and_group_names(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_name="chat-completions", consumer_group_names=["trusted-clients", "partner-clients"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authorization"]["ModelAPIId"] == "api-1001"
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2001", "group-2002"]
    assert result["authorization"]["AffectedConsumerGroupIds"] == ["group-2001", "group-2002"]
    ops = [c for c, unused in fake.calls]
    assert "DescribeCloudNativeAPIGatewayLLMModelAPIs" in ops
    assert "DescribeCloudNativeAPIGatewayConsumerGroupList" in ops


def test_present_unknown_group_name_fails(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", consumer_group_names=["ghost-group"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "consumer group names were not found" in payload["msg"]
    assert payload["consumer_group_names"] == ["ghost-group"]


def test_present_unknown_model_api_name_fails(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_name="ghost-api", consumer_group_ids=["group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Model API name was not found" in payload["msg"]
    assert payload["model_api_name"] == "ghost-api"


def test_present_unknown_model_api_id_fails(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-nope", consumer_group_ids=["group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Model API was not found" in payload["msg"]
    assert payload["model_api_id"] == "api-nope"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_no_intersection_is_idempotent(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}])
    _make_module(monkeypatch, fake)
    _base(state="absent", model_api_id="api-1001", consumer_group_ids=["group-3001"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2001"]
    ops = [c for c, unused in fake.calls]
    assert "RemoveCloudNativeAPIGatewayConsumerGroupAuth" not in ops


def test_absent_revokes_authorized_group(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}, {"PrincipalId": "group-2002"}])
    _make_module(monkeypatch, fake)
    _base(state="absent", model_api_id="api-1001", consumer_group_ids=["group-2001"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2002"]
    assert result["authorization"]["AffectedConsumerGroupIds"] == ["group-2001"]
    ops = [c for c, unused in fake.calls]
    assert "RemoveCloudNativeAPIGatewayConsumerGroupAuth" in ops
    remove_call = fake.calls[[c for c, unused in fake.calls].index("RemoveCloudNativeAPIGatewayConsumerGroupAuth")][1]
    assert remove_call.ConsumerGroupIds == ["group-2001"]
    assert [s.get("PrincipalId") for s in fake.scopes] == ["group-2002"]


def test_absent_check_mode_previews_revoke(monkeypatch):
    fake = FakeTseClient(scopes=[{"PrincipalId": "group-2001"}, {"PrincipalId": "group-2002"}])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="absent",
        model_api_id="api-1001",
        consumer_group_ids=["group-2001"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["authorization"]["ConsumerGroupIds"] == ["group-2002"]
    assert result["authorization"]["AffectedConsumerGroupIds"] == ["group-2001"]
    assert len(fake.scopes) == 2
    assert "RemoveCloudNativeAPIGatewayConsumerGroupAuth" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_api_identity_is_required(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", consumer_group_ids=["group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "model_api_id" in message
    assert "model_api_name" in message


def test_group_identity_is_required(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "consumer_group_ids" in message
    assert "consumer_group_names" in message


def test_api_identity_is_mutually_exclusive(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", model_api_name="chat", consumer_group_ids=["group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_group_identity_is_mutually_exclusive(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", consumer_group_ids=["group-2001"], consumer_group_names=["trusted"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_more_than_ten_groups_fail(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    groups = ["group-%02d" % i for i in range(11)]
    _base(state="present", model_api_id="api-1001", consumer_group_ids=groups)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "between 1 and 10 entries" in exc.value.args[0]["msg"]


def test_duplicate_groups_fail(monkeypatch):
    fake = FakeTseClient(scopes=[])
    _make_module(monkeypatch, fake)
    _base(state="present", model_api_id="api-1001", consumer_group_ids=["group-2001", "group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must not contain duplicates" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayLLMModelAPI(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", model_api_id="api-1001", consumer_group_ids=["group-2001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_model_api_group_auth.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    pass


def test_group_ids_reads_model_api_scopes():
    value = {"ConsumerGroupModelScopes": [{"PrincipalId": "cg2"}, {"PrincipalId": "cg1"}, {"PrincipalId": "cg1"}]}
    assert mod.group_ids(value) == ["cg1", "cg2"]


def test_auth_request_uses_model_api_resource_type():
    p = {"gateway_id": "g1", "model_api_id": "api1"}
    request = mod.mutation_request(LegacyValue, p, ["cg1"])
    assert request.ResourceType == "ModelAPI" and request.ResourceId == "api1"


def test_resolve_ids_reports_missing_group_names():
    ids, missing = mod.resolve_ids([{"Name": "trusted", "ConsumerGroupId": "cg1"}], ["trusted", "missing"], "ConsumerGroupId")
    assert ids == ["cg1"] and missing == ["missing"]
