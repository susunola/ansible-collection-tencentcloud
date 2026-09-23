"""Unit tests for the tione_model_service_auth_token write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TIONE client whose
create/modify/delete token operations mutate the service-group's token list so
service-group discovery refetches converge immediately.

Scenario matrix:

* token_id/name identity guard and token_id-required-for-deletion guard
* absent on a missing token (idempotent no-op)
* absent with a matching token (allow_delete guard, missing token value
  guard, check-mode dry run, real delete)
* creation by name (happy path, check mode, limits applied after creation)
* token_id pointing at a missing token, service group missing
* no-op when nothing drifts
* update drifts (description, limits) and rotate_from_token_id rotation
* show_token_value and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_auth_token as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = "ms-group-abc"
TOKEN_ID = "token-1"
NAME = "production-client"

LIMITS = [{"Strategy": "PerMinute", "Max": 1200}]


def _token(**overrides):
    item = {
        "Base": {"Id": TOKEN_ID, "Name": NAME, "Description": "client token", "Value": "token-value-1"},
        "Limits": [],
    }
    base = overrides.pop("Base", None)
    if base is not None:
        item["Base"].update(base)
    for key in ("Limits",):
        if key in overrides:
            item[key] = overrides.pop(key)
    item.update(overrides)
    return item


def _group(tokens=None, group_id=GROUP_ID):
    return {"ServiceGroupId": group_id, "AuthTokens": [copy.deepcopy(t) for t in (tokens or [])]}


def _id_args(**overrides):
    params = {"service_group_id": GROUP_ID, "token_id": TOKEN_ID}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"service_group_id": GROUP_ID, "name": NAME}
    params.update(overrides)
    return module_args(**params)


class FakeTioneClient(object):
    """In-memory TIONE client mutating one service-group's token list."""

    def __init__(self, group=None):
        self.group = copy.deepcopy(group) if group else None
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeModelServiceGroup(self, request):
        self._record("DescribeModelServiceGroup", request)
        return SimpleNamespace(ServiceGroup=FakeResource(copy.deepcopy(self.group)) if self.group else None)

    def _find_token(self, token_id):
        for token in (self.group or {}).get("AuthTokens") or []:
            if (token.get("Base") or {}).get("Id") == token_id:
                return token
        return None

    def CreateModelServiceAuthToken(self, request):
        self._record("CreateModelServiceAuthToken", request)
        self._next += 1
        token = {
            "Base": {
                "Id": "token-new-%03d" % self._next,
                "Name": getattr(request, "Name", None),
                "Description": getattr(request, "Description", None),
                "Value": "generated-value-%03d" % self._next,
            },
            "Limits": [],
        }
        self.group.setdefault("AuthTokens", []).append(token)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyModelServiceAuthToken(self, request):
        self._record("ModifyModelServiceAuthToken", request)
        auth_token = getattr(request, "AuthToken", None)
        data = getattr(auth_token, "__dict__", {}) or {}
        base = data.get("Base") or {}
        token = self._find_token(base.get("Id"))
        if token is None:
            return SimpleNamespace(RequestId="req-fake")
        if base.get("Name") is not None:
            token["Base"]["Name"] = base["Name"]
        if base.get("Description") is not None:
            token["Base"]["Description"] = base["Description"]
        if getattr(request, "NeedReset", False):
            token["Base"]["Value"] = "rotated-value-%03d" % self._next
        if data.get("Limits") is not None:
            token["Limits"] = copy.deepcopy(data["Limits"])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteModelServiceAuthToken(self, request):
        self._record("DeleteModelServiceAuthToken", request)
        value = getattr(request, "AuthTokenValue", None)
        group = self.group or {}
        group["AuthTokens"] = [
            t for t in group.get("AuthTokens") or [] if (t.get("Base") or {}).get("Value") != value
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identity guards
# ---------------------------------------------------------------------------


def test_token_id_or_name_is_required(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    module_args(service_group_id=GROUP_ID, state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "token_id or name is required"


def test_absent_requires_token_id(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "token_id is required for safe deletion"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_token_is_idempotent(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(state="absent", token_id="ghost-token")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["auth_token"] is None
    assert result["token_id"] == "ghost-token"


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true is required" in exc.value.args[0]["msg"]


def test_absent_requires_token_value(monkeypatch):
    token = _token(Base={"Value": None})
    fake = FakeTioneClient(group=_group([token]))
    _make_module(monkeypatch, fake)
    _id_args(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "token value required by its delete API" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"] is None
    assert len((fake.group or {}).get("AuthTokens") or []) == 1
    assert "DeleteModelServiceAuthToken" not in [c for c, unused in fake.calls]


def test_absent_deletes_token(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"] is None
    assert (fake.group or {}).get("AuthTokens") == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteModelServiceAuthToken" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_token(monkeypatch):
    fake = FakeTioneClient(group=_group([]))
    _make_module(monkeypatch, fake)
    _name_args(state="present", description="client token")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Base"]["Name"] == NAME
    assert "Value" not in result["auth_token"]["Base"]
    assert result["token_id"].startswith("token-new-")
    assert len((fake.group or {}).get("AuthTokens") or []) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateModelServiceAuthToken" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(group=_group([]))
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", description="client token")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Base"]["Name"] == NAME
    assert result["token_id"] is None
    assert (fake.group or {}).get("AuthTokens") == []
    assert "CreateModelServiceAuthToken" not in [c for c, unused in fake.calls]


def test_create_with_limits_applies_after_create(monkeypatch):
    fake = FakeTioneClient(group=_group([]))
    _make_module(monkeypatch, fake)
    _name_args(state="present", limits=LIMITS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Limits"] == LIMITS
    ops = [c for c, unused in fake.calls]
    assert "CreateModelServiceAuthToken" in ops
    assert "ModifyModelServiceAuthToken" in ops


def test_create_with_show_token_value(monkeypatch):
    fake = FakeTioneClient(group=_group([]))
    _make_module(monkeypatch, fake)
    _name_args(state="present", show_token_value=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Base"]["Value"].startswith("generated-value-")


def test_requested_token_id_does_not_exist(monkeypatch):
    fake = FakeTioneClient(group=_group([]))
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "requested token_id does not exist"


def test_missing_service_group_fails(monkeypatch):
    fake = FakeTioneClient(group=None)
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TIONE service group does not exist" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-token flows
# ---------------------------------------------------------------------------


def test_existing_token_no_drift_is_idempotent(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _name_args(state="present", description="client token")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["auth_token"]["Base"]["Id"] == TOKEN_ID


def test_description_drift_updates_token(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _name_args(state="present", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Base"]["Description"] == "renamed description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyModelServiceAuthToken" in ops


def test_rotate_from_token_id_rotates(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(state="present", name=NAME, rotate_from_token_id=TOKEN_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auth_token"]["Base"]["Id"] == TOKEN_ID
    ops = [c for c, unused in fake.calls]
    assert "ModifyModelServiceAuthToken" in ops
    modify = next(request for op, request in fake.calls if op == "ModifyModelServiceAuthToken")
    assert getattr(modify, "NeedReset", False) is True


def test_rotate_mismatch_is_idempotent(monkeypatch):
    fake = FakeTioneClient(group=_group([_token()]))
    _make_module(monkeypatch, fake)
    _id_args(state="present", name=NAME, rotate_from_token_id="other-token")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ModifyModelServiceAuthToken" not in [c for c, unused in fake.calls]


def test_multiple_name_matches_fail(monkeypatch):
    token_a = _token()
    token_b = _token(Base={"Id": "token-2"}, Limits=[])
    fake = FakeTioneClient(group=_group([token_a, token_b]))
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE auth tokens matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeModelServiceGroup(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tione_model_service_auth_token.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    def from_json_string(self, value):
        self.value = value


class LegacyModels(object):
    CreateModelServiceAuthTokenRequest = ModifyModelServiceAuthTokenRequest = DeleteModelServiceAuthTokenRequest = AuthToken = LegacyObject


class LegacyModule(object):
    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


LEGACY_TOKENS = [{
    "Base": {"Id": "t1", "Value": "secret", "Name": "prod", "Description": "old"},
    "Limits": [{"Strategy": "PerDay", "Max": 10}],
}]
LEGACY_P = {
    "service_group_id": "g1",
    "project_id": "p1",
    "token_id": "t1",
    "name": "prod",
    "description": "new",
    "limits": [{"Strategy": "PerMinute", "Max": 5}],
}


def test_find_prefers_stable_id_and_rejects_duplicate_names():
    assert mod.find(LegacyModule(), LEGACY_TOKENS, LEGACY_P)["Base"]["Id"] == "t1"
    try:
        mod.find(LegacyModule(), LEGACY_TOKENS * 2, dict(LEGACY_P, token_id=None))
    except ValueError:
        pass
    else:
        raise AssertionError("ambiguous token name was accepted")


def test_desired_preserves_identity_and_normalizes_limits():
    value = mod.desired(LEGACY_P, LEGACY_TOKENS[0])
    assert value["Base"]["Id"] == "t1" and value["Base"]["Description"] == "new"
    assert value["Limits"] == mod.normalized_limits(LEGACY_P["limits"])


def test_requests_keep_group_workspace_and_secret_identity():
    create = mod.create_request(LegacyModels, LEGACY_P)
    modify = mod.modify_request(LegacyModels, LEGACY_P, LEGACY_TOKENS[0], True)
    delete = mod.delete_request(LegacyModels, LEGACY_P, LEGACY_TOKENS[0])
    assert (create.ServiceGroupId, create.TiProjectId, create.Name) == ("g1", "p1", "prod")
    assert modify.NeedReset is True and '"Id": "t1"' in modify.AuthToken.value
    assert delete.AuthTokenValue == "secret"


def test_sanitize_removes_value_unless_explicitly_requested():
    assert "Value" not in mod.sanitize(LEGACY_TOKENS[0])["Base"]
    assert mod.sanitize(LEGACY_TOKENS[0], True)["Base"]["Value"] == "secret"
