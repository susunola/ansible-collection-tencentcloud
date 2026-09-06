#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tsf_cluster
short_description: Manage a Tencent Cloud TSF cluster
version_added: "0.15.0"
description: Creates, updates and deletes a TSF cluster while protecting immutable placement fields.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID; exact name is used when omitted.}
  name: {type: str, required: true, description: Cluster name.}
  cluster_type: {type: str, choices: [V, C, S], description: Cluster type; required when creating.}
  description: {type: str, description: Cluster description.}
  remark_name: {type: str, description: Cluster display remark.}
  vpc_id: {type: str, description: VPC ID, immutable after creation.}
  subnet_id: {type: str, description: Subnet ID, immutable after creation.}
  cluster_cidr: {type: str, description: Container and service CIDR, immutable after creation.}
  tsf_region_id: {type: str, description: TSF region ID, immutable after creation.}
  tsf_zone_id: {type: str, description: TSF zone ID, immutable after creation.}
  cluster_version: {type: str, description: Cluster version, immutable after creation.}
  max_node_pods: {type: int, description: Maximum pods per node at creation.}
  max_cluster_services: {type: int, description: Maximum services at creation.}
  enable_log_collection: {type: bool, description: Enable CLS collection.}
  unbind_only: {type: bool, default: false, description: Unbind instead of deleting the underlying container cluster.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_cluster:
    name: production
    cluster_type: C
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    enable_log_collection: true
"""
RETURN = r"""cluster: {description: Effective cluster metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def _ser(x):
    return x._serialize(allow_none=True) if x is not None else None


def find(module, client, models, p):
    r = models.DescribeClustersRequest()
    r.Offset, r.Limit = 0, 50
    if p.get("cluster_id"):
        r.ClusterIdList = [p["cluster_id"]]
    else:
        r.SearchWord = p["name"]
    result = module.sdk_call(client.DescribeClusters, r).Result
    values = [_ser(x) for x in ((result.Content if result else None) or [])]
    matches = (
        [x for x in values if x.get("ClusterId") == p.get("cluster_id")] if p.get("cluster_id") else [x for x in values if x.get("ClusterName") == p["name"]]
    )
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF clusters matched", name=p["name"])
    return matches[0] if matches else None


def desired(p):
    mapping = {
        "name": "ClusterName",
        "cluster_type": "ClusterType",
        "description": "ClusterDesc",
        "remark_name": "ClusterRemarkName",
        "vpc_id": "VpcId",
        "subnet_id": "SubnetId",
        "cluster_cidr": "ClusterCIDR",
        "tsf_region_id": "TsfRegionId",
        "tsf_zone_id": "TsfZoneId",
        "cluster_version": "ClusterVersion",
        "max_node_pods": "MaxNodePodNum",
        "max_cluster_services": "MaxClusterServiceNum",
        "enable_log_collection": "EnableLogCollection",
    }
    return {b: p[a] for a, b in mapping.items() if p.get(a) is not None}


def comparable(current, target):
    return {k: current.get(k) for k in target if k not in ("MaxNodePodNum", "MaxClusterServiceNum")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {},
            "name": {"required": True},
            "cluster_type": {"choices": ["V", "C", "S"]},
            "description": {},
            "remark_name": {},
            "vpc_id": {},
            "subnet_id": {},
            "cluster_cidr": {},
            "tsf_region_id": {},
            "tsf_zone_id": {},
            "cluster_version": {},
            "max_node_pods": {"type": "int"},
            "max_cluster_services": {"type": "int"},
            "enable_log_collection": {"type": "bool"},
            "unbind_only": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                r = models.DeleteClusterRequest()
                r.ClusterId = current["ClusterId"]
                r.Unbind = p["unbind_only"]
                response = module.sdk_call(client.DeleteCluster, r)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF cluster deletion", request_id=response.RequestId)
            module.exit_json(changed=True, **(diff or {}), cluster=None)
        target = desired(p)
        if not current and not p.get("cluster_type"):
            module.fail_json(msg="cluster_type is required when creating a TSF cluster")
        if current:
            require_immutable_unchanged(
                module, current, target, ["ClusterType", "VpcId", "SubnetId", "ClusterCIDR", "TsfRegionId", "TsfZoneId", "ClusterVersion"], "TSF cluster"
            )
        compare_target = {k: v for k, v in target.items() if k not in ("MaxNodePodNum", "MaxClusterServiceNum")}
        if current and comparable(current, target) == compare_target:
            module.exit_json(changed=False, cluster=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, compare_target)
        if not module.check_mode:
            if current:
                r = models.ModifyClusterRequest()
                r.ClusterId = current["ClusterId"]
                for key in ("ClusterName", "ClusterDesc", "ClusterRemarkName", "EnableLogCollection"):
                    if key in target:
                        setattr(r, key, target[key])
                response = module.sdk_call(client.ModifyCluster, r)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF cluster update", request_id=response.RequestId)
                p["cluster_id"] = current["ClusterId"]
            else:
                r = models.CreateClusterRequest()
                for key, value in target.items():
                    setattr(r, key, value)
                p["cluster_id"] = module.sdk_call(client.CreateCluster, r).Result
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
