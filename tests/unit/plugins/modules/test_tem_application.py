"""Unit tests for the tem_application write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/tem_application.py`` with an in-memory fake TEM client
whose write operations mutate the application store, so the module's
post-write ``find`` refetch converges immediately. Applications are matched
by ``application_id`` or by ``ApplicationName`` across the paged
DescribeApplications; only ApplicationName is immutable, and updates are
limited to Description + EnableTracing via ModifyApplicationInfo. The
create response carries the new id directly on ``.Result``. The
``default_repo_parameters`` payload round-trips through a fake
UseDefaultRepoParameters model that implements ``from_json_string``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tem_application as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

APP = {
    "ApplicationId": "app-1",
    "ApplicationName": "order-api",
    "Description": "Order service",
    "EnableTracing": 0,
}


def _app(**overrides):
    """API-shaped application dict isolated from the shared constant."""
    item = copy.deepcopy(APP)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "application_id": None,
        "name": "order-api",
        "description": "Order service",
        "use_default_image_service": None,
        "repo_type": None,
        "instance_id": None,
        "repo_server": None,
        "repo_name": None,
        "source_channel": 0,
        "subnet_ids": None,
        "coding_language": None,
        "deploy_mode": None,
        "enable_tracing": None,
        "default_repo_parameters": None,
        "tags": None,
        "environment_id": None,
        "delete_if_no_running_version": True,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _JsonModel(object):
    """SDK model whose payload round-trips through from_json_string."""

    def from_json_string(self, payload):
        for key, value in json.loads(payload).items():
            setattr(self, key, value)
        return self


class FakeTemModels(FakeModels):
    """FakeModels whose UseDefaultRepoParameters implements from_json_string."""

    def __getattr__(self, name):
        if name == "UseDefaultRepoParameters":
            return _JsonModel
        return super(FakeTemModels, self).__getattr__(name)


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


class FakeTemClient(object):
    """In-memory TemClient stand-in for applications.

    Stores API-shaped application dicts. DescribeApplications pages over the
    store honouring Offset/Limit; write operations mutate the store so
    post-write refetches converge.
    """

    def __init__(self, applications=None):
        self.applications = [copy.deepcopy(a) for a in (applications or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "app-%d" % self._next_id

    def DescribeApplications(self, request):
        self._record("DescribeApplications", request)
        page = self.applications[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Result=SimpleNamespace(
                Records=[FakeResource(dict(a)) for a in page],
                Total=len(self.applications),
            ),
            RequestId="req-fake",
        )

    def CreateApplication(self, request):
        self._record("CreateApplication", request)
        app_id = self._new_id()
        self.applications.append(
            {
                "ApplicationId": app_id,
                "ApplicationName": request.ApplicationName,
                "Description": request.Description,
                "EnableTracing": request.EnableTracing,
            }
        )
        return SimpleNamespace(Result=app_id, RequestId="req-fake")

    def ModifyApplicationInfo(self, request):
        self._record("ModifyApplicationInfo", request)
        for stored in self.applications:
            if stored.get("ApplicationId") != request.ApplicationId:
                continue
            if request.Description is not None:
                stored["Description"] = request.Description
            if request.EnableTracing is not None:
                stored["EnableTracing"] = request.EnableTracing
        return SimpleNamespace(RequestId="req-fake")

    def DeleteApplication(self, request):
        self._record("DeleteApplication", request)
        self.applications = [a for a in self.applications if a.get("ApplicationId") != request.ApplicationId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeTemModels(), SimpleNamespace(TemClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeTemModels(), _params())
    assert request.ApplicationId is None
    assert request.Keyword == "order-api"  # name lookup drives Keyword
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.SourceChannel == 0


def test_describe_request_with_application_id_clears_keyword():
    request = mod.describe_request(FakeTemModels(), _params(application_id="app-9", name=None), offset=100)
    assert request.ApplicationId == "app-9"
    assert request.Keyword is None
    assert request.Offset == 100


def test_tags_builder_sorted():
    items = mod._tags(FakeTemModels(), {"z": "2", "a": "1"})
    assert [(x.TagKey, x.TagValue) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeTemModels(), None) == []
    assert mod._tags(FakeTemModels(), {}) == []


def test_model_none_returns_none():
    assert mod._model(FakeTemModels().UseDefaultRepoParameters, None) is None


def test_model_round_trips_json_payload():
    obj = mod._model(FakeTemModels().UseDefaultRepoParameters, {"RepoName": "nginx", "RepoServer": "ccr.ccs.tencentyun.com"})
    assert obj.RepoName == "nginx"
    assert obj.RepoServer == "ccr.ccs.tencentyun.com"


def test_create_request_fields():
    request = mod.create_request(
        FakeTemModels(),
        _params(
            use_default_image_service=1,
            repo_type=0,
            instance_id="ins-1",
            repo_server="ccr.ccs.tencentyun.com",
            repo_name="team/order",
            subnet_ids=["subnet-1"],
            coding_language="JAVA",
            deploy_mode="IMAGE",
            enable_tracing=1,
            default_repo_parameters={"RepoName": "nginx"},
            tags={"env": "prod"},
        ),
    )
    assert request.ApplicationName == "order-api"
    assert request.Description == "Order service"
    assert request.UseDefaultImageService == 1
    assert request.RepoType == 0
    assert request.InstanceId == "ins-1"
    assert request.RepoServer == "ccr.ccs.tencentyun.com"
    assert request.RepoName == "team/order"
    assert request.SourceChannel == 0
    assert request.SubnetList == ["subnet-1"]
    assert request.CodingLanguage == "JAVA"
    assert request.DeployMode == "IMAGE"
    assert request.EnableTracing == 1
    assert request.UseDefaultImageServiceParameters.RepoName == "nginx"
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("env", "prod")]


def test_create_request_leaves_optionals_none():
    request = mod.create_request(FakeTemModels(), _params())
    assert request.Description is None or request.Description == "Order service"
    assert request.UseDefaultImageService is None
    assert request.SubnetList is None
    assert request.UseDefaultImageServiceParameters is None
    assert request.Tags == []  # _tags() normalises None to an empty list


def test_update_request_fields():
    request = mod.update_request(FakeTemModels(), _params(enable_tracing=1), "app-1", "new-desc")
    assert request.ApplicationId == "app-1"
    assert request.Description == "new-desc"
    assert request.SourceChannel == 0
    assert request.EnableTracing == 1


def test_delete_request_fields():
    request = mod.delete_request(FakeTemModels(), _params(environment_id="env-1", delete_if_no_running_version=False), "app-1")
    assert request.ApplicationId == "app-1"
    assert request.EnvironmentId == "env-1"
    assert request.SourceChannel == 0
    assert request.DeleteApplicationIfNoRunningVersion is False


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_application_id(monkeypatch):
    fake = FakeTemClient([_app(), _app(ApplicationId="app-2", ApplicationName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(application_id="app-2", name=None))
    value = mod.find(module, fake, FakeTemModels(), module.params)
    assert value["ApplicationId"] == "app-2"


def test_find_by_name(monkeypatch):
    fake = FakeTemClient([_app(ApplicationName="other"), _app()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="order-api"))
    value = mod.find(module, fake, FakeTemModels(), module.params)
    assert value["ApplicationId"] == "app-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeTemModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTemClient([_app(), _app(ApplicationId="app-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="order-api"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeTemModels(), module.params)
    assert "Multiple TEM applications matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    apps = [_app(ApplicationId="bulk-%04d" % i, ApplicationName="bulk-%04d" % i) for i in range(101)]
    apps.append(_app())
    fake = FakeTemClient(apps)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="order-api"))
    value = mod.find(module, fake, FakeTemModels(), module.params)
    assert value["ApplicationId"] == "app-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribeApplications"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither application_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_application(monkeypatch):
    fake = FakeTemClient()
    _make_module(monkeypatch, fake)
    _run_args(use_default_image_service=1, coding_language="JAVA", deploy_mode="IMAGE")
    result = run(mod.run_module)
    assert result["changed"] is True
    app = result["application"]
    assert app["ApplicationId"] == "app-101"
    assert app["ApplicationName"] == "order-api"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeApplications") == 2  # find + refetch
    assert names.count("CreateApplication") == 1
    create = [c for c in fake.calls if c[0] == "CreateApplication"][0][1]
    assert create.ApplicationName == "order-api"
    assert create.UseDefaultImageService == 1
    assert create.CodingLanguage == "JAVA"
    assert create.DeployMode == "IMAGE"


def test_present_requires_name_to_create(monkeypatch):
    fake = FakeTemClient()
    _make_module(monkeypatch, fake)
    _run_args(application_id="app-ghost", name=None)  # id given but absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create a TEM application" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["application"]["ApplicationId"] == "app-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyApplicationInfo" not in names
    assert "CreateApplication" not in names


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(application_id="app-1", description="updated-desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["Description"] == "updated-desc"
    modify = [c for c in fake.calls if c[0] == "ModifyApplicationInfo"][0][1]
    assert modify.ApplicationId == "app-1"
    assert modify.Description == "updated-desc"


def test_present_enable_tracing_drift_triggers_update(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(application_id="app-1", enable_tracing=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["EnableTracing"] == 1
    modify = [c for c in fake.calls if c[0] == "ModifyApplicationInfo"][0][1]
    assert modify.ApplicationId == "app-1"
    assert modify.EnableTracing == 1


def test_present_immutable_name_drift_fails(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(application_id="app-1", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["ApplicationName"]["before"] == "order-api"
    assert payload["immutable_changes"]["ApplicationName"]["after"] == "renamed"
    assert not any("ModifyApplicationInfo" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeTemModels(), SimpleNamespace(TemClient=object)),
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


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTemClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["ApplicationName"] == "order-api"  # desired reported
    assert not any("CreateApplication" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(application_id="app-1", description="new").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["Description"] == "new"  # desired reported
    assert not any("ModifyApplicationInfo" == c[0] for c in fake.calls)


def test_absent_deletes_application(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="order-api", environment_id="env-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteApplication"][0][1]
    assert delete.ApplicationId == "app-1"
    assert delete.EnvironmentId == "env-1"
    assert delete.DeleteApplicationIfNoRunningVersion is True
    assert fake.applications == []


def test_absent_keeps_running_version_flag(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", application_id="app-1", delete_if_no_running_version=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    delete = [c for c in fake.calls if c[0] == "DeleteApplication"][0][1]
    assert delete.DeleteApplicationIfNoRunningVersion is False


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["application"] is None
    assert not any("DeleteApplication" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient([_app()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DeleteApplication" == c[0] for c in fake.calls)
    assert len(fake.applications) == 1
