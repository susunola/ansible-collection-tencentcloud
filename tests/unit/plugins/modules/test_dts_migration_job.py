"""Unit tests for the dts_migration_job write module (helpers + run_module).

Purchases, renames, resizes and destroys DTS migration jobs. A job is
looked up through DescribeMigrationJobs by JobId or by JobName (client
scan across pages). Creation needs the five database/region identity
fields and sets Count=1 with the instance class and tags; name drift
becomes ModifyMigrateName and instance-class drift (only when the job's
TradeInfo exposes one) becomes ModifyMigrateJobSpec.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dts_migration_job as mod
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


def _job(**overrides):
    """API-shaped migration-job dict; fresh copy per call."""
    item = {
        "JobId": "dts-1001",
        "JobName": "mysql-migration",
        "TradeInfo": {"InstanceClass": "micro"},
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "job_id": None,
        "name": "mysql-migration",
        "source_database_type": None,
        "destination_database_type": None,
        "source_region": None,
        "destination_region": None,
        "instance_class": "micro",
        "tags": {},
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


def _create_args():
    """The five identity fields required for a fresh migration job."""
    return {
        "source_database_type": "mysql",
        "destination_database_type": "mysql",
        "source_region": "ap-guangzhou",
        "destination_region": "ap-shanghai",
    }


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


class FakeDtsClient(object):
    """In-memory DtsClient stand-in storing migration-job dicts.

    DescribeMigrationJobs filters by JobId then JobName server-side and
    pages by Offset/Limit with TotalCount; CreateMigrationService
    synthesizes sequential JobIds; ModifyMigrateName /
    ModifyMigrateJobSpec patch the stored job; DestroyMigrateJob
    removes by JobId.
    """

    def __init__(self, jobs=None):
        self.jobs = [dict(j) for j in (jobs or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeMigrationJobs(self, request):
        self._record("DescribeMigrationJobs", request)
        job_id = getattr(request, "JobId", None)
        name = getattr(request, "JobName", None)
        values = self.jobs
        if job_id:
            values = [j for j in values if j["JobId"] == job_id]
        elif name:
            values = [j for j in values if j["JobName"] == name]
        offset = getattr(request, "Offset", 0)
        limit = getattr(request, "Limit", 100)
        return SimpleNamespace(
            JobList=[FakeResource(dict(j)) for j in values[offset : offset + limit]],
            TotalCount=len(values),
            RequestId="req-fake",
        )

    def CreateMigrationService(self, request):
        self._record("CreateMigrationService", request)
        stored = {
            "JobId": "dts-%04d" % self._seq,
            "JobName": request.JobName,
            "TradeInfo": {"InstanceClass": getattr(request, "InstanceClass", None)},
        }
        self._seq += 1
        self.jobs.append(stored)
        return SimpleNamespace(JobIds=[stored["JobId"]], RequestId="req-fake")

    def ModifyMigrateName(self, request):
        self._record("ModifyMigrateName", request)
        for stored in self.jobs:
            if stored["JobId"] == request.JobId:
                stored["JobName"] = request.JobName
        return SimpleNamespace(RequestId="req-fake")

    def ModifyMigrateJobSpec(self, request):
        self._record("ModifyMigrateJobSpec", request)
        for stored in self.jobs:
            if stored["JobId"] == request.JobId:
                stored.setdefault("TradeInfo", {})["InstanceClass"] = request.NewInstanceClass
        return SimpleNamespace(RequestId="req-fake")

    def DestroyMigrateJob(self, request):
        self._record("DestroyMigrateJob", request)
        self.jobs = [j for j in self.jobs if j["JobId"] != request.JobId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(DtsClient=object)),
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


def test_describe_request_sets_identity_and_paging():
    request = mod.describe_request(FakeModels(), job_id="dts-1001", name="mysql-migration", offset=50)
    assert request.JobId == "dts-1001"
    assert request.JobName == "mysql-migration"
    assert request.Offset == 50
    assert request.Limit == 100


def test_describe_request_defaults_paging():
    request = mod.describe_request(FakeModels())
    assert request.JobId is None
    assert request.JobName is None
    assert request.Offset == 0
    assert request.Limit == 100


def test_tag_list_sorts_and_stringifies():
    models = FakeModels()
    tags = mod.tag_list(models, {"zone": "cn", "env": "prod", "count": 3})
    assert [t.TagKey for t in tags] == ["count", "env", "zone"]
    assert tags[0].TagValue == "3"
    assert tags[1].TagValue == "prod"


def test_tag_list_empty():
    assert mod.tag_list(FakeModels(), {}) == []


def test_find_by_job_id(monkeypatch):
    fake = FakeDtsClient([_job(), _job(JobId="dts-1002", JobName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(job_id="dts-1002", name=None))
    value = mod.find(module, fake, FakeModels(), "dts-1002", None)
    assert value["JobId"] == "dts-1002"
    assert value["JobName"] == "other"


def test_find_by_name(monkeypatch):
    fake = FakeDtsClient([_job(), _job(JobId="dts-1002", JobName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(job_id=None, name="mysql-migration"))
    value = mod.find(module, fake, FakeModels(), None, "mysql-migration")
    assert value["JobId"] == "dts-1001"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeDtsClient([_job(JobName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(job_id=None, name="missing"))
    assert mod.find(module, fake, FakeModels(), None, "missing") is None


def test_find_multiple_name_matches_fail(monkeypatch):
    fake = FakeDtsClient([_job(), _job(JobId="dts-1002")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(job_id=None, name="mysql-migration"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), None, "mysql-migration")
    payload = exc.value.args[0]
    assert "Multiple DTS migration jobs have the requested name" in payload["msg"]
    assert payload["name"] == "mysql-migration"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", job_id="dts-ghost", name=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_job"] is None
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_absent_check_mode_destroy_is_dry_run(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", job_id="dts-1001", name=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["JobId"] == "dts-1001"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_absent_destroys_job(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", job_id="dts-1001", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"] is None
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs", "DestroyMigrateJob"]
    assert fake.calls[1][1].JobId == "dts-1001"
    assert fake.jobs == []


def test_create_requires_all_creation_params(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-ghost", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Creation parameters are required" in payload["msg"]
    assert payload["missing"] == [
        "name",
        "source_database_type",
        "destination_database_type",
        "source_region",
        "destination_region",
    ]


def test_create_requires_remaining_creation_params(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-ghost", name="mysql-migration")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["missing"] == [
        "source_database_type",
        "destination_database_type",
        "source_region",
        "destination_region",
    ]


def test_present_check_mode_create_reports_target(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _run_args(job_id=None, name="mysql-migration", _ansible_check_mode=True, **_create_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["JobName"] == "mysql-migration"
    assert result["diff"]["after"]["InstanceClass"] == "micro"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-ghost", name="mysql-migration", instance_class="small", tags={"env": "prod"}, **_create_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["JobId"] == "dts-2001"
    assert result["migration_job"]["JobName"] == "mysql-migration"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs", "CreateMigrationService", "DescribeMigrationJobs"]
    created = fake.calls[1][1]
    assert created.SrcDatabaseType == "mysql"
    assert created.DstDatabaseType == "mysql"
    assert created.SrcRegion == "ap-guangzhou"
    assert created.DstRegion == "ap-shanghai"
    assert created.InstanceClass == "small"
    assert created.Count == 1
    assert created.JobName == "mysql-migration"
    assert [t.TagKey for t in created.Tags] == ["env"]
    assert created.Tags[0].TagValue == "prod"


def test_present_noop(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="mysql-migration")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_job"]["JobId"] == "dts-1001"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_present_name_drift_triggers_rename(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="renamed-migration")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["JobName"] == "renamed-migration"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs", "ModifyMigrateName", "DescribeMigrationJobs"]
    assert fake.calls[1][1].JobId == "dts-1001"
    assert fake.calls[1][1].JobName == "renamed-migration"


def test_present_instance_class_drift_triggers_resize(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="mysql-migration", instance_class="small")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["TradeInfo"]["InstanceClass"] == "small"
    assert [c[0] for c in fake.calls] == [
        "DescribeMigrationJobs",
        "ModifyMigrateJobSpec",
        "DescribeMigrationJobs",
    ]
    assert fake.calls[1][1].JobId == "dts-1001"
    assert fake.calls[1][1].NewInstanceClass == "small"


def test_present_name_and_instance_drift_both_applied(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="renamed-migration", instance_class="large")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["JobName"] == "renamed-migration"
    assert result["migration_job"]["TradeInfo"]["InstanceClass"] == "large"
    assert [c[0] for c in fake.calls] == [
        "DescribeMigrationJobs",
        "ModifyMigrateName",
        "ModifyMigrateJobSpec",
        "DescribeMigrationJobs",
    ]


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeDtsClient([_job()])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="renamed-migration", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["JobName"] == "mysql-migration"
    assert result["diff"]["after"]["JobName"] == "renamed-migration"
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_present_class_ignored_without_trade_info(monkeypatch):
    fake = FakeDtsClient([_job(TradeInfo={})])
    _make_module(monkeypatch, fake)
    _run_args(job_id="dts-1001", name="mysql-migration", instance_class="small")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeMigrationJobs"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", job_id="dts-1001", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
