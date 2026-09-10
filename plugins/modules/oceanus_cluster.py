#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_cluster
short_description: Manage Tencent Cloud Oceanus dedicated clusters
version_added: "0.14.0"
description: Creates, scales, waits for and deletes dedicated Oceanus compute clusters.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID.}
  name: {type: str, description: Cluster name; immutable after creation.}
  region_id: {type: int, description: Numeric region ID; required for creation.}
  zone_id: {type: int, description: Numeric availability-zone ID; required for creation.}
  login_password: {type: str, description: Initial Flink UI administrator password.}
  vpc_descriptions: {type: list, elements: dict, description: SDK VPCDescription list; immutable after creation.}
  default_cos_bucket: {type: str, description: Default checkpoint and artifact COS bucket; immutable after creation.}
  cu: {type: int, description: Desired CU count following 12 + 7n.}
  cu_memory: {type: int, choices: [0, 2, 4, 8], description: CU memory ratio; immutable after creation.}
  remark: {type: str, description: Creation-time cluster description.}
  period: {type: int, default: 1, description: Prepaid purchase period in months.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_SECOND], default: POSTPAID_BY_SECOND, description: Billing mode; immutable after creation.}
  cluster_type: {type: str, choices: [MULTI_AZ_CLUSTER], description: Multi-zone cluster marker.}
  renew_flag: {type: str, choices: [NOTIFY_AND_MANUAL_RENEW, NOTIFY_AND_AUTO_RENEW, DISABLE_NOTIFY_AND_MANUAL_RENEW], description: Prepaid renewal behavior.}
  flink_ui_access_type: {type: str, choices: [NetworkAccess_INTERNAL, NetworkAccess_EXTERNAL], description: Flink UI network access; immutable after creation.}
  slave_vpc_descriptions: {type: list, elements: dict, description: SDK SlaveVpcDescriptions list for multi-zone creation.}
  allow_scale_down: {type: bool, default: false, description: Explicitly authorize reducing cluster CU.}
  wait: {type: bool, default: true, description: Wait for running or absent convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_cluster:
    name: production-flink
    region_id: 1
    zone_id: 100001
    login_password: "{{ vault_flink_ui_password }}"
    vpc_descriptions: [{VpcId: vpc-xxxxxxxx, SubnetId: subnet-xxxxxxxx}]
    default_cos_bucket: flink-artifacts-1250000000
    cu: 19
    charge_type: POSTPAID_BY_SECOND
"""
RETURN = r"""cluster: {description: Effective Oceanus cluster metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def valid_cu(value):
    return value is not None and value >= 12 and (value - 12) % 7 == 0


def _model(cls, value):
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, p, offset=0):
    r = models.DescribeClustersRequest()
    r.Offset, r.Limit = offset, 100
    if p.get("cluster_id"):
        r.ClusterIds = [p["cluster_id"]]
    elif p.get("name"):
        f = models.Filter()
        f.Name, f.Values = "Name", [p["name"]]
        r.Filters = [f]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeClusters, describe_request(models, p, offset))
        page = response.ClusterSet or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("Name") == p.get("name")):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Oceanus clusters matched; specify cluster_id")
    return matches[0] if matches else None


def create_request(models, p):
    r = models.CreateOceanusClusterRequest()
    r.ClusterName, r.RegionId, r.ZoneId = p["name"], p["region_id"], p["zone_id"]
    r.LoginPassword = p["login_password"]
    r.VpcDescriptions = [_model(models.VPCDescription, x) for x in p["vpc_descriptions"]]
    r.DefaultCOSBucket, r.CU = p["default_cos_bucket"], p["cu"]
    r.Remark, r.Period, r.InstanceChargeType = p.get("remark"), p["period"], p["charge_type"]
    r.ClusterType, r.RenewFlag = p.get("cluster_type"), p.get("renew_flag")
    r.FlinkWebUINetworkAccessType = p.get("flink_ui_access_type")
    r.SlaveVpcDescriptions = [_model(models.SlaveVpcDescriptions, x) for x in p.get("slave_vpc_descriptions") or []]
    r.CUMemory = p.get("cu_memory")
    return r


def scale_request(models, cluster_id, current, target):
    r = models.ScaleOceanusClusterRequest()
    r.ClusterId, r.NewCU = cluster_id, target
    r.ScaleMode = "ScaleDown" if target < current else "ScaleUp"
    return r


def delete_request(models, cluster_id):
    r = models.DeleteOceanusClusterRequest()
    r.ClusterId = cluster_id
    return r


def wait_ready(module, client, models, p, target_cu=None):
    def poll():
        current = find(module, client, models, p)
        if current is None:
            return "absent"
        return "ready" if current.get("Status") == 2 and (target_cu is None or current.get("CuNum") == target_cu) else "pending"

    wait_for_state(module, poll, ["ready" if target_cu is not False else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "cluster_id": {},
        "name": {},
        "region_id": {"type": "int"},
        "zone_id": {"type": "int"},
        "login_password": {"no_log": True},
        "vpc_descriptions": {"type": "list", "elements": "dict"},
        "default_cos_bucket": {},
        "cu": {"type": "int"},
        "cu_memory": {"type": "int", "choices": [0, 2, 4, 8]},
        "remark": {},
        "period": {"type": "int", "default": 1},
        "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_SECOND"], "default": "POSTPAID_BY_SECOND"},
        "cluster_type": {"choices": ["MULTI_AZ_CLUSTER"]},
        "renew_flag": {"choices": ["NOTIFY_AND_MANUAL_RENEW", "NOTIFY_AND_AUTO_RENEW", "DISABLE_NOTIFY_AND_MANUAL_RENEW"]},
        "flink_ui_access_type": {"choices": ["NetworkAccess_INTERNAL", "NetworkAccess_EXTERNAL"]},
        "slave_vpc_descriptions": {"type": "list", "elements": "dict"},
        "allow_scale_down": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10},
        "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("cluster_id", "name")], supports_check_mode=True)
    p = module.params
    if p.get("cu") is not None and not valid_cu(p["cu"]):
        module.fail_json(msg="Oceanus cu must follow 12 + 7n", cu=p["cu"])
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                p["cluster_id"] = current["ClusterId"]
                response = module.sdk_call(client.DeleteOceanusCluster, delete_request(models, p["cluster_id"]))
                if str(response.TaskExecResult).lower() != "success":
                    module.fail_json(msg="Oceanus cluster deletion was not accepted", task_result=response.TaskExecResult)
                wait_ready(module, client, models, p, False) if p["wait"] else None
            module.exit_json(changed=True, **(diff or {}), cluster=None)
        if not current:
            required = ("name", "region_id", "zone_id", "login_password", "vpc_descriptions", "default_cos_bucket", "cu")
            missing = [x for x in required if p.get(x) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for an Oceanus cluster", missing=missing)
            target = {"Name": p["name"], "CuNum": p["cu"]}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["cluster_id"] = module.sdk_call(client.CreateOceanusCluster, create_request(models, p)).ClusterId
                wait_ready(module, client, models, p, p["cu"]) if p["wait"] else None
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        immutable = {"Name": p.get("name"), "DefaultCOSBucket": p.get("default_cos_bucket"), "CuMem": p.get("cu_memory")}
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift:
            module.fail_json(msg="Oceanus cluster identity, storage and CU memory are immutable", immutable_drift=drift)
        target = p.get("cu") if p.get("cu") is not None else current.get("CuNum")
        if target == current.get("CuNum"):
            module.exit_json(changed=False, cluster=current)
        if target < current.get("CuNum") and not p["allow_scale_down"]:
            module.fail_json(msg="set allow_scale_down=true to authorize reducing Oceanus cluster CU")
        diff = maybe_diff(module, {"CuNum": current.get("CuNum")}, {"CuNum": target})
        if not module.check_mode:
            response = module.sdk_call(client.ScaleOceanusCluster, scale_request(models, current["ClusterId"], current["CuNum"], target))
            if str(response.TaskExecResult).lower() != "success":
                module.fail_json(msg="Oceanus cluster scaling was not accepted", task_result=response.TaskExecResult)
            p["cluster_id"] = current["ClusterId"]
            wait_ready(module, client, models, p, target) if p["wait"] else None
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else {"ClusterId": current["ClusterId"], "CuNum": target})
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
