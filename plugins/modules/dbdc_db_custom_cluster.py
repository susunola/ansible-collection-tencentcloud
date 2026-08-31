#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dbdc_db_custom_cluster
short_description: Manage Tencent Cloud DB Custom clusters
version_added: "0.14.0"
description: Creates and destroys DB Custom clusters and reconciles exact node membership, tags and deletion protection.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing DB Custom cluster ID.}
  name: {type: str, description: Cluster name; immutable after creation.}
  description: {type: str, description: Cluster description; immutable after creation.}
  container_vpc_id: {type: str, description: Container-network VPC ID; immutable after creation.}
  container_subnet_ids: {type: list, elements: str, description: Container-network subnet IDs; immutable after creation.}
  api_server_vpc_id: {type: str, description: API-server VPC ID; immutable after creation.}
  api_server_subnet_id: {type: str, description: API-server subnet ID; immutable after creation.}
  deletion_protection: {type: bool, description: Desired deletion protection; defaults to true during creation and must explicitly be false before deletion.}
  tags: {type: dict, description: Exact desired cluster tags.}
  client_token: {type: str, description: Caller-provided creation idempotency token.}
  node_ids: {type: list, elements: str, description: Exact desired set of existing DB Custom node IDs attached to the cluster.}
  node_image_id: {type: str, description: Image applied when attaching nodes.}
  login_password: {type: str, description: Node login password used during attach or detach.}
  login_key_id: {type: str, description: Single SSH key ID used during attach or detach.}
  keep_image_login: {type: bool, description: Preserve image login settings during attach or detach.}
  labels: {type: dict, description: Initial Kubernetes labels for newly attached nodes.}
  taints:
    type: list
    elements: dict
    description: Initial Kubernetes taints for newly attached nodes.
    suboptions:
      key: {type: str, required: true, description: Taint key.}
      value: {type: str, description: Optional taint value.}
      effect: {type: str, required: true, choices: [NoSchedule, PreferNoSchedule, NoExecute], description: Scheduling effect.}
  host_name: {type: str, description: Host-name pattern for newly attached nodes.}
  host_name_type: {type: int, choices: [0, 1, 2], description: "Reuse, explicitly set or automatically assign host names."}
  allow_node_removal: {type: bool, default: false, description: Authorize removal when node_ids omits currently attached nodes.}
  force_node_removal: {type: bool, default: false, description: Force removal even when business pods are running.}
  remove_nodes_on_delete: {type: bool, default: false, description: Authorize detaching every node before cluster destruction.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dbdc_db_custom_cluster:
    name: production-db-custom
    container_vpc_id: vpc-xxxxxxxx
    container_subnet_ids: [subnet-aaaaaaaa, subnet-bbbbbbbb]
    api_server_vpc_id: vpc-xxxxxxxx
    api_server_subnet_id: subnet-aaaaaaaa
    deletion_protection: true
    tags: {environment: production}

- name: Attach an exact node set
  susunola.tencentcloud.dbdc_db_custom_cluster:
    cluster_id: dbcc-xxxxxxxx
    node_ids: [dbcn-aaaaaaaa, dbcn-bbbbbbbb]
    node_image_id: img-xxxxxxxx
    login_key_id: skey-xxxxxxxx
"""
RETURN = r"""cluster: {description: Effective DB Custom cluster detail including attached nodes., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state, wait_for_task


def _load():
    from tencentcloud.dbdc.v20201029 import models, dbdc_client

    return models, dbdc_client


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.Key, item.Value = key, value
        result.append(item)
    return result


def _login(models, p):
    if p.get("login_password") is None and p.get("login_key_id") is None and p.get("keep_image_login") is None:
        return None
    item = models.LoginSettings()
    item.Password = p.get("login_password")
    item.KeyIds = [p["login_key_id"]] if p.get("login_key_id") else None
    item.KeepImageLogin = "true" if p.get("keep_image_login") else None
    return item


def _labels(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Label()
        item.Key, item.Value = key, value
        result.append(item)
    return result


def _taints(models, values):
    result = []
    for value in values or []:
        item = models.Taint()
        item.Key, item.Value, item.Effect = value["key"], value.get("value"), value["effect"]
        result.append(item)
    return result


def describe_request(models, p, offset=0):
    r = models.DescribeDBCustomClustersRequest()
    r.Offset, r.Limit = offset, 100
    r.ClusterIds = [p["cluster_id"]] if p.get("cluster_id") else None
    if not p.get("cluster_id") and p.get("name"):
        f = models.Filter()
        f.Name, f.Values = "cluster-name", [p["name"]]
        r.Filters = [f]
    return r


def detail_request(models, cluster_id):
    r = models.DescribeDBCustomClusterDetailRequest()
    r.ClusterId = cluster_id
    return r


def nodes_request(models, cluster_id, offset=0):
    r = models.DescribeDBCustomClusterNodesRequest()
    r.ClusterId, r.Offset, r.Limit = cluster_id, offset, 100
    return r


def task_request(models, task_id):
    r = models.DescribeDBCustomTaskStatusRequest()
    r.TaskId = task_id
    return r


def create_request(models, p):
    r = models.CreateDBCustomClusterRequest()
    r.ClusterName, r.ClusterDescription = p["name"], p.get("description")
    r.ContainerNetwork = models.ContainerNetwork()
    r.ContainerNetwork.VpcId, r.ContainerNetwork.SubnetIds = p["container_vpc_id"], p["container_subnet_ids"]
    r.ApiServerNetwork = models.ApiServerNetwork()
    r.ApiServerNetwork.VpcId, r.ApiServerNetwork.SubnetId = p["api_server_vpc_id"], p["api_server_subnet_id"]
    r.Tags, r.ClientToken = _tags(models, p.get("tags")), p.get("client_token")
    r.DeletionProtection = p["deletion_protection"] if p.get("deletion_protection") is not None else True
    return r


def attributes_request(models, cluster_id, protection):
    r = models.ModifyDBCustomClusterAttributesRequest()
    r.ClusterId, r.DeletionProtection = cluster_id, protection
    return r


def tags_request(models, cluster_id, add, remove):
    r = models.ModifyDBCustomClusterTagsRequest()
    r.ClusterId, r.AddTags, r.DeleteTagKeys = cluster_id, _tags(models, add), sorted(remove)
    return r


def add_nodes_request(models, p, cluster_id, node_ids):
    r = models.AddNodesToDBCustomClusterRequest()
    r.ClusterId, r.NodeIds, r.ImageId = cluster_id, sorted(node_ids), p["node_image_id"]
    r.LoginSettings = _login(models, p)
    r.Labels, r.Taints = _labels(models, p.get("labels")), _taints(models, p.get("taints"))
    r.HostName, r.HostNameType = p.get("host_name"), p.get("host_name_type")
    return r


def remove_nodes_request(models, p, cluster_id, node_ids):
    r = models.RemoveNodesFromDBCustomClusterRequest()
    r.ClusterId, r.NodeIds, r.LoginSettings, r.Force = cluster_id, sorted(node_ids), _login(models, p), p["force_node_removal"]
    return r


def destroy_request(models, cluster_id):
    r = models.DestroyDBCustomClusterRequest()
    r.ClusterId = cluster_id
    return r


def _node_set(module, client, models, cluster_id):
    offset, result = 0, []
    while True:
        response = module.sdk_call(client.DescribeDBCustomClusterNodes, nodes_request(models, cluster_id, offset))
        items = response.NodeSet or []
        result.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if not items or offset >= (response.TotalCount or 0):
            return result


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDBCustomClusters, describe_request(models, p))
    matches = []
    for item in response.ClusterSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple DB Custom clusters matched; specify cluster_id")
    if matches:
        detail = module.sdk_call(client.DescribeDBCustomClusterDetail, detail_request(models, matches[0]["ClusterId"]))._serialize(allow_none=True)
        detail.pop("RequestId", None)
        matches[0].update(detail)
        matches[0]["Nodes"] = _node_set(module, client, models, matches[0]["ClusterId"])
    return matches[0] if matches else None


def _wait_task(module, client, models, task_id):
    def poll():
        response = module.sdk_call(client.DescribeDBCustomTaskStatus, task_request(models, task_id))
        return response.Status, None, response

    return wait_for_task(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
        success_statuses=("Succeeded",),
        failure_statuses=("Failed",),
    )


def _wait_cluster(module, client, models, p, states):
    return wait_for_state(
        module,
        lambda: str((find(module, client, models, p) or {}).get("ClusterStatus", "Absent")),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _tag_dict(values):
    return {item.get("Key"): item.get("Value") for item in values or []}


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "cluster_id": {},
        "name": {},
        "description": {},
        "container_vpc_id": {},
        "container_subnet_ids": {"type": "list", "elements": "str"},
        "api_server_vpc_id": {},
        "api_server_subnet_id": {},
        "deletion_protection": {"type": "bool"},
        "tags": {"type": "dict"},
        "client_token": {"no_log": True},
        "node_ids": {"type": "list", "elements": "str"},
        "node_image_id": {},
        "login_password": {"no_log": True},
        "login_key_id": {"no_log": False},
        "keep_image_login": {"type": "bool"},
        "labels": {"type": "dict"},
        "taints": {
            "type": "list",
            "elements": "dict",
            "options": {
                "key": {"required": True, "no_log": False},
                "value": {},
                "effect": {"required": True, "choices": ["NoSchedule", "PreferNoSchedule", "NoExecute"]},
            },
        },
        "host_name": {},
        "host_name_type": {"type": "int", "choices": [0, 1, 2]},
        "allow_node_removal": {"type": "bool", "default": False},
        "force_node_removal": {"type": "bool", "default": False},
        "remove_nodes_on_delete": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(
        argument_spec=spec,
        required_one_of=[("cluster_id", "name")],
        mutually_exclusive=[("login_password", "login_key_id", "keep_image_login")],
        required_if=[("host_name_type", 1, ["host_name"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DbdcClient, "dbdc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            if current.get("DeletionProtection") and p.get("deletion_protection") is not False:
                module.fail_json(msg="DB Custom deletion protection is enabled; set deletion_protection=false to authorize disabling it")
            nodes = [node["NodeId"] for node in current.get("Nodes") or []]
            if nodes and not p["remove_nodes_on_delete"]:
                module.fail_json(
                    msg="DB Custom cluster must have no nodes before destruction; set remove_nodes_on_delete=true to authorize detaching them", node_ids=nodes
                )
            if nodes and _login(models, p) is None:
                module.fail_json(msg="node login settings are required to detach nodes before cluster destruction")
            diff = maybe_diff(module, current, None)
            cluster_id = current["ClusterId"]
            if not module.check_mode:
                if nodes:
                    _wait_task(
                        module,
                        client,
                        models,
                        module.sdk_call(client.RemoveNodesFromDBCustomCluster, remove_nodes_request(models, p, cluster_id, nodes)).TaskId,
                    )
                if current.get("DeletionProtection"):
                    module.sdk_call(client.ModifyDBCustomClusterAttributes, attributes_request(models, cluster_id, False))
                _wait_task(module, client, models, module.sdk_call(client.DestroyDBCustomCluster, destroy_request(models, cluster_id)).TaskId)
                p["cluster_id"] = cluster_id
                _wait_cluster(module, client, models, p, ["Absent"])
            module.exit_json(changed=True, **(diff or {}), cluster=None)
        if not current:
            missing = [key for key in ("name", "container_vpc_id", "container_subnet_ids", "api_server_vpc_id", "api_server_subnet_id") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new DB Custom cluster", missing=missing)
            target = {
                "ClusterName": p["name"],
                "ClusterDescription": p.get("description"),
                "ContainerNetwork": {"VpcId": p["container_vpc_id"], "SubnetIds": p["container_subnet_ids"]},
                "ApiServerNetwork": {"VpcId": p["api_server_vpc_id"], "SubnetId": p["api_server_subnet_id"]},
                "DeletionProtection": p["deletion_protection"] if p.get("deletion_protection") is not None else True,
                "Tags": p.get("tags") or {},
                "Nodes": [],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateDBCustomCluster, create_request(models, p))
                p["cluster_id"] = response.ClusterId
                _wait_task(module, client, models, response.TaskId)
                _wait_cluster(module, client, models, p, ["Running"])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        container, api = current.get("ContainerNetwork") or {}, current.get("ApiServerNetwork") or {}
        immutable = {
            "ClusterName": p.get("name"),
            "ClusterDescription": p.get("description"),
            "ContainerVpcId": p.get("container_vpc_id"),
            "ContainerSubnetIds": sorted(p["container_subnet_ids"]) if p.get("container_subnet_ids") is not None else None,
            "ApiServerVpcId": p.get("api_server_vpc_id"),
            "ApiServerSubnetId": p.get("api_server_subnet_id"),
        }
        observed = {
            "ClusterName": current.get("ClusterName"),
            "ClusterDescription": current.get("ClusterDescription"),
            "ContainerVpcId": container.get("VpcId"),
            "ContainerSubnetIds": sorted(container.get("SubnetIds") or []),
            "ApiServerVpcId": api.get("VpcId"),
            "ApiServerSubnetId": api.get("SubnetId"),
        }
        drift = {key: (observed.get(key), value) for key, value in immutable.items() if value is not None and observed.get(key) != value}
        if drift:
            module.fail_json(msg="DB Custom cluster identity and network fields are immutable", immutable_drift=drift)
        cluster_id = current["ClusterId"]
        current_tags = _tag_dict(current.get("Tags"))
        desired_tags = p.get("tags") if p.get("tags") is not None else current_tags
        current_nodes = {node["NodeId"] for node in current.get("Nodes") or []}
        desired_nodes = set(p["node_ids"]) if p.get("node_ids") is not None else current_nodes
        to_add, to_remove = desired_nodes - current_nodes, current_nodes - desired_nodes
        if to_add and (not p.get("node_image_id") or _login(models, p) is None):
            module.fail_json(msg="node_image_id and one node login method are required to attach nodes", node_ids=sorted(to_add))
        if to_remove and not p["allow_node_removal"]:
            module.fail_json(msg="set allow_node_removal=true to authorize detaching nodes", node_ids=sorted(to_remove))
        protection = p.get("deletion_protection") if p.get("deletion_protection") is not None else current.get("DeletionProtection")
        before = {"DeletionProtection": current.get("DeletionProtection"), "Tags": current_tags, "NodeIds": sorted(current_nodes)}
        desired = {"DeletionProtection": protection, "Tags": desired_tags, "NodeIds": sorted(desired_nodes)}
        if before == desired:
            module.exit_json(changed=False, cluster=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if current.get("DeletionProtection") != protection:
                module.sdk_call(client.ModifyDBCustomClusterAttributes, attributes_request(models, cluster_id, protection))
            if current_tags != desired_tags:
                add = {key: value for key, value in desired_tags.items() if current_tags.get(key) != value}
                remove = set(current_tags) - set(desired_tags)
                module.sdk_call(client.ModifyDBCustomClusterTags, tags_request(models, cluster_id, add, remove))
            if to_add:
                _wait_task(module, client, models, module.sdk_call(client.AddNodesToDBCustomCluster, add_nodes_request(models, p, cluster_id, to_add)).TaskId)
            if to_remove:
                _wait_task(
                    module,
                    client,
                    models,
                    module.sdk_call(client.RemoveNodesFromDBCustomCluster, remove_nodes_request(models, p, cluster_id, to_remove)).TaskId,
                )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
