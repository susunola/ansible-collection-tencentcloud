#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: eks_cluster
short_description: Manage Tencent Cloud EKS clusters
version_added: "0.14.0"
description:
  - Create, update or remove an Elastic Kubernetes Service (EKS) cluster
    through the C(tke.v20180525) API C(CreateEKSCluster), C(UpdateEKSCluster),
    C(DeleteEKSCluster) and C(DescribeEKSClusters).
  - This module is idempotent. When a cluster with the same name already
    exists, the module compares the cluster description and issues an
    update only when it differs; all other fields are create-only.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  cluster_name:
    description: Name of the EKS cluster, e.g. C(eks-prod).
    type: str
    required: true
  state:
    description: Whether the cluster should exist.
    type: str
    choices: [present, absent]
    default: present
  vpc_id:
    description:
      - VPC the cluster runs in, written to
        V(CreateEKSClusterRequest.VpcId). Required when the cluster has to
        be created.
    type: str
  subnet_ids:
    description:
      - Subnet IDs for the cluster, written to
        V(CreateEKSClusterRequest.SubnetIds). Required when the cluster has
        to be created.
    type: list
    elements: str
  k8s_version:
    description:
      - Kubernetes version, written to V(CreateEKSClusterRequest.K8SVersion).
        Only sent when provided at creation.
    type: str
  cluster_desc:
    description:
      - Cluster description. Compared against the remote value and written
        through V(UpdateEKSClusterRequest.ClusterDesc) when it differs.
    type: str
  enable_vpc_coredns:
    description:
      - Enable VPC-native CoreDNS, written to
        V(CreateEKSClusterRequest.EnableVpcCoreDNS). Only sent when
        provided at creation.
    type: bool
  service_subnet_id:
    description:
      - Service CIDR subnet, written to
        V(CreateEKSClusterRequest.ServiceSubnetId). Only sent when provided
        at creation.
    type: str
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-tke) package on the controller.
  - Cluster creation is asynchronous; this module returns as soon as the
    create/update/delete request is accepted and does not wait for the
    cluster to reach a ready state.
  - Changing the VPC, subnets or Kubernetes version of an existing cluster
    is not supported by the platform; remove the cluster (state=absent) and
    re-run to rebuild it.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an EKS cluster
  susunola.tencentcloud.eks_cluster:
    region: ap-guangzhou
    cluster_name: eks-prod
    vpc_id: vpc-xxxxxxxx
    subnet_ids:
      - subnet-xxxxxxxx
      - subnet-yyyyyyyy
    k8s_version: "1.28.5"
    cluster_desc: production EKS cluster

- name: Remove an EKS cluster
  susunola.tencentcloud.eks_cluster:
    region: ap-guangzhou
    cluster_name: eks-prod
    state: absent
'''

RETURN = r'''
cluster_id:
  description: ID of the matched or newly created cluster.
  returned: when known
  type: str
cluster_name:
  description: Name of the managed cluster.
  returned: always
  type: str
status:
  description: Status of the existing cluster.
  returned: when a matching cluster exists
  type: str
changed:
  description: Whether an API write happened.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def find_cluster(module, client, models, cluster_name):
    """Return the serialized EKS cluster dict with the given name, or None."""
    request = models.DescribeEKSClustersRequest()
    offset = 0
    while True:
        request.Offset = offset
        request.Limit = 100
        response = module.sdk_call(client.DescribeEKSClusters, request)
        items = response.Clusters or []
        for item in items:
            data = item._serialize(allow_none=True)
            if data.get("ClusterName") == cluster_name:
                return data
        if len(items) < 100:
            break
        offset += len(items)
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "vpc_id": {"type": "str"},
            "subnet_ids": {"type": "list", "elements": "str"},
            "k8s_version": {"type": "str"},
            "cluster_desc": {"type": "str"},
            "enable_vpc_coredns": {"type": "bool"},
            "service_subnet_id": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        cluster = find_cluster(module, client, models, p["cluster_name"])

        if p["state"] == "absent":
            if cluster is None:
                module.exit_json(changed=False, cluster_name=p["cluster_name"], msg="EKS cluster not present")
            diff = maybe_diff(module, cluster, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    cluster_name=p["cluster_name"],
                    msg="Would delete EKS cluster {0}".format(cluster.get("ClusterId")),
                )
            request = models.DeleteEKSClusterRequest()
            request.ClusterId = cluster["ClusterId"]
            module.sdk_call(client.DeleteEKSCluster, request)
            module.exit_json(
                changed=True, **(diff or {}),
                cluster_name=p["cluster_name"],
                msg="Deleted EKS cluster {0}".format(cluster.get("ClusterId")),
            )

        # state == present
        if cluster is not None:
            current_desc = cluster.get("ClusterDesc") or ""
            desired_desc = p["cluster_desc"] or ""
            if current_desc == desired_desc:
                module.exit_json(
                    changed=False,
                    cluster_id=cluster.get("ClusterId"),
                    cluster_name=p["cluster_name"],
                    status=cluster.get("Status"),
                    msg="EKS cluster already present",
                )
            after = {"ClusterDesc": desired_desc}
            diff = maybe_diff(module, {"ClusterDesc": current_desc}, after)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    cluster_id=cluster.get("ClusterId"),
                    cluster_name=p["cluster_name"],
                    msg="Would update description of EKS cluster {0}".format(cluster.get("ClusterId")),
                )
            request = models.UpdateEKSClusterRequest()
            request.ClusterId = cluster["ClusterId"]
            request.ClusterDesc = desired_desc
            module.sdk_call(client.UpdateEKSCluster, request)
            module.exit_json(
                changed=True, **(diff or {}),
                cluster_id=cluster.get("ClusterId"),
                cluster_name=p["cluster_name"],
                msg="Updated description of EKS cluster {0}".format(cluster.get("ClusterId")),
            )

        missing = [k for k in ("vpc_id", "subnet_ids") if p[k] is None]
        if missing:
            module.fail_json(
                msg="Parameters required to create an EKS cluster are missing: {0}".format(", ".join(missing)),
            )
        after = {"ClusterName": p["cluster_name"]}
        diff = maybe_diff(module, None, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                cluster_name=p["cluster_name"],
                msg="Would create EKS cluster {0}".format(p["cluster_name"]),
            )

        request = models.CreateEKSClusterRequest()
        request.ClusterName = p["cluster_name"]
        request.VpcId = p["vpc_id"]
        request.SubnetIds = p["subnet_ids"]
        if p["k8s_version"]:
            request.K8SVersion = p["k8s_version"]
        if p["cluster_desc"]:
            request.ClusterDesc = p["cluster_desc"]
        if p["enable_vpc_coredns"]:
            request.EnableVpcCoreDNS = p["enable_vpc_coredns"]
        if p["service_subnet_id"]:
            request.ServiceSubnetId = p["service_subnet_id"]
        response = module.sdk_call(client.CreateEKSCluster, request)
        cluster_id = getattr(response, "ClusterId", None)
        module.exit_json(
            changed=True, **(diff or {}),
            cluster_id=cluster_id,
            cluster_name=p["cluster_name"],
            msg="EKS cluster creation submitted",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
