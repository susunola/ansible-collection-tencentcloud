"""Main-path (run_module) unit tests for the dlc_job_spec write module.

Complements ``test_dlc_job_spec.py`` (request-builder level) by driving
``run_module()`` end to end against an in-memory fake DLC client whose write
operations mutate a job-spec store so post-write ``find`` and waiters converge.

Scenario matrix:
* validation guards (priority bounds, group/cluster and resource conflicts,
  malformed JSON payloads)
* absent flows (missing, allow_delete guard, running-jobs guard, check mode,
  real delete)
* creation flows (entrypoint guard, check mode, real create with wait)
* idempotent no-op and drift updates (regular fields, tags, priority)
* pagination and multiple-match guards
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_job_spec as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SPEC = {
    "Id": "spec-123",
    "Name": "daily-ray-etl",
    "Entrypoint": "python main.py",
    "Description": "Daily ETL",
    "Image": "ccr.ccs.tencentyun.com/analytics/ray:stable",
    "ImagePullType": "Custom",
    "ImagePullPolicy": "Always",
    "ResourceConfigId": "rc-1",
    "GroupId": "cg-1",
    "Priority": 5,
    "Tags": [{"TagKey": "workload", "TagValue": "etl"}],
    "DispatchStrategy": "RANDOM",
    "HasRunningJobs": False,
}


def _spec(**overrides):
    item = copy.deepcopy(SPEC)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "daily-ray-etl"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a job-spec store."""

    def __init__(self, specs=None):
        self.specs = [copy.deepcopy(s) for s in (specs or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, spec_id):
        return next((s for s in self.specs if s.get("Id") == spec_id), None)

    def ListJobSpecs(self, request):
        self._record("ListJobSpecs", request)
        page = getattr(request, "Page", 1) or 1
        if page == 1:
            # Pagination scenario support: the single-spec case returns all.
            return SimpleNamespace(Items=[FakeResource(copy.deepcopy(s)) for s in self.specs], TotalPages=1)
        return SimpleNamespace(Items=[], TotalPages=page - 1)

    def CreateJobSpec(self, request):
        self._record("CreateJobSpec", request)
        self._next += 1
        item = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        item["Id"] = "spec-new-%03d" % self._next
        item["HasRunningJobs"] = False
        self.specs.append(item)
        return SimpleNamespace(Id=item["Id"])

    def UpdateJobSpec(self, request):
        self._record("UpdateJobSpec", request)
        item = self._by_id(getattr(request, "SpecId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for key, value in vars(request).items():
            if not key.startswith("_") and key not in ("SpecId",):
                item[key] = copy.deepcopy(value)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateJobSpecPriority(self, request):
        self._record("UpdateJobSpecPriority", request)
        item = self._by_id(getattr(request, "SpecId", None))
        if item is not None:
            item["Priority"] = getattr(request, "Priority", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteJobSpec(self, request):
        self._record("DeleteJobSpec", request)
        spec_id = getattr(request, "SpecId", None)
        self.specs = [s for s in self.specs if s.get("Id") != spec_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards (before any SDK call)
# ---------------------------------------------------------------------------


def test_priority_out_of_range_fails(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(priority=10)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "priority must be between 1 and 9" in exc.value.args[0]["msg"]


def test_group_and_cluster_mutually_exclusive(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(group_id="cg-1", cluster_id="cc-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_resource_config_and_id_mutually_exclusive(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(resource_config='{"cpu": 1}', resource_config_id="rc-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_invalid_json_field_fails(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(entrypoint="python main.py", resource_config="not-json")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_config must be valid JSON" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_spec_is_idempotent(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job_spec"] is None
    assert [c for c, unused in fake.calls] == ["ListJobSpecs"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_with_running_jobs_requires_allow_delete_running(monkeypatch):
    fake = FakeDlcClient(specs=[_spec(HasRunningJobs=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_running=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.specs) == 1
    assert "DeleteJobSpec" not in [c for c, unused in fake.calls]


def test_absent_deletes_spec(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.specs == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteJobSpec" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_entrypoint(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "entrypoint is required when creating" in exc.value.args[0]["msg"]


def test_create_spec(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        entrypoint="python main.py",
        description="Daily ETL",
        image="ccr.ccs.tencentyun.com/analytics/ray:stable",
        image_pull_type="Custom",
        image_pull_policy="Always",
        resource_config_id="rc-1",
        group_id="cg-1",
        priority=5,
        tags=[{"key": "workload", "value": "etl"}],
        dispatch_strategy="RANDOM",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_spec"]["Name"] == "daily-ray-etl"
    assert result["job_spec"]["Entrypoint"] == "python main.py"
    assert len(fake.specs) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateJobSpec" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(specs=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", entrypoint="python main.py", image_pull_type="Custom")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.specs == []
    assert "CreateJobSpec" not in [c for c, unused in fake.calls]
    assert result["job_spec"]["Entrypoint"] == "python main.py"


# ---------------------------------------------------------------------------
# existing-spec flows
# ---------------------------------------------------------------------------


def test_existing_spec_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(state="present", entrypoint="python main.py", description="Daily ETL", priority=5)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job_spec"]["Id"] == "spec-123"
    assert result["job_spec_id"] == "spec-123"


def test_update_regular_field_drift(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(state="present", entrypoint="python train.py --epochs 5", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_spec"]["Entrypoint"] == "python train.py --epochs 5"
    ops = [c for c, unused in fake.calls]
    assert "UpdateJobSpec" in ops
    assert "UpdateJobSpecPriority" not in ops


def test_update_priority_only(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(state="present", priority=3, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_spec"]["Priority"] == 3
    ops = [c for c, unused in fake.calls]
    assert "UpdateJobSpecPriority" in ops
    assert "UpdateJobSpec" not in ops


def test_update_tags_drift(monkeypatch):
    fake = FakeDlcClient(specs=[_spec(Tags=[])])
    _make_module(monkeypatch, fake)
    _base(state="present", tags=[{"key": "env", "value": "prod"}], wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_spec"]["Tags"] == [{"TagKey": "env", "TagValue": "prod"}]


def test_update_resource_config_drift(monkeypatch):
    fake = FakeDlcClient(specs=[_spec(ResourceConfig='{"cpu":1}')])
    _make_module(monkeypatch, fake)
    _base(state="present", resource_config='{"cpu": 4}', wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job_spec"]["ResourceConfig"] == '{"cpu":4}'


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(specs=[_spec()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", entrypoint="python train.py")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.specs[0]["Entrypoint"] == "python main.py"
    assert "UpdateJobSpec" not in [c for c, unused in fake.calls]
    assert result["job_spec"]["Entrypoint"] == "python train.py"


# ---------------------------------------------------------------------------
# pagination / multiple-match / failure
# ---------------------------------------------------------------------------


def test_find_paginates_to_locate_spec(monkeypatch):
    class PagedClient(object):
        def __init__(self):
            self.calls = []

        def ListJobSpecs(self, request):
            self.calls.append(getattr(request, "Page", 1))
            if getattr(request, "Page", 1) == 1:
                return SimpleNamespace(Items=[FakeResource(_spec(Name="other-spec"))], TotalPages=2)
            return SimpleNamespace(Items=[FakeResource(_spec())], TotalPages=2)

    fake = PagedClient()
    _make_module(monkeypatch, fake)
    _base(state="present", entrypoint="python main.py")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert fake.calls == [1, 2]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(specs=[_spec(), _spec(Id="spec-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC job specifications matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListJobSpecs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", entrypoint="python main.py")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_job_spec.py)
# ---------------------------------------------------------------------------


class LegacyRequest(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    ListJobSpecsRequest = LegacyRequest
    CreateJobSpecRequest = LegacyRequest
    UpdateJobSpecRequest = LegacyRequest
    DeleteJobSpecRequest = LegacyRequest
    UpdateJobSpecPriorityRequest = LegacyRequest


def test_json_and_tags_compare_semantically():
    current = mod.normalize({"Name": "etl", "RuntimeEnv": '{"b":2,"a":1}', "Tags": [{"TagValue": "prod", "TagKey": "env"}]})
    params = {"name": "etl", "runtime_env": '{"a":1,"b":2}', "tags": [{"key": "env", "value": "prod"}]}
    assert mod.drift(params, current) == {}


def test_requests_use_spec_id_and_normalized_payload():
    params = {"name": "etl", "entrypoint": "python main.py", "runtime_env": '{"z":1,"a":2}', "tags": [{"key": "b", "value": "2"}, {"key": "a", "value": "1"}]}
    create = mod.make_request(LegacyModels, params)
    update = mod.make_request(LegacyModels, params, update=True, spec_id="spec-1")
    delete = mod.delete_request(LegacyModels, "spec-1")
    listing = mod.list_request(LegacyModels, 2)
    assert create.RuntimeEnv == '{"a":2,"z":1}' and create.Tags[0]["TagKey"] == "a"
    assert update.SpecId == "spec-1" and delete.SpecId == "spec-1"
    assert not hasattr(update, "Priority")
    priority = mod.priority_request(LegacyModels, "spec-1", 7)
    assert priority.SpecId == "spec-1" and priority.Priority == 7
    assert listing.Page == 2 and listing.PageSize == 200
