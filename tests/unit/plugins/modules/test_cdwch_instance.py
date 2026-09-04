"""Unit tests for the cdwch_instance write module (helpers + run_module).

Covers the create / destroy / reconcile flows of
``plugins/modules/cdwch_instance.py`` with an in-memory fake TCHouse-C
client, following the collection's module test harness (see harness.py).

The module reconciles ClickHouse (data) and ZooKeeper (common) node
spec / count / disk. Write operations are asynchronous, so the fake
client transitions its store from a transitional status to ``Serving``
once describe polls pass the first (``auto_advance``), mirroring how the
real API only reports the converged state after a few seconds.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_instance as cdwch
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "cdwch-8b0a1c2d",
    "InstanceName": "prod-clickhouse",
    "Status": "Serving",
    "Zone": "ap-beijing-2",
    "VpcId": "vpc-0a1b2c3d",
    "SubnetId": "subnet-4e5f6a7b",
    "Version": "23.8.9.1",
    "HA": "true",
    "HAZk": True,
    "PayMode": "hour",
    "Tags": [{"TagKey": "env", "TagValue": "prod"}],
    "MasterSummary": {"Spec": "S_16_64_H", "NodeSize": 2, "Disk": 200},
    "CommonSummary": {"Spec": "S_4_16_H", "NodeSize": 3, "Disk": 100},
}

WRITE_OPS = ("CreateInstanceNew", "DestroyInstance", "ScaleUpInstance", "ResizeDisk", "ScaleOutInstance")

# Statuses the real API reports while an asynchronous operation is still
# converging; the fake advances them to "Serving" once reads pass the first.
_TRANSITIONAL = ("creating", "modifying")


def _serving(**overrides):
    """Return a Serving fixture isolated from the shared INSTANCE constant.

    Write ops mutate nested summary dicts in place; sharing them with a
    module-level constant would leak one test's writes into the next.
    """
    instance = copy.deepcopy(INSTANCE)
    instance.update(overrides)
    return instance


class FakeCdwchClient(object):
    """In-memory TCHouse-C client that mutates a small instance store."""

    def __init__(self, instances=None, auto_advance=False):
        # Deep-copy so nested summaries mutated by write ops never leak back
        # into the shared INSTANCE fixture used by later tests.
        self.instances = [copy.deepcopy(instance) for instance in (instances or [])]
        self.auto_advance = auto_advance
        self.describe_count = 0
        self.calls = []
        self._next_id = 1000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, instance_id):
        return next(instance for instance in self.instances if instance["InstanceId"] == instance_id)

    def _visible(self):
        """Advance transitional statuses to Serving once reads pass the first.

        ``find`` re-reads the instance through ``DescribeInstance`` after the
        list call, so the transition must mutate the store itself (not just
        the copy returned by ``DescribeInstancesNew``). ``deleting``
        instances are dropped, which lets the destroy waiter converge to a
        missing resource exactly like the real API does.
        """
        if self.auto_advance and self.describe_count >= 2:
            kept = []
            for instance in self.instances:
                status = str(instance.get("Status", "")).lower()
                if status == "deleting":
                    continue
                if status in _TRANSITIONAL:
                    instance["Status"] = "Serving"
                kept.append(instance)
            self.instances = kept
        return [dict(instance) for instance in self.instances]

    def DescribeInstancesNew(self, request):
        self._record("DescribeInstancesNew", request)
        self.describe_count += 1
        return SimpleNamespace(InstancesList=[FakeResource(item) for item in self._visible()])

    def DescribeInstance(self, request):
        self._record("DescribeInstance", request)
        return SimpleNamespace(InstanceInfo=FakeResource(dict(self._by_id(request.InstanceId))))

    def CreateInstanceNew(self, request):
        self._record("CreateInstanceNew", request)
        instance_id = "cdwch-new%04d" % self._next_id
        self._next_id += 1
        data = request.DataSpec
        instance = {
            "InstanceId": instance_id,
            "InstanceName": request.InstanceName,
            "Status": "creating",
            "Zone": request.Zone,
            "VpcId": request.UserVPCId,
            "SubnetId": request.UserSubnetId,
            "Version": request.ProductVersion,
            "HA": "true" if request.HaFlag else "false",
            "HAZk": request.HAZk,
            "PayMode": "prepay" if request.ChargeProperties.ChargeType == "PREPAID" else "hour",
            "Tags": [{"TagKey": tag.TagKey, "TagValue": tag.TagValue} for tag in (request.TagItems or [])],
            "MasterSummary": {"Spec": data.SpecName, "NodeSize": data.Count, "Disk": data.DiskSize},
        }
        common = request.CommonSpec
        if common is not None:
            instance["CommonSummary"] = {"Spec": common.SpecName, "NodeSize": common.Count, "Disk": common.DiskSize}
        self.instances.append(instance)
        return SimpleNamespace(InstanceId=instance_id)

    def DestroyInstance(self, request):
        self._record("DestroyInstance", request)
        self._by_id(request.InstanceId)["Status"] = "deleting"
        return SimpleNamespace()

    def _summary(self, request):
        instance = self._by_id(request.InstanceId)
        instance["Status"] = "modifying"
        key = "MasterSummary" if request.Type == "DATA" else "CommonSummary"
        return instance.setdefault(key, {})

    def ScaleUpInstance(self, request):
        self._record("ScaleUpInstance", request)
        self._summary(request)["Spec"] = request.SpecName
        return SimpleNamespace()

    def ResizeDisk(self, request):
        self._record("ResizeDisk", request)
        self._summary(request)["Disk"] = request.DiskSize
        return SimpleNamespace()

    def ScaleOutInstance(self, request):
        self._record("ScaleOutInstance", request)
        self._summary(request)["NodeSize"] = request.NodeCount
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helper functions that only need params/sdk_call."""

    def __init__(self, **params):
        self.params = dict(params)
        self.check_mode = False
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCdwchClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cdwch, "_load",
        lambda: (FakeModels(), SimpleNamespace(CdwchClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_instance_id():
    request = cdwch.describe_request(FakeModels(), {"instance_id": "cdwch-abc", "name": "ignored"})
    assert request.SearchInstanceId == "cdwch-abc"
    assert request.SearchInstanceName is None
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.IsSimple is False


def test_describe_request_filters_by_name_when_no_instance_id():
    request = cdwch.describe_request(FakeModels(), {"name": "prod-clickhouse"})
    assert request.SearchInstanceId is None
    assert request.SearchInstanceName == "prod-clickhouse"


def test_describe_request_accepts_offset():
    request = cdwch.describe_request(FakeModels(), {}, offset=40)
    assert request.Offset == 40


def test_detail_request_sets_instance_id_and_openapi_flag():
    request = cdwch.detail_request(FakeModels(), "cdwch-abc")
    assert request.InstanceId == "cdwch-abc"
    assert request.IsOpenApi is True


def test_tags_sorts_and_maps_values():
    tags = cdwch._tags(FakeModels(), {"z": "1", "a": "2"})
    assert [(tag.TagKey, tag.TagValue) for tag in tags] == [("a", "2"), ("z", "1")]


def test_tags_empty_when_none():
    assert cdwch._tags(FakeModels(), None) == []


def test_spec_builder_sets_fields():
    item = cdwch._spec(FakeModels(), "S_16_64_H", 2, 200)
    assert item.SpecName == "S_16_64_H"
    assert item.Count == 2
    assert item.DiskSize == 200


def test_spec_builder_none_when_all_omitted():
    assert cdwch._spec(FakeModels(), None, None, None) is None


def test_secondary_zones_builder_maps_zone_and_subnet():
    zones = cdwch._secondary_zones(FakeModels(), [
        {"zone": "ap-beijing-3", "subnet_id": "subnet-z", "user_ip_count": 32},
        {"zone": "ap-beijing-4", "subnet_id": "subnet-y"},
    ])
    assert zones[0].SecondaryZone == "ap-beijing-3"
    assert zones[0].SecondarySubnet == "subnet-z"
    assert zones[0].UserIpNum == "32"
    assert zones[0].SecondaryUserSubnetIPNum == 32
    assert zones[1].UserIpNum is None
    assert zones[1].SecondaryUserSubnetIPNum is None


def test_secondary_zones_empty_when_none():
    assert cdwch._secondary_zones(FakeModels(), None) == []


def _create_params(**overrides):
    params = {
        "zone": "ap-beijing-2",
        "high_availability": True,
        "zk_high_availability": True,
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "product_version": "23.8.9.1",
        "name": "new-clickhouse",
        "charge_type": "PREPAID",
        "auto_renew": True,
        "period_months": 12,
        "data_spec_name": "S_16_64_H",
        "data_node_count": 2,
        "data_disk_size": 200,
        "common_spec_name": "S_4_16_H",
        "common_node_count": 3,
        "common_disk_size": 100,
        "tags": {"env": "prod"},
        "cls_logset_id": "cls-1",
        "cos_bucket_name": "bucket-1",
        "mount_disk_type": 1,
        "secondary_zones": [{"zone": "ap-beijing-3", "subnet_id": "subnet-z", "user_ip_count": 32}],
        "password": "secret",
    }
    params.update(overrides)
    return params


def test_create_request_sets_all_fields():
    request = cdwch.create_request(FakeModels(), _create_params())
    assert request.Zone == "ap-beijing-2"
    assert request.HaFlag is True
    assert request.UserVPCId == "vpc-1"
    assert request.UserSubnetId == "subnet-1"
    assert request.ProductVersion == "23.8.9.1"
    assert request.InstanceName == "new-clickhouse"
    assert request.ChargeProperties.ChargeType == "PREPAID"
    assert request.ChargeProperties.RenewFlag == 1
    assert request.ChargeProperties.TimeSpan == 12
    assert request.DataSpec.SpecName == "S_16_64_H"
    assert request.DataSpec.Count == 2
    assert request.DataSpec.DiskSize == 200
    assert request.CommonSpec.SpecName == "S_4_16_H"
    assert request.CommonSpec.Count == 3
    assert request.CommonSpec.DiskSize == 100
    assert [(tag.TagKey, tag.TagValue) for tag in request.TagItems] == [("env", "prod")]
    assert request.ClsLogSetId == "cls-1"
    assert request.CosBucketName == "bucket-1"
    assert request.MountDiskType == 1
    assert request.HAZk is True
    assert request.SecondaryZoneInfo[0].SecondaryZone == "ap-beijing-3"
    assert request.SecondaryZoneInfo[0].SecondarySubnet == "subnet-z"
    assert request.SecondaryZoneInfo[0].UserIpNum == "32"
    assert request.CkDefaultUserPwd == "secret"


def test_create_request_applies_defaults_and_optionals():
    request = cdwch.create_request(FakeModels(), _create_params(
        high_availability=False, charge_type=None, auto_renew=False, period_months=1,
        common_spec_name=None, common_node_count=None, common_disk_size=None,
        tags=None, zk_high_availability=None, mount_disk_type=None, secondary_zones=None,
    ))
    assert request.HaFlag is False
    assert request.ChargeProperties.ChargeType == "POSTPAID_BY_HOUR"
    assert request.ChargeProperties.RenewFlag == 0
    assert request.ChargeProperties.TimeSpan == 1
    assert request.CommonSpec is None
    assert request.TagItems == []
    assert request.HAZk is None
    assert request.MountDiskType is None
    assert request.SecondaryZoneInfo == []


def test_destroy_request_sets_instance_id():
    request = cdwch.destroy_request(FakeModels(), "cdwch-abc")
    assert request.InstanceId == "cdwch-abc"


def test_scale_nodes_request_sets_scale_context():
    request = cdwch.scale_nodes_request(FakeModels(), {
        "scale_out_cluster": "vc-1", "user_subnet_ip_count": 8,
        "scale_out_node_ip": "10.0.0.9", "reduce_shard_info": ["10.0.0.1"],
    }, "cdwch-abc", "DATA", 4)
    assert request.InstanceId == "cdwch-abc"
    assert request.Type == "DATA"
    assert request.NodeCount == 4
    assert request.ScaleOutCluster == "vc-1"
    assert request.UserSubnetIPNum == 8
    assert request.ScaleOutNodeIp == "10.0.0.9"
    assert request.ReduceShardInfo == ["10.0.0.1"]


def test_scale_spec_request_rolling_flag():
    assert cdwch.scale_spec_request(FakeModels(), "cdwch-abc", "COMMON", "S_8_32_H").ScaleUpEnableRolling is True
    assert cdwch.scale_spec_request(FakeModels(), "cdwch-abc", "DATA", "S_32_128_H", rolling=False).ScaleUpEnableRolling is False


def test_resize_disk_request_fields():
    request = cdwch.resize_disk_request(FakeModels(), "cdwch-abc", "DATA", 400)
    assert request.InstanceId == "cdwch-abc"
    assert request.Type == "DATA"
    assert request.DiskSize == 400


def test_tag_dict_maps_tag_items():
    assert cdwch._tag_dict([{"TagKey": "a", "TagValue": "b"}]) == {"a": "b"}
    assert cdwch._tag_dict(None) == {}
    assert cdwch._tag_dict([]) == {}


def test_find_by_id_enriches_with_detail():
    module = FakeModule()
    client = FakeCdwchClient(instances=[INSTANCE])
    found = cdwch.find(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"})
    assert found["InstanceName"] == "prod-clickhouse"
    assert found["MasterSummary"]["Spec"] == "S_16_64_H"
    names = [name for name, request in client.calls]
    assert names == ["DescribeInstancesNew", "DescribeInstance"]


def test_find_by_name_matches():
    module = FakeModule()
    client = FakeCdwchClient(instances=[INSTANCE])
    found = cdwch.find(module, client, FakeModels(), {"name": "prod-clickhouse"})
    assert found["InstanceId"] == "cdwch-8b0a1c2d"


def test_find_no_match_returns_none():
    module = FakeModule()
    client = FakeCdwchClient(instances=[INSTANCE])
    assert cdwch.find(module, client, FakeModels(), {"name": "nope"}) is None


def test_find_multiple_matches_fails():
    module = FakeModule()
    duplicate = _serving(InstanceId="cdwch-0002")
    client = FakeCdwchClient(instances=[INSTANCE, duplicate])
    with pytest.raises(AnsibleFailJson) as exc:
        cdwch.find(module, client, FakeModels(), {"name": "prod-clickhouse"})
    assert "Multiple TCHouse-C instances" in exc.value.args[0]["msg"]


def test_wait_helper_returns_when_serving():
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    client = FakeCdwchClient(instances=[INSTANCE])
    cdwch._wait(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"}, lambda value: value is not None, "create")


def test_wait_helper_returns_when_deleted():
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    client = FakeCdwchClient(instances=[_serving(Status="Deleted")])
    cdwch._wait(
        module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"},
        lambda value: value is None or value.get("Status") == "Deleted", "destroy",
    )


def test_wait_helper_advances_transitional_status():
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    client = FakeCdwchClient(instances=[_serving(Status="creating")], auto_advance=True)
    cdwch._wait(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"}, lambda value: value is not None, "create")
    assert client.describe_count >= 2
    assert client.instances[0]["Status"] == "Serving"


def test_wait_helper_times_out(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=1, waiter_delay=1)
    client = FakeCdwchClient(instances=[_serving(Status="creating")])
    with pytest.raises(AnsibleFailJson) as exc:
        cdwch._wait(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"}, lambda value: value is not None, "create")
    assert "Timed out" in exc.value.args[0]["msg"]


def test_wait_helper_detects_failed_status():
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    client = FakeCdwchClient(instances=[_serving(Status="failed")])
    with pytest.raises(AnsibleFailJson) as exc:
        cdwch._wait(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"}, lambda value: value is not None, "create")
    assert "asynchronous operation failed" in exc.value.args[0]["msg"]


def test_wait_helper_detects_failed_flow_message():
    module = FakeModule(instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    client = FakeCdwchClient(instances=[_serving(InstanceStateInfo={"FlowMsg": "ScaleUp failed: limit reached"})])
    with pytest.raises(AnsibleFailJson) as exc:
        cdwch._wait(module, client, FakeModels(), {"instance_id": "cdwch-8b0a1c2d"}, lambda value: value is not None, "scale specification")
    assert "asynchronous operation failed" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_module_requires_instance_id_or_name(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "instance_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_absent_missing_instance_is_unchanged(client):
    module_args(state="absent", name="nope")
    result = run(cdwch.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_destroys_serving_instance(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(state="absent", instance_id="cdwch-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert any(name == "DestroyInstance" for name, request in client.calls)
    assert client.describe_count >= 2
    assert client.instances == []


def test_absent_destroy_stalls_times_out(client):
    client.instances = [_serving()]
    module_args(state="absent", instance_id="cdwch-8b0a1c2d", waiter_timeout=3, waiter_delay=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    assert "Timed out" in exc.value.args[0]["msg"]


def test_check_mode_absent_makes_no_writes(client):
    client.instances = [_serving()]
    module_args(state="absent", instance_id="cdwch-8b0a1c2d", _ansible_check_mode=True)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_create_requires_creation_parameters(client):
    module_args(state="present", name="new-clickhouse")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "required" in payload["msg"]
    assert "zone" in payload["missing"]
    assert "password" in payload["missing"]
    assert "data_spec_name" in payload["missing"]


def test_create_reports_changed(client):
    client.auto_advance = True
    module_args(
        state="present", name="new-clickhouse", zone="ap-beijing-2", vpc_id="vpc-x",
        subnet_id="subnet-y", product_version="23.8.9.1", data_spec_name="S_16_64_H",
        data_node_count=2, data_disk_size=200, password="secret-pass",
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(cdwch.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "cdwch-new1000"
    assert result["instance"]["Status"] == "Serving"
    assert any(name == "CreateInstanceNew" for name, request in client.calls)
    assert len(client.instances) == 1
    assert client.instances[0]["MasterSummary"]["NodeSize"] == 2


def test_check_mode_create_makes_no_writes(client):
    module_args(
        state="present", name="new-clickhouse", zone="ap-beijing-2", vpc_id="vpc-x",
        subnet_id="subnet-y", product_version="23.8.9.1", data_spec_name="S_16_64_H",
        data_node_count=2, data_disk_size=200, password="secret-pass",
        _ansible_check_mode=True,
    )
    result = run(cdwch.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "new-clickhouse"
    assert result["instance"]["MasterSummary"]["Spec"] == "S_16_64_H"
    assert result["diff"]["after"]["InstanceName"] == "new-clickhouse"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_idempotent_is_unchanged(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d")
    result = run(cdwch.run_module)
    assert result["changed"] is False
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_immutable_zone_drift_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", zone="ap-guangzhou-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


def test_immutable_name_drift_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "InstanceName" in payload["immutable_drift"]


def test_immutable_tags_drift_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", tags={"env": "staging"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "Tags" in payload["immutable_drift"]


def test_immutable_paymode_drift_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", charge_type="PREPAID")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "PayMode" in payload["immutable_drift"]


def test_immutable_ha_drift_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", high_availability=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "HA" in payload["immutable_drift"]


def test_disk_shrink_fails(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_disk_size=100)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert "cannot be reduced" in payload["msg"]
    assert payload["field"] == "DataDisk"


def test_scale_in_requires_allow_scale_in(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_node_count=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    assert "allow_scale_in=true" in exc.value.args[0]["msg"]


def test_scale_in_requires_reduce_shard_info(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_node_count=1, allow_scale_in=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    assert "reduce_shard_info is required" in exc.value.args[0]["msg"]


def test_scale_out_requires_ip_parameters(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_node_count=4)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    assert "user_subnet_ip_count and scale_out_node_ip" in exc.value.args[0]["msg"]


def test_update_changes_data_spec(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_spec_name="S_32_128_H", waiter_timeout=30, waiter_delay=0)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    scale_up = [(name, request) for name, request in client.calls if name == "ScaleUpInstance"]
    assert len(scale_up) == 1
    assert scale_up[0][1].Type == "DATA"
    assert scale_up[0][1].SpecName == "S_32_128_H"
    assert scale_up[0][1].ScaleUpEnableRolling is True
    assert client.instances[0]["MasterSummary"]["Spec"] == "S_32_128_H"


def test_update_resizes_data_disk(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_disk_size=400, waiter_timeout=30, waiter_delay=0)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    resize = [(name, request) for name, request in client.calls if name == "ResizeDisk"]
    assert len(resize) == 1
    assert resize[0][1].Type == "DATA"
    assert resize[0][1].DiskSize == 400
    assert client.instances[0]["MasterSummary"]["Disk"] == 400


def test_update_changes_common_spec(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(state="present", instance_id="cdwch-8b0a1c2d", common_spec_name="S_8_32_H", waiter_timeout=30, waiter_delay=0)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    scale_up = [(name, request) for name, request in client.calls if name == "ScaleUpInstance"]
    assert scale_up[0][1].Type == "COMMON"
    assert scale_up[0][1].SpecName == "S_8_32_H"
    assert client.instances[0]["CommonSummary"]["Spec"] == "S_8_32_H"


def test_update_scale_out_nodes(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(
        state="present", instance_id="cdwch-8b0a1c2d", data_node_count=4,
        user_subnet_ip_count=10, scale_out_node_ip="10.0.0.5",
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(cdwch.run_module)
    assert result["changed"] is True
    scale_out = [(name, request) for name, request in client.calls if name == "ScaleOutInstance"]
    assert len(scale_out) == 1
    assert scale_out[0][1].Type == "DATA"
    assert scale_out[0][1].NodeCount == 4
    assert client.instances[0]["MasterSummary"]["NodeSize"] == 4


def test_update_scale_in_nodes(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(
        state="present", instance_id="cdwch-8b0a1c2d", data_node_count=1,
        allow_scale_in=True, reduce_shard_info=["10.0.0.1"],
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(cdwch.run_module)
    assert result["changed"] is True
    scale_out = [(name, request) for name, request in client.calls if name == "ScaleOutInstance"]
    assert len(scale_out) == 1
    assert scale_out[0][1].NodeCount == 1
    assert client.instances[0]["MasterSummary"]["NodeSize"] == 1


def test_update_reconciles_spec_disk_and_nodes_in_order(client):
    client.instances = [_serving()]
    client.auto_advance = True
    module_args(
        state="present", instance_id="cdwch-8b0a1c2d", data_spec_name="S_32_128_H",
        data_disk_size=400, data_node_count=4, user_subnet_ip_count=10,
        scale_out_node_ip="10.0.0.5", waiter_timeout=30, waiter_delay=0,
    )
    result = run(cdwch.run_module)
    assert result["changed"] is True
    writes = [name for name, request in client.calls if name in WRITE_OPS]
    assert writes == ["ScaleUpInstance", "ResizeDisk", "ScaleOutInstance"]
    summary = client.instances[0]["MasterSummary"]
    assert summary == {"Spec": "S_32_128_H", "NodeSize": 4, "Disk": 400}


def test_check_mode_update_makes_no_writes(client):
    client.instances = [_serving()]
    module_args(state="present", instance_id="cdwch-8b0a1c2d", data_spec_name="S_32_128_H", _ansible_check_mode=True)
    result = run(cdwch.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["DataSpec"] == "S_16_64_H"
    assert result["diff"]["after"]["DataSpec"] == "S_32_128_H"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_is_reported(client):
    def boom(request):
        raise RuntimeError("cdwch api exploded")

    client.DescribeInstancesNew = boom
    module_args(state="present", name="new-clickhouse")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cdwch.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "cdwch api exploded" in payload["error"]
