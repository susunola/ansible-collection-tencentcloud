"""Unit tests for the waf_area_ban_rule write module (run_module flows).

Drives ``run_module()`` against an in-memory fake WAF client whose create /
modify / status operations mutate a geographic-blocking store so
post-write describes converge immediately.

Geographic blocking is a per-domain singleton. ``state=absent`` does not
delete the configuration; it flips ``Status`` to 0 through
``ModifyAreaBanStatus`` because the API has no delete for it.

Scenario matrix:

* absent on a missing or already-disabled rule is idempotent
* absent on a live rule disables it (check-mode dry run included)
* present creates the rule and enables it (empty-areas guard first)
* no-op when the rule already matches and updates on drift
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_area_ban_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = "api.example.com"

AREAS = [
    {"Country": "中国", "Region": "广东", "City": "深圳"},
    {"Country": "美国", "Region": "", "City": ""},
]

JOB_DATETIME = {"Timed": [{"StartDateTime": 1788134400, "EndDateTime": 1788220800}], "TimeTZone": "Asia/Shanghai"}

RULE = {
    "Status": 1,
    "Areas": AREAS,
    "JobType": "TimedJob",
    "JobDateTime": JOB_DATETIME,
    "Lang": "cn",
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _args(state="present", areas=None, **overrides):
    params = {
        "state": state,
        "domain": DOMAIN,
        "areas": copy.deepcopy(areas if areas is not None else AREAS),
        "job_type": "TimedJob",
        "job_datetime": copy.deepcopy(JOB_DATETIME),
        "language": "cn",
    }
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client holding the per-domain geographic-blocking rule."""

    def __init__(self, rule=None):
        self.rule = copy.deepcopy(rule)  # None means "no singleton rule yet"
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAreaBanRule(self, request):
        self._record("DescribeAreaBanRule", request)
        return SimpleNamespace(Data=FakeResource(copy.deepcopy(self.rule)) if self.rule is not None else None)

    def _apply_request(self, request):
        request_data = {
            "Status": 1,
            "Areas": [dict(vars(a)) for a in (getattr(request, "Areas", None) or [])],
            "JobType": getattr(request, "JobType", None),
            "JobDateTime": dict(vars(getattr(request, "JobDateTime", None)) or {}),
            "Lang": getattr(request, "Lang", None),
        }
        return request_data

    def CreateAreaBanRule(self, request):
        self._record("CreateAreaBanRule", request)
        self.rule = self._apply_request(request)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAreaBanRule(self, request):
        self._record("ModifyAreaBanRule", request)
        if self.rule is not None:
            self.rule = self._apply_request(request)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAreaBanStatus(self, request):
        self._record("ModifyAreaBanStatus", request)
        if self.rule is not None:
            self.rule["Status"] = getattr(request, "Status", self.rule.get("Status"))
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards and absent flows
# ---------------------------------------------------------------------------


def test_present_with_empty_areas_fails(monkeypatch):
    fake = FakeWafClient(rule=None)
    _make_module(monkeypatch, fake)
    _args(areas=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "areas must not be empty when state=present" in exc.value.args[0]["msg"]


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeWafClient(rule=None)
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAreaBanRule"]


def test_absent_disabled_rule_is_idempotent(monkeypatch):
    fake = FakeWafClient(rule=_rule(Status=0))
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["Status"] == 0
    assert "ModifyAreaBanStatus" not in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 1
    assert "ModifyAreaBanStatus" not in [c for c, unused in fake.calls]


def test_absent_disables_rule(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeAreaBanRule", "ModifyAreaBanStatus", "DescribeAreaBanRule"]
    status_call = [r for c, r in fake.calls if c == "ModifyAreaBanStatus"][0]
    assert status_call.Status == 0
    assert status_call.Domain == DOMAIN


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_create_rule(monkeypatch):
    fake = FakeWafClient(rule=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 1
    assert len(result["rule"]["Areas"]) == 2
    assert result["rule"]["Lang"] == "cn"
    ops = [c for c, unused in fake.calls]
    assert "CreateAreaBanRule" in ops
    assert "ModifyAreaBanStatus" in ops
    create_call = [r for c, r in fake.calls if c == "CreateAreaBanRule"][0]
    assert create_call.Domain == DOMAIN
    status_call = [r for c, r in fake.calls if c == "ModifyAreaBanStatus"][0]
    assert status_call.Status == 1


def test_create_when_existing_rule_has_no_areas(monkeypatch):
    # A stale singleton that exists but carries no areas still goes through
    # the create branch rather than the update branch.
    fake = FakeWafClient(rule=_rule(Status=0, Areas=[]))
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateAreaBanRule" in ops
    assert "ModifyAreaBanRule" not in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rule=None)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rule is None
    assert not [c for c, unused in fake.calls if c != "DescribeAreaBanRule"]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["Status"] == 1
    assert not [c for c, unused in fake.calls if c != "DescribeAreaBanRule"]


def test_area_set_drift_updates(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args(areas=[{"Country": "日本", "Region": "", "City": ""}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [a["Country"] for a in result["rule"]["Areas"]] == ["日本"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyAreaBanRule" in ops
    assert "ModifyAreaBanStatus" in ops


def test_language_drift_updates(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args(language="en")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Lang"] == "en"


def test_job_type_drift_updates(monkeypatch):
    fake = FakeWafClient(rule=_rule())
    _make_module(monkeypatch, fake)
    _args(job_type="CronJob")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["JobType"] == "CronJob"


def test_re_enable_disabled_rule(monkeypatch):
    fake = FakeWafClient(rule=_rule(Status=0))
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 1
    status_call = [r for c, r in fake.calls if c == "ModifyAreaBanStatus"][0]
    assert status_call.Status == 1


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAreaBanRule(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
