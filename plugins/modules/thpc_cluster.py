#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: thpc_cluster
short_description: Manage Tencent Cloud THPC clusters
version_added: "0.14.0"
description:
  - Creates and deletes THPC clusters and reconciles deletion protection.
  - Node, image, network, scheduler and storage topology is immutable because THPC exposes no general cluster update API.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID.}
  name: {type: str, description: Cluster display name; immutable after creation.}
  zone: {type: str, description: Availability zone; immutable after creation.}
  manager_node: {type: dict, description: Manager-node configuration using snake_case THPC SDK fields.}
  manager_node_count: {type: int, description: Number of manager nodes; defaults to 1 during creation.}
  compute_node: {type: dict, description: Compute-node configuration using snake_case THPC SDK fields.}
  compute_node_count: {type: int, description: Number of initial compute nodes; defaults to 0 during creation.}
  login_node: {type: dict, description: Login-node configuration using snake_case THPC SDK fields.}
  login_node_count: {type: int, description: Number of login nodes; defaults to 0 during creation.}
  scheduler_type: {type: str, choices: [SLURM], description: Cluster scheduler type; defaults to SLURM during creation.}
  scheduler_version: {type: str, description: Scheduler version; defaults to latest during creation.}
  image_id: {type: str, description: Image used by cluster nodes; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  login_password: {type: str, description: Initial node login password.}
  login_key_ids: {type: list, elements: str, description: Initial node SSH key IDs.}
  security_group_ids: {type: list, elements: str, description: Initial security groups.}
  client_token: {type: str, description: Caller-provided idempotency token.}
  account_type: {type: str, description: Domain account service type; defaults to NIS during creation.}
  storage_option: {type: dict, description: "Initial CFS, GooseFS, GooseFSx or COS mount options using snake_case SDK fields."}
  tags: {type: dict, description: Tags applied during creation.}
  auto_scaling_type: {type: str, description: Elastic scaling implementation; defaults to THPC_AS during creation.}
  init_node_scripts: {type: list, elements: dict, description: Initial COS-backed node scripts with script_path and timeout.}
  hpc_cluster_id: {type: str, description: CVM high-performance cluster placement ID.}
  deletion_protection:
    type: bool
    description: Desired deletion protection. Must explicitly be false to delete a protected cluster.
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a SLURM cluster
  susunola.tencentcloud.thpc_cluster:
    name: production-hpc
    zone: ap-guangzhou-3
    image_id: img-xxxxxxxx
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    manager_node:
      instance_type: S5.LARGE8
      system_disk: {disk_type: CLOUD_PREMIUM, disk_size: 100}
    compute_node:
      instance_type: HCCPNV5.24XLARGE384
      instance_charge_type: POSTPAID_BY_HOUR
    compute_node_count: 2
    login_key_ids: [skey-xxxxxxxx]
    security_group_ids: [sg-xxxxxxxx]
    deletion_protection: true

- name: Explicitly disable protection and delete the cluster
  susunola.tencentcloud.thpc_cluster:
    cluster_id: x-xxxxxxxx
    state: absent
    deletion_protection: false
'''

RETURN = r'''
cluster:
  description: Effective THPC cluster overview.
  type: dict
  returned: always
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.thpc.v20230321 import models, thpc_client
    return models, thpc_client


def _api_key(value):
    acronyms = {"cfs": "CFS", "cos": "Cos", "fs": "FS", "hpc": "Hpc", "id": "Id", "ids": "Ids", "ip": "Ip", "ipv6": "Ipv6", "vpc": "Vpc"}
    return "".join(acronyms.get(part, part[:1].upper() + part[1:]) for part in value.split("_"))


def _api_value(value):
    if isinstance(value, dict):
        return {_api_key(str(key)): _api_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_api_value(item) for item in value]
    return value


def _model(models, class_name, value):
    if value is None:
        return None
    result = getattr(models, class_name)()
    result._deserialize(_api_value(value))
    return result


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.Key, item.Value = key, value
        result.append(item)
    return result


def describe_request(models, p, offset=0):
    request = models.DescribeClustersRequest()
    request.Offset, request.Limit = offset, 100
    request.ClusterIds = [p["cluster_id"]] if p.get("cluster_id") else None
    return request


def create_request(models, p):
    request = models.CreateClusterRequest()
    request.Placement = _model(models, "Placement", {"zone": p["zone"]})
    request.ManagerNode = _model(models, "ManagerNode", p["manager_node"])
    request.ManagerNodeCount = p.get("manager_node_count") if p.get("manager_node_count") is not None else 1
    request.ComputeNode = _model(models, "ComputeNode", p["compute_node"])
    request.ComputeNodeCount = p.get("compute_node_count") if p.get("compute_node_count") is not None else 0
    request.SchedulerType, request.SchedulerVersion = p.get("scheduler_type") or "SLURM", p.get("scheduler_version") or "latest"
    request.ImageId = p["image_id"]
    request.VirtualPrivateCloud = _model(models, "VirtualPrivateCloud", {"vpc_id": p["vpc_id"], "subnet_id": p["subnet_id"]})
    login_settings = {"password": p.get("login_password"), "key_ids": p.get("login_key_ids")}
    request.LoginSettings = _model(models, "LoginSettings", login_settings) if any(value is not None for value in login_settings.values()) else None
    request.SecurityGroupIds, request.ClientToken = p.get("security_group_ids"), p.get("client_token")
    request.AccountType, request.ClusterName = p.get("account_type") or "NIS", p["name"]
    request.StorageOption = _model(models, "StorageOption", p.get("storage_option"))
    request.LoginNode = _model(models, "LoginNode", p.get("login_node"))
    request.LoginNodeCount = p.get("login_node_count") if p.get("login_node_count") is not None else 0
    request.Tags, request.AutoScalingType = _tags(models, p.get("tags")), p.get("auto_scaling_type") or "THPC_AS"
    request.InitNodeScripts = [_model(models, "NodeScript", value) for value in p.get("init_node_scripts") or []]
    request.HpcClusterId = p.get("hpc_cluster_id")
    return request


def deletion_protection_request(models, cluster_id, enabled):
    request = models.ModifyClusterDeletionProtectionRequest()
    request.ClusterId = cluster_id
    request.DeletionProtection = "ON" if enabled else "OFF"
    return request


def delete_request(models, cluster_id):
    request = models.DeleteClusterRequest()
    request.ClusterId = cluster_id
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeClusters, describe_request(models, p, offset))
        items = response.ClusterSet or []
        for item in items:
            value = item._serialize(allow_none=True)
            if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p.get("name")):
                matches.append(value)
        offset += len(items)
        if p.get("cluster_id") or not items or offset >= (response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple THPC clusters matched; specify cluster_id")
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    def poll():
        current = find(module, client, models, p)
        status = str((current or {}).get("ClusterStatus", "ABSENT")).upper()
        if status == "INIT_FAILED":
            module.fail_json(msg="THPC cluster initialization failed", cluster=current)
        return status
    return wait_for_state(module, poll, states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {}, "name": {}, "zone": {},
        "manager_node": {"type": "dict"}, "manager_node_count": {"type": "int"},
        "compute_node": {"type": "dict"}, "compute_node_count": {"type": "int"},
        "login_node": {"type": "dict"}, "login_node_count": {"type": "int"},
        "scheduler_type": {"choices": ["SLURM"]}, "scheduler_version": {},
        "image_id": {}, "vpc_id": {}, "subnet_id": {}, "login_password": {"no_log": True},
        "login_key_ids": {"type": "list", "elements": "str", "no_log": False}, "security_group_ids": {"type": "list", "elements": "str"},
        "client_token": {"no_log": True}, "account_type": {}, "storage_option": {"type": "dict"},
        "tags": {"type": "dict"}, "auto_scaling_type": {},
        "init_node_scripts": {"type": "list", "elements": "dict"}, "hpc_cluster_id": {},
        "deletion_protection": {"type": "bool"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("cluster_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.ThpcClient, "thpc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            cluster_id = current["ClusterId"]
            protected = str(current.get("DeletionProtection", "OFF")).upper() == "ON"
            if protected and p.get("deletion_protection") is not False:
                module.fail_json(msg="THPC cluster deletion protection is enabled; set deletion_protection=false to authorize disabling it before deletion")
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                if protected:
                    module.sdk_call(client.ModifyClusterDeletionProtection, deletion_protection_request(models, cluster_id, False))
                module.sdk_call(client.DeleteCluster, delete_request(models, cluster_id))
                p["cluster_id"] = cluster_id
                _wait(module, client, models, p, ["ABSENT"])
            module.exit_json(changed=True, **(diff or {}), cluster=None)

        if not current:
            missing = [key for key in ("name", "zone", "manager_node", "compute_node", "image_id", "vpc_id", "subnet_id") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new THPC cluster", missing=missing)
            target = {"ClusterName": p["name"], "Placement": {"Zone": p["zone"]}, "SchedulerType": p.get("scheduler_type") or "SLURM", "SchedulerVersion": p.get("scheduler_version") or "latest", "ManagerNodeCount": p.get("manager_node_count") if p.get("manager_node_count") is not None else 1, "ComputeNodeCount": p.get("compute_node_count") if p.get("compute_node_count") is not None else 0, "LoginNodeCount": p.get("login_node_count") if p.get("login_node_count") is not None else 0, "VpcId": p["vpc_id"], "AutoScalingType": p.get("auto_scaling_type") or "THPC_AS", "DeletionProtection": "ON" if p.get("deletion_protection") else "OFF"}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["cluster_id"] = module.sdk_call(client.CreateCluster, create_request(models, p)).ClusterId
                _wait(module, client, models, p, ["RUNNING"])
                if p.get("deletion_protection"):
                    module.sdk_call(client.ModifyClusterDeletionProtection, deletion_protection_request(models, p["cluster_id"], True))
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)

        placement = current.get("Placement") or {}
        immutable = {
            "ClusterName": p.get("name"), "Zone": p.get("zone"), "SchedulerType": p.get("scheduler_type"),
            "SchedulerVersion": p.get("scheduler_version"), "ManagerNodeCount": p.get("manager_node_count"),
            "ComputeNodeCount": p.get("compute_node_count"), "LoginNodeCount": p.get("login_node_count"),
            "VpcId": p.get("vpc_id"), "AutoScalingType": p.get("auto_scaling_type"),
        }
        observed = dict(current)
        observed["Zone"] = placement.get("Zone")
        drift = {key: (observed.get(key), value) for key, value in immutable.items() if value is not None and observed.get(key) != value}
        if drift:
            module.fail_json(msg="THPC cluster topology fields are immutable", immutable_drift=drift)
        desired_protection = p.get("deletion_protection")
        current_protection = str(current.get("DeletionProtection", "OFF")).upper() == "ON"
        if desired_protection is None or desired_protection == current_protection:
            module.exit_json(changed=False, cluster=current)
        diff = maybe_diff(module, {"DeletionProtection": current_protection}, {"DeletionProtection": desired_protection})
        if not module.check_mode:
            module.sdk_call(client.ModifyClusterDeletionProtection, deletion_protection_request(models, current["ClusterId"], desired_protection))
            current["DeletionProtection"] = "ON" if desired_protection else "OFF"
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
