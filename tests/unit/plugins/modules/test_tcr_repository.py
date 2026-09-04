"""Unit tests for the tcr_repository write module (helpers + run_module).

Plain present/absent CRUD for a single repository inside a TCR Enterprise
registry, identified by ``registry_id`` + ``namespace`` + ``name``. The read
path converts SDK objects through ``json.loads(value.to_json_string())``, so
the fake repository objects here implement ``to_json_string()`` (not
``_serialize``). The module builds its failure envelope inline rather than via
``sdk_error_payload``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_repository as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


class FakeTcrResource(object):
    """SDK repository object stand-in: serializes through ``to_json_string``."""

    def __init__(self, data):
        self._data = dict(data)

    def to_json_string(self):
        return json.dumps(self._data)


def _repository(**overrides):
    """API-shaped repository dict isolated from the shared constant."""
    item = {
        "RegistryId": "tcr-abc",
        "NamespaceName": "production",
        "Name": "api",
        "RepositoryName": "api",
        "BriefDescription": "",
        "Description": "",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "registry_id": "tcr-abc",
        "namespace": "production",
        "name": "api",
        "brief_description": "",
        "description": "",
        "force_delete": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**dict(_params(), **extra))


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
    """In-memory TcrClient stand-in storing repository dicts per registry."""

    def __init__(self, repositories=None):
        self.repositories = [copy.deepcopy(r) for r in (repositories or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeRepositories(self, request):
        self._record("DescribeRepositories", request)
        matched = [
            r for r in self.repositories
            if r.get("RegistryId") == request.RegistryId and r.get("NamespaceName") == request.NamespaceName
        ]
        return SimpleNamespace(RepositoryList=[FakeTcrResource(r) for r in matched], RequestId="req-fake")

    def CreateRepository(self, request):
        self._record("CreateRepository", request)
        entry = {
            "RegistryId": request.RegistryId,
            "NamespaceName": request.NamespaceName,
            "Name": request.RepositoryName,
            "RepositoryName": request.RepositoryName,
            "BriefDescription": request.BriefDescription,
            "Description": request.Description,
        }
        self.repositories.append(entry)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRepository(self, request):
        self._record("ModifyRepository", request)
        for stored in self.repositories:
            if stored.get("Name") != request.RepositoryName or stored.get("RegistryId") != request.RegistryId:
                continue
            if stored.get("NamespaceName") != request.NamespaceName:
                continue
            stored["BriefDescription"] = request.BriefDescription
            stored["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRepository(self, request):
        self._record("DeleteRepository", request)
        self.repositories = [
            r for r in self.repositories
            if r.get("Name") != request.RepositoryName
            or r.get("RegistryId") != request.RegistryId
            or r.get("NamespaceName") != request.NamespaceName
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


def test_as_dict_none_returns_none():
    assert mod._as_dict(None) is None


def test_as_dict_parses_to_json_string():
    value = mod._as_dict(FakeTcrResource({"Name": "api", "Description": "d"}))
    assert value == {"Name": "api", "Description": "d"}


def test_find_repository_matches_by_name(monkeypatch):
    fake = FakeTcrClient([_repository(Name="other", RepositoryName="other"), _repository()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_repository(module, fake, FakeModels(), "tcr-abc", "production", "api")
    assert value["Name"] == "api"


def test_find_repository_matches_by_repository_name(monkeypatch):
    fake = FakeTcrClient([_repository(Name="production/api")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_repository(module, fake, FakeModels(), "tcr-abc", "production", "api")
    assert value["RepositoryName"] == "api"


def test_find_repository_no_match_returns_none(monkeypatch):
    fake = FakeTcrClient([_repository(Name="other", RepositoryName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_repository(module, fake, FakeModels(), "tcr-abc", "production", "ghost") is None


def test_find_repository_empty_repository_list(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_repository(module, fake, FakeModels(), "tcr-abc", "production", "api") is None


def test_find_repository_builds_request(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    mod.find_repository(module, fake, FakeModels(), "tcr-abc", "production", "api")
    name, request = module.sdk_calls[0]
    assert name.__name__ == "DescribeRepositories"
    assert request.RegistryId == "tcr-abc"
    assert request.NamespaceName == "production"
    assert request.RepositoryName == "api"
    assert request.Limit == 100


def test_build_create_request_sets_all_fields():
    request = mod.build_create_request(FakeModels(), _params(brief_description="brief", description="full"))
    assert request.RegistryId == "tcr-abc"
    assert request.NamespaceName == "production"
    assert request.RepositoryName == "api"
    assert request.BriefDescription == "brief"
    assert request.Description == "full"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_registry_id_required():
    module_args(state="present", namespace="production", name="api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "registry_id" in exc.value.args[0]["msg"]


def test_namespace_required():
    module_args(state="present", registry_id="tcr-abc", name="api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "namespace" in exc.value.args[0]["msg"]


def test_name_required():
    module_args(state="present", registry_id="tcr-abc", namespace="production")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported_inline(monkeypatch):
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
    assert payload["error_code"] is None
    assert payload["request_id"] is None


def test_present_creates_repository(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    _run_args(brief_description="Production API images")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["Name"] == "api"
    assert result["repository"]["BriefDescription"] == "Production API images"
    assert result["msg"] == "TCR repository created"
    assert len([c for c in fake.calls if c[0] == "CreateRepository"]) == 1
    assert len([c for c in fake.calls if c[0] == "DescribeRepositories"]) == 2  # find + refetch


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"] is None
    assert "Would create" in result["msg"]
    assert not any(c[0] == "CreateRepository" for c in fake.calls)


def test_present_noop_is_up_to_date(monkeypatch):
    fake = FakeTcrClient([_repository()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["repository"]["Name"] == "api"
    assert result["msg"] == "TCR repository is up to date"
    assert not any(c[0] in ("CreateRepository", "ModifyRepository", "DeleteRepository") for c in fake.calls)


def test_present_brief_description_drift_triggers_update(monkeypatch):
    fake = FakeTcrClient([_repository(BriefDescription="old")])
    _make_module(monkeypatch, fake)
    _run_args(brief_description="new brief")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["BriefDescription"] == "new brief"
    assert result["msg"] == "TCR repository updated"
    update = [c for c in fake.calls if c[0] == "ModifyRepository"][0][1]
    assert update.BriefDescription == "new brief"
    assert update.Description == ""


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeTcrClient([_repository(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(description="full new description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["Description"] == "full new description"
    update = [c for c in fake.calls if c[0] == "ModifyRepository"][0][1]
    assert update.Description == "full new description"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_repository(BriefDescription="old")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params(brief_description="new brief")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["BriefDescription"] == "old"
    assert "Would update" in result["msg"]
    assert not any(c[0] == "ModifyRepository" for c in fake.calls)


def test_absent_deletes_repository(monkeypatch):
    fake = FakeTcrClient([_repository()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", force_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"] is None
    assert result["msg"] == "TCR repository deleted"
    delete = [c for c in fake.calls if c[0] == "DeleteRepository"][0][1]
    assert delete.RegistryId == "tcr-abc"
    assert delete.NamespaceName == "production"
    assert delete.RepositoryName == "api"
    assert delete.ForceDelete is True
    assert fake.repositories == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTcrClient([_repository(Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["repository"] is None
    assert result["msg"] == "TCR repository already absent"
    assert not any(c[0] == "DeleteRepository" for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_repository()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["Name"] == "api"
    assert "Would delete" in result["msg"]
    assert not any(c[0] == "DeleteRepository" for c in fake.calls)
    assert len(fake.repositories) == 1
