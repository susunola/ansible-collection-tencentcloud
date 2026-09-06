"""Unit tests for the tcr_namespace write module (helpers + run_module).

Covers the create / settings-drift / delete flows of
``plugins/modules/tcr_namespace.py`` with an in-memory fake TCR client whose
write operations mutate the namespace store, so post-write refetches
converge. Namespaces are matched by ``RegistryId`` + ``Name`` against the
(All=true) DescribeNamespaces list; access and vulnerability settings are
enforced on existing namespaces with ModifyNamespace.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_namespace as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAMESPACE = {
    "Name": "team-a",
    "Public": False,
}


def _namespace(**overrides):
    """API-shaped namespace dict isolated from the shared constant."""
    item = copy.deepcopy(NAMESPACE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "registry_id": "tcr-abc",
        "name": "team-a",
        "is_public": False,
        "is_auto_scan": None,
        "is_prevent_vul": None,
        "severity": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _clean_params(**overrides):
    """_params() with None-valued keys dropped.

    ``severity`` is a no-default ``choices`` parameter; Ansible validates
    choices for every explicitly passed key, so a pre-filled None must be
    omitted or the module fails validation before any SDK call.
    """
    return {key: value for key, value in _params(**overrides).items() if value is not None}


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**dict(_clean_params(), **extra))


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


class FakeTcrClient(object):
    """In-memory TcrClient stand-in.

    Stores API-shaped namespace dicts. DescribeNamespaces returns the whole
    store (the module sets All=true); the write operations mutate the store
    so post-write refetches converge.
    """

    def __init__(self, namespaces=None):
        self.namespaces = [copy.deepcopy(n) for n in (namespaces or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    @staticmethod
    def _match(stored, request):
        return stored.get("Name") == request.NamespaceName and stored.get("RegistryId", "tcr-abc") == request.RegistryId

    def DescribeNamespaces(self, request):
        self._record("DescribeNamespaces", request)
        return SimpleNamespace(
            NamespaceList=[FakeResource(dict(n)) for n in self.namespaces],
            TotalCount=len(self.namespaces),
            RequestId="req-fake",
        )

    def CreateNamespace(self, request):
        self._record("CreateNamespace", request)
        entry = {"Name": request.NamespaceName, "Public": bool(request.IsPublic), "RegistryId": request.RegistryId}
        if getattr(request, "IsAutoScan", None) is not None:
            entry["AutoScan"] = bool(request.IsAutoScan)
        if getattr(request, "IsPreventVUL", None) is not None:
            entry["PreventVUL"] = bool(request.IsPreventVUL)
        if getattr(request, "Severity", None) is not None:
            entry["Severity"] = request.Severity
        self.namespaces.append(entry)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyNamespace(self, request):
        self._record("ModifyNamespace", request)
        for stored in self.namespaces:
            if stored.get("Name") != request.NamespaceName or stored.get("RegistryId", "tcr-abc") != request.RegistryId:
                continue
            if getattr(request, "IsPublic", None) is not None:
                stored["Public"] = bool(request.IsPublic)
            if getattr(request, "IsAutoScan", None) is not None:
                stored["AutoScan"] = bool(request.IsAutoScan)
            if getattr(request, "IsPreventVUL", None) is not None:
                stored["PreventVUL"] = bool(request.IsPreventVUL)
            if getattr(request, "Severity", None) is not None:
                stored["Severity"] = request.Severity
        return SimpleNamespace(RequestId="req-fake")

    def DeleteNamespace(self, request):
        self._record("DeleteNamespace", request)
        self.namespaces = [
            n for n in self.namespaces
            if n.get("Name") != request.NamespaceName or n.get("RegistryId", "tcr-abc") != request.RegistryId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_tcr",
        lambda: (FakeModels(), SimpleNamespace(TcrClient=object)),
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
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_build_describe_request_fields():
    request = mod.build_describe_request(FakeModels(), "tcr-abc", "team-a")
    assert request.RegistryId == "tcr-abc"
    assert request.NamespaceName == "team-a"
    assert request.All is True


def test_build_describe_request_without_name():
    request = mod.build_describe_request(FakeModels(), "tcr-abc", None)
    assert request.RegistryId == "tcr-abc"
    assert request.All is True
    assert not hasattr(request, "NamespaceName")


def test_build_create_request_base_fields():
    request = mod.build_create_request(FakeModels(), _params(is_public=True))
    assert request.RegistryId == "tcr-abc"
    assert request.NamespaceName == "team-a"
    assert request.IsPublic is True
    assert not hasattr(request, "IsAutoScan")
    assert not hasattr(request, "IsPreventVUL")
    assert not hasattr(request, "Severity")


def test_build_create_request_optional_fields():
    request = mod.build_create_request(FakeModels(), _params(is_auto_scan=True, is_prevent_vul=True, severity="high"))
    assert request.IsAutoScan is True
    assert request.IsPreventVUL is True
    assert request.Severity == "high"


def test_desired_settings_only_public_by_default():
    desired = mod._desired_settings(FakeModule(_params()))
    assert desired == {"Public": False}


def test_desired_settings_includes_configured():
    desired = mod._desired_settings(FakeModule(_params(is_public=True, is_auto_scan=True, is_prevent_vul=True, severity="medium")))
    assert desired == {"Public": True, "AutoScan": True, "PreventVUL": True, "Severity": "medium"}


def test_find_namespace_matches_by_name(monkeypatch):
    fake = FakeTcrClient([_namespace(Name="other"), _namespace()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_namespace(module, fake, FakeModels(), "tcr-abc", "team-a")
    assert value["Name"] == "team-a"


def test_find_namespace_no_match_returns_none(monkeypatch):
    fake = FakeTcrClient([_namespace(Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_namespace(module, fake, FakeModels(), "tcr-abc", "ghost") is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_registry_id_required():
    module_args(state="present", name="team-a")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "registry_id" in exc.value.args[0]["msg"]


def test_name_required():
    module_args(state="present", registry_id="tcr-abc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_tcr",
        lambda: (FakeModels(), SimpleNamespace(TcrClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_namespace(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Name"] == "team-a"
    assert result["namespace"]["Public"] is False
    assert "created" in result["msg"]
    assert len([c for c in fake.calls if c[0] == "CreateNamespace"]) == 1
    assert len([c for c in fake.calls if c[0] == "DescribeNamespaces"]) == 2  # find + refetch


def test_present_creates_with_settings(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    _run_args(is_auto_scan=True, is_prevent_vul=True, severity="high")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["AutoScan"] is True
    assert result["namespace"]["PreventVUL"] is True
    assert result["namespace"]["Severity"] == "high"
    create = [c for c in fake.calls if c[0] == "CreateNamespace"][0][1]
    assert create.IsAutoScan is True
    assert create.IsPreventVUL is True
    assert create.Severity == "high"


def test_present_noop_is_up_to_date(monkeypatch):
    fake = FakeTcrClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"]["Name"] == "team-a"
    assert "up to date" in result["msg"]
    assert not any(c[0] in ("CreateNamespace", "ModifyNamespace") for c in fake.calls)


def test_present_public_drift_triggers_update(monkeypatch):
    fake = FakeTcrClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(is_public=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Public"] is True
    assert "settings updated" in result["msg"]
    update = [c for c in fake.calls if c[0] == "ModifyNamespace"][0][1]
    assert update.IsPublic is True
    assert update.NamespaceName == "team-a"


def test_present_vulnerability_drift_triggers_update(monkeypatch):
    fake = FakeTcrClient([_namespace(Public=True)])
    _make_module(monkeypatch, fake)
    _run_args(is_public=True, is_auto_scan=True, is_prevent_vul=True, severity="low")
    result = run(mod.run_module)
    assert result["changed"] is True
    updated = result["namespace"]
    assert updated["AutoScan"] is True
    assert updated["PreventVUL"] is True
    assert updated["Severity"] == "low"
    update = [c for c in fake.calls if c[0] == "ModifyNamespace"][0][1]
    assert update.IsAutoScan is True
    assert update.IsPreventVUL is True
    assert update.Severity == "low"


def test_present_severity_only_drift(monkeypatch):
    fake = FakeTcrClient([_namespace(Public=False, AutoScan=True, PreventVUL=True, Severity="medium")])
    _make_module(monkeypatch, fake)
    _run_args(is_auto_scan=True, is_prevent_vul=True, severity="high")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Severity"] == "high"
    update = [c for c in fake.calls if c[0] == "ModifyNamespace"][0][1]
    assert update.Severity == "high"


def test_present_no_drift_with_full_settings(monkeypatch):
    fake = FakeTcrClient([_namespace(Public=False, AutoScan=True, PreventVUL=True, Severity="high")])
    _make_module(monkeypatch, fake)
    _run_args(is_public=False, is_auto_scan=True, is_prevent_vul=True, severity="high")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0] == "ModifyNamespace" for c in fake.calls)


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert not any(c[0] == "CreateNamespace" for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_namespace()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(is_public=True)))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert not any(c[0] == "ModifyNamespace" for c in fake.calls)


def test_absent_deletes_namespace(monkeypatch):
    fake = FakeTcrClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    assert "deleted" in result["msg"]
    delete = [c for c in fake.calls if c[0] == "DeleteNamespace"][0][1]
    assert delete.RegistryId == "tcr-abc"
    assert delete.NamespaceName == "team-a"
    assert fake.namespaces == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTcrClient([_namespace(Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(c[0] == "DeleteNamespace" for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_namespace()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete" in result["msg"]
    assert not any(c[0] == "DeleteNamespace" for c in fake.calls)
    assert len(fake.namespaces) == 1
