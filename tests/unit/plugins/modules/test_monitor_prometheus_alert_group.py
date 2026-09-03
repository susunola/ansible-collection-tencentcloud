"""Unit tests for the monitor_prometheus_alert_group module (helpers + run_module).

Creates, updates and deletes Prometheus alert groups. A group is looked
up by GroupId or by name (multiple name matches fail). Rule and custom-
receiver payloads are ingested into SDK models through
``_deserialize``, so the test models carry that method and capture the
payload. GroupState (enabled) is written at create/update time but is not
part of the comparable fields, so an enabled-only change is a noop; any
name/receiver/interval/rule drift goes through
UpdatePrometheusAlertGroup and the module re-finds by group id.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alert_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
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


class _DeserializableRequest(object):
    """SDK request/model stand-in: attributes assignable and ``_deserialize``
    captures the payload for later assertions."""

    def _deserialize(self, data):
        self._payload = dict(data or {})


class _Models(object):
    """Models stand-in whose every class carries ``_deserialize``."""

    def __getattr__(self, name):
        return type(name, (_DeserializableRequest,), {})


def _group(**overrides):
    """API-shaped alert-group dict; fresh copy per call."""
    item = {
        "GroupId": "grp-101",
        "GroupName": "app-alerts",
        "GroupState": 2,
        "AMPReceivers": [],
        "CustomReceiver": None,
        "RepeatInterval": "1h",
        "Rules": [],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "prom-abc",
        "group_id": None,
        "name": "app-alerts",
        "enabled": True,
        "receivers": [],
        "custom_receiver": None,
        "repeat_interval": "1h",
        "rules": [],
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


class FakeMonitorClient(object):
    """In-memory MonitorClient stand-in storing alert-group dicts.

    DescribePrometheusAlertGroups filters by GroupId when the request
    carries one and otherwise returns every group (the module re-filters
    by name client-side). Create/Update store the rule payloads as plain
    dict lists and Delete removes by GroupIds.
    """

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribePrometheusAlertGroups(self, request):
        self._record("DescribePrometheusAlertGroups", request)
        values = self.groups
        group_id = getattr(request, "GroupId", None)
        if group_id:
            values = [g for g in values if g["GroupId"] == group_id]
        return SimpleNamespace(
            AlertGroupSet=[FakeResource(dict(g)) for g in values],
            RequestId="req-fake",
        )

    def _store(self, request):
        return {
            "GroupName": request.GroupName,
            "GroupState": request.GroupState,
            "AMPReceivers": list(request.AMPReceivers),
            "CustomReceiver": getattr(request, "CustomReceiver", None),
            "RepeatInterval": request.RepeatInterval,
            "Rules": [r._payload for r in request.Rules],
        }

    def CreatePrometheusAlertGroup(self, request):
        self._record("CreatePrometheusAlertGroup", request)
        group_id = "grp-%d" % self._seq
        self._seq += 1
        stored = {"GroupId": group_id}
        stored.update(self._store(request))
        self.groups.append(stored)
        return SimpleNamespace(GroupId=group_id, RequestId="req-fake")

    def UpdatePrometheusAlertGroup(self, request):
        self._record("UpdatePrometheusAlertGroup", request)
        for group in self.groups:
            if group["GroupId"] == request.GroupId:
                group.update(self._store(request))
        return SimpleNamespace(RequestId="req-fake")

    def DeletePrometheusAlertGroups(self, request):
        self._record("DeletePrometheusAlertGroups", request)
        ids = request.GroupIds
        self.groups = [g for g in self.groups if g["GroupId"] not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_Models(), SimpleNamespace(MonitorClient=object)),
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


RULE = {"RuleName": "high-error-rate", "Expr": "rate(errors_total[5m]) > 1"}


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_build_describe_carries_fields():
    request = mod.build_describe(_Models(), _params(group_id="grp-101"))
    assert request.InstanceId == "prom-abc"
    assert request.GroupId == "grp-101"
    assert request.GroupName == "app-alerts"
    assert request.Offset == 0
    assert request.Limit == 100


def test_model_deserializes_payload():
    value = mod._model(_Models(), "PrometheusAlertGroupRuleSet", RULE)
    assert value._payload == RULE


def test_apply_create_carries_fields():
    request = mod.apply(
        _Models().CreatePrometheusAlertGroupRequest(),
        _Models(),
        _params(receivers=["notice-1"], repeat_interval="5m", rules=[RULE]),
    )
    assert request.InstanceId == "prom-abc"
    assert request.GroupName == "app-alerts"
    assert request.GroupState == 2
    assert request.AMPReceivers == ["notice-1"]
    assert request.RepeatInterval == "5m"
    assert len(request.Rules) == 1
    assert request.Rules[0]._payload == RULE
    assert not hasattr(request, "CustomReceiver")
    assert not hasattr(request, "GroupId")


def test_apply_group_state_disabled():
    request = mod.apply(
        _Models().CreatePrometheusAlertGroupRequest(), _Models(), _params(enabled=False)
    )
    assert request.GroupState == 3


def test_apply_custom_receiver_deserialized():
    receiver = {"ReceiverType": "notice", "ReceiverUser": ["u-1"]}
    request = mod.apply(
        _Models().CreatePrometheusAlertGroupRequest(),
        _Models(),
        _params(custom_receiver=receiver),
    )
    assert request.CustomReceiver._payload == receiver


def test_apply_update_sets_group_id():
    request = mod.apply(
        _Models().UpdatePrometheusAlertGroupRequest(),
        _Models(),
        _params(),
        group_id="grp-101",
    )
    assert request.GroupId == "grp-101"


def test_build_delete_carries_ids():
    request = mod.build_delete(_Models(), "prom-abc", "grp-101")
    assert request.InstanceId == "prom-abc"
    assert request.GroupIds == ["grp-101"]


def test_desired_matches_params():
    value = mod.desired(
        _params(receivers=["notice-1"], repeat_interval="5m", rules=[RULE])
    )
    assert value == {
        "GroupName": "app-alerts",
        "AMPReceivers": ["notice-1"],
        "CustomReceiver": None,
        "RepeatInterval": "5m",
        "Rules": [RULE],
    }


def test_comparable_normalizes_defaults():
    value = mod.comparable({"GroupName": "app-alerts"})
    assert value == {
        "GroupName": "app-alerts",
        "AMPReceivers": [],
        "CustomReceiver": None,
        "RepeatInterval": "1h",
        "Rules": [],
    }


def test_find_by_group_id(monkeypatch):
    fake = FakeMonitorClient([_group(), _group(GroupId="grp-102", GroupName="other")])
    module = FakeModule(_params(group_id="grp-102"))
    value = mod.find(module, fake, _Models(), module.params)
    assert value["GroupId"] == "grp-102"


def test_find_by_name(monkeypatch):
    fake = FakeMonitorClient([_group(GroupId="grp-102")])
    module = FakeModule(_params())
    value = mod.find(module, fake, _Models(), module.params)
    assert value["GroupId"] == "grp-102"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMonitorClient([_group(GroupName="other")])
    module = FakeModule(_params())
    assert mod.find(module, fake, _Models(), module.params) is None


def test_find_multi_match_fails(monkeypatch):
    fake = FakeMonitorClient([_group(), _group(GroupId="grp-102")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, _Models(), module.params)
    payload = exc.value.args[0]
    assert "Multiple Prometheus alert groups have the requested name" in payload["msg"]
    assert payload["name"] == "app-alerts"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(group_id="grp-101", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alert_group"] is None
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"]["GroupId"] == "grp-101"
    assert result["diff"]["before"]["GroupName"] == "app-alerts"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]
    assert len(fake.groups) == 1


def test_absent_deletes_group(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusAlertGroups",
        "DeletePrometheusAlertGroups",
    ]
    assert fake.calls[1][1].GroupIds == ["grp-101"]
    assert fake.groups == []


def test_present_noop_when_group_matches(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alert_group"]["GroupId"] == "grp-101"
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]


def test_present_noop_via_group_id(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="grp-101")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]


def test_enabled_only_change_is_noop(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]


def test_present_renames_via_group_id(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(group_id="grp-101", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"]["GroupName"] == "new-name"
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusAlertGroups",
        "UpdatePrometheusAlertGroup",
        "DescribePrometheusAlertGroups",
    ]
    updated = fake.calls[1][1]
    assert updated.GroupId == "grp-101"
    assert updated.GroupName == "new-name"
    assert updated.GroupState == 2


def test_present_updates_rules(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[RULE], receivers=["notice-9"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"]["Rules"] == [RULE]
    assert fake.calls[1][0] == "UpdatePrometheusAlertGroup"
    assert fake.calls[1][1].Rules[0]._payload == RULE
    assert fake.calls[1][1].AMPReceivers == ["notice-9"]


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMonitorClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(repeat_interval="5m", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"]["RepeatInterval"] == "1h"
    assert result["diff"]["after"]["RepeatInterval"] == "5m"
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]


def test_present_creates_group(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(receivers=["notice-1"], repeat_interval="5m", rules=[RULE])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"]["GroupId"] == "grp-2001"
    assert result["alert_group"]["Rules"] == [RULE]
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusAlertGroups",
        "CreatePrometheusAlertGroup",
        "DescribePrometheusAlertGroups",
    ]
    created = fake.calls[1][1]
    assert created.InstanceId == "prom-abc"
    assert created.GroupName == "app-alerts"
    assert created.GroupState == 2
    assert created.RepeatInterval == "5m"
    assert created.Rules[0]._payload == RULE
    assert len(fake.groups) == 1


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["alert_group"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["GroupName"] == "app-alerts"
    assert [c[0] for c in fake.calls] == ["DescribePrometheusAlertGroups"]
    assert fake.groups == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["alert_group"] is None
