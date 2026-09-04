"""Unit tests for the ckafka_instance write module (helpers + run_module).

Creates prepaid or postpaid CKafka instances, reconciles runtime attributes
(name, retention, message size, unclean leader election, deletion
protection) and prepaid capacity (disk/bandwidth/partitions; postpaid
capacity changes are refused because the SDK only exposes the resize API
for prepaid), and deletes instances via the charge-type-specific API.
Placement (VPC/subnet/zones) and the Kafka version are immutable. Lookup
lists instances by id or name filter and then fetches full attributes for
the matched record.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(CkafkaClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _instance(instance_id="ckafka-1", name="prod-kafka", **overrides):
    """A serialized CKafka instance attributes record (Status 1 running)."""
    record = {
        "InstanceId": instance_id,
        "InstanceName": name,
        "Status": 1,
        "InstanceChargeType": "PREPAID",
        "VpcId": "vpc-1",
        "SubnetId": "subnet-1",
        "Version": "2.8.1",
        "ZoneIds": [100003],
        "ZoneId": 100003,
        "DiskSize": 500,
        "Bandwidth": 40,
        "PartitionNumber": 400,
        "MsgRetentionTime": 10080,
        "MaxMessageByte": 1048576,
        "RetentionBytes": -1,
        "UncleanLeaderElectionEnable": 0,
        "DeleteProtectionEnable": 0,
    }
    record.update(overrides)
    return record


class FakeCkafkaClient(object):
    """In-memory CkafkaClient stand-in storing CKafka instance records.

    DescribeInstancesDetail returns every record; DescribeInstanceAttributes
    returns the record addressed by InstanceId. Mutating operations apply
    only the non-None request fields (mirroring the real SDK, which omits
    unset fields), so a rename or resize leaves unrelated attributes intact.
    """

    def __init__(self, instances=None):
        self.instances = [dict(x) for x in (instances or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))

    def _by_id(self, instance_id):
        for record in self.instances:
            if record["InstanceId"] == instance_id:
                return record
        return None

    def DescribeInstancesDetail(self, request):
        self._record("DescribeInstancesDetail", request)
        return SimpleNamespace(Result=SimpleNamespace(InstanceList=[FakeResource(dict(x)) for x in self.instances]))

    def DescribeInstanceAttributes(self, request):
        self._record("DescribeInstanceAttributes", request)
        record = self._by_id(request.InstanceId)
        return SimpleNamespace(Result=FakeResource(dict(record)) if record else None)

    def _make(self, request, charge_type):
        instance_id = "ckafka-%d" % self._next_id
        self._next_id += 1
        self.instances.append(
            {
                "InstanceId": instance_id,
                "InstanceName": request.InstanceName,
                "Status": 1,
                "InstanceChargeType": charge_type,
                "VpcId": request.VpcId,
                "SubnetId": request.SubnetId,
                "Version": request.KafkaVersion,
                "ZoneIds": list(request.ZoneIds),
                "ZoneId": request.ZoneId,
                "DiskSize": request.DiskSize,
                "Bandwidth": request.BandWidth,
                "PartitionNumber": request.Partition,
                "MsgRetentionTime": request.MsgRetentionTime,
                "MaxMessageByte": 1048576,
                "RetentionBytes": -1,
                "UncleanLeaderElectionEnable": 0,
                "DeleteProtectionEnable": 0,
            }
        )
        return SimpleNamespace(Result=SimpleNamespace(Data=SimpleNamespace(InstanceId=instance_id)))

    def CreateInstancePre(self, request):
        self._record("CreateInstancePre", request)
        return self._make(request, "PREPAID")

    def CreatePostPaidInstance(self, request):
        self._record("CreatePostPaidInstance", request)
        return self._make(request, "POSTPAID_BY_HOUR")

    def ModifyInstanceAttributes(self, request):
        self._record("ModifyInstanceAttributes", request)
        record = self._by_id(request.InstanceId)
        for field in ("InstanceName", "MsgRetentionTime", "MaxMessageByte", "RetentionBytes", "UncleanLeaderElectionEnable", "DeleteProtectionEnable"):
            value = getattr(request, field)
            if value is not None:
                record[field] = value
        return SimpleNamespace()

    def ModifyInstancePre(self, request):
        self._record("ModifyInstancePre", request)
        record = self._by_id(request.InstanceId)
        if request.DiskSize is not None:
            record["DiskSize"] = request.DiskSize
        if request.BandWidth is not None:
            record["Bandwidth"] = request.BandWidth
        if request.Partition is not None:
            record["PartitionNumber"] = request.Partition
        return SimpleNamespace()

    def DeleteInstancePre(self, request):
        self._record("DeleteInstancePre", request)
        self.instances = [x for x in self.instances if x["InstanceId"] != request.InstanceId]
        return SimpleNamespace()

    def DeleteInstancePost(self, request):
        self._record("DeleteInstancePost", request)
        self.instances = [x for x in self.instances if x["InstanceId"] != request.InstanceId]
        return SimpleNamespace()


# Creation parameters covering every required field for a new instance.
_CREATE_ARGS = {
    "name": "prod-kafka",
    "zones": [100003],
    "vpc_id": "vpc-1",
    "subnet_id": "subnet-1",
    "charge_type": "PREPAID",
    "period_months": 12,
    "auto_renew": True,
    "instance_type": 1,
    "specification": "profession",
    "kafka_version": "2.8.1",
    "disk_type": "CLOUD_BASIC",
    "disk_size": 500,
    "bandwidth": 40,
    "partitions": 400,
    "topic_count": 100,
    "retention_minutes": 10080,
    "tags": {"team": "pay", "env": "prod"},
}


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _call_names(fake):
    return [name for name, request in fake.calls]


# ---------------------------------------------------------------------------
# request-builder and mapping helper tests
# ---------------------------------------------------------------------------


def test_list_request_by_instance_id():
    request = mod.list_request(FakeModels(), {"instance_id": "ckafka-1"})
    assert type(request).__name__ == "DescribeInstancesDetailRequest"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.InstanceIdList == ["ckafka-1"]


def test_list_request_by_name_builds_filter():
    request = mod.list_request(FakeModels(), {"name": "prod-kafka"}, offset=42)
    assert request.InstanceIdList is None
    assert request.Offset == 42
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["prod-kafka"]


def test_attributes_request_fields():
    request = mod.attributes_request(FakeModels(), "ckafka-1")
    assert type(request).__name__ == "DescribeInstanceAttributesRequest"
    assert request.InstanceId == "ckafka-1"


def test_tags_sorted_and_stringified():
    items = mod._tags(FakeModels(), {"b": 2, "a": "x"})
    assert [i.TagKey for i in items] == ["a", "b"]
    assert [i.TagValue for i in items] == ["x", 2]


def test_tags_empty_returns_empty_list():
    assert mod._tags(FakeModels(), {}) == []


def test_create_prepaid_request_full_payload():
    params = dict(_CREATE_ARGS)
    request = mod.create_prepaid_request(FakeModels(), params)
    assert type(request).__name__ == "CreateInstancePreRequest"
    assert request.InstanceName == "prod-kafka"
    assert request.ZoneId == 100003
    assert request.ZoneIds == [100003]
    assert request.MultiZoneFlag is False  # single zone
    assert request.Period == "12"  # stringified
    assert request.RenewFlag == 1  # auto_renew
    assert request.InstanceType == 1
    assert request.SpecificationsType == "profession"
    assert request.KafkaVersion == "2.8.1"
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.MsgRetentionTime == 10080
    assert request.DiskType == "CLOUD_BASIC"
    assert request.DiskSize == 500
    assert request.BandWidth == 40
    assert request.Partition == 400
    assert request.InstanceNum == 1
    assert [t.TagKey for t in request.Tags] == ["env", "team"]  # sorted by key
    assert [t.TagValue for t in request.Tags] == ["prod", "pay"]


def test_create_prepaid_multi_zone_sets_flag():
    params = dict(_CREATE_ARGS)
    params["zones"] = [100003, 100004]
    request = mod.create_prepaid_request(FakeModels(), params)
    assert request.ZoneIds == [100003, 100004]
    assert request.MultiZoneFlag is True


def test_create_postpaid_request_fields():
    params = dict(_CREATE_ARGS)
    request = mod.create_postpaid_request(FakeModels(), params)
    assert type(request).__name__ == "CreatePostPaidInstanceRequest"
    assert request.TopicNum == 100
    assert request.InstanceNum == 1
    assert request.MultiZoneFlag is False
    no_topic = mod.create_postpaid_request(FakeModels(), dict(params, topic_count=None))
    assert no_topic.TopicNum is None


def test_modify_request_maps_optional_fields():
    params = {
        "name": "renamed",
        "retention_minutes": 2880,
        "max_message_bytes": 2097152,
        "retention_bytes": -1,
        "unclean_leader_election": True,
        "deletion_protection": True,
    }
    request = mod.modify_request(FakeModels(), params, "ckafka-1")
    assert type(request).__name__ == "ModifyInstanceAttributesRequest"
    assert request.InstanceId == "ckafka-1"
    assert request.InstanceName == "renamed"
    assert request.MsgRetentionTime == 2880
    assert request.MaxMessageByte == 2097152
    assert request.RetentionBytes == -1
    assert request.UncleanLeaderElectionEnable == 1  # bool coerced to int
    assert request.DeleteProtectionEnable == 1


def test_modify_request_leaves_unset_fields_none():
    request = mod.modify_request(FakeModels(), {}, "ckafka-1")
    assert request.InstanceName is None
    assert request.MsgRetentionTime is None
    assert request.MaxMessageByte is None
    assert request.RetentionBytes is None
    assert request.UncleanLeaderElectionEnable is None
    assert request.DeleteProtectionEnable is None


def test_resize_request_fields():
    params = {"disk_size": 600, "bandwidth": 60, "partitions": 500}
    request = mod.resize_request(FakeModels(), params, "ckafka-1")
    assert type(request).__name__ == "ModifyInstancePreRequest"
    assert request.InstanceId == "ckafka-1"
    assert request.DiskSize == 600
    assert request.BandWidth == 60
    assert request.Partition == 500
    sparse = mod.resize_request(FakeModels(), {}, "ckafka-1")
    assert sparse.DiskSize is None and sparse.BandWidth is None and sparse.Partition is None


def test_delete_request_builders():
    prepaid = mod.delete_prepaid_request(FakeModels(), "ckafka-1")
    assert type(prepaid).__name__ == "DeleteInstancePreRequest"
    assert prepaid.InstanceId == "ckafka-1"
    postpaid = mod.delete_postpaid_request(FakeModels(), "ckafka-1")
    assert type(postpaid).__name__ == "DeleteInstancePostRequest"
    assert postpaid.InstanceId == "ckafka-1"


# ---------------------------------------------------------------------------
# find helper tests (list + attributes)
# ---------------------------------------------------------------------------


def test_find_matches_by_name_then_fetches_attributes():
    fake = FakeCkafkaClient([_instance(), _instance("ckafka-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"name": "other"})
    assert found["InstanceId"] == "ckafka-2"
    assert [name for name, request in fake.calls] == ["DescribeInstancesDetail", "DescribeInstanceAttributes"]
    attributes = [req for name, req in fake.calls if name == "DescribeInstanceAttributes"][0]
    assert attributes.InstanceId == "ckafka-2"


def test_find_matches_by_instance_id():
    fake = FakeCkafkaClient([_instance()])
    found = mod.find(FakeModule(), fake, FakeModels(), {"instance_id": "ckafka-1"})
    assert found["InstanceName"] == "prod-kafka"
    assert found["DiskSize"] == 500  # full attributes record


def test_find_no_match_returns_none_with_single_call():
    fake = FakeCkafkaClient([_instance()])
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "missing"}) is None
    assert [name for name, request in fake.calls] == ["DescribeInstancesDetail"]


def test_find_multiple_name_matches_fail():
    fake = FakeCkafkaClient([_instance("ckafka-1", "dup"), _instance("ckafka-2", "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), {"name": "dup"})
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple CKafka instances matched; specify instance_id"


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_requires_instance_id_or_name(monkeypatch):
    _make_module(monkeypatch, FakeCkafkaClient())
    module_args(vpc_id="vpc-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "one of the following is required" in msg
    assert "instance_id" in msg and "name" in msg


# ---------------------------------------------------------------------------
# absent main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ckafka-9")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert not any(name.startswith("Delete") for name, request in fake.calls)


def test_absent_prepaid_uses_delete_pre(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ckafka-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert _call_names(fake) == ["DescribeInstancesDetail", "DescribeInstanceAttributes", "DeleteInstancePre"]
    delete = [req for name, req in fake.calls if name == "DeleteInstancePre"][0]
    assert delete.InstanceId == "ckafka-1"
    assert fake.instances == []


def test_absent_postpaid_uses_delete_post(monkeypatch):
    fake = FakeCkafkaClient([_instance(InstanceChargeType="POSTPAID_BY_HOUR")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ckafka-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert "DeleteInstancePost" in _call_names(fake)
    assert "DeleteInstancePre" not in _call_names(fake)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", instance_id="ckafka-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert result["diff"]["before"]["InstanceId"] == "ckafka-1"
    assert result["diff"]["after"] is None
    assert not any(name.startswith("Delete") for name, request in fake.calls)
    assert len(fake.instances) == 1  # remote untouched


# ---------------------------------------------------------------------------
# present main-path tests: creation
# ---------------------------------------------------------------------------


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(name="prod-kafka")  # satisfies required_one_of but nothing else
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "creation parameters are required for a new CKafka instance"
    assert payload["missing"] == [
        "zones", "vpc_id", "subnet_id", "instance_type", "specification", "kafka_version",
        "disk_type", "disk_size", "bandwidth", "partitions", "retention_minutes",
    ]
    assert not any(name.startswith("Create") for name, request in fake.calls)


def test_present_creates_prepaid_instance_and_refinds(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(**_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "ckafka-1"
    assert result["instance"]["InstanceName"] == "prod-kafka"
    assert result["instance"]["Status"] == 1
    # find, create, wait poll (list+attributes), re-find (list+attributes)
    assert _call_names(fake) == [
        "DescribeInstancesDetail",
        "CreateInstancePre",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
    ]
    create = [req for name, req in fake.calls if name == "CreateInstancePre"][0]
    assert create.InstanceName == "prod-kafka"
    assert create.ZoneId == 100003
    assert create.ZoneIds == [100003]
    assert create.MultiZoneFlag is False
    assert create.Period == "12"
    assert create.RenewFlag == 1
    assert create.InstanceType == 1
    assert create.SpecificationsType == "profession"
    assert create.KafkaVersion == "2.8.1"
    assert create.VpcId == "vpc-1"
    assert create.SubnetId == "subnet-1"
    assert create.DiskType == "CLOUD_BASIC"
    assert create.DiskSize == 500
    assert create.BandWidth == 40
    assert create.Partition == 400
    assert create.InstanceNum == 1
    assert [t.TagKey for t in create.Tags] == ["env", "team"]


def test_present_creates_postpaid_instance(monkeypatch):
    args = {**_CREATE_ARGS, "charge_type": "POSTPAID_BY_HOUR"}
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(**args)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceChargeType"] == "POSTPAID_BY_HOUR"
    create = [req for name, req in fake.calls if name == "CreatePostPaidInstance"][0]
    assert create.TopicNum == 100
    assert create.InstanceNum == 1
    assert "CreateInstancePre" not in _call_names(fake)


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_CREATE_ARGS)
    result = run(mod.run_module)
    target = {
        "InstanceName": "prod-kafka",
        "ZoneIds": [100003],
        "VpcId": "vpc-1",
        "SubnetId": "subnet-1",
        "DiskSize": 500,
        "Bandwidth": 40,
        "PartitionNumber": 400,
    }
    assert result["changed"] is True
    assert result["instance"] == target
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == target
    assert _call_names(fake) == ["DescribeInstancesDetail"]  # no write
    assert fake.instances == []


# ---------------------------------------------------------------------------
# present main-path tests: immutability drift
# ---------------------------------------------------------------------------


def test_present_zone_drift_fails_immutable(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", zones=[100002])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CKafka placement and Kafka version are immutable"
    assert payload["immutable_drift"] == {"ZoneIds": ([100003], [100002])}


def test_present_vpc_and_version_drift_fails_immutable(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", vpc_id="vpc-9", kafka_version="3.2.0")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CKafka placement and Kafka version are immutable"
    assert payload["immutable_drift"] == {"VpcId": ("vpc-1", "vpc-9"), "Version": ("2.8.1", "3.2.0")}
    assert not any(name.startswith("Modify") for name, request in fake.calls)


def test_present_immutable_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id="ckafka-1", subnet_id="subnet-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "CKafka placement and Kafka version are immutable"


# ---------------------------------------------------------------------------
# present main-path tests: attribute and capacity reconciliation
# ---------------------------------------------------------------------------


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "ckafka-1"
    assert _call_names(fake) == ["DescribeInstancesDetail", "DescribeInstanceAttributes"]
    assert not any(name.startswith("Modify") for name, request in fake.calls)


def test_present_rename_modifies_attributes(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", name="renamed-kafka")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "renamed-kafka"  # re-found after modify
    assert _call_names(fake) == [
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
        "ModifyInstanceAttributes",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
    ]
    modify = [req for name, req in fake.calls if name == "ModifyInstanceAttributes"][0]
    assert modify.InstanceId == "ckafka-1"
    assert modify.InstanceName == "renamed-kafka"
    assert not any(name == "ModifyInstancePre" for name, request in fake.calls)


def test_present_retention_drift_modifies_attributes(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", retention_minutes=2880)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["MsgRetentionTime"] == 2880
    modify = [req for name, req in fake.calls if name == "ModifyInstanceAttributes"][0]
    assert modify.MsgRetentionTime == 2880
    assert modify.InstanceName is None  # untouched fields stay None


def test_present_protection_flags_drift_modifies_attributes(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", unclean_leader_election=True, deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["UncleanLeaderElectionEnable"] == 1
    assert result["instance"]["DeleteProtectionEnable"] == 1
    modify = [req for name, req in fake.calls if name == "ModifyInstanceAttributes"][0]
    assert modify.UncleanLeaderElectionEnable == 1  # bool coerced to int
    assert modify.DeleteProtectionEnable == 1


def test_present_capacity_drift_resizes_prepaid(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", disk_size=600, bandwidth=60)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DiskSize"] == 600
    assert result["instance"]["Bandwidth"] == 60
    resize = [req for name, req in fake.calls if name == "ModifyInstancePre"][0]
    assert resize.InstanceId == "ckafka-1"
    assert resize.DiskSize == 600
    assert resize.BandWidth == 60
    assert not any(name == "ModifyInstanceAttributes" for name, request in fake.calls)


def test_present_postpaid_capacity_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_instance(InstanceChargeType="POSTPAID_BY_HOUR")])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", partitions=800)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CKafka capacity modification is only exposed by the SDK for prepaid instances"
    assert not any(name == "ModifyInstancePre" for name, request in fake.calls)


def test_present_combined_attribute_and_capacity_drift(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1", disk_size=600, max_message_bytes=2097152)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DiskSize"] == 600
    assert result["instance"]["MaxMessageByte"] == 2097152
    assert _call_names(fake) == [
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
        "ModifyInstanceAttributes",
        "ModifyInstancePre",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
        "DescribeInstancesDetail",
        "DescribeInstanceAttributes",
    ]
    modify = [req for name, req in fake.calls if name == "ModifyInstanceAttributes"][0]
    assert modify.MaxMessageByte == 2097152
    resize = [req for name, req in fake.calls if name == "ModifyInstancePre"][0]
    assert resize.DiskSize == 600


def test_present_check_mode_drift_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id="ckafka-1", disk_size=600)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DiskSize"] == 500  # pre-change snapshot
    assert result["diff"]["before"]["DiskSize"] == 500
    assert result["diff"]["after"]["DiskSize"] == 600
    assert not any(name.startswith("Modify") for name, request in fake.calls)
    assert fake.instances[0]["DiskSize"] == 500  # remote untouched


# ---------------------------------------------------------------------------
# error path and entry point
# ---------------------------------------------------------------------------


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    module_args(name="prod-kafka")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCkafkaClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="ckafka-1")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "ckafka-1"
