"""Unit tests for the tdmq_rocketmq_group write module (helpers + run_module).

Creates, updates and deletes a RocketMQ consumer group inside a namespace.
Lookup pages through DescribeRocketMQGroups (Limit 100, FilterOneGroup set
to the desired name as a server-side hint) and matches by exact ``Name``,
so the module keeps working even when the API returns fuzzy matches.
``GroupType`` is immutable on an existing group: drift fails through
``require_immutable_unchanged`` instead of silently recreating the group.
Every other attribute (remark, read/broadcast enablement, retry count) is
mutable and becomes a ModifyRocketMQGroup call.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _group(**overrides):
    """API-shaped RocketMQ group dict; fresh copy per call."""
    item = {
        "Name": "order-workers",
        "GroupType": "TCP",
        "ReadEnabled": True,
        "BroadcastEnabled": False,
        "RetryMaxTimes": 16,
        "Remark": "",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "cluster_id": "rocketmq-1",
        "namespace": "production",
        "name": "order-workers",
        "group_type": "TCP",
        "read_enabled": True,
        "broadcast_enabled": False,
        "retry_max_times": 16,
        "remark": "",
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
    """In-memory TdmqClient stand-in storing RocketMQ group dicts.

    DescribeRocketMQGroups filters by ClusterId + NamespaceId and pages
    with the request's Offset/Limit, so the module's paging loop is
    exercised; the module applies its own exact ``Name`` match. The fake
    ignores FilterOneGroup because that hint only narrows the server-side
    result set and the module must not depend on it. Create/Modify write
    back the attribute set the request builders place on the model.
    """

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _namespace_items(self, cluster_id, namespace_id):
        return [
            g for g in self.groups
            if g.get("_cluster") == cluster_id and g.get("_namespace") == namespace_id
        ]

    @staticmethod
    def _serializable(group):
        return {k: v for k, v in group.items() if not k.startswith("_")}

    def DescribeRocketMQGroups(self, request):
        self._record("DescribeRocketMQGroups", request)
        items = self._namespace_items(request.ClusterId, request.NamespaceId)
        offset = getattr(request, "Offset", 0) or 0
        limit = getattr(request, "Limit", 100) or 100
        page = items[offset:offset + limit]
        return SimpleNamespace(
            Groups=[FakeResource(self._serializable(g)) for g in page],
            TotalCount=len(items),
            RequestId="req-fake",
        )

    def CreateRocketMQGroup(self, request):
        self._record("CreateRocketMQGroup", request)
        self.groups.append({
            "_cluster": request.ClusterId,
            "_namespace": request.Namespaces[0],
            "Name": request.GroupId,
            "GroupType": request.GroupType,
            "ReadEnabled": request.ReadEnable,
            "BroadcastEnabled": request.BroadcastEnable,
            "RetryMaxTimes": request.RetryMaxTimes,
            "Remark": request.Remark,
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQGroup(self, request):
        self._record("ModifyRocketMQGroup", request)
        for group in self.groups:
            if (
                group.get("_cluster") == request.ClusterId
                and group.get("_namespace") == request.NamespaceId
                and group.get("Name") == request.GroupId
            ):
                group["ReadEnabled"] = request.ReadEnable
                group["BroadcastEnabled"] = request.BroadcastEnable
                group["RetryMaxTimes"] = request.RetryMaxTimes
                group["Remark"] = request.Remark
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQGroup(self, request):
        self._record("DeleteRocketMQGroup", request)
        self.groups = [
            g for g in self.groups
            if not (
                g.get("_cluster") == request.ClusterId
                and g.get("_namespace") == request.NamespaceId
                and g.get("Name") == request.GroupId
            )
        ]
        return SimpleNamespace(RequestId="req-fake")


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


def _store(fake, group, cluster="rocketmq-1", namespace="production"):
    """Store an API-shaped group dict under a cluster/namespace identity."""
    record = dict(group)
    record["_cluster"] = cluster
    record["_namespace"] = namespace
    fake.groups.append(record)


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / comparable / desired tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=20)
    assert request.ClusterId == "rocketmq-1"
    assert request.NamespaceId == "production"
    assert request.Offset == 20
    assert request.Limit == 100
    assert request.FilterOneGroup == "order-workers"


def test_describe_request_default_offset_is_zero():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Offset == 0


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(group_type="HTTP", remark="billing", retry_max_times=12))
    assert request.GroupId == "order-workers"
    assert request.Namespaces == ["production"]
    assert request.ClusterId == "rocketmq-1"
    assert request.ReadEnable is True
    assert request.BroadcastEnable is False
    assert request.Remark == "billing"
    assert request.GroupType == "HTTP"
    assert request.RetryMaxTimes == 12


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(remark="billing", read_enabled=False, retry_max_times=32))
    assert request.ClusterId == "rocketmq-1"
    assert request.NamespaceId == "production"
    assert request.GroupId == "order-workers"
    assert request.Remark == "billing"
    assert request.ReadEnable is False
    assert request.BroadcastEnable is False
    assert request.RetryMaxTimes == 32


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.GroupId == "order-workers"
    assert request.NamespaceId == "production"
    assert request.ClusterId == "rocketmq-1"


def test_comparable_coerces_scalar_types():
    value = mod.comparable({
        "Name": "order-workers",
        "GroupType": "HTTP",
        "ReadEnabled": 1,
        "BroadcastEnabled": 0,
        "RetryMaxTimes": "16",
        "Remark": None,
    })
    assert value == {
        "Name": "order-workers",
        "GroupType": "HTTP",
        "ReadEnabled": True,
        "BroadcastEnabled": False,
        "RetryMaxTimes": 16,
        "Remark": "",
    }


def test_comparable_tolerates_missing_scalars():
    value = mod.comparable({"Name": "order-workers", "GroupType": "TCP"})
    assert value["ReadEnabled"] is False
    assert value["BroadcastEnabled"] is False
    assert value["RetryMaxTimes"] == 0
    assert value["Remark"] == ""


def test_desired_matches_params():
    assert mod.desired(_params()) == {
        "Name": "order-workers",
        "GroupType": "TCP",
        "ReadEnabled": True,
        "BroadcastEnabled": False,
        "RetryMaxTimes": 16,
        "Remark": "",
    }


def test_desired_reflects_overrides():
    assert mod.desired(_params(group_type="HTTP", read_enabled=False, remark="x"))["GroupType"] == "HTTP"
    assert mod.desired(_params(group_type="HTTP", read_enabled=False, remark="x"))["ReadEnabled"] is False
    assert mod.desired(_params(group_type="HTTP", read_enabled=False, remark="x"))["Remark"] == "x"


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_name(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group(Name="rg-a"))
    _store(fake, _group(Name="order-workers"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "order-workers"
    assert value["Remark"] == ""


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group(Name="rg-a"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_other_namespace_is_isolated(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group(Name="order-workers"), namespace="staging")
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_across_pages(monkeypatch):
    groups = [_group(Name="rg-%03d" % i) for i in range(205)]
    groups.append(_group(Name="order-workers", RetryMaxTimes=42))
    fake = FakeTdmqClient()
    for g in groups:
        _store(fake, g)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "order-workers"
    assert value["RetryMaxTimes"] == 42
    assert [c[0] for c in fake.calls].count("DescribeRocketMQGroups") == 3  # pages 0/100/200


def test_find_page_exhaustion_stops(monkeypatch):
    fake = FakeTdmqClient()
    for i in range(250):
        _store(fake, _group(Name="rg-%03d" % i))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert [c[0] for c in fake.calls].count("DescribeRocketMQGroups") == 3


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_name_missing_fails():
    module_args(
        state="present",
        cluster_id="rocketmq-1",
        namespace="production",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments: name" in exc.value.args[0]["msg"]


def test_present_creates_group(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["group"]
    assert group["Name"] == "order-workers"
    assert group["GroupType"] == "TCP"
    assert group["ReadEnabled"] is True
    assert group["RetryMaxTimes"] == 16
    assert [c[0] for c in fake.calls].count("DescribeRocketMQGroups") == 2  # find + refetch
    assert [c[0] for c in fake.calls].count("CreateRocketMQGroup") == 1
    assert not any(c[0] == "ModifyRocketMQGroup" for c in fake.calls)


def test_present_creates_with_overrides(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(group_type="HTTP", remark="billing", broadcast_enabled=True, retry_max_times=12)
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["group"]
    assert group["GroupType"] == "HTTP"
    assert group["Remark"] == "billing"
    assert group["BroadcastEnabled"] is True
    assert group["RetryMaxTimes"] == 12
    create = [c for c in fake.calls if c[0] == "CreateRocketMQGroup"][0][1]
    assert create.GroupType == "HTTP"
    assert create.Namespaces == ["production"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None  # nothing was created to report
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Name"] == "order-workers"
    assert not any(c[0] == "CreateRocketMQGroup" for c in fake.calls)
    assert fake.groups == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"]["Name"] == "order-workers"
    assert not any(c[0] in ("CreateRocketMQGroup", "ModifyRocketMQGroup") for c in fake.calls)


def test_present_remark_drift_triggers_update(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(remark="billing")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Remark"] == "billing"
    update = [c for c in fake.calls if c[0] == "ModifyRocketMQGroup"][0][1]
    assert update.GroupId == "order-workers"
    assert update.Remark == "billing"
    assert update.NamespaceId == "production"
    assert "CreateRocketMQGroup" not in [c[0] for c in fake.calls]


def test_present_read_enabled_drift_triggers_update(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(read_enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["ReadEnabled"] is False
    update = [c for c in fake.calls if c[0] == "ModifyRocketMQGroup"][0][1]
    assert update.ReadEnable is False


def test_present_retry_and_broadcast_drift_triggers_update(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(broadcast_enabled=True, retry_max_times=32)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["BroadcastEnabled"] is True
    assert result["group"]["RetryMaxTimes"] == 32
    update = [c for c in fake.calls if c[0] == "ModifyRocketMQGroup"][0][1]
    assert update.BroadcastEnable is True
    assert update.RetryMaxTimes == 32


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, remark="billing")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Remark"] == ""  # pre-change state reported
    assert result["diff"]["after"]["Remark"] == "billing"
    assert not any(c[0] == "ModifyRocketMQGroup" for c in fake.calls)
    assert fake.groups[0]["Remark"] == ""  # remote untouched


def test_present_group_type_drift_fails_immutable(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(group_type="HTTP")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing RocketMQ consumer group" in payload["msg"]
    assert payload["immutable_changes"] == {
        "GroupType": {"before": "TCP", "after": "HTTP"},
    }
    assert payload["replacement_required"] is True
    assert not any(c[0] in ("CreateRocketMQGroup", "ModifyRocketMQGroup") for c in fake.calls)


def test_present_group_type_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, group_type="HTTP")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "replacement_required" in exc.value.args[0]
    assert not any(c[0] in ("CreateRocketMQGroup", "ModifyRocketMQGroup") for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group(Name="rg-a"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"] is None
    assert not any(c[0] == "DeleteRocketMQGroup" for c in fake.calls)


def test_absent_deletes_group(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group(Name="order-workers"))
    _store(fake, _group(Name="rg-a"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteRocketMQGroup"][0][1]
    assert delete.GroupId == "order-workers"
    assert delete.NamespaceId == "production"
    assert delete.ClusterId == "rocketmq-1"
    assert [g.get("Name") for g in fake.groups] == ["rg-a"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == "order-workers"  # pre-delete state reported
    assert result["diff"]["after"] is None
    assert not any(c[0] == "DeleteRocketMQGroup" for c in fake.calls)
    assert len(fake.groups) == 1


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


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeTdmqClient()
    _store(fake, _group())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["group"]["Name"] == "order-workers"
