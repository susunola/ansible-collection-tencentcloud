#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster
short_description: Manage Tencent Cloud TKE clusters
version_added: "0.12.0"
description:
  - Create, update and delete TKE (Kubernetes) clusters through the
    C(tke.v20180525) API.
  - This module is idempotent. Running it twice leaves the cluster
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A cluster is identified by O(cluster_id) or by O(name). Worker node
    provisioning is intentionally out of scope; create the cluster with
    this module and manage node pools or add nodes through dedicated
    tooling afterwards.
options:
  state:
    description:
      - C(present) creates the cluster when it does not exist and updates
        its name, description and project when it does.
      - C(absent) deletes the cluster and (optionally) its attached
        resources.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - ID of an existing cluster, e.g. C(cls-xxxxxxxx).
      - When given, the module operates on that cluster; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the cluster, written to
        V(ClusterBasicSettings.ClusterName) and
        V(ModifyClusterAttributeRequest.ClusterName).
    type: str
  vpc_id:
    description:
      - ID of the VPC, written to V(ClusterBasicSettings.VpcId).
      - Required when creating the cluster.
    type: str
  subnet_id:
    description:
      - ID of the subnet for the master nodes, written to
        V(ClusterBasicSettings.SubnetId).
    type: str
  cluster_version:
    description:
      - Kubernetes version of the cluster, written to
        V(ClusterBasicSettings.ClusterVersion).
      - Only applied at creation.
    type: str
  cluster_desc:
    description:
      - Description of the cluster, written to
        V(ClusterBasicSettings.ClusterDescription) and
        V(ModifyClusterAttributeRequest.ClusterDesc).
    type: str
  project_id:
    description:
      - Project the cluster belongs to, written to
        V(ClusterBasicSettings.ProjectId) and
        V(ModifyClusterAttributeRequest.ProjectId).
    type: int
  cluster_type:
    description:
      - Type of the cluster (C(MANAGED_CLUSTER) or C(INDEPENDENT_CLUSTER)),
        written to V(CreateClusterRequest.ClusterType).
      - Only applied at creation.
    type: str
    choices: [MANAGED_CLUSTER, INDEPENDENT_CLUSTER]
    default: MANAGED_CLUSTER
  cluster_cidr:
    description:
      - CIDR of the pod network, written to V(ClusterCIDRSettings.
        ClusterCIDR).
      - Only applied at creation.
    type: str
  service_cidr:
    description:
      - CIDR of the service network, written to V(ClusterCIDRSettings.
        ServiceCIDR).
      - Only applied at creation.
    type: str
  max_node_pod_num:
    description:
      - Maximum pods per node, written to V(ClusterCIDRSettings.
        MaxNodePodNum).
      - Only applied at creation.
    type: int
  deletion_protection:
    description:
      - Protect the cluster from deletion, written to
        V(ClusterAdvancedSettings.DeletionProtection).
      - When true and O(state=absent), the module disables the protection
        first, then deletes the cluster.
    type: bool
    default: false
  instance_delete_mode:
    description:
      - How to treat the instances of a deleted cluster, written to
        V(DeleteClusterRequest.InstanceDeleteMode).
    type: str
    choices: [terminate, retain]
    default: retain
  tags:
    description:
      - Tags to apply to the cluster as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
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
  - Cluster creation takes 10-20 minutes; the module returns as soon as
    the creation request is accepted.
  - Worker nodes are not provisioned by this module; add them via node
    pools or other dedicated tooling.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a managed TKE cluster
  susunola.tencentcloud.tke_cluster:
    region: ap-guangzhou
    state: present
    name: prod-k8s
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    cluster_version: "1.28"
    cluster_cidr: 10.42.0.0/16
    service_cidr: 10.43.0.0/16
    tags:
      env: prod

- name: Rename it
  susunola.tencentcloud.tke_cluster:
    region: ap-guangzhou
    state: present
    name: prod-k8s-v2

- name: Delete it, keeping the underlying instances
  susunola.tencentcloud.tke_cluster:
    region: ap-guangzhou
    state: absent
    name: prod-k8s-v2
    instance_delete_mode: retain
'''

RETURN = r'''
cluster:
  description: The cluster as reported by V(DescribeClusters) after the
    operation.
  returned: success
  type: dict
  sample:
    ClusterId: cls-xxxxxxxx
    ClusterName: prod-k8s
    ClusterStatus: Running
    ClusterVersion: "1.28"
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def build_describe_request(models, cluster_id, name):
    request = models.DescribeClustersRequest()
    request.Limit = 100
    if cluster_id:
        request.ClusterIds = [cluster_id]
    elif name:
        name_filter = models.Filter()
        name_filter.Name = "cluster-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_cluster(module, client, models, cluster_id, name):
    """Return the matching cluster dict or None."""
    request = build_describe_request(models, cluster_id, name)
    response = module.sdk_call(client.DescribeClusters, request)
    if cluster_id:
        cluster = _first(response.Clusters or [])
        return cluster._serialize(allow_none=True) if cluster is not None else None
    for cluster in response.Clusters or []:
        current = cluster._serialize(allow_none=True)
        if current.get("ClusterName") == name:
            return current
    return None


def _create(module, client, models, params):
    request = models.CreateClusterRequest()
    request.ClusterType = params["cluster_type"]
    basic = models.ClusterBasicSettings()
    basic.ClusterName = params["name"]
    basic.VpcId = params["vpc_id"]
    if params["subnet_id"]:
        basic.SubnetId = params["subnet_id"]
    if params["cluster_version"]:
        basic.ClusterVersion = params["cluster_version"]
    if params["cluster_desc"]:
        basic.ClusterDescription = params["cluster_desc"]
    if params["project_id"] is not None:
        basic.ProjectId = params["project_id"]
    if params["tags"]:
        spec = models.TagSpecification()
        spec.ResourceType = "cluster"
        sdk_tags = []
        for key, value in sorted(params["tags"].items()):
            sdk_tag = models.Tag()
            sdk_tag.Key = key
            sdk_tag.Value = value
            sdk_tags.append(sdk_tag)
        spec.Tags = sdk_tags
        basic.TagSpecification = [spec]
    request.ClusterBasicSettings = basic
    if params["cluster_cidr"] or params["service_cidr"] or params["max_node_pod_num"] is not None:
        cidr = models.ClusterCIDRSettings()
        if params["cluster_cidr"]:
            cidr.ClusterCIDR = params["cluster_cidr"]
        if params["service_cidr"]:
            cidr.ServiceCIDR = params["service_cidr"]
        if params["max_node_pod_num"] is not None:
            cidr.MaxNodePodNum = params["max_node_pod_num"]
        request.ClusterCIDRSettings = cidr
    if params["deletion_protection"]:
        advanced = models.ClusterAdvancedSettings()
        advanced.DeletionProtection = True
        request.ClusterAdvancedSettings = advanced
    response = module.sdk_call(client.CreateCluster, request)
    return response.ClusterId


def _update(module, client, models, cluster_id, name, cluster_desc, project_id):
    request = models.ModifyClusterAttributeRequest()
    request.ClusterId = cluster_id
    if name is not None:
        request.ClusterName = name
    if cluster_desc is not None:
        request.ClusterDesc = cluster_desc
    if project_id is not None:
        request.ProjectId = project_id
    module.sdk_call(client.ModifyClusterAttribute, request)


def _set_deletion_protection(module, client, models, cluster_id, enabled):
    request = models.ModifyClusterAttributeRequest()
    request.ClusterId = cluster_id
    advanced = models.ClusterAdvancedSettings()
    advanced.DeletionProtection = enabled
    request.ClusterProperty = advanced
    module.sdk_call(client.ModifyClusterAttribute, request)


def _delete(module, client, models, cluster_id, instance_delete_mode):
    request = models.DeleteClusterRequest()
    request.ClusterId = cluster_id
    if instance_delete_mode:
        request.InstanceDeleteMode = instance_delete_mode
    module.sdk_call(client.DeleteCluster, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "cluster_version": {"type": "str"},
            "cluster_desc": {"type": "str"},
            "project_id": {"type": "int"},
            "cluster_type": {"type": "str", "choices": ["MANAGED_CLUSTER", "INDEPENDENT_CLUSTER"], "default": "MANAGED_CLUSTER"},
            "cluster_cidr": {"type": "str"},
            "service_cidr": {"type": "str"},
            "max_node_pod_num": {"type": "int"},
            "deletion_protection": {"type": "bool", "default": False},
            "instance_delete_mode": {"type": "str", "choices": ["terminate", "retain"], "default": "retain"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    cluster_id = module.params["cluster_id"]
    name = module.params["name"]

    if not cluster_id and not name:
        module.fail_json(msg="cluster_id or name is required to identify the cluster")

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")

    try:
        current = find_cluster(module, client, models, cluster_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="TKE cluster already absent")
        target_id = current["ClusterId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete TKE cluster")
        if current.get("DeletionProtection"):
            _set_deletion_protection(module, client, models, target_id, False)
        _delete(module, client, models, target_id, module.params["instance_delete_mode"])
        module.exit_json(changed=True, **(diff or {}), cluster=None, msg="TKE cluster deleted")

    # state == present
    if current is None:
        missing = [key for key in ("name", "vpc_id") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a TKE cluster" % ", ".join(missing))
        desired = {
            "ClusterName": name,
            "ClusterType": module.params["cluster_type"],
            "VpcId": module.params["vpc_id"],
            "DeletionProtection": module.params["deletion_protection"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create TKE cluster")
        created_id = _create(module, client, models, module.params)
        current = find_cluster(module, client, models, created_id, None)
        module.exit_json(changed=True, **(diff or {}), cluster=current, msg="TKE cluster created")

    target_id = current["ClusterId"]
    changes = []
    if name and current.get("ClusterName") != name:
        changes.append("name")
    cluster_desc = module.params["cluster_desc"]
    if cluster_desc is not None and current.get("ClusterDescription") != cluster_desc:
        changes.append("cluster_desc")
    project_id = module.params["project_id"]
    if project_id is not None and current.get("ProjectId") != project_id:
        changes.append("project_id")

    if not changes:
        module.exit_json(changed=False, cluster=current, msg="TKE cluster is up to date")

    diff = maybe_diff(module, current, {
        "ClusterName": name or current.get("ClusterName"),
        "ClusterDescription": cluster_desc if cluster_desc is not None else current.get("ClusterDescription"),
        "ProjectId": project_id if project_id is not None else current.get("ProjectId"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update TKE cluster")

    _update(
        module, client, models, target_id,
        name if "name" in changes else None,
        cluster_desc if "cluster_desc" in changes else None,
        project_id if "project_id" in changes else None,
    )
    updated = find_cluster(module, client, models, target_id, None)
    module.exit_json(changed=True, **(diff or {}), cluster=updated, msg="TKE cluster updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
