#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cvm_hpc_cluster
short_description: Manage Tencent Cloud CVM high-performance clusters
version_added: "0.14.0"
description: Creates, updates and deletes CVM high-performance clusters with guarded replacement of immutable topology.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing HPC cluster ID.}
  name: {type: str, description: Cluster name.}
  zone: {type: str, description: Availability zone; immutable after creation.}
  remark: {type: str, default: managed by Ansible, description: Cluster remark.}
  cluster_type: {type: str, choices: [STANDARD, CDC, CHC], default: STANDARD, description: HPC cluster type.}
  business_id: {type: str, description: Business-scene ID used by CDC clusters.}
  force_replace: {type: bool, default: false, description: Replace an empty cluster when immutable topology changes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cvm_hpc_cluster:
    name: rdma-production
    zone: ap-guangzhou-3
    cluster_type: STANDARD
    remark: Production RDMA placement
'''
RETURN = r'''hpc_cluster: {description: Effective HPC cluster metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client
def describe_request(models, p):
    request = models.DescribeHpcClustersRequest(); request.Limit = 100
    if p.get("cluster_id"): request.HpcClusterIds = [p["cluster_id"]]
    elif p.get("name"): request.Name = p["name"]
    return request
def create_request(models, p):
    request = models.CreateHpcClusterRequest(); request.Zone, request.Name, request.Remark = p["zone"], p["name"], p["remark"]
    request.HpcClusterType, request.HpcClusterBusinessId = p["cluster_type"], p.get("business_id"); return request
def update_request(models, p, cluster_id):
    request = models.ModifyHpcClusterAttributeRequest(); request.HpcClusterId, request.Name, request.Remark = cluster_id, p["name"], p["remark"]; return request
def delete_request(models, cluster_id):
    request = models.DeleteHpcClustersRequest(); request.HpcClusterIds = [cluster_id]; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeHpcClusters, describe_request(models, p)); matches = []
    for item in response.HpcClusterSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("cluster_id") and value.get("HpcClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("Name") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple CVM HPC clusters matched; specify cluster_id")
    return matches[0] if matches else None
def comparable(v): return {"Name": v.get("Name"), "Remark": v.get("Remark"), "Zone": v.get("Zone"), "HpcClusterType": v.get("HpcClusterType") or "STANDARD", "HpcClusterBusinessId": v.get("HpcClusterBusinessId")}
def desired(p): return {"Name": p["name"], "Remark": p["remark"], "Zone": p["zone"], "HpcClusterType": p["cluster_type"], "HpcClusterBusinessId": p.get("business_id")}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {}, "name": {}, "zone": {}, "remark": {"default": "managed by Ansible"}, "cluster_type": {"choices": ["STANDARD", "CDC", "CHC"], "default": "STANDARD"}, "business_id": {}, "force_replace": {"type": "bool", "default": False}}, required_one_of=[("cluster_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p.get("zone")): module.fail_json(msg="name and zone are required when state=present")
    if p["cluster_type"] == "CDC" and not p.get("business_id"): module.fail_json(msg="business_id is required for CDC clusters")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, hpc_cluster=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteHpcClusters, delete_request(models, current["HpcClusterId"]))
            module.exit_json(changed=True, **(diff or {}), hpc_cluster=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        replace = bool(current and (before["Zone"], before["HpcClusterType"], before["HpcClusterBusinessId"]) != (target["Zone"], target["HpcClusterType"], target["HpcClusterBusinessId"]))
        if replace and not p["force_replace"]: module.fail_json(msg="HPC cluster topology is immutable; set force_replace=true to replace an empty cluster", current=before, desired=target)
        if replace and current.get("InstanceIds"): module.fail_json(msg="cannot replace a non-empty HPC cluster", instance_ids=current["InstanceIds"])
        if before == target: module.exit_json(changed=False, hpc_cluster=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace: module.sdk_call(client.DeleteHpcClusters, delete_request(models, current["HpcClusterId"])); current = None
            if current: module.sdk_call(client.ModifyHpcClusterAttribute, update_request(models, p, current["HpcClusterId"]))
            else: p["cluster_id"] = module.sdk_call(client.CreateHpcCluster, create_request(models, p)).HpcClusterId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), hpc_cluster=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
