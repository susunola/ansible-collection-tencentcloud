"""Unit tests for the tke_node_pool write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/tke_node_pool.py`` with an in-memory fake TKE client whose
write operations mutate the node-pool store, so the module's post-write
``find_node_pool`` refetch converges immediately. Only the module's initial
describe is wrapped in the sdk-error envelope, so the error test targets
``DescribeClusterNodePools``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_node_pool as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POOL = {
    "NodePoolId": "np-8b0a1c2d",
    "Name": "pool-workers",
    "EnableAutoscale": False,
    "MaxNodesNum": 3,
    "MinNodesNum": 1,
    "Labels": [],
    "Taints": [],
    "DeletionProtection": False,
}

WRITE_OPS = (
    "CreateClusterNodePool",
    "ModifyClusterNodePool",
    "DeleteClusterNodePool",
)


def _pool(**overrides):
    """Return a node-pool fixture isolated from the shared constant."""
    pool = copy.deepcopy(POOL)
    pool.update(overrides)
    return pool


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "cluster_id": "cls-8b0a1c2d",
        "name": "pool-workers",
        "launch_configuration_json": None,
        "autoscaling_group_json": None,
        "enable_autoscale": None,
        "max_nodes_num": None,
        "min_nodes_num": None,
        "labels": {},
        "taints": [],
        "node_pool_os": None,
        "deletion_protection": None,
        "keep_instance": False,
        "tags": {},
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
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


class FakeTkeClient(object):
    """In-memory TKE client that mutates a small node-pool store."""

    def __init__(self, pools=None):
        self.pools = [copy.deepcopy(p) for p in (pools or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeClusterNodePools(self, request):
        self._record("DescribeClusterNodePools", request)
        return SimpleNamespace(NodePoolSet=[FakeResource(dict(p)) for p in self.pools])

    def CreateClusterNodePool(self, request):
        self._record("CreateClusterNodePool", request)
        self.pools.append(
            {
                "NodePoolId": "np-fake-001",
                "Name": request.Name,
                "EnableAutoscale": getattr(request, "EnableAutoscale", False),
            }
        )
        return SimpleNamespace()

    def ModifyClusterNodePool(self, request):
        self._record("ModifyClusterNodePool", request)
        for pool in self.pools:
            if pool["NodePoolId"] != request.NodePoolId:
                continue
            if getattr(request, "Name", None):
                pool["Name"] = request.Name
            if hasattr(request, "EnableAutoscale"):
                pool["EnableAutoscale"] = request.EnableAutoscale
            if hasattr(request, "MaxNodesNum"):
                pool["MaxNodesNum"] = request.MaxNodesNum
            if hasattr(request, "MinNodesNum"):
                pool["MinNodesNum"] = request.MinNodesNum
            if hasattr(request, "DeletionProtection"):
                pool["DeletionProtection"] = request.DeletionProtection
        return SimpleNamespace()

    def DeleteClusterNodePool(self, request):
        self._record("DeleteClusterNodePool", request)
        ids = list(request.NodePoolIds)
        self.pools = [p for p in self.pools if p["NodePoolId"] not in ids]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        '_load_tke',
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_build_describe_request_sets_cluster():
    request = mod.build_describe_request(FakeModels(), "cls-8b0a1c2d")
    assert request.ClusterId == "cls-8b0a1c2d"


def test_find_node_pool_returns_matching_pool():
    module = FakeModule()
    client = FakeTkeClient(pools=[_pool(), _pool(Name="pool-other", NodePoolId="np-2")])
    found = mod.find_node_pool(module, client, FakeModels(), "cls-8b0a1c2d", "pool-workers")
    assert found["NodePoolId"] == "np-8b0a1c2d"
    assert found["MaxNodesNum"] == 3


def test_find_node_pool_missing_returns_none():
    module = FakeModule()
    client = FakeTkeClient()
    assert mod.find_node_pool(module, client, FakeModels(), "cls-8b0a1c2d", "pool-workers") is None


def test_build_create_request_sets_required_fields():
    request = mod.build_create_request(FakeModels(), _params(launch_configuration_json="{}"))
    assert request.ClusterId == "cls-8b0a1c2d"
    assert request.Name == "pool-workers"
    assert request.LaunchConfigurePara == "{}"
    assert not hasattr(request, "EnableAutoscale")
    assert not hasattr(request, "Labels")


def test_build_create_request_sets_optional_fields():
    request = mod.build_create_request(
        FakeModels(),
        _params(
            launch_configuration_json="{}",
            autoscaling_group_json="{}",
            enable_autoscale=True,
            labels={"app": "workers", "zone": "2"},
            taints=[{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}],
            node_pool_os="tlinux2.6",
            deletion_protection=True,
            tags={"team": "platform"},
        ),
    )
    assert request.AutoScalingGroupPara == "{}"
    assert request.EnableAutoscale is True
    assert request.NodePoolOs == "tlinux2.6"
    assert request.DeletionProtection is True
    assert [(label.Name, label.Value) for label in request.Labels] == [
        ("app", "workers"),
        ("zone", "2"),
    ]
    assert request.Taints[0].Key == "dedicated"
    assert request.Taints[0].Value == "gpu"
    assert request.Taints[0].Effect == "NoSchedule"
    assert [(tag.Key, tag.Value) for tag in request.Tags] == [("team", "platform")]


def test_build_labels_sorts_and_stringifies():
    labels = mod._build_labels(FakeModels(), {"b": 2, "a": "1"})
    assert [(label.Name, label.Value) for label in labels] == [("a", "1"), ("b", "2")]


def test_build_taints_maps_fields():
    taints = mod._build_taints(FakeModels(), [{"key": "k", "value": "v", "effect": "NoExecute"}])
    assert len(taints) == 1
    assert taints[0].Key == "k"
    assert taints[0].Value == "v"
    assert taints[0].Effect == "NoExecute"


def test_build_tags_sorts_and_stringifies():
    tags = mod._build_tags(FakeModels(), {"b": 2, "a": "1"})
    assert [(tag.Key, tag.Value) for tag in tags] == [("a", "1"), ("b", "2")]


def test_labels_to_dict_round_trips():
    assert mod._labels_to_dict([{"Name": "a", "Value": "1"}]) == {"a": "1"}
    assert mod._labels_to_dict(None) == {}


def test_taints_to_list_round_trips_sorted():
    result = mod._taints_to_list(
        [{"Key": "b", "Value": "2", "Effect": "NoSchedule"}, {"Key": "a", "Value": "1", "Effect": "NoExecute"}]
    )
    assert result == [
        {"key": "a", "value": "1", "effect": "NoExecute"},
        {"key": "b", "value": "2", "effect": "NoSchedule"},
    ]


def test_create_issues_create_call(monkeypatch):
    module = FakeModule()
    client = FakeTkeClient()
    monkeypatch.setattr(mod, "build_create_request", lambda models, params: SimpleNamespace(Name="pool-workers"))
    mod._create(module, client, FakeModels(), _params(launch_configuration_json="{}"))
    assert len(module.sdk_calls) == 1
    assert module.sdk_calls[0][0] == client.CreateClusterNodePool


def test_update_sets_all_supplied_fields():
    module = FakeModule()
    client = FakeTkeClient()
    mod._update(
        module,
        client,
        FakeModels(),
        _params(name="pool-workers", enable_autoscale=True, max_nodes_num=5, min_nodes_num=2, deletion_protection=True),
        "np-8b0a1c2d",
    )
    assert len(module.sdk_calls) == 1
    request = module.sdk_calls[0][1]
    assert request.ClusterId == "cls-8b0a1c2d"
    assert request.NodePoolId == "np-8b0a1c2d"
    assert request.Name == "pool-workers"
    assert request.EnableAutoscale is True
    assert request.MaxNodesNum == 5
    assert request.MinNodesNum == 2
    assert request.DeletionProtection is True


def test_delete_sets_keep_instance_only_when_requested():
    module = FakeModule()
    client = FakeTkeClient()
    mod._delete(module, client, FakeModels(), "cls-8b0a1c2d", "np-8b0a1c2d", keep_instance=False)
    request = module.sdk_calls[0][1]
    assert request.NodePoolIds == ["np-8b0a1c2d"]
    assert not hasattr(request, "KeepInstance")

    module2 = FakeModule()
    client2 = FakeTkeClient()
    mod._delete(module2, client2, FakeModels(), "cls-8b0a1c2d", "np-8b0a1c2d", keep_instance=True)
    request2 = module2.sdk_calls[0][1]
    assert request2.KeepInstance is True


def test_pool_drift_empty_when_matching():
    module = FakeModule(_params(name="pool-workers"))
    assert mod._pool_drift(module, _pool()) == {}


def test_pool_drift_detects_name_change():
    module = FakeModule(_params(name="pool-renamed"))
    drift = mod._pool_drift(module, _pool(Name="pool-workers"))
    assert drift == {"Name": "pool-renamed"}


def test_pool_drift_detects_scalar_changes():
    module = FakeModule(_params(name="pool-workers", enable_autoscale=True, max_nodes_num=9, min_nodes_num=4, deletion_protection=True))
    drift = mod._pool_drift(module, _pool())
    assert drift == {
        "EnableAutoscale": True,
        "MaxNodesNum": 9,
        "MinNodesNum": 4,
        "DeletionProtection": True,
    }


def test_pool_drift_detects_label_and_taint_changes():
    module = FakeModule(
        _params(
            name="pool-workers",
            labels={"app": "workers"},
            taints=[{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}],
        )
    )
    drift = mod._pool_drift(module, _pool(Labels=[{"Name": "app", "Value": "old"}], Taints=[{"Key": "old", "Value": "1", "Effect": "NoExecute"}]))
    assert drift == {
        "Labels": {"app": "workers"},
        "Taints": [{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}],
    }


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]


def test_name_is_required(client):
    _run_args(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required" in exc.value.args[0]["msg"]


def test_absent_missing_pool_is_unchanged(client):
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_pool(client):
    client.pools = [_pool()]
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "deleted" in result["msg"]
    assert result["node_pool"] is None
    assert any(name == "DeleteClusterNodePool" for name, request in client.calls)
    assert client.pools == []
    delete_request = next(request for name, request in client.calls if name == "DeleteClusterNodePool")
    assert delete_request.NodePoolIds == ["np-8b0a1c2d"]
    assert not hasattr(delete_request, "KeepInstance")


def test_absent_delete_keeps_instances_when_requested(client):
    client.pools = [_pool()]
    _run_args(state="absent", keep_instance=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    delete_request = next(request for name, request in client.calls if name == "DeleteClusterNodePool")
    assert delete_request.KeepInstance is True


def test_present_create_requires_launch_configuration(client):
    _run_args(name="pool-workers", launch_configuration_json=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "launch_configuration_json is required" in exc.value.args[0]["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_creates_pool(client):
    _run_args(launch_configuration_json='{"InstanceType": "S5.MEDIUM2"}', enable_autoscale=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "created" in result["msg"]
    assert result["node_pool"]["Name"] == "pool-workers"
    assert any(name == "CreateClusterNodePool" for name, request in client.calls)
    assert len(client.pools) == 1
    create_request = next(request for name, request in client.calls if name == "CreateClusterNodePool")
    assert create_request.LaunchConfigurePara == '{"InstanceType": "S5.MEDIUM2"}'
    assert create_request.EnableAutoscale is True


def test_present_existing_is_up_to_date(client):
    client.pools = [_pool()]
    _run_args(name="pool-workers")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert result["node_pool"]["NodePoolId"] == "np-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_drifted_pool(client):
    client.pools = [_pool(MaxNodesNum=3)]
    _run_args(name="pool-workers", max_nodes_num=10, enable_autoscale=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert any(name == "ModifyClusterNodePool" for name, request in client.calls)
    assert client.pools[0]["MaxNodesNum"] == 10
    assert client.pools[0]["EnableAutoscale"] is True
    assert result["node_pool"]["MaxNodesNum"] == 10
    update_request = next(request for name, request in client.calls if name == "ModifyClusterNodePool")
    assert update_request.NodePoolId == "np-8b0a1c2d"
    assert update_request.MaxNodesNum == 10


def test_present_update_applies_labels_and_taints(client):
    client.pools = [_pool()]
    _run_args(
        name="pool-workers",
        labels={"app": "workers"},
        taints=[{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    update_request = next(request for name, request in client.calls if name == "ModifyClusterNodePool")
    assert [(label.Name, label.Value) for label in update_request.Labels] == [("app", "workers")]
    assert update_request.Taints[0].Key == "dedicated"
    assert update_request.Taints[0].Effect == "NoSchedule"


def test_check_mode_create_makes_no_writes(client):
    _run_args(launch_configuration_json="{}", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert client.pools == []
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_update_makes_no_writes(client):
    client.pools = [_pool(MaxNodesNum=3)]
    _run_args(name="pool-workers", max_nodes_num=10, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert result["diff"]["before"]["MaxNodesNum"] == 3
    assert result["diff"]["after"]["MaxNodesNum"] == 10
    assert client.pools[0]["MaxNodesNum"] == 3
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_delete_makes_no_writes(client):
    client.pools = [_pool()]
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete" in result["msg"]
    assert len(client.pools) == 1
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("tke api exploded")

    client.DescribeClusterNodePools = boom
    _run_args(name="pool-workers")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "tke api exploded"
    assert payload["error_code"] is None
