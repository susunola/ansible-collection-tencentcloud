"""Unit tests for the cdb_audit_config write module (helpers + run_module).

Enables, configures or closes database audit logging for a CDB instance.
The module is converge-only (no state/absent path): the desired target is
derived from ``enabled`` and ``retention_days`` (retention collapses to 0
when disabled) and compared against the normalized DescribeAuditConfig
response. ``normalize`` maps a raw response onto ``{enabled, retention_days}``
where enabled requires a positive LogExpireDay *and* IsClosing != true.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_audit_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "instance_id": "cdb-abc123",
        "enabled": True,
        "retention_days": 30,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _describe_response(log_expire_day, is_closing=None):
    data = {"LogExpireDay": log_expire_day}
    if is_closing is not None:
        data["IsClosing"] = is_closing
    return FakeResource(data)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing one instance's audit state.

    DescribeAuditConfig reports ``{LogExpireDay, IsClosing}``;
    ModifyAuditConfig applies the request: closing zeroes LogExpireDay (the
    steady disabled state), enabling stores the requested retention.
    """

    def __init__(self, state=None):
        self.state = dict(state or {"LogExpireDay": 0, "IsClosing": False})
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeAuditConfig(self, request):
        self._record("DescribeAuditConfig", request)
        return FakeResource(dict(self.state))

    def ModifyAuditConfig(self, request):
        self._record("ModifyAuditConfig", request)
        if request.CloseAudit:
            self.state = {"LogExpireDay": 0, "IsClosing": False}
        else:
            self.state = {"LogExpireDay": request.LogExpireDay, "IsClosing": False}
        return SimpleNamespace(RequestId="req-fake")


_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(CdbClient=object)


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder and normalize helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_instance_id():
    request = mod.describe_request(FakeModels(), "cdb-abc123")
    assert request.InstanceId == "cdb-abc123"


def test_modify_request_enabled_sets_close_false_and_retention():
    request = mod.modify_request(FakeModels(), _params(enabled=True, retention_days=180))
    assert request.InstanceId == "cdb-abc123"
    assert request.CloseAudit is False
    assert request.LogExpireDay == 180


def test_modify_request_disabled_sets_close_true_and_omits_retention():
    request = mod.modify_request(FakeModels(), _params(enabled=False, retention_days=180))
    assert request.CloseAudit is True
    assert not hasattr(request, "LogExpireDay")  # retention never sent when closing


def test_normalize_enabled_open_audit():
    assert mod.normalize(_describe_response(30, is_closing=False)) == {"enabled": True, "retention_days": 30}


def test_normalize_enabled_when_isclosing_absent():
    assert mod.normalize(_describe_response(180)) == {"enabled": True, "retention_days": 180}


def test_normalize_isclosing_true_disables_even_with_retention():
    assert mod.normalize(_describe_response(30, is_closing=True)) == {"enabled": False, "retention_days": 30}


def test_normalize_isclosing_string_true_disables():
    response = FakeResource({"LogExpireDay": 30, "IsClosing": "true"})
    assert mod.normalize(response) == {"enabled": False, "retention_days": 30}


def test_normalize_zero_retention_disables():
    assert mod.normalize(_describe_response(0, is_closing=False)) == {"enabled": False, "retention_days": 0}


def test_normalize_missing_log_expire_day_disables():
    assert mod.normalize(FakeResource({})) == {"enabled": False, "retention_days": 0}


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_unchanged_enabled_is_noop(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 30, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit_config"] == {"enabled": True, "retention_days": 30}
    assert not any(name == "ModifyAuditConfig" for name, _ in fake.calls)


def test_unchanged_disabled_is_noop(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 0, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args(enabled=False, retention_days=365)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit_config"] == {"enabled": False, "retention_days": 0}


def test_enable_audit_from_disabled(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 0, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args(enabled=True, retention_days=180)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit_config"] == {"enabled": True, "retention_days": 180}
    assert [name for name, _ in fake.calls] == ["DescribeAuditConfig", "ModifyAuditConfig", "DescribeAuditConfig"]
    modify = [req for name, req in fake.calls if name == "ModifyAuditConfig"][0]
    assert modify.CloseAudit is False
    assert modify.LogExpireDay == 180


def test_retention_drift_updates_existing(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 30, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args(enabled=True, retention_days=365)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit_config"] == {"enabled": True, "retention_days": 365}
    modify = [req for name, req in fake.calls if name == "ModifyAuditConfig"][0]
    assert modify.CloseAudit is False
    assert modify.LogExpireDay == 365


def test_disable_audit(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 30, "IsClosing": False})
    _make_module(monkeypatch, fake)
    # Fake request classes: the real SDK model always exposes LogExpireDay
    # (defaulting to None), so attribute-absence can only be asserted with
    # the fake models.
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CdbClient=object)))
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit_config"] == {"enabled": False, "retention_days": 0}
    modify = [req for name, req in fake.calls if name == "ModifyAuditConfig"][0]
    assert modify.CloseAudit is True
    assert not hasattr(modify, "LogExpireDay")


def test_check_mode_enable_is_dry_run(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 0, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, enabled=True, retention_days=180)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit_config"] == {"enabled": False, "retention_days": 0}  # current, not target
    assert result["diff"]["before"] == {"enabled": False, "retention_days": 0}
    assert result["diff"]["after"] == {"enabled": True, "retention_days": 180}
    assert not any(name == "ModifyAuditConfig" for name, _ in fake.calls)
    assert fake.state == {"LogExpireDay": 0, "IsClosing": False}  # remote untouched


def test_check_mode_disable_is_dry_run(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 30, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["after"] == {"enabled": False, "retention_days": 0}
    assert not any(name == "ModifyAuditConfig" for name, _ in fake.calls)


def test_missing_instance_id_fails_validation():
    _run_args(instance_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id" in exc.value.args[0]["msg"]


def test_invalid_retention_choice_fails_validation():
    _run_args(retention_days=60)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_days" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCdbClient({"LogExpireDay": 30, "IsClosing": False})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["audit_config"] == {"enabled": True, "retention_days": 30}
