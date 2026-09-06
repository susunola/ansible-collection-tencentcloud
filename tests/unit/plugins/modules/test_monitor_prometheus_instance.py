"""Unit tests for the monitor_prometheus_instance write module (helpers + run_module).

Creates, updates and terminates pay-as-you-go Managed Prometheus
instances. Instances are looked up by InstanceId or by name (multiple
name matches fail). Creation requires vpc_id/subnet_id/zone; updates only
rewrite the name and retention window through ModifyPrometheusInstance
Attributes, and the module re-finds by the resulting instance id after
every mutation. Tag and attribute dicts become sorted SDK object lists.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_instance as mod
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


def _instance(**overrides):
    """API-shaped Prometheus instance dict; fresh copy per call."""
    item = {
        "InstanceId": "prom-101",
        "InstanceName": "prod-obs",
        "DataRetentionTime": 15,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": None,
        "name": "prod-obs",
        "vpc_id": None,
        "subnet_id": None,
        "zone": None,
        "retention_days": 15,
        "grafana_instance_id": None,
        "tags": {},
        "instance_attributes": {},
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
    """In-memory MonitorClient stand-in storing instance dicts.

    DescribePrometheusInstances filters by InstanceIds when the request
    carries them and otherwise returns every instance (the module
    re-filters by name client-side). CreatePrometheusMultiTenantInstance
    PostPayMode synthesizes prom-NNNN ids, ModifyPrometheusInstance
    Attributes rewrites InstanceName/DataRetentionTime and
    TerminatePrometheusInstances removes by id.
    """

    def __init__(self, instances=None):
        self.instances = [dict(i) for i in (instances or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribePrometheusInstances(self, request):
        self._record("DescribePrometheusInstances", request)
        values = self.instances
        ids = getattr(request, "InstanceIds", None)
        if ids:
            values = [i for i in values if i["InstanceId"] in ids]
        return SimpleNamespace(
            InstanceSet=[FakeResource(dict(i)) for i in values],
            RequestId="req-fake",
        )

    def CreatePrometheusMultiTenantInstancePostPayMode(self, request):
        self._record("CreatePrometheusMultiTenantInstancePostPayMode", request)
        instance_id = "prom-%d" % self._seq
        self._seq += 1
        stored = {
            "InstanceId": instance_id,
            "InstanceName": request.InstanceName,
            "DataRetentionTime": request.DataRetentionTime,
        }
        self.instances.append(stored)
        return SimpleNamespace(InstanceId=instance_id, RequestId="req-fake")

    def ModifyPrometheusInstanceAttributes(self, request):
        self._record("ModifyPrometheusInstanceAttributes", request)
        for instance in self.instances:
            if instance["InstanceId"] == request.InstanceId:
                instance["InstanceName"] = request.InstanceName
                instance["DataRetentionTime"] = request.DataRetentionTime
        return SimpleNamespace(RequestId="req-fake")

    def TerminatePrometheusInstances(self, request):
        self._record("TerminatePrometheusInstances", request)
        ids = request.InstanceIds
        self.instances = [i for i in self.instances if i["InstanceId"] not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)),
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


def test_tags_builds_sorted_objects():
    values = mod._tags(FakeModels(), {"b": "2", "a": 1})
    assert [(x.Key, x.Value) for x in values] == [("a", "1"), ("b", "2")]


def test_attrs_builds_sorted_objects():
    values = mod._attrs(FakeModels(), {"y": "2", "x": 1})
    assert [(x.Key, x.Value) for x in values] == [("x", "1"), ("y", "2")]


def test_build_describe_with_instance_id():
    request = mod.build_describe(FakeModels(), "prom-101", "prod-obs")
    assert request.InstanceIds == ["prom-101"]
    assert request.InstanceName == "prod-obs"
    assert request.Offset == 0
    assert request.Limit == 100


def test_build_describe_name_only():
    request = mod.build_describe(FakeModels(), None, "prod-obs")
    assert request.InstanceIds is None
    assert request.InstanceName == "prod-obs"


def test_build_create_carries_fields():
    request = mod.build_create(
        FakeModels(),
        _params(
            name="prod-obs",
            vpc_id="vpc-1",
            subnet_id="subnet-1",
            zone="ap-guangzhou-3",
            retention_days=30,
            grafana_instance_id="grafana-1",
            tags={"env": "prod"},
            instance_attributes={"foo": "bar"},
        ),
    )
    assert request.InstanceName == "prod-obs"
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.Zone == "ap-guangzhou-3"
    assert request.DataRetentionTime == 30
    assert request.GrafanaInstanceId == "grafana-1"
    assert [(x.Key, x.Value) for x in request.TagSpecification] == [("env", "prod")]
    assert [(x.Key, x.Value) for x in request.InstanceAttributes] == [("foo", "bar")]


def test_build_update_carries_fields():
    request = mod.build_update(FakeModels(), _params(retention_days=90), "prom-101")
    assert request.InstanceId == "prom-101"
    assert request.InstanceName == "prod-obs"
    assert request.DataRetentionTime == 90
    assert request.InstanceAttributes == []


def test_build_delete_carries_ids():
    request = mod.build_delete(FakeModels(), "prom-101")
    assert request.InstanceIds == ["prom-101"]


def test_wanted_selects_name_and_retention():
    assert mod.wanted(_params(retention_days=45)) == {
        "InstanceName": "prod-obs",
        "DataRetentionTime": 45,
    }


def test_find_by_instance_id(monkeypatch):
    fake = FakeMonitorClient([_instance(), _instance(InstanceId="prom-102", InstanceName="other")])
    module = FakeModule(_params(instance_id="prom-102"))
    value = mod.find(module, fake, FakeModels(), "prom-102", None)
    assert value["InstanceId"] == "prom-102"


def test_find_by_name(monkeypatch):
    fake = FakeMonitorClient([_instance(InstanceId="prom-102")])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), None, "prod-obs")
    assert value["InstanceId"] == "prom-102"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMonitorClient([_instance(InstanceName="other")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), None, "prod-obs") is None


def test_find_multi_match_fails(monkeypatch):
    fake = FakeMonitorClient([_instance(), _instance(InstanceId="prom-102")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), None, "prod-obs")
    payload = exc.value.args[0]
    assert "Multiple Prometheus instances have the requested name" in payload["msg"]
    assert payload["name"] == "prod-obs"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(instance_id="prom-101", name=None)
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
    assert result["instance"] is None
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "prom-101"
    assert result["diff"]["before"]["InstanceName"] == "prod-obs"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]
    assert len(fake.instances) == 1


def test_absent_terminates_instance(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusInstances",
        "TerminatePrometheusInstances",
    ]
    assert fake.calls[1][1].InstanceIds == ["prom-101"]
    assert fake.instances == []


def test_present_noop_when_instance_matches(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "prom-101"
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]


def test_present_noop_via_instance_id(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(instance_id="prom-101")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]


def test_present_requires_vpc_subnet_zone_when_creating(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "vpc_id, subnet_id and zone are required when creating" in exc.value.args[0]["msg"]
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(
        vpc_id="vpc-1", subnet_id="subnet-1", zone="ap-guangzhou-3",
        _ansible_check_mode=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["InstanceName"] == "prod-obs"
    assert result["diff"]["after"]["DataRetentionTime"] == 15
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]
    assert fake.instances == []


def test_present_creates_instance(monkeypatch):
    fake = FakeMonitorClient()
    _make_module(monkeypatch, fake)
    _run_args(
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        zone="ap-guangzhou-3",
        retention_days=30,
        grafana_instance_id="grafana-1",
        tags={"env": "prod"},
        instance_attributes={"team": "sre"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "prom-2001"
    assert result["instance"]["DataRetentionTime"] == 30
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusInstances",
        "CreatePrometheusMultiTenantInstancePostPayMode",
        "DescribePrometheusInstances",
    ]
    created = fake.calls[1][1]
    assert created.InstanceName == "prod-obs"
    assert created.VpcId == "vpc-1"
    assert created.SubnetId == "subnet-1"
    assert created.Zone == "ap-guangzhou-3"
    assert created.DataRetentionTime == 30
    assert created.GrafanaInstanceId == "grafana-1"
    assert [(x.Key, x.Value) for x in created.TagSpecification] == [("env", "prod")]
    assert [(x.Key, x.Value) for x in created.InstanceAttributes] == [("team", "sre")]
    assert len(fake.instances) == 1


def test_present_updates_retention_drift(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(retention_days=90)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DataRetentionTime"] == 90
    assert [c[0] for c in fake.calls] == [
        "DescribePrometheusInstances",
        "ModifyPrometheusInstanceAttributes",
        "DescribePrometheusInstances",
    ]
    updated = fake.calls[1][1]
    assert updated.InstanceId == "prom-101"
    assert updated.InstanceName == "prod-obs"
    assert updated.DataRetentionTime == 90
    assert updated.InstanceAttributes == []


def test_present_renames_via_instance_id(monkeypatch):
    fake = FakeMonitorClient([_instance(InstanceName="legacy")])
    _make_module(monkeypatch, fake)
    _run_args(instance_id="prom-101", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "new-name"
    assert fake.calls[1][0] == "ModifyPrometheusInstanceAttributes"
    assert fake.calls[1][1].InstanceName == "new-name"
    assert fake.calls[2][1].InstanceIds == ["prom-101"]


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMonitorClient([_instance()])
    _make_module(monkeypatch, fake)
    _run_args(retention_days=90, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DataRetentionTime"] == 15
    assert result["diff"]["after"]["DataRetentionTime"] == 90
    assert [c[0] for c in fake.calls] == ["DescribePrometheusInstances"]


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
    assert result["instance"] is None
