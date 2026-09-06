"""Unit tests for the config_alarm_policy write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/config_alarm_policy.py`` with an in-memory fake Config
client whose write operations mutate the policy store, so the module's
post-write ``find_policy`` refetch converges immediately. Policies are
matched by ``AlarmPolicyId`` (int) or by name across the paged
ListAlarmPolicy (``response.AlarmPolicyList`` / ``response.Total``). The
module gates the create-only ``Type`` field on a *class-level* attribute
check (``hasattr(type(request), "Type")``), so the fake request classes
must differ: AddAlarmPolicyRequest declares ``Type`` while
UpdateAlarmPolicyRequest does not. Status is 1 when enabled and 2 when
disabled. In check mode a would-be create reports ``alarm_policy=None``
and a would-be update the pre-change policy.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_alarm_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeRequest,
    FakeResource,
    module_args,
    run,
)

POLICY = {
    "AlarmPolicyId": 7,
    "Name": "high-risk-compliance",
    "Type": 1,
    "EventScope": [1],
    "RiskLevel": [1, 2, 3],
    "NoticeTime": "09:00-18:00",
    "NotificationMechanism": "USER",
    "Status": 1,
    "NoticePeriod": [1, 2, 3, 4, 5],
    "Description": "",
}


def _policy(**overrides):
    """API-shaped policy dict isolated from the shared constant."""
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "alarm_policy_id": None,
        "name": "high-risk-compliance",
        "event_type": 1,
        "event_scopes": [1],
        "risk_levels": [1, 2, 3],
        "notice_time": "09:00-18:00",
        "notification_mechanism": "USER",
        "enabled": True,
        "notice_period": [1, 2, 3, 4, 5],
        "description": "",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class FakeConfigModels(FakeModels):
    """FakeModels whose AddAlarmPolicyRequest carries a class-level Type.

    The module decides whether to send the create-only ``Type`` field with
    ``hasattr(type(request), "Type")``, so Add must declare it as a class
    attribute while Update must not.
    """

    def __getattr__(self, name):
        if name == "AddAlarmPolicyRequest":
            return type(name, (FakeRequest,), {"Type": None})
        return super(FakeConfigModels, self).__getattr__(name)


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


class FakeConfigClient(object):
    """In-memory ConfigClient stand-in for alarm policies.

    Stores API-shaped policy dicts keyed by integer AlarmPolicyId. List
    pages over the store honouring Offset/Limit and reports Total at the
    top level (mirroring the SDK); write operations mutate the store so
    post-write refetches converge.
    """

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListAlarmPolicy(self, request):
        self._record("ListAlarmPolicy", request)
        page = self.policies[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            AlarmPolicyList=[FakeResource(dict(p)) for p in page],
            Total=len(self.policies),
            RequestId="req-fake",
        )

    def AddAlarmPolicy(self, request):
        self._record("AddAlarmPolicy", request)
        policy_id = self._next_id
        self._next_id += 1
        self.policies.append(
            {
                "AlarmPolicyId": policy_id,
                "Name": request.Name,
                "Type": getattr(request, "Type", 1),
                "EventScope": list(request.EventScope or []),
                "RiskLevel": list(request.RiskLevel or []),
                "NoticeTime": request.NoticeTime,
                "NotificationMechanism": request.NotificationMechanism,
                "Status": request.Status,
                "NoticePeriod": list(request.NoticePeriod or []),
                "Description": request.Description or "",
            }
        )
        return SimpleNamespace(AlarmPolicyId=policy_id, RequestId="req-fake")

    def UpdateAlarmPolicy(self, request):
        self._record("UpdateAlarmPolicy", request)
        for stored in self.policies:
            if stored.get("AlarmPolicyId") != request.AlarmPolicyId:
                continue
            stored["Name"] = request.Name
            stored["EventScope"] = list(request.EventScope or [])
            stored["RiskLevel"] = list(request.RiskLevel or [])
            stored["NoticeTime"] = request.NoticeTime
            stored["NotificationMechanism"] = request.NotificationMechanism
            stored["Status"] = request.Status
            stored["NoticePeriod"] = list(request.NoticePeriod or [])
            stored["Description"] = request.Description or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAlarmPolicy(self, request):
        self._record("DeleteAlarmPolicy", request)
        self.policies = [p for p in self.policies if p.get("AlarmPolicyId") != request.AlarmPolicyId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeConfigModels(), SimpleNamespace(ConfigClient=object)),
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


def test_list_request_fields():
    request = mod.list_request(FakeConfigModels(), offset=0)
    assert request.Offset == 0
    assert request.Limit == 100


def test_create_request_fields():
    request = mod.create_request(FakeConfigModels(), _params())
    assert request.Name == "high-risk-compliance"
    assert request.Type == 1  # class-level Type present on Add request
    assert request.EventScope == [1]
    assert request.RiskLevel == [1, 2, 3]
    assert request.NoticeTime == "09:00-18:00"
    assert request.NotificationMechanism == "USER"
    assert request.Status == 1
    assert request.NoticePeriod == [1, 2, 3, 4, 5]
    assert request.Description == ""
    assert not hasattr(request, "AlarmPolicyId")


def test_create_request_sorts_and_dedupes_lists():
    request = mod.create_request(FakeConfigModels(), _params(event_scopes=[2, 1, 1], risk_levels=[3, 1], notice_period=[5, 1, 5]))
    assert request.EventScope == [1, 2]
    assert request.RiskLevel == [1, 3]
    assert request.NoticePeriod == [1, 5]


def test_create_request_disabled_status_two():
    request = mod.create_request(FakeConfigModels(), _params(enabled=False))
    assert request.Status == 2


def test_update_request_fields_omits_type():
    request = mod.update_request(FakeConfigModels(), _params(name="renamed"), 7)
    assert request.AlarmPolicyId == 7
    assert request.Name == "renamed"
    assert request.Status == 1
    # Type is create-only; the Update request class has no Type attribute
    assert not hasattr(request, "Type")


def test_delete_request_fields():
    request = mod.delete_request(FakeConfigModels(), 7)
    assert request.AlarmPolicyId == 7


def test_desired_maps_status_and_fields():
    desired = mod.desired(_params(enabled=True))
    assert desired["Status"] == 1
    assert mod.desired(_params(enabled=False))["Status"] == 2
    assert desired["Name"] == "high-risk-compliance"
    assert desired["EventScope"] == [1]
    assert desired["NoticePeriod"] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# find_policy tests
# ---------------------------------------------------------------------------


def test_find_by_id(monkeypatch):
    fake = FakeConfigClient([_policy(), _policy(AlarmPolicyId=8, Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(alarm_policy_id=8, name=None))
    value = mod.find_policy(module, fake, FakeConfigModels(), module.params)
    assert value["AlarmPolicyId"] == 8


def test_find_by_name(monkeypatch):
    fake = FakeConfigClient([_policy(Name="other"), _policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="high-risk-compliance"))
    value = mod.find_policy(module, fake, FakeConfigModels(), module.params)
    assert value["AlarmPolicyId"] == 7


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find_policy(module, fake, FakeConfigModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeConfigClient([_policy(), _policy(AlarmPolicyId=8)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="high-risk-compliance"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_policy(module, fake, FakeConfigModels(), module.params)
    assert "Multiple Config alarm policies matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    policies = [_policy(AlarmPolicyId=1000 + i, Name="bulk-%04d" % i) for i in range(101)]
    policies.append(_policy())
    fake = FakeConfigClient(policies)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="high-risk-compliance"))
    value = mod.find_policy(module, fake, FakeConfigModels(), module.params)
    assert value["AlarmPolicyId"] == 7
    list_calls = [c for c in fake.calls if c[0] == "ListAlarmPolicy"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args()  # neither alarm_policy_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name_notice_and_mechanism():
    module_args(name="high-risk-compliance")  # missing notice_time/mechanism
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, notice_time and notification_mechanism are required when state=present" in exc.value.args[0]["msg"]


def test_present_requires_notice_time_and_mechanism():
    module_args(name="high-risk-compliance", notice_time="09:00-18:00")  # missing mechanism
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, notice_time and notification_mechanism are required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_policy(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["alarm_policy"]
    assert policy["AlarmPolicyId"] == 100
    assert policy["Name"] == "high-risk-compliance"
    assert policy["Status"] == 1
    names = [c[0] for c in fake.calls]
    assert names.count("ListAlarmPolicy") == 2  # find + refetch
    assert names.count("AddAlarmPolicy") == 1
    add = [c for c in fake.calls if c[0] == "AddAlarmPolicy"][0][1]
    assert add.Type == 1
    assert add.Name == "high-risk-compliance"


def test_present_creates_disabled_policy(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["Status"] == 2
    add = [c for c in fake.calls if c[0] == "AddAlarmPolicy"][0][1]
    assert add.Status == 2


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alarm_policy"]["AlarmPolicyId"] == 7
    names = [c[0] for c in fake.calls]
    assert "UpdateAlarmPolicy" not in names
    assert "AddAlarmPolicy" not in names


def test_present_name_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["Name"] == "renamed"
    names = [c[0] for c in fake.calls]
    assert names.count("UpdateAlarmPolicy") == 1
    update = [c for c in fake.calls if c[0] == "UpdateAlarmPolicy"][0][1]
    assert update.AlarmPolicyId == 7
    assert update.Name == "renamed"
    assert not hasattr(update, "Type")  # create-only field not resent


def test_present_risk_levels_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, risk_levels=[1])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["RiskLevel"] == [1]
    update = [c for c in fake.calls if c[0] == "UpdateAlarmPolicy"][0][1]
    assert update.RiskLevel == [1]


def test_present_enabled_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["Status"] == 2
    update = [c for c in fake.calls if c[0] == "UpdateAlarmPolicy"][0][1]
    assert update.Status == 2


def test_present_event_scopes_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy(EventScope=[1])])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, event_scopes=[1, 2])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["EventScope"] == [1, 2]


def test_present_notice_period_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy(NoticePeriod=[1, 2, 3, 4, 5])])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, notice_period=[1, 2])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["NoticePeriod"] == [1, 2]


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(alarm_policy_id=7, description="tuned down")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["Description"] == "tuned down"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["ListAlarmPolicy"]  # find only
    assert not any("AddAlarmPolicy" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(alarm_policy_id=7, risk_levels=[1]).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["AlarmPolicyId"] == 7  # pre-change policy reported
    assert not any("UpdateAlarmPolicy" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeConfigModels(), SimpleNamespace(ConfigClient=object)),
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


def test_absent_deletes_policy(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="high-risk-compliance")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAlarmPolicy"][0][1]
    assert delete.AlarmPolicyId == 7
    assert fake.policies == []


def test_absent_deletes_by_id_without_name(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name=None, alarm_policy_id=7)
    result = run(mod.run_module)
    assert result["changed"] is True
    delete = [c for c in fake.calls if c[0] == "DeleteAlarmPolicy"][0][1]
    assert delete.AlarmPolicyId == 7


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alarm_policy"] is None
    assert not any("DeleteAlarmPolicy" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alarm_policy"]["AlarmPolicyId"] == 7  # pre-change policy reported
    assert not any("DeleteAlarmPolicy" == c[0] for c in fake.calls)
    assert len(fake.policies) == 1
