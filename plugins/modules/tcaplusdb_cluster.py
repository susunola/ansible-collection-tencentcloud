#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcaplusdb_cluster
short_description: Manage Tencent Cloud TcaplusDB clusters
version_added: "0.14.0"
description: Creates, renames, rotates credentials for and deletes TcaplusDB clusters, including optional server and proxy topology.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - Existing cluster ID.
    type: str
  name:
    description:
      - Cluster name.
    type: str
  idl_type:
    description:
      - Interface definition language type; immutable after creation.
    type: str
    choices: [TDR, PROTO]
    default: TDR
  vpc_id:
    description:
      - VPC ID; immutable after creation.
    type: str
  subnet_id:
    description:
      - Subnet ID; immutable after creation.
    type: str
  password:
    description:
      - Password required during creation and as the old credential during rotation.
    type: str
  new_password:
    description:
      - New password to rotate to on an existing cluster.
    type: str
  rotate_password:
    description:
      - Explicitly request password rotation on this run.
    type: bool
    default: false
  old_password_expire_time:
    description:
      - API-formatted expiration time for the old password.
    type: str
  cluster_type:
    description:
      - Cluster type; immutable after creation.
    type: int
  auth_type:
    description:
      - Authentication type; immutable after creation.
    type: int
  ipv6:
    description:
      - Enable IPv6 during creation.
    type: bool
    default: false
  servers:
    type: list
    elements: dict
    description: Initial storage server topology.
    suboptions:
      server_uid:
        description:
          - Server resource UID.
        type: str
        required: true
      machine_type:
        description:
          - Server machine type.
        type: str
        required: true
  proxies:
    type: list
    elements: dict
    description: Initial proxy topology.
    suboptions:
      proxy_uid:
        description:
          - Proxy resource UID.
        type: str
        required: true
      machine_type:
        description:
          - Proxy machine type.
        type: str
        required: true
      available_count:
        description:
          - Proxy count.
        type: int
        required: true
  tags:
    description:
      - Tags applied during creation.
    type: dict
    default: {}

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
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tcaplusdb_cluster_info
    description: Gather information about Tencent Cloud TCAPLUSDB clusters.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcaplusdb_cluster:
    name: production-tcaplus
    idl_type: TDR
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    password: "{{ vault_tcaplus_password }}"

- name: Delete the cluster
  susunola.tencentcloud.tcaplusdb_cluster:
    state: absent
    name: production-tcaplus
"""
RETURN = r"""cluster:
  description:
    - Effective TcaplusDB cluster metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    ClusterId: cluster-1a2b3c4d
    ClusterName: renamed-tcaplus
    IdlType: TDR
    VpcId: vpc-1111
    SubnetId: subnet-2222
    ClusterStatus: 1
    ClusterType: 1
    Password: old-secret
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tcaplusdb.v20190823 import models, tcaplusdb_client

    return models, tcaplusdb_client


def describe_request(models, p, offset=0):
    r = models.DescribeClustersRequest()
    r.Offset, r.Limit = offset, 100
    r.ClusterIds = [p["cluster_id"]] if p.get("cluster_id") else None
    if not p.get("cluster_id") and p.get("name"):
        f = models.Filter()
        f.Name, f.Values = "ClusterName", [p["name"]]
        r.Filters = [f]
    return r


def _servers(models, values):
    result = []
    for value in values or []:
        item = models.ServerMachineInfo()
        item.ServerUid, item.MachineType = value["server_uid"], value["machine_type"]
        result.append(item)
    return result


def _proxies(models, values):
    result = []
    for value in values or []:
        item = models.ProxyMachineInfo()
        item.ProxyUid, item.MachineType, item.AvailableCount = value["proxy_uid"], value["machine_type"], value["available_count"]
        result.append(item)
    return result


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.TagInfoUnit()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def create_request(models, p):
    r = models.CreateClusterRequest()
    r.IdlType, r.ClusterName, r.VpcId, r.SubnetId, r.Password = p["idl_type"], p["name"], p["vpc_id"], p["subnet_id"], p["password"]
    r.Ipv6Enable, r.ClusterType, r.AuthType = 1 if p["ipv6"] else 0, p.get("cluster_type"), p.get("auth_type")
    r.ServerList, r.ProxyList, r.ResourceTags = _servers(models, p.get("servers")), _proxies(models, p.get("proxies")), _tags(models, p["tags"])
    return r


def rename_request(models, cluster_id, name):
    r = models.ModifyClusterNameRequest()
    r.ClusterId, r.ClusterName = cluster_id, name
    return r


def password_request(models, p, cluster_id):
    r = models.ModifyClusterPasswordRequest()
    r.ClusterId, r.OldPassword, r.NewPassword = cluster_id, p["password"], p["new_password"]
    r.OldPasswordExpireTime, r.Mode = p.get("old_password_expire_time"), "update"
    return r


def delete_request(models, cluster_id):
    r = models.DeleteClusterRequest()
    r.ClusterId = cluster_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeClusters, describe_request(models, p))
    matches = []
    for item in response.Clusters or []:
        value = item._serialize(allow_none=True)
        if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TcaplusDB clusters matched; specify cluster_id")
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: (find(module, client, models, p) or {}).get("ClusterStatus"),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "cluster_id": {},
        "name": {},
        "idl_type": {"choices": ["TDR", "PROTO"], "default": "TDR"},
        "vpc_id": {},
        "subnet_id": {},
        "password": {"no_log": True},
        "new_password": {"no_log": True},
        "rotate_password": {"type": "bool", "default": False},
        "old_password_expire_time": {"no_log": False},
        "cluster_type": {"type": "int"},
        "auth_type": {"type": "int"},
        "ipv6": {"type": "bool", "default": False},
        "servers": {"type": "list", "elements": "dict", "options": {"server_uid": {"required": True}, "machine_type": {"required": True}}},
        "proxies": {
            "type": "list",
            "elements": "dict",
            "options": {"proxy_uid": {"required": True}, "machine_type": {"required": True}, "available_count": {"type": "int", "required": True}},
        },
        "tags": {"type": "dict", "default": {}},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("cluster_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcaplusdbClient, "tcaplusdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCluster, delete_request(models, current["ClusterId"]))
            module.exit_json(changed=True, **(diff or {}), cluster=None)
        if not current:
            missing = [k for k in ("name", "vpc_id", "subnet_id", "password") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new TcaplusDB cluster", missing=missing)
            target = {
                "ClusterName": p["name"],
                "IdlType": p["idl_type"],
                "VpcId": p["vpc_id"],
                "SubnetId": p["subnet_id"],
                "ClusterType": p.get("cluster_type"),
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["cluster_id"] = module.sdk_call(client.CreateCluster, create_request(models, p)).ClusterId
                _wait(module, client, models, p, [1])
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), cluster=current if not module.check_mode else target)
        immutable = {"IdlType": p.get("idl_type"), "VpcId": p.get("vpc_id"), "SubnetId": p.get("subnet_id"), "ClusterType": p.get("cluster_type")}
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift:
            module.fail_json(msg="TcaplusDB network, IDL and cluster type are immutable", immutable_drift=drift)
        rename = p.get("name") is not None and p["name"] != current.get("ClusterName")
        rotate = p["rotate_password"]
        if not rename and not rotate:
            module.exit_json(changed=False, cluster=current)
        if rotate and (not p.get("password") or not p.get("new_password")):
            module.fail_json(msg="password and new_password are required when rotate_password is true")
        desired = dict(current)
        desired["ClusterName"] = p.get("name") or current.get("ClusterName")
        desired["PasswordRotationRequested"] = rotate
        diff = maybe_diff(module, current, desired)
        cluster_id = current["ClusterId"]
        if not module.check_mode:
            if rename:
                module.sdk_call(client.ModifyClusterName, rename_request(models, cluster_id, p["name"]))
            if rotate:
                module.sdk_call(client.ModifyClusterPassword, password_request(models, p, cluster_id))
            p["cluster_id"] = cluster_id
            _wait(module, client, models, p, [1])
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
