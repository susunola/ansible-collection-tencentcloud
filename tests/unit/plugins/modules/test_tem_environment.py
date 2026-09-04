"""Unit tests for the tem_environment write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/tem_environment.py`` with an in-memory fake TEM client
whose write operations mutate the environment store, so the module's
post-write ``find`` refetch converges immediately. Environments are matched
by ``environment_id`` or by ``EnvironmentName`` across the paged
DescribeEnvironments; EnvironmentName is immutable after creation and drift
on it fails with a replacement-required error. The create response carries
the new id directly on ``.Result``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tem_environment as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENV = {
    "EnvironmentId": "env-1",
    "EnvironmentName": "production",
    "Description": "Production TEM environment",
    "Vpc": "vpc-1",
    "SubnetId": ["subnet-1"],
    "EnvType": "prod",
}


def _env(**overrides):
    """API-shaped environment dict isolated from the shared constant."""
    item = copy.deepcopy(ENV)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "environment_id": None,
        "name": "production",
        "description": "Production TEM environment",
        "vpc_id": "vpc-1",
        "subnet_ids": ["subnet-1"],
        "kubernetes_version": None,
        "source_channel": 0,
        "enable_tsw_tracing": None,
        "tags": None,
        "environment_type": "prod",
        "create_region": None,
        "setup_vpc": None,
        "setup_prometheus": None,
        "prometheus_id": None,
        "apm_id": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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
    """In-memory TemClient stand-in for environments.

    Stores API-shaped environment dicts. DescribeEnvironments pages over the
    store honouring Offset/Limit; write operations mutate the store so
    post-write refetches converge.
    """

    def __init__(self, environments=None):
        self.environments = [copy.deepcopy(e) for e in (environments or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "env-%d" % self._next_id

    def DescribeEnvironments(self, request):
        self._record("DescribeEnvironments", request)
        page = self.environments[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Result=SimpleNamespace(
                Records=[FakeResource(dict(e)) for e in page],
                Total=len(self.environments),
            ),
            RequestId="req-fake",
        )

    def CreateEnvironment(self, request):
        self._record("CreateEnvironment", request)
        env_id = self._new_id()
        self.environments.append(
            {
                "EnvironmentId": env_id,
                "EnvironmentName": request.EnvironmentName,
                "Description": request.Description,
                "Vpc": request.Vpc,
                "SubnetId": list(request.SubnetIds or []),
                "EnvType": request.EnvType,
            }
        )
        return SimpleNamespace(Result=env_id, RequestId="req-fake")

    def ModifyEnvironment(self, request):
        self._record("ModifyEnvironment", request)
        for stored in self.environments:
            if stored.get("EnvironmentId") != request.EnvironmentId:
                continue
            stored["EnvironmentName"] = request.EnvironmentName
            stored["Description"] = request.Description
            stored["Vpc"] = request.Vpc
            stored["SubnetId"] = list(request.SubnetIds or [])
            stored["EnvType"] = request.EnvType
        return SimpleNamespace(RequestId="req-fake")

    def DestroyEnvironment(self, request):
        self._record("DestroyEnvironment", request)
        self.environments = [e for e in self.environments if e.get("EnvironmentId") != request.EnvironmentId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TemClient=object)),
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
    request = mod.describe_request(FakeModels(), _params())
    assert request.EnvironmentId is None
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.SourceChannel == 0


def test_describe_request_with_environment_id_and_offset():
    request = mod.describe_request(FakeModels(), _params(environment_id="env-9"), offset=100)
    assert request.EnvironmentId == "env-9"
    assert request.Offset == 100


def test_tags_builder_sorted():
    items = mod._tags(FakeModels(), {"z": "2", "a": "1"})
    assert [(x.TagKey, x.TagValue) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeModels(), None) == []
    assert mod._tags(FakeModels(), {}) == []


def test_create_request_fields():
    request = mod.create_request(
        FakeModels(),
        _params(kubernetes_version="1.24", enable_tsw_tracing=True, tags={"env": "prod"}),
    )
    assert request.EnvironmentName == "production"
    assert request.Description == "Production TEM environment"
    assert request.Vpc == "vpc-1"
    assert request.SubnetIds == ["subnet-1"]
    assert request.K8sVersion == "1.24"
    assert request.SourceChannel == 0
    assert request.EnableTswTraceService is True
    assert request.EnvType == "prod"
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("env", "prod")]


def test_create_request_optional_flags():
    request = mod.create_request(FakeModels(), _params(setup_vpc=True, setup_prometheus=True, prometheus_id="prom-1", apm_id="apm-1"))
    assert request.SetupVpc is True
    assert request.SetupPrometheus is True
    assert request.PrometheusId == "prom-1"
    assert request.ApmId == "apm-1"


def test_update_request_fields():
    target = {"EnvironmentName": "production", "Description": "new-desc", "Vpc": "vpc-1", "SubnetIds": ["subnet-2"], "EnvType": "prod"}
    request = mod.update_request(FakeModels(), _params(), "env-1", target)
    assert request.EnvironmentId == "env-1"
    assert request.EnvironmentName == "production"
    assert request.Description == "new-desc"
    assert request.SubnetIds == ["subnet-2"]
    assert request.SourceChannel == 0
    assert request.EnvType == "prod"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), "env-1")
    assert request.EnvironmentId == "env-1"
    assert request.SourceChannel == 0


def test_comparable_normalises_subnet_field():
    value = mod.comparable(_env())
    assert value["SubnetIds"] == ["subnet-1"]
    assert value["EnvironmentName"] == "production"
    assert value["Vpc"] == "vpc-1"
    assert value["EnvType"] == "prod"


def test_comparable_scalar_subnet_becomes_list():
    assert mod.comparable(_env(SubnetId="subnet-9"))["SubnetIds"] == ["subnet-9"]
    assert mod.comparable(_env(SubnetId=None))["SubnetIds"] == []
    assert mod.comparable(_env(SubnetId=[]))["SubnetIds"] == []


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_environment_id(monkeypatch):
    fake = FakeTemClient([_env(), _env(EnvironmentId="env-2", EnvironmentName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(environment_id="env-2", name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvironmentId"] == "env-2"


def test_find_by_name(monkeypatch):
    fake = FakeTemClient([_env(EnvironmentName="other"), _env()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvironmentId"] == "env-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTemClient([_env(), _env(EnvironmentId="env-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple TEM environments matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    envs = [_env(EnvironmentId="bulk-%04d" % i, EnvironmentName="bulk-%04d" % i) for i in range(101)]
    envs.append(_env())
    fake = FakeTemClient(envs)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvironmentId"] == "env-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribeEnvironments"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither environment_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_environment(monkeypatch):
    fake = FakeTemClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    env = result["environment"]
    assert env["EnvironmentId"] == "env-101"
    assert env["EnvironmentName"] == "production"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeEnvironments") == 2  # find + refetch
    assert names.count("CreateEnvironment") == 1
    create = [c for c in fake.calls if c[0] == "CreateEnvironment"][0][1]
    assert create.Vpc == "vpc-1"


def test_present_requires_name_to_create(monkeypatch):
    fake = FakeTemClient()
    _make_module(monkeypatch, fake)
    _run_args(environment_id="env-ghost", name=None)  # id given but absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create a TEM environment" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["environment"]["EnvironmentId"] == "env-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyEnvironment" not in names
    assert "CreateEnvironment" not in names


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(environment_id="env-1", description="updated-desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["Description"] == "updated-desc"
    modify = [c for c in fake.calls if c[0] == "ModifyEnvironment"][0][1]
    assert modify.EnvironmentId == "env-1"
    assert modify.Description == "updated-desc"


def test_present_subnet_drift_triggers_update(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(environment_id="env-1", subnet_ids=["subnet-2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["SubnetId"] == ["subnet-2"]
    modify = [c for c in fake.calls if c[0] == "ModifyEnvironment"][0][1]
    assert modify.SubnetIds == ["subnet-2"]


def test_present_vpc_drift_triggers_update(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(environment_id="env-1", vpc_id="vpc-2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["Vpc"] == "vpc-2"
    modify = [c for c in fake.calls if c[0] == "ModifyEnvironment"][0][1]
    assert modify.Vpc == "vpc-2"


def test_present_immutable_name_drift_fails(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(environment_id="env-1", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["EnvironmentName"]["before"] == "production"
    assert payload["immutable_changes"]["EnvironmentName"]["after"] == "renamed"
    assert not any("ModifyEnvironment" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TemClient=object)),
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
    assert result["environment"]["EnvironmentName"] == "production"  # desired reported
    assert not any("CreateEnvironment" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(environment_id="env-1", description="new").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["Description"] == "new"  # desired reported
    assert not any("ModifyEnvironment" == c[0] for c in fake.calls)


def test_absent_destroys_environment(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"] is None
    destroy = [c for c in fake.calls if c[0] == "DestroyEnvironment"][0][1]
    assert destroy.EnvironmentId == "env-1"
    assert fake.environments == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["environment"] is None
    assert not any("DestroyEnvironment" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient([_env()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DestroyEnvironment" == c[0] for c in fake.calls)
    assert len(fake.environments) == 1
