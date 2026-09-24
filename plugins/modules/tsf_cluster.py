#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tsf_cluster
short_description: Manage a Tencent Cloud TSF cluster
version_added: "0.15.0"
description: Creates, updates and deletes a TSF cluster while protecting immutable placement fields.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - Existing cluster ID; exact name is used when omitted.
    type: str
  name:
    description:
      - Cluster name.
    type: str
    required: true
  cluster_type:
    description:
      - Cluster type; required when creating.
    type: str
    choices: [V, C, S]
  description:
    description:
      - Cluster description.
    type: str
  remark_name:
    description:
      - Cluster display remark.
    type: str
  vpc_id:
    description:
      - VPC ID, immutable after creation.
    type: str
  subnet_id:
    description:
      - Subnet ID, immutable after creation.
    type: str
  cluster_cidr:
    description:
      - Container and service CIDR, immutable after creation.
    type: str
  tsf_region_id:
    description:
      - TSF region ID, immutable after creation.
    type: str
  tsf_zone_id:
    description:
      - TSF zone ID, immutable after creation.
    type: str
  cluster_version:
    description:
      - Cluster version, immutable after creation.
    type: str
  max_node_pods:
    description:
      - Maximum pods per node at creation.
    type: int
  max_cluster_services:
    description:
      - Maximum services at creation.
    type: int
  enable_log_collection:
    description:
      - Enable CLS collection.
    type: bool
  unbind_only:
    description:
      - Unbind instead of deleting the underlying container cluster.
    type: bool
    default: false
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
