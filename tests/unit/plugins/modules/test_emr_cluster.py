"""Unit tests for the emr_cluster write module (helpers + run_module).

Creates EMR clusters through the current CreateCluster API (complex scene
and node-topology payloads pass through with their SDK field names),
renames an existing cluster via ModifyInstanceBasic, and terminates via
TerminateInstance (optionally retaining the associated TKE cluster).
Creation convergence polls the cluster Status until 2 (running) with the
desired name; 301/302 fail the wait. Lookup pages DescribeInstances and
matches by cluster_id or client-side by ClusterName (multiple name
matches are refused).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import emr_cluster as mod
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
        return FakeModels(), SimpleNamespace(EmrClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _cluster(instance_id="emr-1", name="analytics-emr", status=2, **overrides):
    """A serialized EMR cluster record (Status 2 = running)."""
    record = {
        "ClusterId": instance_id,
        "ClusterName": name,
        "Status": status,
        "ProductVersion": "EMR-V3.5.0",
        "ChargeType": "POSTPAID_BY_HOUR",
    }
    record.update(overrides)
    return record


class FakeEmrClient(object):
    """In-memory EmrClient stand-in storing EMR cluster records.

    DescribeInstances returns every record (or a page slice when
    ``page_size`` is set, honouring the request Offset). CreateCluster
    assigns a fresh id with Status 2 (or ``create_status``); with
    ``slow_start`` the created record first reports Status 3 (pending) and
    flips to 2 after one more describe, so the waiter observes a RUNNING
    poll before succeeding. TerminateInstance removes the record, so an
    absent wait converges on its first poll.
    """

    def __init__(self, instances=None, page_size=None, create_status=2, slow_start=False):
        self.instances = [dict(x) for x in (instances or [])]
        self.calls = []
        self._next_id = 1
        self._page_size = page_size
        self._create_status = create_status
        self._slow_start = slow_start
        self._promote_id = None

    def _record(self, name, request):
        self.calls.append((name, request))

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        page = self.instances
        if self._page_size is not None:
            page = self.instances[request.Offset : request.Offset + self._page_size]
        # Snapshot before promoting so the poll observing Status 3 sees it.
        page = [FakeResource(dict(x)) for x in page]
        if self._promote_id is not None:
            for record in self.instances:
                if record["ClusterId"] == self._promote_id:
                    record["Status"] = 2
                    break
            self._promote_id = None
        return SimpleNamespace(ClusterList=page, TotalCnt=len(self.instances))

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        instance_id = "emr-%d" % self._next_id
        self._next_id += 1
        record = {
            "ClusterId": instance_id,
            "ClusterName": request.InstanceName,
            "Status": 3 if self._slow_start else self._create_status,
        }
        if self._create_status in (301, 302):
            record["AlarmInfo"] = "cluster launch failed"
        self.instances.append(record)
        if self._slow_start:
            self._promote_id = instance_id
        return SimpleNamespace(InstanceId=instance_id)

    def ModifyInstanceBasic(self, request):
        self._record("ModifyInstanceBasic", request)
        for record in self.instances:
            if record["ClusterId"] == request.InstanceId:
                record["ClusterName"] = request.ClusterName
        return SimpleNamespace()

    def TerminateInstance(self, request):
        self._record("TerminateInstance", request)
        self.instances = [x for x in self.instances if x["ClusterId"] != request.InstanceId]
        return SimpleNamespace()


# Creation parameters covering every required field for a new cluster.
_CREATE_ARGS = {
    "name": "analytics-emr",
    "product_version": "EMR-V3.5.0",
    "enable_ha": True,
    "charge_type": "POSTPAID_BY_HOUR",
    "login_settings": {"Password": "vault-secret", "UserName": "root"},
    "scene_software_config": {"SceneName": "Hadoop", "Software": ["HDFS", "YARN"]},
    "prepaid": {"Period": 1, "RenewFlag": 0},
    "security_group_ids": ["sg-1", "sg-2"],
    "bootstrap_actions": [{"ScriptPath": "cos://bucket/init.sh", "Args": ["--fast"]}],
    "client_token": "token-1",
    "need_master_wan": "NEED_MASTER_WAN",
    "enable_remote_login": True,
    "enable_kerberos": False,
    "custom_conf": '{"yarn.scheduler.maximum-allocation-mb": 8192}',
    "tags": {"team": "pay", "env": "prod"},
    "disaster_recover_group_ids": ["pg-1"],
    "enable_cbs_encrypt": True,
    "enable_cbs_system_encrypt": False,
    "meta_db_info": {"MetaType": "EMBEDDED"},
    "depend_services": [{"ServiceName": "cos", "ServiceRole": "emr"}],
    "zone_resource_configurations": [
        {
            "VirtualPrivateCloud": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
            "Placement": {"Zone": "ap-guangzhou-3"},
            "AllNodeResourceSpec": {},
        }
    ],
    "cos_bucket": "cos://bucket",
    "node_marks": [{"NodeMark": "master", "NodeType": "master"}],
    "load_balancer_id": "lb-1",
    "default_meta_version": "default",
    "need_cdb_audit": 1,
    "source_ip": "10.0.0.0/8",
    "partition_number": 1,
    "web_ui_version": 1,
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
# model-building and request-builder helper tests
# ---------------------------------------------------------------------------


def test_model_none_returns_none():
    assert mod._model(FakeModels().LoginSettings, None) is None


def test_model_populates_from_json_string():
    item = mod._model(FakeModels().LoginSettings, {"Password": "x", "UserName": "root"})
    assert item.Password == "x"
    assert item.UserName == "root"
    nested = mod._model(FakeModels().ZoneResourceConfiguration, {"VirtualPrivateCloud": {"VpcId": "vpc-1"}})
    assert nested.VirtualPrivateCloud == {"VpcId": "vpc-1"}  # raw SDK payload kept


def test_models_none_returns_none():
    assert mod._models(FakeModels(), "DependService", None) is None


def test_models_builds_one_model_per_value():
    items = mod._models(FakeModels(), "DependService", [{"ServiceName": "cos"}, {"ServiceName": "hdfs"}])
    assert len(items) == 2
    assert [i.ServiceName for i in items] == ["cos", "hdfs"]


def test_tags_sorted_and_stringified():
    items = mod._tags(FakeModels(), {"b": 2, "a": "x"})
    assert [i.TagKey for i in items] == ["a", "b"]
    assert [i.TagValue for i in items] == ["x", "2"]  # str() applied to values


def test_tags_empty_and_none_return_empty_list():
    assert mod._tags(FakeModels(), {}) == []
    assert mod._tags(FakeModels(), None) == []


def test_describe_request_with_cluster_id_and_offset():
    request = mod.describe_request(FakeModels(), "emr-1", offset=40)
    assert type(request).__name__ == "DescribeInstancesRequest"
    assert request.DisplayStrategy == "clusterList"
    assert request.InstanceIds == ["emr-1"]
    assert request.Offset == 40
    assert request.Limit == 100
    assert request.ProjectId == -1


def test_describe_request_without_cluster_id_leaves_ids_none():
    request = mod.describe_request(FakeModels())
    assert request.InstanceIds is None
    assert request.Offset == 0


def test_create_request_full_payload():
    request = mod.create_request(FakeModels(), dict(_CREATE_ARGS))
    assert type(request).__name__ == "CreateClusterRequest"
    assert request.ProductVersion == "EMR-V3.5.0"
    assert request.EnableSupportHAFlag is True
    assert request.InstanceName == "analytics-emr"
    assert request.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert request.LoginSettings.Password == "vault-secret"
    assert request.SceneSoftwareConfig.SceneName == "Hadoop"
    assert request.SceneSoftwareConfig.Software == ["HDFS", "YARN"]
    assert request.InstanceChargePrepaid.Period == 1
    assert request.SecurityGroupIds == ["sg-1", "sg-2"]
    assert request.ScriptBootstrapActionConfig[0].ScriptPath == "cos://bucket/init.sh"
    assert request.ClientToken == "token-1"
    assert request.NeedMasterWan == "NEED_MASTER_WAN"
    assert request.EnableRemoteLoginFlag is True
    assert request.EnableKerberosFlag is False
    assert request.CustomConf == '{"yarn.scheduler.maximum-allocation-mb": 8192}'
    assert [t.TagKey for t in request.Tags] == ["env", "team"]  # sorted by key
    assert [t.TagValue for t in request.Tags] == ["prod", "pay"]
    assert request.DisasterRecoverGroupIds == ["pg-1"]
    assert request.EnableCbsEncryptFlag is True
    assert request.EnableCbsSysEncryptFlag is False
    assert request.MetaDBInfo.MetaType == "EMBEDDED"
    assert request.DependService[0].ServiceName == "cos"
    zone = request.ZoneResourceConfiguration[0]
    assert zone.VirtualPrivateCloud["VpcId"] == "vpc-1"
    assert zone.Placement["Zone"] == "ap-guangzhou-3"
    assert request.CosBucket == "cos://bucket"
    assert request.NodeMarks[0].NodeMark == "master"
    assert request.LoadBalancerId == "lb-1"
    assert request.DefaultMetaVersion == "default"
    assert request.NeedCdbAudit == 1
    assert request.SgIP == "10.0.0.0/8"
    assert request.PartitionNumber == 1
    assert request.WebUiVersion == 1


def test_create_request_optional_fields_stay_unset():
    params = {"name": "minimal-emr", "product_version": "EMR-V3.5.0", "charge_type": "PREPAID"}
    request = mod.create_request(FakeModels(), params)
    assert request.InstanceName == "minimal-emr"
    assert request.EnableSupportHAFlag is None
    assert request.LoginSettings is None
    assert request.SceneSoftwareConfig is None
    assert request.InstanceChargePrepaid is None
    assert request.SecurityGroupIds is None
    assert request.ScriptBootstrapActionConfig is None
    assert request.ClientToken is None
    assert request.NeedMasterWan is None
    assert request.EnableRemoteLoginFlag is None
    assert request.EnableKerberosFlag is None
    assert request.CustomConf is None
    assert request.Tags == []
    assert request.DisasterRecoverGroupIds is None
    assert request.EnableCbsEncryptFlag is None
    assert request.EnableCbsSysEncryptFlag is None
    assert request.MetaDBInfo is None
    assert request.DependService is None
    assert request.ZoneResourceConfiguration is None
    assert request.CosBucket is None
    assert request.NodeMarks is None
    assert request.LoadBalancerId is None
    assert request.DefaultMetaVersion is None
    assert request.NeedCdbAudit is None
    assert request.SgIP is None
    assert request.PartitionNumber is None
    assert request.WebUiVersion is None


def test_update_request_fields():
    request = mod.update_request(FakeModels(), "emr-1", "renamed")
    assert type(request).__name__ == "ModifyInstanceBasicRequest"
    assert request.InstanceId == "emr-1"
    assert request.ClusterName == "renamed"


def test_delete_request_retain_flag_default_and_enabled():
    plain = mod.delete_request(FakeModels(), "emr-1")
    assert type(plain).__name__ == "TerminateInstanceRequest"
    assert plain.InstanceId == "emr-1"
    assert plain.RetainTkeCluster is False
    kept = mod.delete_request(FakeModels(), "emr-1", retain_tke_cluster=True)
    assert kept.RetainTkeCluster is True


# ---------------------------------------------------------------------------
# find helper tests (paged DescribeInstances)
# ---------------------------------------------------------------------------


def test_find_matches_by_cluster_id():
    fake = FakeEmrClient([_cluster(), _cluster("emr-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"cluster_id": "emr-2"})
    assert found["ClusterId"] == "emr-2"
    assert found["ClusterName"] == "other"
    assert _call_names(fake) == ["DescribeInstances"]


def test_find_matches_by_name():
    fake = FakeEmrClient([_cluster(), _cluster("emr-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"name": "other"})
    assert found["ClusterId"] == "emr-2"


def test_find_no_match_returns_none():
    fake = FakeEmrClient([_cluster()])
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "missing"}) is None
    assert _call_names(fake) == ["DescribeInstances"]


def test_find_empty_store_returns_none():
    fake = FakeEmrClient()
    assert mod.find(FakeModule(), fake, FakeModels(), {"cluster_id": "emr-1"}) is None


def test_find_multiple_name_matches_fail():
    fake = FakeEmrClient([_cluster("emr-1", "dup"), _cluster("emr-2", "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), {"name": "dup"})
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple EMR clusters matched; specify cluster_id"


def test_find_pages_by_offset_until_total():
    fake = FakeEmrClient([_cluster(), _cluster("emr-2", "other")], page_size=1)
    found = mod.find(FakeModule(), fake, FakeModels(), {"cluster_id": "emr-2"})
    assert found["ClusterId"] == "emr-2"
    offsets = [request.Offset for name, request in fake.calls if name == "DescribeInstances"]
    assert offsets == [0, 1]  # page 1 had no match, page 2 did


def test_find_name_paging_exhausts_all_pages():
    fake = FakeEmrClient([_cluster(), _cluster("emr-2", "other")], page_size=1)
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "missing"}) is None
    offsets = [request.Offset for name, request in fake.calls if name == "DescribeInstances"]
    assert offsets == [0, 1]
    assert fake._next_id == 1  # no writes happened


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_requires_cluster_id_or_name(monkeypatch):
    _make_module(monkeypatch, FakeEmrClient())
    module_args(product_version="EMR-V3.5.0")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "one of the following is required" in msg
    assert "cluster_id" in msg and "name" in msg


# ---------------------------------------------------------------------------
# absent main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeEmrClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="emr-9")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert not any(name.startswith("Terminate") for name, request in fake.calls)


def test_absent_terminates_and_waits_gone(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="emr-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert _call_names(fake) == ["DescribeInstances", "TerminateInstance", "DescribeInstances"]
    terminate = [req for name, req in fake.calls if name == "TerminateInstance"][0]
    assert terminate.InstanceId == "emr-1"
    assert terminate.RetainTkeCluster is False
    assert fake.instances == []


def test_absent_retains_tke_cluster_when_requested(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="emr-1", retain_tke_cluster=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    terminate = [req for name, req in fake.calls if name == "TerminateInstance"][0]
    assert terminate.RetainTkeCluster is True


def test_absent_without_wait_returns_immediately(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="emr-1", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert _call_names(fake) == ["DescribeInstances", "TerminateInstance"]  # no wait poll


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", cluster_id="emr-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "emr-1"  # pre-termination snapshot
    assert result["diff"]["before"]["ClusterId"] == "emr-1"
    assert result["diff"]["after"] is None
    assert not any(name.startswith("Terminate") for name, request in fake.calls)
    assert len(fake.instances) == 1  # remote untouched


# ---------------------------------------------------------------------------
# present main-path tests: creation
# ---------------------------------------------------------------------------


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeEmrClient()
    _make_module(monkeypatch, fake)
    module_args(name="analytics-emr")  # satisfies required_one_of but nothing else
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "creation parameters are required for an EMR cluster"
    assert payload["missing"] == ["product_version", "charge_type", "login_settings", "scene_software_config", "zone_resource_configurations"]
    assert not any(name.startswith("Create") for name, request in fake.calls)


def test_present_creates_cluster_and_waits(monkeypatch):
    fake = FakeEmrClient()
    _make_module(monkeypatch, fake)
    module_args(**_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "emr-1"
    assert result["cluster"]["ClusterName"] == "analytics-emr"
    assert result["cluster"]["Status"] == 2
    # find (no match), create, wait poll (running immediately)
    assert _call_names(fake) == ["DescribeInstances", "CreateCluster", "DescribeInstances"]
    create = [req for name, req in fake.calls if name == "CreateCluster"][0]
    assert create.InstanceName == "analytics-emr"
    assert create.ProductVersion == "EMR-V3.5.0"
    assert create.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert create.EnableSupportHAFlag is True
    assert create.LoginSettings.Password == "vault-secret"
    assert [t.TagKey for t in create.Tags] == ["env", "team"]


def test_present_waits_through_running_state(monkeypatch):
    fake = FakeEmrClient(slow_start=True)
    _make_module(monkeypatch, fake)
    module_args(waiter_delay=0, **_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["Status"] == 2  # converged on second wait poll
    # find, create, poll RUNNING (Status 3), poll SUCCESS (Status 2)
    assert _call_names(fake) == ["DescribeInstances", "CreateCluster", "DescribeInstances", "DescribeInstances"]


def test_present_create_failed_state_fails(monkeypatch):
    fake = FakeEmrClient(create_status=301)
    _make_module(monkeypatch, fake)
    module_args(**_CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Asynchronous task failed: cluster launch failed"


def test_present_create_without_wait_returns_found(monkeypatch):
    fake = FakeEmrClient()
    _make_module(monkeypatch, fake)
    module_args(wait=False, **_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "emr-1"
    assert _call_names(fake) == ["DescribeInstances", "CreateCluster", "DescribeInstances"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeEmrClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_CREATE_ARGS)
    result = run(mod.run_module)
    target = {"ClusterName": "analytics-emr", "ProductVersion": "EMR-V3.5.0", "ChargeType": "POSTPAID_BY_HOUR"}
    assert result["changed"] is True
    assert result["cluster"] == target
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == target
    assert _call_names(fake) == ["DescribeInstances"]  # no write
    assert fake.instances == []


# ---------------------------------------------------------------------------
# present main-path tests: rename reconciliation
# ---------------------------------------------------------------------------


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "emr-1"
    assert _call_names(fake) == ["DescribeInstances"]
    assert not any(name.startswith("Modify") for name, request in fake.calls)


def test_present_name_matching_current_is_noop(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-1", name="analytics-emr")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert _call_names(fake) == ["DescribeInstances"]


def test_present_rename_modifies_and_waits(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-1", name="renamed-emr")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "renamed-emr"  # re-found after modify
    assert _call_names(fake) == ["DescribeInstances", "ModifyInstanceBasic", "DescribeInstances"]
    modify = [req for name, req in fake.calls if name == "ModifyInstanceBasic"][0]
    assert modify.InstanceId == "emr-1"
    assert modify.ClusterName == "renamed-emr"


def test_present_rename_without_wait_returns_found(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-1", name="renamed-emr", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "renamed-emr"
    assert _call_names(fake) == ["DescribeInstances", "ModifyInstanceBasic", "DescribeInstances"]


def test_present_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, cluster_id="emr-1", name="renamed-emr")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] == {"ClusterName": "renamed-emr"}  # target snapshot
    assert result["diff"]["before"]["ClusterName"] == "analytics-emr"
    assert result["diff"]["after"] == {"ClusterName": "renamed-emr"}
    assert _call_names(fake) == ["DescribeInstances"]  # no write
    assert fake.instances[0]["ClusterName"] == "analytics-emr"  # remote untouched


# ---------------------------------------------------------------------------
# error path and entry point
# ---------------------------------------------------------------------------


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(EmrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    module_args(name="analytics-emr")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeEmrClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-1")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "emr-1"
