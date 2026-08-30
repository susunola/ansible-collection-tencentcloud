#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tcaplusdb_cluster
short_description: Manage Tencent Cloud TcaplusDB clusters
version_added: "0.14.0"
description: Creates, renames, rotates credentials for and deletes TcaplusDB clusters, including optional server and proxy topology.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID.}
  name: {type: str, description: Cluster name.}
  idl_type: {type: str, choices: [TDR, PROTO], default: TDR, description: Interface definition language type; immutable after creation.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  password: {type: str, description: Password required during creation and as the old credential during rotation.}
  new_password: {type: str, description: New password to rotate to on an existing cluster.}
  rotate_password: {type: bool, default: false, description: Explicitly request password rotation on this run.}
  old_password_expire_time: {type: str, description: API-formatted expiration time for the old password.}
  cluster_type: {type: int, description: Cluster type; immutable after creation.}
  auth_type: {type: int, description: Authentication type; immutable after creation.}
  ipv6: {type: bool, default: false, description: Enable IPv6 during creation.}
  servers:
    type: list
    elements: dict
    description: Initial storage server topology.
    suboptions:
      server_uid: {type: str, required: true, description: Server resource UID.}
      machine_type: {type: str, required: true, description: Server machine type.}
  proxies:
    type: list
    elements: dict
    description: Initial proxy topology.
    suboptions:
      proxy_uid: {type: str, required: true, description: Proxy resource UID.}
      machine_type: {type: str, required: true, description: Proxy machine type.}
      available_count: {type: int, required: true, description: Proxy count.}
  tags: {type: dict, default: {}, description: Tags applied during creation.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tcaplusdb_cluster:
    name: production-tcaplus
    idl_type: TDR
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    password: "{{ vault_tcaplus_password }}"
'''
RETURN = r'''cluster: {description: Effective TcaplusDB cluster metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tcaplusdb.v20190823 import models, tcaplusdb_client
    return models, tcaplusdb_client
def describe_request(models, p, offset=0):
    r = models.DescribeClustersRequest(); r.Offset, r.Limit = offset, 100; r.ClusterIds = [p["cluster_id"]] if p.get("cluster_id") else None
    if not p.get("cluster_id") and p.get("name"):
        f = models.Filter(); f.Name, f.Values = "ClusterName", [p["name"]]; r.Filters = [f]
    return r
def _servers(models, values):
    result = []
    for value in values or []:
        item = models.ServerMachineInfo(); item.ServerUid, item.MachineType = value["server_uid"], value["machine_type"]; result.append(item)
    return result
def _proxies(models, values):
    result = []
    for value in values or []:
        item = models.ProxyMachineInfo(); item.ProxyUid, item.MachineType, item.AvailableCount = value["proxy_uid"], value["machine_type"], value["available_count"]; result.append(item)
    return result
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.TagInfoUnit(); item.TagKey, item.TagValue = key, value; result.append(item)
    return result
def create_request(models, p):
    r = models.CreateClusterRequest(); r.IdlType, r.ClusterName, r.VpcId, r.SubnetId, r.Password = p["idl_type"], p["name"], p["vpc_id"], p["subnet_id"], p["password"]
    r.Ipv6Enable, r.ClusterType, r.AuthType = 1 if p["ipv6"] else 0, p.get("cluster_type"), p.get("auth_type")
    r.ServerList, r.ProxyList, r.ResourceTags = _servers(models, p.get("servers")), _proxies(models, p.get("proxies")), _tags(models, p["tags"]); return r
def rename_request(models, cluster_id, name):
    r = models.ModifyClusterNameRequest(); r.ClusterId, r.ClusterName = cluster_id, name; return r
def password_request(models, p, cluster_id):
    r = models.ModifyClusterPasswordRequest(); r.ClusterId, r.OldPassword, r.NewPassword = cluster_id, p["password"], p["new_password"]
    r.OldPasswordExpireTime, r.Mode = p.get("old_password_expire_time"), "update"; return r
def delete_request(models, cluster_id):
    r = models.DeleteClusterRequest(); r.ClusterId = cluster_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeClusters, describe_request(models, p)); matches = []
    for item in response.Clusters or []:
        value = item._serialize(allow_none=True)
        if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple TcaplusDB clusters matched; specify cluster_id")
    return matches[0] if matches else None
def _wait(module, client, models, p, states):
    wait_for_state(module, lambda: (find(module, client, models, p) or {}).get("ClusterStatus"), states, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {}, "name": {}, "idl_type": {"choices": ["TDR", "PROTO"], "default": "TDR"}, "vpc_id": {}, "subnet_id": {}, "password": {"no_log": True}, "new_password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "old_password_expire_time": {"no_log": False}, "cluster_type": {"type": "int"}, "auth_type": {"type": "int"}, "ipv6": {"type": "bool", "default": False}, "servers": {"type": "list", "elements": "dict", "options": {"server_uid": {"required": True}, "machine_type": {"required": True}}}, "proxies": {"type": "list", "elements": "dict", "options": {"proxy_uid": {"required": True}, "machine_type": {"required": True}, "available_count": {"type": "int", "required": True}}}, "tags": {"type": "dict", "default": {}}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("cluster_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TcaplusdbClient, "tcaplusdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, cluster=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteCluster, delete_request(models, current["ClusterId"]))
            module.exit_json(changed=True, **(diff or {}), cluster=None)
        if not current:
            missing = [k for k in ("name", "vpc_id", "subnet_id", "password") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new TcaplusDB cluster", missing=missing)
            target = {"ClusterName": p["name"], "IdlType": p["idl_type"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "ClusterType": p.get("cluster_type")}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["cluster_id"] = module.sdk_call(client.CreateCluster, create_request(models, p)).ClusterId; _wait(module, client, models, p, [1]); current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        immutable = {"IdlType": p.get("idl_type"), "VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "ClusterType": p.get("cluster_type")}; drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift: module.fail_json(msg="TcaplusDB network, IDL and cluster type are immutable", immutable_drift=drift)
        rename = p.get("name") is not None and p["name"] != current.get("ClusterName"); rotate = p["rotate_password"]
        if not rename and not rotate: module.exit_json(changed=False, cluster=current)
        if rotate and (not p.get("password") or not p.get("new_password")): module.fail_json(msg="password and new_password are required when rotate_password is true")
        desired = dict(current); desired["ClusterName"] = p.get("name") or current.get("ClusterName"); desired["PasswordRotationRequested"] = rotate; diff = maybe_diff(module, current, desired); cluster_id = current["ClusterId"]
        if not module.check_mode:
            if rename: module.sdk_call(client.ModifyClusterName, rename_request(models, cluster_id, p["name"]))
            if rotate: module.sdk_call(client.ModifyClusterPassword, password_request(models, p, cluster_id))
            p["cluster_id"] = cluster_id; _wait(module, client, models, p, [1]); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
