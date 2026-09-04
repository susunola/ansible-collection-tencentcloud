"""Unit tests for the scf_version write module (helpers + run_module).

Publishes (PublishVersion) and deletes (DeleteFunctionVersion) SCF
function versions. A version is identified by ``function_name`` +
``version`` (+ namespace): the module lists versions with
ListVersionByFunction and matches by string-compared Version number.
``$LATEST`` and ``default`` are rejected up front; the description is
only sent at publish time (None is never written); ForceDelete is only
set on the delete request when requested. Publishing an existing version
reports up to date, deleting an absent one is a noop.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_version as mod
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


def _version(**overrides):
    """API-shaped version dict; fresh copy per call."""
    item = {
        "Version": 2,
        "Description": "Deployed by ansible",
        "AddTime": "2026-08-28 10:00:00",
        "Status": "Active",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "function_name": "my-func",
        "version": "2",
        "namespace": "default",
        "description": None,
        "force_delete": False,
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
    """In-memory ScfClient stand-in storing version dicts.

    ListVersionByFunction returns every stored version (the module matches
    by string-compared Version); PublishVersion appends a fresh version
    numbered with the configured ``publish_creates`` (the real API assigns
    the number, which the module then re-lists to confirm); DeleteFunction
    removes the version whose number matches the request Qualifier.
    """

    def __init__(self, versions=None, publish_creates=2):
        self.versions = [dict(v) for v in (versions or [])]
        self.publish_creates = publish_creates
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListVersionByFunction(self, request):
        self._record("ListVersionByFunction", request)
        return SimpleNamespace(
            Versions=[FakeResource(dict(v)) for v in self.versions],
            RequestId="req-fake",
        )

    def PublishVersion(self, request):
        self._record("PublishVersion", request)
        stored = {
            "Version": self.publish_creates,
            "Description": getattr(request, "Description", None),
        }
        self.versions.append(stored)
        return SimpleNamespace(
            Version=self.publish_creates,
            RequestId="req-fake",
        )

    def DeleteFunctionVersion(self, request):
        self._record("DeleteFunctionVersion", request)
        self.versions = [
            v for v in self.versions if str(v.get("Version")) != str(request.Qualifier)
        ]
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


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_build_list_request_fields():
    request = mod.build_list_request(FakeModels(), _params())
    assert request.FunctionName == "my-func"
    assert request.Namespace == "default"
    assert request.Limit == 100


def test_build_publish_request_with_description():
    request = mod.build_publish_request(FakeModels(), _params(description="Deployed by ansible"))
    assert request.FunctionName == "my-func"
    assert request.Namespace == "default"
    assert request.Description == "Deployed by ansible"


def test_build_publish_request_omits_description_when_none():
    request = mod.build_publish_request(FakeModels(), _params())
    assert not hasattr(request, "Description")


def test_find_version_returns_matching_version(monkeypatch):
    fake = FakeScfClient([_version(), _version(Version=3, Description="canary")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version="3"))
    value = mod.find_version(module, fake, FakeModels(), module.params)
    assert value["Version"] == 3
    assert value["Description"] == "canary"


def test_find_version_matches_string_to_int(monkeypatch):
    # The module compares string-cast versions, so an int payload matches.
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version="2"))
    value = mod.find_version(module, fake, FakeModels(), module.params)
    assert value["Version"] == 2


def test_find_version_no_match_returns_none(monkeypatch):
    fake = FakeScfClient([_version(Version=3)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version="2"))
    assert mod.find_version(module, fake, FakeModels(), module.params) is None


def test_publish_and_delete_issue_requests(monkeypatch):
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    params = _params()
    module = FakeModule(params)
    mod._publish(module, fake, FakeModels(), params)
    mod._delete(module, fake, FakeModels(), params)
    assert [c[0] for c in fake.calls] == ["PublishVersion", "DeleteFunctionVersion"]
    assert fake.calls[0][1].FunctionName == "my-func"
    assert fake.calls[0][1].Namespace == "default"
    assert fake.calls[1][1].Qualifier == "2"
    assert fake.calls[1][1].Namespace == "default"
    assert not hasattr(fake.calls[1][1], "ForceDelete")


def test_delete_force_delete_flag_set_when_requested():
    module = FakeModule()
    client = FakeScfClient()
    mod._delete(module, client, FakeModels(), _params(force_delete=True))
    assert client.calls[0][1].ForceDelete is True


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_latest_version_is_rejected(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    _run_args(version="$LATEST")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be managed" in exc.value.args[0]["msg"]


def test_default_version_is_rejected(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    _run_args(version="default")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be managed" in exc.value.args[0]["msg"]


def test_present_noop_when_version_exists(monkeypatch):
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF version already exists"
    assert result["version"]["Version"] == 2
    assert [c[0] for c in fake.calls] == ["ListVersionByFunction"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would publish SCF version"
    assert [c[0] for c in fake.calls] == ["ListVersionByFunction"]


def test_present_create_publishes_and_confirms(monkeypatch):
    fake = FakeScfClient(publish_creates=2)
    _make_module(monkeypatch, fake)
    _run_args(description="Deployed by ansible")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF version published"
    assert result["version"]["Version"] == 2
    assert [c[0] for c in fake.calls] == [
        "ListVersionByFunction",
        "PublishVersion",
        "ListVersionByFunction",
    ]
    assert fake.calls[1][1].Description == "Deployed by ansible"


def test_absent_noop_when_version_missing(monkeypatch):
    fake = FakeScfClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF version already absent"
    assert [c[0] for c in fake.calls] == ["ListVersionByFunction"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete SCF version"
    assert [c[0] for c in fake.calls] == ["ListVersionByFunction"]


def test_absent_delete_removes_version(monkeypatch):
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF version deleted"
    assert result["version"] is None
    assert [c[0] for c in fake.calls] == ["ListVersionByFunction", "DeleteFunctionVersion"]
    assert fake.calls[1][1].Qualifier == "2"
    assert fake.versions == []


def test_absent_delete_with_force_delete(monkeypatch):
    fake = FakeScfClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", force_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.calls[1][1].ForceDelete is True


def test_find_failure_reports_sdk_error(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
