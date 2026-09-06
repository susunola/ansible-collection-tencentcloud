"""Unit tests for the scf_trigger write module (helpers + run_module).

Creates, enables/disables, replaces and deletes SCF function triggers. A
trigger is identified by TriggerName + Type inside a function/namespace;
multiple matches fail. Only the enabled state is mutable in place
(UpdateTriggerStatus toggles OPEN/CLOSE); qualifier, trigger_desc,
custom_argument and description are immutable — any drift fails unless
force_replace is set, which recreates the trigger through delete-then-
create. Check mode never performs the replacement.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_trigger as mod
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


def _trigger(**overrides):
    """API-shaped trigger dict; fresh copy per call."""
    item = {
        "Enable": "OPEN",
        "Qualifier": "$LATEST",
        "TriggerName": "every-hour",
        "Type": "timer",
        "TriggerDesc": "0 0 * * * * *",
        "CustomArgument": None,
        "Description": "",
        "FunctionName": "rotate-logs",
        "Namespace": "default",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "function_name": "rotate-logs",
        "namespace": "default",
        "qualifier": "$LATEST",
        "name": "every-hour",
        "trigger_type": "timer",
        "trigger_desc": "0 0 * * * * *",
        "enabled": True,
        "custom_argument": None,
        "description": "",
        "force_replace": False,
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
    """In-memory ScfClient stand-in storing trigger dicts.

    ListTriggers returns the triggers of the requested function/namespace;
    CreateTrigger appends a trigger built from the request; DeleteTrigger
    removes the first trigger matching TriggerName + Type;
    UpdateTriggerStatus flips the Enable flag of that identity.
    """

    def __init__(self, triggers=None):
        self.triggers = [dict(t) for t in (triggers or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _identity(self, request):
        return request.TriggerName, request.Type

    def ListTriggers(self, request):
        self._record("ListTriggers", request)
        values = [
            t for t in self.triggers
            if t.get("FunctionName") == request.FunctionName and t.get("Namespace") == request.Namespace
        ]
        return SimpleNamespace(
            Triggers=[FakeResource(dict(t)) for t in values],
            RequestId="req-fake",
        )

    def CreateTrigger(self, request):
        self._record("CreateTrigger", request)
        stored = {
            "Enable": request.Enable,
            "Qualifier": request.Qualifier,
            "TriggerName": request.TriggerName,
            "Type": request.Type,
            "TriggerDesc": request.TriggerDesc,
            "CustomArgument": getattr(request, "CustomArgument", None),
            "Description": request.Description,
            "FunctionName": request.FunctionName,
            "Namespace": request.Namespace,
        }
        self.triggers.append(stored)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateTriggerStatus(self, request):
        self._record("UpdateTriggerStatus", request)
        name, trigger_type = self._identity(request)
        for trigger in self.triggers:
            if trigger["TriggerName"] == name and trigger["Type"] == trigger_type:
                trigger["Enable"] = request.Enable
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTrigger(self, request):
        self._record("DeleteTrigger", request)
        name, trigger_type = self._identity(request)
        self.triggers = [
            t for t in self.triggers
            if not (t["TriggerName"] == name and t["Type"] == trigger_type)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ScfClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_find_returns_matching_trigger(monkeypatch):
    fake = FakeScfClient([
        _trigger(TriggerName="other", Type="timer"),
        _trigger(),
    ])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["TriggerName"] == "every-hour"
    request = module.sdk_calls[0][1]
    assert request.FunctionName == "rotate-logs"
    assert request.Namespace == "default"
    assert request.Offset == 0
    assert request.Limit == 100


def test_find_ignores_other_type(monkeypatch):
    fake = FakeScfClient([_trigger(TriggerName="every-hour", Type="cos")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeScfClient([_trigger(TriggerName="other", Type="timer")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multi_match_fails(monkeypatch):
    fake = FakeScfClient([_trigger(), _trigger(TriggerDesc="dup")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple SCF triggers match the requested identity" in payload["msg"]
    assert payload["name"] == "every-hour"


def test_delete_request_falls_back_to_param_desc():
    request = mod.delete_request(FakeModels(), _params())
    assert request.FunctionName == "rotate-logs"
    assert request.Namespace == "default"
    assert request.Qualifier == "$LATEST"
    assert request.TriggerName == "every-hour"
    assert request.Type == "timer"
    assert request.TriggerDesc == "0 0 * * * * *"


def test_delete_request_prefers_current_desc():
    request = mod.delete_request(FakeModels(), _params(), current={"TriggerDesc": "old-desc"})
    assert request.TriggerDesc == "old-desc"


def test_wanted_maps_enabled_state():
    value = mod.wanted(_params(enabled=False, custom_argument="--flag", description="d"))
    assert value["Enable"] == "CLOSE"
    assert value["Qualifier"] == "$LATEST"
    assert value["TriggerName"] == "every-hour"
    assert value["Type"] == "timer"
    assert value["TriggerDesc"] == "0 0 * * * * *"
    assert value["CustomArgument"] == "--flag"
    assert value["Description"] == "d"


def test_wanted_open_when_enabled():
    assert mod.wanted(_params())["Enable"] == "OPEN"


def test_create_builds_and_sends_request(monkeypatch):
    fake = FakeScfClient()
    module = FakeModule(_params(custom_argument="--flag"))
    mod.create(module, fake, FakeModels(), module.params)
    request = module.sdk_calls[0][1]
    assert request.FunctionName == "rotate-logs"
    assert request.Namespace == "default"
    assert request.Qualifier == "$LATEST"
    assert request.TriggerName == "every-hour"
    assert request.Type == "timer"
    assert request.TriggerDesc == "0 0 * * * * *"
    assert request.Enable == "OPEN"
    assert request.CustomArgument == "--flag"
    assert request.Description == ""


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_trigger_desc(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(trigger_desc=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "trigger_desc is required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["trigger"] is None
    assert [c[0] for c in fake.calls] == ["ListTriggers"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["TriggerName"] == "every-hour"
    assert result["diff"]["before"]["TriggerName"] == "every-hour"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["ListTriggers"]
    assert len(fake.triggers) == 1


def test_absent_deletes_trigger(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"] is None
    assert [c[0] for c in fake.calls] == ["ListTriggers", "DeleteTrigger"]
    deleted = fake.calls[1][1]
    assert deleted.TriggerName == "every-hour"
    assert deleted.Type == "timer"
    assert deleted.TriggerDesc == "0 0 * * * * *"
    assert fake.triggers == []


def test_present_noop_when_trigger_matches(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["trigger"]["TriggerName"] == "every-hour"
    assert [c[0] for c in fake.calls] == ["ListTriggers"]


def test_present_toggles_enabled_state(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["Enable"] == "CLOSE"
    assert [c[0] for c in fake.calls] == [
        "ListTriggers",
        "UpdateTriggerStatus",
        "ListTriggers",
    ]
    updated = fake.calls[1][1]
    assert updated.Enable == "CLOSE"
    assert updated.FunctionName == "rotate-logs"
    assert updated.Namespace == "default"
    assert updated.Qualifier == "$LATEST"
    assert updated.TriggerName == "every-hour"
    assert updated.Type == "timer"
    assert updated.TriggerDesc == "0 0 * * * * *"


def test_present_check_mode_toggle_is_dry_run(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["Enable"] == "OPEN"
    assert result["diff"]["after"]["Enable"] == "CLOSE"
    assert [c[0] for c in fake.calls] == ["ListTriggers"]


def test_qualifier_drift_requires_force_replace(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(qualifier="v1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "SCF trigger configuration is immutable" in payload["msg"]
    assert payload["trigger"]["TriggerName"] == "every-hour"
    assert [c[0] for c in fake.calls] == ["ListTriggers"]


def test_custom_argument_drift_requires_force_replace(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(custom_argument="--flag")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "set force_replace=true" in exc.value.args[0]["msg"]


def test_force_replace_recreates_trigger(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(qualifier="v1", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["Qualifier"] == "v1"
    assert [c[0] for c in fake.calls] == [
        "ListTriggers",
        "DeleteTrigger",
        "CreateTrigger",
        "ListTriggers",
    ]
    deleted = fake.calls[1][1]
    assert deleted.TriggerName == "every-hour"
    assert deleted.TriggerDesc == "0 0 * * * * *"
    created = fake.calls[2][1]
    assert created.Qualifier == "v1"
    assert created.Enable == "OPEN"
    assert len(fake.triggers) == 1


def test_force_replace_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient([_trigger()])
    _make_module(monkeypatch, fake)
    _run_args(qualifier="v1", force_replace=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["Qualifier"] == "$LATEST"
    assert result["diff"]["before"]["Qualifier"] == "$LATEST"
    assert result["diff"]["after"]["Qualifier"] == "v1"
    assert [c[0] for c in fake.calls] == ["ListTriggers"]
    assert len(fake.triggers) == 1


def test_present_creates_trigger(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(description="hourly", custom_argument="--x")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"]["TriggerName"] == "every-hour"
    assert result["trigger"]["Description"] == "hourly"
    assert [c[0] for c in fake.calls] == [
        "ListTriggers",
        "CreateTrigger",
        "ListTriggers",
    ]
    created = fake.calls[1][1]
    assert created.FunctionName == "rotate-logs"
    assert created.TriggerDesc == "0 0 * * * * *"
    assert created.Enable == "OPEN"
    assert created.CustomArgument == "--x"
    assert created.Description == "hourly"
    assert len(fake.triggers) == 1


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["trigger"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["TriggerName"] == "every-hour"
    assert [c[0] for c in fake.calls] == ["ListTriggers"]
    assert fake.triggers == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["trigger"] is None
