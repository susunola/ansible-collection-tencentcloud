"""Unit tests for the alb_target_group write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/alb_target_group.py`` with an in-memory fake ALB client
whose write operations mutate the target-group store, so the module's
post-write ``find`` refetch converges immediately. Target groups are
matched by ``target_group_id`` or by ``TargetGroupName``; VpcId / TargetType
/ Protocol are immutable after creation and drift on them fails with a
replacement-required error. SDK config sub-objects
(HealthCheckConfig / StickySessionConfig) round-trip through
``from_json_string``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import alb_target_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "TargetGroupId": "lbtg-1",
    "TargetGroupName": "app-http",
    "VpcId": "vpc-1",
    "TargetType": "Instance",
    "Protocol": "HTTP",
    "SchedulerAlgorithm": "wrr",
    "KeepaliveEnabled": False,
    "HealthCheckConfig": {"HealthCheckEnabled": True, "HealthCheckPath": "/health"},
    "StickySessionConfig": {"StickySessionSwitch": "OFF"},
}


def _group(**overrides):
    """API-shaped target-group dict isolated from the shared constant."""
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "target_group_id": None,
        "name": "app-http",
        "vpc_id": "vpc-1",
        "target_type": "Instance",
        "protocol": "HTTP",
        "scheduler_algorithm": "wrr",
        "keepalive_enabled": False,
        "health_check": {"HealthCheckEnabled": True, "HealthCheckPath": "/health"},
        "sticky_session": {"StickySessionSwitch": "OFF"},
        "tags": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class _JsonModel(object):
    """SDK model whose config sub-objects round-trip through from_json_string."""

    def from_json_string(self, payload):
        for key, value in json.loads(payload).items():
            setattr(self, key, value)
        return self


class FakeAlbModels(FakeModels):
    """FakeModels whose config classes implement from_json_string."""

    def __getattr__(self, name):
        if name in ("HealthCheckConfig", "StickySessionConfig"):
            return _JsonModel
        return super(FakeAlbModels, self).__getattr__(name)


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


class FakeAlbClient(object):
    """In-memory AlbClient stand-in.

    Stores API-shaped target-group dicts. DescribeTargetGroups returns the
    whole store (optionally filtered by TargetGroupIds); write operations
    mutate the store so the module's post-write find refetch converges.
    """

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 20000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "lbtg-%05d" % self._next_id

    @staticmethod
    def _as_dict(value):
        return dict(vars(value)) if value is not None else None

    def DescribeTargetGroups(self, request):
        self._record("DescribeTargetGroups", request)
        groups = self.groups
        ids = getattr(request, "TargetGroupIds", None)
        if ids:
            groups = [g for g in groups if g.get("TargetGroupId") in ids]
        return SimpleNamespace(
            TargetGroups=[FakeResource(dict(g)) for g in groups],
            TotalCount=len(groups),
            RequestId="req-fake",
        )

    def CreateTargetGroup(self, request):
        self._record("CreateTargetGroup", request)
        group_id = self._new_id()
        self.groups.append(
            {
                "TargetGroupId": group_id,
                "TargetGroupName": request.TargetGroupName,
                "VpcId": request.VpcId,
                "TargetType": request.TargetType,
                "Protocol": request.Protocol,
                "SchedulerAlgorithm": request.SchedulerAlgorithm,
                "KeepaliveEnabled": bool(request.KeepaliveEnabled),
                "HealthCheckConfig": self._as_dict(request.HealthCheckConfig),
                "StickySessionConfig": self._as_dict(request.StickySessionConfig),
            }
        )
        return SimpleNamespace(TargetGroupId=group_id, RequestId="req-fake")

    def ModifyTargetGroupAttributes(self, request):
        self._record("ModifyTargetGroupAttributes", request)
        for stored in self.groups:
            if stored.get("TargetGroupId") != request.TargetGroupId:
                continue
            stored["TargetGroupName"] = request.TargetGroupName
            stored["SchedulerAlgorithm"] = request.SchedulerAlgorithm
            stored["KeepaliveEnabled"] = bool(request.KeepaliveEnabled)
            stored["HealthCheckConfig"] = self._as_dict(request.HealthCheckConfig)
            stored["StickySessionConfig"] = self._as_dict(request.StickySessionConfig)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTargetGroups(self, request):
        self._record("DeleteTargetGroups", request)
        ids = list(request.TargetGroupIds or [])
        self.groups = [g for g in self.groups if g.get("TargetGroupId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeAlbModels(), SimpleNamespace(AlbClient=object)),
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
# request-builder / model helper tests
# ---------------------------------------------------------------------------


def test_model_returns_none_for_none_value():
    assert mod._model(FakeAlbModels().HealthCheckConfig, None) is None


def test_model_round_trips_payload():
    item = mod._model(FakeAlbModels().HealthCheckConfig, {"HealthCheckEnabled": True, "HealthCheckPath": "/x"})
    assert item.HealthCheckEnabled is True
    assert item.HealthCheckPath == "/x"


def test_describe_request_base_fields():
    request = mod.describe_request(FakeAlbModels(), _params(target_group_id=None, name="app-http"))
    assert request.MaxResults == 100
    assert not hasattr(request, "TargetGroupIds")


def test_describe_request_filters_by_id():
    request = mod.describe_request(FakeAlbModels(), _params(target_group_id="lbtg-9"))
    assert request.TargetGroupIds == ["lbtg-9"]


def test_tags_builder_sorted():
    items = mod._tags(FakeAlbModels(), {"z": "2", "a": "1"})
    assert [(x.TagKey, x.TagValue) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeAlbModels(), None) == []
    assert mod._tags(FakeAlbModels(), {}) == []


def test_create_request_fields():
    request = mod.create_request(FakeAlbModels(), _params())
    assert request.TargetType == "Instance"
    assert request.VpcId == "vpc-1"
    assert request.Protocol == "HTTP"
    assert request.TargetGroupName == "app-http"
    assert request.SchedulerAlgorithm == "wrr"
    assert request.KeepaliveEnabled is False
    assert request.HealthCheckConfig.HealthCheckPath == "/health"
    assert request.StickySessionConfig.StickySessionSwitch == "OFF"
    assert request.Tags == []


def test_create_request_with_tags():
    request = mod.create_request(FakeAlbModels(), _params(tags={"env": "prod"}))
    assert [(x.TagKey, x.TagValue) for x in request.Tags] == [("env", "prod")]


def test_update_request_fields():
    request = mod.update_request(FakeAlbModels(), _params(name="renamed"), "lbtg-1")
    assert request.TargetGroupId == "lbtg-1"
    assert request.TargetGroupName == "renamed"
    assert not hasattr(request, "Tags")
    assert not hasattr(request, "VpcId")


def test_delete_request_fields():
    request = mod.delete_request(FakeAlbModels(), "lbtg-1")
    assert request.TargetGroupIds == ["lbtg-1"]


def test_comparable_normalises_keepalive_bool():
    value = mod.comparable(_group(KeepaliveEnabled=1))
    assert value["KeepaliveEnabled"] is True
    assert value["TargetGroupName"] == "app-http"
    assert value["HealthCheckConfig"]["HealthCheckPath"] == "/health"


def test_desired_uses_params_and_old_state():
    value = mod.desired(_params(health_check=None, sticky_session=None), _group())
    assert value["TargetGroupName"] == "app-http"
    assert value["VpcId"] == "vpc-1"
    assert value["TargetType"] == "Instance"
    assert value["Protocol"] == "HTTP"
    assert value["SchedulerAlgorithm"] == "wrr"
    assert value["KeepaliveEnabled"] is False
    # unset configs fall back to remote state
    assert value["HealthCheckConfig"] == GROUP["HealthCheckConfig"]
    assert value["StickySessionConfig"] == GROUP["StickySessionConfig"]


def test_desired_falls_back_without_current():
    value = mod.desired(_params(health_check=None, sticky_session=None), None)
    assert value["VpcId"] == "vpc-1"
    assert value["HealthCheckConfig"] is None


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeAlbClient([_group(TargetGroupName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeAlbModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeAlbClient([_group(TargetGroupName="other"), _group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="app-http"))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["TargetGroupId"] == "lbtg-1"


def test_find_by_target_group_id(monkeypatch):
    fake = FakeAlbClient([_group(), _group(TargetGroupId="lbtg-2", TargetGroupName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_group_id="lbtg-2", name=None))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["TargetGroupId"] == "lbtg-2"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeAlbClient([_group(), _group(TargetGroupId="lbtg-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="app-http"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeAlbModels(), module.params)
    assert "Multiple ALB target groups matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither target_group_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_target_group(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["target_group"]
    assert group["TargetGroupId"] == "lbtg-20001"
    assert group["TargetGroupName"] == "app-http"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeTargetGroups") == 2  # find + refetch
    assert names.count("CreateTargetGroup") == 1
    create = [c for c in fake.calls if c[0] == "CreateTargetGroup"][0][1]
    assert create.VpcId == "vpc-1"


def test_present_requires_name_and_vpc_for_new(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    _run_args(target_group_id="lbtg-ghost", name=None, vpc_id=None)  # id given but absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "creation parameters are required for a new ALB target group" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target_group"]["TargetGroupId"] == "lbtg-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyTargetGroupAttributes" not in names
    assert "CreateTargetGroup" not in names


def test_present_algorithm_drift_triggers_update(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(scheduler_algorithm="wlc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["SchedulerAlgorithm"] == "wlc"
    modify = [c for c in fake.calls if c[0] == "ModifyTargetGroupAttributes"][0][1]
    assert modify.TargetGroupId == "lbtg-1"
    assert modify.SchedulerAlgorithm == "wlc"


def test_present_health_check_drift_triggers_update(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(health_check={"HealthCheckEnabled": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["HealthCheckConfig"] == {"HealthCheckEnabled": False}
    modify = [c for c in fake.calls if c[0] == "ModifyTargetGroupAttributes"][0][1]
    assert modify.HealthCheckConfig.HealthCheckEnabled is False


def test_present_rename_by_id(monkeypatch):
    fake = FakeAlbClient([_group(TargetGroupName="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(target_group_id="lbtg-1", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupName"] == "new-name"
    assert len(fake.groups) == 1  # renamed in place


def test_present_immutable_vpc_drift_fails(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["VpcId"]["before"] == "vpc-1"
    assert payload["immutable_changes"]["VpcId"]["after"] == "vpc-other"
    assert not any("ModifyTargetGroupAttributes" == c[0] for c in fake.calls)


def test_present_immutable_protocol_drift_fails(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(protocol="HTTPS")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Immutable fields cannot be changed" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeAlbModels(), SimpleNamespace(AlbClient=object)),
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
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupName"] == "app-http"  # desired reported
    assert not any("CreateTargetGroup" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(scheduler_algorithm="wlc"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("ModifyTargetGroupAttributes" == c[0] for c in fake.calls)


def test_absent_removes_target_group(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="app-http")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteTargetGroups"][0][1]
    assert delete.TargetGroupIds == ["lbtg-1"]
    assert fake.groups == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target_group"] is None
    assert not any("DeleteTargetGroups" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", name="app-http"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DeleteTargetGroups" == c[0] for c in fake.calls)
    assert len(fake.groups) == 1
