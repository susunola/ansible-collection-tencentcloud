#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdcpg_cluster
short_description: Manage Tencent Cloud TDSQL-C PostgreSQL clusters
version_added: "0.14.0"
description: Creates, renames, scales, isolates and permanently deletes TDSQL-C PostgreSQL clusters and reconciles their instance topology.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID.}
  name: {type: str, description: Cluster name.}
  zone: {type: str, description: Availability zone; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  master_password: {type: str, description: Initial master-user password.}
  cpu: {type: int, description: CPU cores per cluster instance.}
  memory: {type: int, description: Memory in GiB per cluster instance.}
  instance_count: {type: int, description: Desired instance count; defaults to one during creation.}
  allow_scale_in: {type: bool, default: false, description: Authorize deleting excess instances when reducing instance_count.}
  db_version: {type: str, description: Compatible PostgreSQL version; immutable after creation.}
  db_major_version: {type: str, description: PostgreSQL major version; immutable after creation.}
  db_kernel_version: {type: str, description: Database kernel version; immutable after creation.}
  pay_mode: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], default: POSTPAID_BY_HOUR, description: Billing mode.}
  period_months: {type: int, default: 1, description: Prepaid purchase period.}
  auto_renew: {type: bool, description: Automatically renew prepaid clusters.}
  port: {type: int, default: 5432, description: Initial database port.}
  storage_pay_mode: {type: str, description: Storage billing mode.}
  storage: {type: int, description: Storage capacity in GiB.}
  purge: {type: bool, default: false, description: Permanently delete an already isolated cluster.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdcpg_cluster:
    name: production-tdcpg
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    master_password: "{{ vault_tdcpg_password }}"
    cpu: 4
    memory: 8
    instance_count: 2
    db_version: '13.3'
'''
RETURN = r'''cluster: {description: Effective TDSQL-C PostgreSQL cluster metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tdcpg.v20211118 import models, tdcpg_client
    return models, tdcpg_client
def describe_request(models, p, page=1):
    r = models.DescribeClustersRequest(); r.PageNumber, r.PageSize = page, 100
    if p.get("cluster_id") or p.get("name"):
        f = models.Filter(); f.Name, f.Values = ("ClusterId", [p["cluster_id"]]) if p.get("cluster_id") else ("ClusterName", [p["name"]]); r.Filters = [f]
    return r
def instances_request(models, cluster_id, page=1):
    r = models.DescribeClusterInstancesRequest(); r.ClusterId, r.PageNumber, r.PageSize = cluster_id, page, 100; return r
def create_request(models, p):
    r = models.CreateClusterRequest(); r.Zone, r.MasterUserPassword, r.CPU, r.Memory = p["zone"], p["master_password"], p["cpu"], p["memory"]
    r.VpcId, r.SubnetId, r.PayMode, r.ClusterName = p["vpc_id"], p["subnet_id"], p["pay_mode"], p["name"]
    r.DBVersion, r.DBMajorVersion, r.DBKernelVersion = p.get("db_version"), p.get("db_major_version"), p.get("db_kernel_version")
    r.Port, r.InstanceCount, r.Period = p["port"], p.get("instance_count") or 1, p["period_months"]
    r.AutoRenewFlag = None if p.get("auto_renew") is None else int(p["auto_renew"]); r.StoragePayMode, r.Storage = p.get("storage_pay_mode"), p.get("storage"); return r
def create_instances_request(models, p, cluster_id, count):
    r = models.CreateClusterInstancesRequest(); r.ClusterId, r.CPU, r.Memory, r.InstanceCount = cluster_id, p["cpu"], p["memory"], count; return r
def resize_request(models, p, cluster_id, instance_ids):
    r = models.ModifyClusterInstancesSpecRequest(); r.ClusterId, r.InstanceIdSet, r.CPU, r.Memory, r.OperationTiming = cluster_id, instance_ids, p["cpu"], p["memory"], "IMMEDIATE"; return r
def delete_instances_request(models, cluster_id, instance_ids):
    r = models.DeleteClusterInstancesRequest(); r.ClusterId, r.InstanceIdSet = cluster_id, instance_ids; return r
def rename_request(models, cluster_id, name):
    r = models.ModifyClusterNameRequest(); r.ClusterId, r.ClusterName = cluster_id, name; return r
def renew_request(models, cluster_id, enabled):
    r = models.ModifyClustersAutoRenewFlagRequest(); r.ClusterIdSet, r.AutoRenewFlag = [cluster_id], int(enabled); return r
def isolate_request(models, cluster_id):
    r = models.IsolateClusterRequest(); r.ClusterId = cluster_id; return r
def delete_request(models, cluster_id):
    r = models.DeleteClusterRequest(); r.ClusterId = cluster_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeClusters, describe_request(models, p)); matches = []
    for item in response.ClusterSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple TDSQL-C PostgreSQL clusters matched; specify cluster_id")
    return matches[0] if matches else None
def instances(module, client, models, cluster_id):
    return [x._serialize(allow_none=True) for x in (module.sdk_call(client.DescribeClusterInstances, instances_request(models, cluster_id)).InstanceSet or [])]
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: str((find(module, client, models, p) or {}).get("Status", "")).lower(), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {}, "name": {}, "zone": {}, "vpc_id": {}, "subnet_id": {}, "master_password": {"no_log": True}, "cpu": {"type": "int"}, "memory": {"type": "int"}, "instance_count": {"type": "int"}, "allow_scale_in": {"type": "bool", "default": False}, "db_version": {}, "db_major_version": {}, "db_kernel_version": {}, "pay_mode": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"}, "period_months": {"type": "int", "default": 1}, "auto_renew": {"type": "bool"}, "port": {"type": "int", "default": 5432}, "storage_pay_mode": {}, "storage": {"type": "int"}, "purge": {"type": "bool", "default": False}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("cluster_id", "name")], required_together=[("cpu", "memory")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdcpgClient, "tdcpg.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, cluster=None)
            status, cluster_id = str(current.get("Status", "")).lower(), current["ClusterId"]
            if p["purge"]:
                if status != "isolated": module.fail_json(msg="purge requires an already isolated TDSQL-C PostgreSQL cluster", current_status=status)
                diff = maybe_diff(module, current, None)
                if not module.check_mode: module.sdk_call(client.DeleteCluster, delete_request(models, cluster_id))
                module.exit_json(changed=True, **(diff or {}), cluster=None)
            if status in ("isolating", "isolated"): module.exit_json(changed=False, cluster=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.IsolateCluster, isolate_request(models, cluster_id))
            module.exit_json(changed=True, **(diff or {}), cluster=current)
        if not current:
            missing = [k for k in ("name", "zone", "vpc_id", "subnet_id", "master_password", "cpu", "memory") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new TDSQL-C PostgreSQL cluster", missing=missing)
            target = {"ClusterName": p["name"], "Zone": p["zone"], "DBVersion": p.get("db_version"), "InstanceCount": p.get("instance_count") or 1, "StorageLimit": p.get("storage")}; diff = maybe_diff(module, None, target)
            if not module.check_mode: module.sdk_call(client.CreateCluster, create_request(models, p)); _wait(module, client, models, p, ["running"]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        endpoints = current.get("EndpointSet") or []; networks = {(x.get("VpcId"), x.get("SubnetId")) for x in endpoints}; immutable = {"Zone": p.get("zone"), "DBVersion": p.get("db_version"), "DBMajorVersion": p.get("db_major_version"), "DBKernelVersion": p.get("db_kernel_version")}; drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if p.get("vpc_id") and (p["vpc_id"], p.get("subnet_id")) not in networks: drift["Network"] = (sorted(networks), (p["vpc_id"], p.get("subnet_id")))
        if drift: module.fail_json(msg="TDSQL-C PostgreSQL placement and database versions are immutable", immutable_drift=drift)
        cluster_id = current["ClusterId"]; members = instances(module, client, models, cluster_id); desired_count = p.get("instance_count") if p.get("instance_count") is not None else len(members)
        if desired_count < len(members) and not p["allow_scale_in"]: module.fail_json(msg="set allow_scale_in=true to delete excess cluster instances", current_count=len(members), desired_count=desired_count)
        changed = False; before = {"ClusterName": current.get("ClusterName"), "InstanceCount": len(members), "AutoRenewFlag": current.get("AutoRenewFlag")}; desired = {"ClusterName": p.get("name") or current.get("ClusterName"), "InstanceCount": desired_count, "AutoRenewFlag": int(p["auto_renew"]) if p.get("auto_renew") is not None else current.get("AutoRenewFlag")}
        spec_drift = p.get("cpu") is not None and any(x.get("CPU") != p["cpu"] or x.get("Memory") != p["memory"] for x in members)
        if before != desired or spec_drift:
            changed = True; diff = maybe_diff(module, before, desired)
            if not module.check_mode:
                if before["ClusterName"] != desired["ClusterName"]: module.sdk_call(client.ModifyClusterName, rename_request(models, cluster_id, desired["ClusterName"]))
                if spec_drift: module.sdk_call(client.ModifyClusterInstancesSpec, resize_request(models, p, cluster_id, [x["InstanceId"] for x in members]))
                if desired_count > len(members): module.sdk_call(client.CreateClusterInstances, create_instances_request(models, p, cluster_id, desired_count - len(members)))
                elif desired_count < len(members): module.sdk_call(client.DeleteClusterInstances, delete_instances_request(models, cluster_id, [x["InstanceId"] for x in members[desired_count:]]))
                if before["AutoRenewFlag"] != desired["AutoRenewFlag"]: module.sdk_call(client.ModifyClustersAutoRenewFlag, renew_request(models, cluster_id, p["auto_renew"]))
                p["cluster_id"] = cluster_id; _wait(module, client, models, p, ["running"]); current = find(module, client, models, p)
        module.exit_json(changed=changed, **((diff if changed else None) or {}), cluster=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
