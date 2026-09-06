"""Unit tests for the tdmq_namespace write module (helpers + run_module).

Creates, updates and deletes TDMQ Pulsar namespaces with their retention
and subscription-lifecycle policies. Lookup pages through
DescribeEnvironments (Limit 20) and matches by ``EnvironmentId`` or the
``NamespaceName`` alias some APIs return; everything else is fully
mutable (there is no immutable field), so drift always becomes a
ModifyEnvironmentAttributes call. The module compares *normalized* views
where retention minutes/size are read out of the nested RetentionPolicy.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_namespace as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _namespace(**overrides):
    """API-shaped namespace dict; fresh copy per call."""
    item = {
        "EnvironmentId": "ns-prod",
        "ClusterId": "pulsar-1",
        "MsgTTL": 86400,
        "Remark": "",
        "RetentionPolicy": {"TimeInMinutes": 0, "SizeInMB": 0},
        "AutoSubscriptionCreation": False,
        "SubscriptionExpirationTimeEnable": False,
        "SubscriptionExpirationTime": 0,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "cluster_id": "pulsar-1",
        "name": "ns-prod",
        "message_ttl": 86400,
        "remark": "",
        "retention_minutes": 0,
        "retention_size_mb": 0,
        "auto_subscription_creation": False,
        "subscription_expiration_enabled": False,
        "subscription_expiration_time": 0,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeTdmqClient(object):
    """In-memory TdmqClient stand-in storing namespace dicts.

    DescribeEnvironments filters by ClusterId and paginates with the
    request's Offset/Limit so the module's paging loop is exercised; the
    module applies its own EnvironmentId/NamespaceName identity match.
    Create/Modify write back the full set of attributes the module's
    apply_request helper placed on the request model.
    """

    def __init__(self, namespaces=None):
        self.namespaces = [dict(n) for n in (namespaces or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _cluster_items(self, cluster_id):
        return [n for n in self.namespaces if n.get("ClusterId") == cluster_id or cluster_id is None]

    def DescribeEnvironments(self, request):
        self._record("DescribeEnvironments", request)
        items = self._cluster_items(request.ClusterId)
        offset = getattr(request, "Offset", 0)
        limit = getattr(request, "Limit", 20)
        page = items[offset:offset + limit]
        return SimpleNamespace(
            EnvironmentSet=[FakeResource(dict(n)) for n in page],
            TotalCount=len(items),
            RequestId="req-fake",
        )

    def CreateEnvironment(self, request):
        self._record("CreateEnvironment", request)
        self.namespaces.append(_namespace_from_request(request))
        return SimpleNamespace(EnvironmentId=request.EnvironmentId, RequestId="req-fake")

    def ModifyEnvironmentAttributes(self, request):
        self._record("ModifyEnvironmentAttributes", request)
        for stored in self.namespaces:
            if stored.get("EnvironmentId") == request.EnvironmentId and stored.get("ClusterId") == request.ClusterId:
                stored.update(_namespace_from_request(request))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEnvironments(self, request):
        self._record("DeleteEnvironments", request)
        self.namespaces = [
            n for n in self.namespaces
            if n.get("ClusterId") != request.ClusterId or n.get("EnvironmentId") not in (request.EnvironmentIds or [])
        ]
        return SimpleNamespace(RequestId="req-fake")


def _namespace_from_request(request):
    return {
        "EnvironmentId": request.EnvironmentId,
        "ClusterId": request.ClusterId,
        "MsgTTL": request.MsgTTL,
        "Remark": request.Remark,
        "RetentionPolicy": {
            "TimeInMinutes": request.RetentionPolicy.TimeInMinutes,
            "SizeInMB": request.RetentionPolicy.SizeInMB,
        },
        "AutoSubscriptionCreation": request.AutoSubscriptionCreation,
        "SubscriptionExpirationTimeEnable": request.SubscriptionExpirationTimeEnable,
        "SubscriptionExpirationTime": request.SubscriptionExpirationTime,
    }


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TdmqClient=object)),
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
# request-builder / normalize / desired tests
# ---------------------------------------------------------------------------


def test_retention_builds_policy_model():
    policy = mod.retention(FakeModels(), _params(retention_minutes=1440, retention_size_mb=10240))
    assert policy.TimeInMinutes == 1440
    assert policy.SizeInMB == 10240


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=20)
    assert request.ClusterId == "pulsar-1"
    assert request.EnvironmentId == "ns-prod"
    assert request.Offset == 20
    assert request.Limit == 20


def test_apply_request_maps_all_attributes():
    params = _params(
        message_ttl=604800,
        remark="production",
        retention_minutes=1440,
        retention_size_mb=10240,
        auto_subscription_creation=True,
        subscription_expiration_enabled=True,
        subscription_expiration_time=3600,
    )
    request = mod.apply_request(FakeModels().CreateEnvironmentRequest(), FakeModels(), params)
    assert request.EnvironmentId == "ns-prod"
    assert request.ClusterId == "pulsar-1"
    assert request.MsgTTL == 604800
    assert request.Remark == "production"
    assert request.RetentionPolicy.TimeInMinutes == 1440
    assert request.RetentionPolicy.SizeInMB == 10240
    assert request.AutoSubscriptionCreation is True
    assert request.SubscriptionExpirationTimeEnable is True
    assert request.SubscriptionExpirationTime == 3600


def test_create_and_update_requests_share_builder():
    models = FakeModels()
    create = mod.create_request(models, _params())
    update = mod.update_request(models, _params())
    assert type(create).__name__ == "CreateEnvironmentRequest"
    assert type(update).__name__ == "ModifyEnvironmentAttributesRequest"
    assert update.EnvironmentId == create.EnvironmentId
    assert update.RetentionPolicy.TimeInMinutes == create.RetentionPolicy.TimeInMinutes


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.ClusterId == "pulsar-1"
    assert request.EnvironmentIds == ["ns-prod"]


def test_normalize_reads_nested_policy():
    value = mod.normalize(
        {
            "EnvironmentId": "ns-prod",
            "MsgTTL": 604800,
            "Remark": None,
            "RetentionPolicy": {"TimeInMinutes": 1440, "SizeInMB": 10240},
            "AutoSubscriptionCreation": 1,
            "SubscriptionExpirationTimeEnable": None,
            "SubscriptionExpirationTime": None,
        }
    )
    assert value["EnvironmentId"] == "ns-prod"
    assert value["MsgTTL"] == 604800
    assert value["Remark"] == ""
    assert value["RetentionMinutes"] == 1440
    assert value["RetentionSizeMB"] == 10240
    assert value["AutoSubscriptionCreation"] is True
    assert value["SubscriptionExpirationTimeEnable"] is False
    assert value["SubscriptionExpirationTime"] == 0


def test_normalize_falls_back_to_namespace_name_and_empty_policy():
    value = mod.normalize({"NamespaceName": "ns-prod", "MsgTTL": 60, "Remark": "x"})
    assert value["EnvironmentId"] == "ns-prod"
    assert value["RetentionMinutes"] == 0
    assert value["RetentionSizeMB"] == 0


def test_desired_matches_params():
    assert mod.desired(_params()) == {
        "EnvironmentId": "ns-prod",
        "MsgTTL": 86400,
        "Remark": "",
        "RetentionMinutes": 0,
        "RetentionSizeMB": 0,
        "AutoSubscriptionCreation": False,
        "SubscriptionExpirationTimeEnable": False,
        "SubscriptionExpirationTime": 0,
    }


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_environment_id(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-a"), _namespace(EnvironmentId="ns-prod")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvironmentId"] == "ns-prod"


def test_find_matches_namespace_name_alias(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-a"), _namespace(EnvironmentId=None, NamespaceName="ns-prod")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["NamespaceName"] == "ns-prod"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-a")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_other_cluster_is_isolated(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-prod", ClusterId="pulsar-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_across_pages(monkeypatch):
    namespaces = [_namespace(EnvironmentId="ns-%03d" % i) for i in range(25)]
    namespaces.append(_namespace(EnvironmentId="ns-prod", MsgTTL=777))
    fake = FakeTdmqClient(namespaces)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvironmentId"] == "ns-prod"
    assert value["MsgTTL"] == 777
    assert [c[0] for c in fake.calls].count("DescribeEnvironments") == 2  # page 0 + page 20


def test_find_page_exhaustion_stops(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-%03d" % i) for i in range(45)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert [c[0] for c in fake.calls].count("DescribeEnvironments") == 3


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_message_ttl_lower_bound_fails():
    _run_args(message_ttl=59)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "message_ttl must be between 60 and 1296000 seconds" in exc.value.args[0]["msg"]


def test_message_ttl_upper_bound_fails():
    _run_args(message_ttl=1296001)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "message_ttl must be between 60 and 1296000 seconds" in exc.value.args[0]["msg"]


def test_present_creates_namespace(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    namespace = result["namespace"]
    assert namespace["EnvironmentId"] == "ns-prod"
    assert namespace["MsgTTL"] == 86400
    assert [c[0] for c in fake.calls].count("DescribeEnvironments") == 2  # find + refetch
    assert [c[0] for c in fake.calls].count("CreateEnvironment") == 1
    assert not any(c[0] == "ModifyEnvironmentAttributes" for c in fake.calls)


def test_present_creates_with_policies(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(
        message_ttl=604800,
        remark="production",
        retention_minutes=1440,
        retention_size_mb=10240,
        auto_subscription_creation=True,
        subscription_expiration_enabled=True,
        subscription_expiration_time=3600,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    namespace = result["namespace"]
    assert namespace["RetentionPolicy"] == {"TimeInMinutes": 1440, "SizeInMB": 10240}
    assert namespace["AutoSubscriptionCreation"] is True
    create = [c for c in fake.calls if c[0] == "CreateEnvironment"][0][1]
    assert create.RetentionPolicy.TimeInMinutes == 1440


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None  # nothing was created to report
    assert not any(c[0] == "CreateEnvironment" for c in fake.calls)
    assert fake.namespaces == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTdmqClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"]["EnvironmentId"] == "ns-prod"
    assert not any(c[0] in ("CreateEnvironment", "ModifyEnvironmentAttributes") for c in fake.calls)


def test_present_ttl_drift_triggers_update(monkeypatch):
    fake = FakeTdmqClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(message_ttl=172800)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["MsgTTL"] == 172800
    update = [c for c in fake.calls if c[0] == "ModifyEnvironmentAttributes"][0][1]
    assert update.EnvironmentId == "ns-prod"
    assert update.MsgTTL == 172800
    assert "CreateEnvironment" not in [c[0] for c in fake.calls]


def test_present_retention_drift_triggers_update(monkeypatch):
    fake = FakeTdmqClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(retention_minutes=1440, retention_size_mb=10240)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["RetentionPolicy"] == {"TimeInMinutes": 1440, "SizeInMB": 10240}
    update = [c for c in fake.calls if c[0] == "ModifyEnvironmentAttributes"][0][1]
    assert update.RetentionPolicy.TimeInMinutes == 1440
    assert update.RetentionPolicy.SizeInMB == 10240


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, message_ttl=172800)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["MsgTTL"] == 86400  # pre-change reported
    assert not any(c[0] == "ModifyEnvironmentAttributes" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTdmqClient([_namespace(EnvironmentId="ns-a")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"] is None
    assert not any(c[0] == "DeleteEnvironments" for c in fake.calls)


def test_absent_deletes_namespace(monkeypatch):
    fake = FakeTdmqClient([_namespace(), _namespace(EnvironmentId="ns-a")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteEnvironments"][0][1]
    assert delete.ClusterId == "pulsar-1"
    assert delete.EnvironmentIds == ["ns-prod"]
    assert [n["EnvironmentId"] for n in fake.namespaces] == ["ns-a"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_namespace()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["EnvironmentId"] == "ns-prod"  # pre-delete reported
    assert not any(c[0] == "DeleteEnvironments" for c in fake.calls)
    assert len(fake.namespaces) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TdmqClient=object)),
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
