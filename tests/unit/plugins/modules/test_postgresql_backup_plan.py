"""Unit tests for the postgresql_backup_plan write module (helpers + run_module).

Creates, updates and deletes TencentDB for PostgreSQL backup plans. The
module requires plan_id or name (required_one_of) and, when state=present,
name + min/max start time + retention days (required_if — enforced by
AnsibleModule at construction). find() returns the FIRST plan whose PlanId
or PlanName matches inside the instance's plan list (no multi-match fail).
BackupPeriodType is immutable on an existing plan — drift fails through
require_immutable_unchanged with replacement_required; creation with any
period_type is fine. BackupPeriod is compared as a sorted list. The update
request carries PlanId + LogBackupRetentionPeriod (may be None) but never
BackupPeriodType; the create request never sets PlanId or
LogBackupRetentionPeriod. Both paths refind by plan id afterwards.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import postgresql_backup_plan as mod
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


def _plan(**overrides):
    """API-shaped stored plan; fresh copy per call."""
    item = {
        "plan_id": "pp-1001",
        "instance_id": "postgres-1001",
        "name": "production",
        "period_type": "week",
        "periods": ["friday", "monday", "wednesday"],
        "min_start_time": "03:00:00",
        "max_start_time": "04:00:00",
        "retention_days": 30,
        "log_retention_days": None,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "postgres-1001",
        "plan_id": None,
        "name": "production",
        "period_type": "week",
        "periods": ["monday", "wednesday", "friday"],
        "min_start_time": "03:00:00",
        "max_start_time": "04:00:00",
        "retention_days": 30,
        "log_retention_days": None,
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


def _serialize_plan(a):
    """Map a stored plan dict onto its API response shape."""
    return {
        "PlanId": a["plan_id"],
        "PlanName": a["name"],
        "BackupPeriodType": a["period_type"],
        "BackupPeriod": list(a["periods"]),
        "MinBackupStartTime": a["min_start_time"],
        "MaxBackupStartTime": a["max_start_time"],
        "BaseBackupRetentionPeriod": a["retention_days"],
        "LogBackupRetentionPeriod": a["log_retention_days"],
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


class FakePostgresClient(object):
    """In-memory PostgresClient stand-in storing plan dicts.

    DescribeBackupPlans returns every plan of the requested instance (the
    module applies its own id/name match and takes the first hit);
    CreateBackupPlan synthesises sequential pp-NNNN ids; ModifyBackupPlan
    rewrites the plan selected by request.PlanId; DeleteBackupPlan removes
    by id.
    """

    def __init__(self, plans=None):
        self.plans = [dict(p) for p in (plans or [])]
        self.calls = []
        self._seq = 2000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return "pp-%d" % self._seq

    def _apply_request(self, stored, request):
        stored["name"] = request.PlanName
        stored["periods"] = list(request.BackupPeriod or [])
        stored["min_start_time"] = request.MinBackupStartTime
        stored["max_start_time"] = request.MaxBackupStartTime
        stored["retention_days"] = request.BaseBackupRetentionPeriod
        if getattr(request, "LogBackupRetentionPeriod", None) is not None:
            stored["log_retention_days"] = request.LogBackupRetentionPeriod

    def DescribeBackupPlans(self, request):
        self._record("DescribeBackupPlans", request)
        values = [
            FakeResource(_serialize_plan(p))
            for p in self.plans
            if p["instance_id"] == request.DBInstanceId
        ]
        return SimpleNamespace(Plans=values, RequestId="req-fake")

    def CreateBackupPlan(self, request):
        self._record("CreateBackupPlan", request)
        plan_id = self._next_id()
        stored = _plan(
            plan_id=plan_id,
            instance_id=request.DBInstanceId,
            name=request.PlanName,
            periods=request.BackupPeriod or [],
            min_start_time=request.MinBackupStartTime,
            max_start_time=request.MaxBackupStartTime,
            retention_days=request.BaseBackupRetentionPeriod,
        )
        stored["period_type"] = request.BackupPeriodType
        self.plans.append(stored)
        return SimpleNamespace(PlanId=plan_id, RequestId="req-fake")

    def ModifyBackupPlan(self, request):
        self._record("ModifyBackupPlan", request)
        for plan in self.plans:
            if plan["plan_id"] == request.PlanId:
                self._apply_request(plan, request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteBackupPlan(self, request):
        self._record("DeleteBackupPlan", request)
        self.plans = [p for p in self.plans if p["plan_id"] != request.PlanId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(PostgresClient=object)),
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


def test_build_describe_sets_instance():
    request = mod.build_describe(FakeModels(), "postgres-7")
    assert request.DBInstanceId == "postgres-7"


def test_apply_request_create_sets_period_type_only():
    request = mod.apply_request(FakeModels().CreateBackupPlanRequest(), _params())
    assert request.DBInstanceId == "postgres-1001"
    assert request.PlanName == "production"
    assert request.BackupPeriod == ["friday", "monday", "wednesday"]
    assert request.MinBackupStartTime == "03:00:00"
    assert request.MaxBackupStartTime == "04:00:00"
    assert request.BaseBackupRetentionPeriod == 30
    assert request.BackupPeriodType == "week"
    assert not hasattr(request, "PlanId")
    assert not hasattr(request, "LogBackupRetentionPeriod")


def test_apply_request_update_sets_plan_and_log_retention():
    request = mod.apply_request(FakeModels().ModifyBackupPlanRequest(), _params(log_retention_days=60), "pp-7")
    assert request.PlanId == "pp-7"
    assert request.LogBackupRetentionPeriod == 60
    assert not hasattr(request, "BackupPeriodType")


def test_apply_request_update_log_retention_none_when_unset():
    request = mod.apply_request(FakeModels().ModifyBackupPlanRequest(), _params(), "pp-7")
    assert request.PlanId == "pp-7"
    assert request.LogBackupRetentionPeriod is None


def test_build_create_and_update_wrappers():
    create = mod.build_create(FakeModels(), _params())
    assert create.BackupPeriodType == "week"
    update = mod.build_update(FakeModels(), _params(), "pp-9")
    assert update.PlanId == "pp-9"
    assert not hasattr(update, "BackupPeriodType")


def test_build_delete_sets_instance_and_plan():
    request = mod.build_delete(FakeModels(), "postgres-1", "pp-2")
    assert request.DBInstanceId == "postgres-1"
    assert request.PlanId == "pp-2"


def test_desired_builds_full_target():
    value = mod.desired(_params(period_type="day", log_retention_days=60))
    assert value["PlanName"] == "production"
    assert value["BackupPeriodType"] == "day"
    assert value["BackupPeriod"] == ["friday", "monday", "wednesday"]
    assert value["MinBackupStartTime"] == "03:00:00"
    assert value["MaxBackupStartTime"] == "04:00:00"
    assert value["BaseBackupRetentionPeriod"] == 30
    assert value["LogBackupRetentionPeriod"] == 60


def test_comparable_normalizes_periods():
    value = mod.comparable({
        "PlanName": "x",
        "BackupPeriodType": "week",
        "BackupPeriod": ["friday", "monday"],
        "MinBackupStartTime": "03:00:00",
        "MaxBackupStartTime": "04:00:00",
        "BaseBackupRetentionPeriod": 30,
        "LogBackupRetentionPeriod": None,
    })
    assert value["BackupPeriod"] == ["friday", "monday"]
    assert value["LogBackupRetentionPeriod"] is None


def test_comparable_tolerates_missing_periods():
    value = mod.comparable({"BackupPeriod": None})
    assert value["BackupPeriod"] == []
    assert value["PlanName"] is None


def test_find_matches_by_plan_id():
    fake = FakePostgresClient([_plan()])
    module = FakeModule(_params(plan_id="pp-1001"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["PlanId"] == "pp-1001"
    assert value["PlanName"] == "production"
    assert module.sdk_calls[0][1].DBInstanceId == "postgres-1001"


def test_find_matches_by_name():
    fake = FakePostgresClient([_plan()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["PlanId"] == "pp-1001"


def test_find_no_match_returns_none():
    fake = FakePostgresClient([_plan()])
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_returns_first_of_duplicates():
    fake = FakePostgresClient([_plan(), _plan(plan_id="pp-1002")])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["PlanId"] == "pp-1001"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"plan_id": "pp-x", "name": None},
        {"min_start_time": None},
        {"max_start_time": None},
        {"retention_days": None},
    ],
)
def test_present_requires_plan_fields(monkeypatch, overrides):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_plan"] is None
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"]["PlanId"] == "pp-1001"
    assert result["diff"]["before"]["PlanId"] == "pp-1001"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]
    assert len(fake.plans) == 1


def test_absent_deletes_plan(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"] is None
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans", "DeleteBackupPlan"]
    deleted = fake.calls[1][1]
    assert deleted.DBInstanceId == "postgres-1001"
    assert deleted.PlanId == "pp-1001"
    assert fake.plans == []


def test_present_noop_when_plan_matches(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_plan"]["PlanId"] == "pp-1001"
    assert result["backup_plan"]["BaseBackupRetentionPeriod"] == 30
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]


def test_present_retention_drift_updates_plan(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args(retention_days=45, log_retention_days=60)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"]["BaseBackupRetentionPeriod"] == 45
    assert result["backup_plan"]["LogBackupRetentionPeriod"] == 60
    assert [c[0] for c in fake.calls] == [
        "DescribeBackupPlans",
        "ModifyBackupPlan",
        "DescribeBackupPlans",
    ]
    updated = fake.calls[1][1]
    assert updated.PlanId == "pp-1001"
    assert updated.BaseBackupRetentionPeriod == 45
    assert updated.LogBackupRetentionPeriod == 60
    assert not hasattr(updated, "BackupPeriodType")
    assert fake.plans[0]["retention_days"] == 45


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args(retention_days=45, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"]["BaseBackupRetentionPeriod"] == 30
    assert result["diff"]["before"]["BaseBackupRetentionPeriod"] == 30
    assert result["diff"]["after"]["BaseBackupRetentionPeriod"] == 45
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]
    assert fake.plans[0]["retention_days"] == 30


def test_present_period_type_drift_fails_immutable(monkeypatch):
    fake = FakePostgresClient([_plan()])
    _make_module(monkeypatch, fake)
    _run_args(period_type="month")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing PostgreSQL backup plan" in payload["msg"]
    assert payload["immutable_changes"] == {
        "BackupPeriodType": {"before": "week", "after": "month"},
    }
    assert payload["replacement_required"] is True
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]


def test_present_creates_plan(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"]["PlanId"] == "pp-2001"
    assert result["backup_plan"]["PlanName"] == "production"
    assert result["backup_plan"]["BackupPeriodType"] == "week"
    assert [c[0] for c in fake.calls] == [
        "DescribeBackupPlans",
        "CreateBackupPlan",
        "DescribeBackupPlans",
    ]
    created = fake.calls[1][1]
    assert created.DBInstanceId == "postgres-1001"
    assert created.PlanName == "production"
    assert created.BackupPeriod == ["friday", "monday", "wednesday"]
    assert created.BackupPeriodType == "week"
    assert created.BaseBackupRetentionPeriod == 30
    assert not hasattr(created, "PlanId")
    assert len(fake.plans) == 1
    assert fake.plans[0]["plan_id"] == "pp-2001"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_plan"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["PlanName"] == "production"
    assert [c[0] for c in fake.calls] == ["DescribeBackupPlans"]
    assert fake.plans == []


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
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_plan"] is None
