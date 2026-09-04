#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_node_pool
short_description: Manage Tencent Cloud TKE cluster node pools
version_added: "0.13.0"
description:
  - Create, update and delete Tencent Cloud TKE (Tencent Kubernetes
    Engine) cluster node pools through the C(tke.v20180525) API.
  - This module is idempotent. Running it twice leaves the node pool
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A node pool is identified by O(cluster_id) plus O(name). The autoscale
    settings (O(enable_autoscale), O(max_nodes_num), O(min_nodes_num)),
    O(labels), O(taints) and O(deletion_protection) are enforced on an
    existing pool with V(ModifyClusterNodePool).
  - The launch configuration is passed as a raw JSON string in
    O(launch_configuration_json) (the C(LaunchConfigurePara) parameter of
    V(CreateClusterNodePool)); it is only applied at creation.
options:
  state:
    description:
      - C(present) creates the node pool when it does not exist and
        enforces the autoscale settings, labels, taints and deletion
        protection on an existing pool.
      - C(absent) deletes the node pool with V(DeleteClusterNodePool).
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - ID of the cluster the node pool belongs to, written to
        V(CreateClusterNodePoolRequest.ClusterId).
    type: str
    required: true
  name:
    description:
      - Name of the node pool, written to
        V(CreateClusterNodePoolRequest.Name) and
        V(ModifyClusterNodePoolRequest.Name).
      - Required when creating the pool.
    type: str
  launch_configuration_json:
    description:
      - Launch configuration of the nodes as a JSON string, written to
        V(CreateClusterNodePoolRequest.LaunchConfigurePara).
      - Required when creating the pool; the schema follows the CVM
        run-instance parameters (see the official API documentation for
        V(CreateClusterNodePool)).
      - Not applied to existing pools.
    type: str
  autoscaling_group_json:
    description:
      - Autoscaling group configuration as a JSON string, written to
        V(CreateClusterNodePoolRequest.AutoScalingGroupPara).
      - Only applied at creation.
    type: str
  enable_autoscale:
    description:
      - Whether autoscaling is enabled, written to
        V(CreateClusterNodePoolRequest.EnableAutoscale) and
        V(ModifyClusterNodePoolRequest.EnableAutoscale).
    type: bool
  max_nodes_num:
    description:
      - Maximum number of nodes, written to
        V(ModifyClusterNodePoolRequest.MaxNodesNum).
    type: int
  min_nodes_num:
    description:
      - Minimum number of nodes, written to
        V(ModifyClusterNodePoolRequest.MinNodesNum).
    type: int
  labels:
    description:
      - Kubernetes labels applied to the nodes as a dict, written to
        V(ModifyClusterNodePoolRequest.Labels).
    type: dict
    default: {}
  taints:
    description:
      - Kubernetes taints applied to the nodes as a list of dicts with
        C(key), C(value) and C(effect) keys, written to
        V(ModifyClusterNodePoolRequest.Taints).
    type: list
    elements: dict
    default: []
  node_pool_os:
    description:
      - Operating system of the nodes, written to
        V(CreateClusterNodePoolRequest.NodePoolOs).
      - For a custom image pass the image ID; otherwise pass the public
        image OS name.
      - Only applied at creation.
    type: str
  deletion_protection:
    description:
      - Whether deletion protection is enabled, written to
        V(CreateClusterNodePoolRequest.DeletionProtection) and
        V(ModifyClusterNodePoolRequest.DeletionProtection).
    type: bool
  keep_instance:
    description:
      - When C(state=absent), whether the instances inside the deleted
        node pool are kept (they are removed from the cluster but not
        destroyed), written to V(DeleteClusterNodePoolRequest.KeepInstance).
    type: bool
    default: false
  tags:
    description:
      - Tags to apply to the node pool as a dict, for example I(env=prod).
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
  - The node pool is considered up to date as soon as the create API
    returns; node provisioning continues asynchronously inside the
    cluster.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an autoscaling node pool
  susunola.tencentcloud.tke_node_pool:
    region: ap-guangzhou
    state: present
    cluster_id: cls-xxxxxxxx
    name: workers
    enable_autoscale: true
    min_nodes_num: 2
    max_nodes_num: 10
    launch_configuration_json: '{"InstanceTypes":["S5.LARGE8"],"InstanceChargeType":"POSTPAID_BY_HOUR","SystemDisk":{"DiskType":"CLOUD_PREMIUM","DiskSize":50}}'
    labels:
      app: workers
    taints:
      - key: dedicated
        value: "true"
        effect: NoSchedule
    deletion_protection: true

- name: Scale the autoscale limits
  susunola.tencentcloud.tke_node_pool:
    region: ap-guangzhou
    state: present
    cluster_id: cls-xxxxxxxx
    name: workers
    enable_autoscale: true
    min_nodes_num: 3
    max_nodes_num: 20

- name: Delete the node pool and keep the instances
  susunola.tencentcloud.tke_node_pool:
    region: ap-guangzhou
    state: absent
    cluster_id: cls-xxxxxxxx
    name: workers
    keep_instance: true
'''

RETURN = r'''
node_pool:
  description: The node pool as reported by V(DescribeClusterNodePools)
    after the operation.
  returned: success
  type: dict
  sample:
    NodePoolId: np-xxxxxxxx
    Name: workers
    LifeState: normal
    MaxNodesNum: 10
    MinNodesNum: 2
    Labels:
      - Name: app
        Value: workers
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def build_describe_request(models, cluster_id):
    request = models.DescribeClusterNodePoolsRequest()
    request.ClusterId = cluster_id
    return request


def find_node_pool(module, client, models, cluster_id, name):
    """Return the matching node pool dict or None."""
    request = build_describe_request(models, cluster_id)
    response = module.sdk_call(client.DescribeClusterNodePools, request)
    for item in response.NodePoolSet or []:
        current = item._serialize(allow_none=True)
        if current.get("Name") == name:
            return current
    return None


def build_create_request(models, params):
    request = models.CreateClusterNodePoolRequest()
    request.ClusterId = params["cluster_id"]
    request.Name = params["name"]
    request.LaunchConfigurePara = params["launch_configuration_json"]
    if params["autoscaling_group_json"]:
        request.AutoScalingGroupPara = params["autoscaling_group_json"]
    if params["enable_autoscale"] is not None:
        request.EnableAutoscale = params["enable_autoscale"]
    if params["labels"]:
        request.Labels = _build_labels(models, params["labels"])
    if params["taints"]:
        request.Taints = _build_taints(models, params["taints"])
    if params["node_pool_os"] is not None:
        request.NodePoolOs = params["node_pool_os"]
    if params["deletion_protection"] is not None:
        request.DeletionProtection = params["deletion_protection"]
    if params["tags"]:
        request.Tags = _build_tags(models, params["tags"])
    return request


def _build_labels(models, labels):
    result = []
    for key, value in sorted(labels.items()):
        label = models.Label()
        label.Name = key
        label.Value = str(value)
        result.append(label)
    return result


def _build_taints(models, taints):
    result = []
    for item in taints:
        taint = models.Taint()
        taint.Key = item.get("key")
        taint.Value = item.get("value")
        taint.Effect = item.get("effect")
        result.append(taint)
    return result


def _build_tags(models, tags):
    result = []
    for key, value in sorted(tags.items()):
        tag = models.Tag()
        tag.Key = key
        tag.Value = str(value)
        result.append(tag)
    return result


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateClusterNodePool, request)


def _update(module, client, models, params, pool_id):
    request = models.ModifyClusterNodePoolRequest()
    request.ClusterId = params["cluster_id"]
    request.NodePoolId = pool_id
    if params["name"]:
        request.Name = params["name"]
    if params["enable_autoscale"] is not None:
        request.EnableAutoscale = params["enable_autoscale"]
    if params["max_nodes_num"] is not None:
        request.MaxNodesNum = params["max_nodes_num"]
    if params["min_nodes_num"] is not None:
        request.MinNodesNum = params["min_nodes_num"]
    if params["labels"]:
        request.Labels = _build_labels(models, params["labels"])
    if params["taints"]:
        request.Taints = _build_taints(models, params["taints"])
    if params["deletion_protection"] is not None:
        request.DeletionProtection = params["deletion_protection"]
    module.sdk_call(client.ModifyClusterNodePool, request)


def _delete(module, client, models, cluster_id, pool_id, keep_instance):
    request = models.DeleteClusterNodePoolRequest()
    request.ClusterId = cluster_id
    request.NodePoolIds = [pool_id]
    if keep_instance:
        request.KeepInstance = True
    module.sdk_call(client.DeleteClusterNodePool, request)


def _labels_to_dict(labels):
    """Convert the SDK label list to a sorted dict for comparison."""
    result = {}
    for item in labels or []:
        result[item.get("Name")] = str(item.get("Value"))
    return result


def _taints_to_list(taints):
    """Convert the SDK taint list to the user-facing dict form."""
    result = []
    for item in taints or []:
        result.append({
            "key": item.get("Key"),
            "value": item.get("Value"),
            "effect": item.get("Effect"),
        })
    return sorted(result, key=lambda t: (t.get("key") or "", t.get("effect") or ""))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
            "name": {"type": "str"},
            "launch_configuration_json": {"type": "str"},
            "autoscaling_group_json": {"type": "str"},
            "enable_autoscale": {"type": "bool"},
            "max_nodes_num": {"type": "int"},
            "min_nodes_num": {"type": "int"},
            "labels": {"type": "dict", "default": {}},
            "taints": {"type": "list", "elements": "dict", "default": []},
            "node_pool_os": {"type": "str"},
            "deletion_protection": {"type": "bool"},
            "keep_instance": {"type": "bool", "default": False},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    cluster_id = module.params["cluster_id"]
    name = module.params["name"]

    if not name:
        module.fail_json(msg="name is required to identify the node pool")

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")

    try:
        current = find_node_pool(module, client, models, cluster_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="TKE node pool already absent")
        pool_id = current["NodePoolId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete TKE node pool")
        _delete(module, client, models, cluster_id, pool_id, module.params["keep_instance"])
        module.exit_json(changed=True, **(diff or {}), node_pool=None, msg="TKE node pool deleted")

    # state == present
    if current is None:
        if not module.params["launch_configuration_json"]:
            module.fail_json(msg="launch_configuration_json is required when creating a node pool")
        desired = {"Name": name}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create TKE node pool")
        _create(module, client, models, module.params)
        current = find_node_pool(module, client, models, cluster_id, name)
        module.exit_json(changed=True, **(diff or {}), node_pool=current, msg="TKE node pool created")

    pool_id = current["NodePoolId"]
    drift = _pool_drift(module, current)
    if drift:
        diff = maybe_diff(
            module,
            {key: current.get(key) for key in drift},
            drift,
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update TKE node pool")
        _update(module, client, models, module.params, pool_id)
        updated = find_node_pool(module, client, models, cluster_id, name)
        module.exit_json(changed=True, **(diff or {}), node_pool=updated, msg="TKE node pool updated")

    module.exit_json(changed=False, node_pool=current, msg="TKE node pool is up to date")


def _pool_drift(module, current):
    """Return the enforced settings that differ from the current pool."""
    drift = {}
    if module.params["name"] and current.get("Name") != module.params["name"]:
        drift["Name"] = module.params["name"]
    if module.params["enable_autoscale"] is not None and current.get("EnableAutoscale") != module.params["enable_autoscale"]:
        drift["EnableAutoscale"] = module.params["enable_autoscale"]
    if module.params["max_nodes_num"] is not None and current.get("MaxNodesNum") != module.params["max_nodes_num"]:
        drift["MaxNodesNum"] = module.params["max_nodes_num"]
    if module.params["min_nodes_num"] is not None and current.get("MinNodesNum") != module.params["min_nodes_num"]:
        drift["MinNodesNum"] = module.params["min_nodes_num"]
    if module.params["labels"] and _labels_to_dict(current.get("Labels")) != _labels_to_dict(
        [{"Name": k, "Value": str(v)} for k, v in sorted(module.params["labels"].items())]
    ):
        drift["Labels"] = module.params["labels"]
    if module.params["taints"] and _taints_to_list(current.get("Taints")) != sorted(
        module.params["taints"], key=lambda t: (t.get("key") or "", t.get("effect") or "")
    ):
        drift["Taints"] = module.params["taints"]
    if module.params["deletion_protection"] is not None and current.get("DeletionProtection") != module.params["deletion_protection"]:
        drift["DeletionProtection"] = module.params["deletion_protection"]
    return drift


def main():
    run_module()


if __name__ == "__main__":
    main()
