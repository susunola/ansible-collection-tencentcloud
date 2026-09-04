"""Unit tests for the scf_alias write module (helpers + run_module).

Creates, updates and deletes SCF function aliases. An alias is
identified by ``function_name`` + ``name`` (+ namespace); GetAlias is the
single lookup and raises a ResourceNotFound-style SDK error for a missing
alias, which run_module maps to ``current=None``. ``function_version`` is
mandatory for every state (it is validated before the state dispatch).
Present drift on FunctionVersion/Description becomes UpdateAlias; a
matching alias reports up to date. Description is only sent to
Create/UpdateAlias when given (None is never written).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_alias as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _alias(**overrides):
    """API-shaped alias dict; fresh copy per call."""
    item = {
        "FunctionName": "my-func",
        "Name": "prod",
        "Namespace": "default",
        "FunctionVersion": "2",
        "Description": "Production traffic",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "function_name": "my-func",
        "name": "prod",
        "function_version": None,
        "namespace": "default",
        "description": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeScfClient(object):
    """In-memory ScfClient stand-in storing alias dicts.

    GetAlias raises a ResourceNotFound-style :class:`_SdkError` when no
    alias matches function_name + name + namespace, mirroring the real
    API; Create/Update/Delete key off the same identity fields.
    """

    def __init__(self, aliases=None):
        self.aliases = [dict(a) for a in (aliases or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _index(self, request):
        return {
            "FunctionName": request.FunctionName,
            "Name": request.Name,
            "Namespace": getattr(request, "Namespace", "default"),
        }

    def _find(self, identity):
        for stored in self.aliases:
            if all(stored.get(k) == v for k, v in identity.items()):
                return stored
        return None

    def GetAlias(self, request):
        self._record("GetAlias", request)
        stored = self._find(self._index(request))
        if stored is None:
            raise _SdkError("ResourceNotFound.Alias", "alias not found", request_id="req-nf")
        return FakeResource(dict(stored))

    def CreateAlias(self, request):
        self._record("CreateAlias", request)
        identity = self._index(request)
        stored = {
            "FunctionName": identity["FunctionName"],
            "Name": identity["Name"],
            "Namespace": identity["Namespace"],
            "FunctionVersion": request.FunctionVersion,
        }
        if getattr(request, "Description", None) is not None:
            stored["Description"] = request.Description
        self.aliases.append(stored)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateAlias(self, request):
        self._record("UpdateAlias", request)
        stored = self._find(self._index(request))
        if stored is not None:
            stored["FunctionVersion"] = request.FunctionVersion
            if getattr(request, "Description", None) is not None:
                stored["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAlias(self, request):
        self._record("DeleteAlias", request)
        identity = self._index(request)
        self.aliases = [a for a in self.aliases if not all(a.get(k) == v for k, v in identity.items())]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_scf",
        lambda: (FakeModels(), SimpleNamespace(ScfClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_build_get_request_fields():
    request = mod.build_get_request(FakeModels(), _params(function_version="2"))
    assert request.FunctionName == "my-func"
    assert request.Name == "prod"
    assert request.Namespace == "default"


def test_find_alias_returns_serialized_alias(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(function_version="2"))
    value = mod.find_alias(module, fake, FakeModels(), module.params)
    assert value["Name"] == "prod"
    assert value["FunctionVersion"] == "2"


def test_find_alias_raises_when_missing(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(function_version="2"))
    with pytest.raises(_SdkError) as exc:
        mod.find_alias(module, fake, FakeModels(), module.params)
    assert exc.value.get_code().startswith("ResourceNotFound")


def test_build_create_request_with_description():
    request = mod.build_create_request(FakeModels(), _params(function_version="3", description="Canary"))
    assert request.FunctionName == "my-func"
    assert request.Name == "prod"
    assert request.FunctionVersion == "3"
    assert request.Namespace == "default"
    assert request.Description == "Canary"


def test_build_create_request_omits_description_when_none():
    request = mod.build_create_request(FakeModels(), _params(function_version="3"))
    assert not hasattr(request, "Description")


def test_create_update_delete_issue_requests(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    params = _params(function_version="3")
    module = FakeModule(params)
    mod._create(module, fake, FakeModels(), params)
    mod._update(module, fake, FakeModels(), params)
    mod._delete(module, fake, FakeModels(), params)
    assert [c[0] for c in fake.calls] == ["CreateAlias", "UpdateAlias", "DeleteAlias"]
    assert fake.calls[0][1].FunctionVersion == "3"
    assert fake.calls[1][1].Name == "prod"
    assert fake.calls[2][1].Namespace == "default"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_function_version_required_for_every_state():
    module_args(state="absent", function_name="my-func", name="prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "function_version is required to identify the alias target" in exc.value.args[0]["msg"]


def test_present_creates_alias(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(function_version="2", description="Production traffic")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias created"
    assert result["alias"]["FunctionVersion"] == "2"
    assert result["alias"]["Description"] == "Production traffic"
    assert [c[0] for c in fake.calls] == ["GetAlias", "CreateAlias", "GetAlias"]  # find + create + refetch
    assert fake.aliases[0]["Name"] == "prod"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, function_version="2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create SCF alias"
    assert not any(c[0] == "CreateAlias" for c in fake.calls)
    assert fake.aliases == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(function_version="2", description="Production traffic")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF alias is up to date"
    assert result["alias"]["FunctionVersion"] == "2"
    assert not any(c[0] in ("CreateAlias", "UpdateAlias") for c in fake.calls)


def test_present_version_drift_triggers_update(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(function_version="3", description="Production traffic")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias updated"
    assert result["alias"]["FunctionVersion"] == "3"
    assert result["alias"]["Description"] == "Production traffic"  # untouched field kept
    update = [c for c in fake.calls if c[0] == "UpdateAlias"][0][1]
    assert update.FunctionVersion == "3"
    assert "CreateAlias" not in [c[0] for c in fake.calls]


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(function_version="2", description="Canary traffic")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias"]["Description"] == "Canary traffic"
    update = [c for c in fake.calls if c[0] == "UpdateAlias"][0][1]
    assert update.Description == "Canary traffic"
    assert update.FunctionVersion == "2"


def test_present_description_cleared_via_empty_string(monkeypatch):
    # Description None means "not sent", so an existing description is
    # cleared by passing an explicit empty string.
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(function_version="2", description="")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alias"].get("Description") is None or result["alias"]["Description"] == ""
    update = [c for c in fake.calls if c[0] == "UpdateAlias"][0][1]
    assert update.Description == ""


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, function_version="3", description="Production traffic")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update SCF alias"
    assert not any(c[0] == "UpdateAlias" for c in fake.calls)
    assert fake.aliases[0]["FunctionVersion"] == "2"


def test_absent_already_absent_is_noop(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", function_version="2")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF alias already absent"
    assert not any(c[0] == "DeleteAlias" for c in fake.calls)


def test_absent_deletes_alias(monkeypatch):
    fake = FakeScfClient([_alias(), _alias(Name="dev")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", function_version="2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias deleted"
    assert result["alias"] is None
    assert [a["Name"] for a in fake.aliases] == ["dev"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient([_alias()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent", function_version="2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete SCF alias"
    assert not any(c[0] == "DeleteAlias" for c in fake.calls)
    assert len(fake.aliases) == 1


def test_non_not_found_error_is_reported(monkeypatch):
    class _FailingClient(object):
        def GetAlias(self, request):
            raise _SdkError("AuthFailure", "no permission", request_id="req-err")

    fake = _FailingClient()
    _make_module(monkeypatch, fake)
    _run_args(function_version="2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "no permission"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
