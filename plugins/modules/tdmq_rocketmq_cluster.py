#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rocketmq_cluster
short_description: Manage TDMQ RocketMQ clusters
version_added: "0.14.0"
description:
  - Creates, renames and deletes a standard RocketMQ cluster.
  - Use C(cluster_id) for stable identity when changing C(name).
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing cluster ID; required for unambiguous rename and preferred for deletion.}
  name: {type: str, required: true, description: Cluster name.}
  remark: {type: str, default: '', description: Cluster remark.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rocketmq_cluster:
    name: application-messaging
    remark: Shared application cluster

- susunola.tencentcloud.tdmq_rocketmq_cluster:
    cluster_id: rocketmq-xxxxxxxx
    name: application-messaging-v2
'''
RETURN = r'''cluster: {description: RocketMQ cluster metadata with credential fields removed., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


SENSITIVE_FIELDS = ("AdminAccessKey", "AdminSecretKey")


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRocketMQClustersRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("cluster_id"): request.ClusterIdList = [p["cluster_id"]]
    else: request.NameKeyword = p["name"]
    return request


def create_request(models, p):
    request = models.CreateRocketMQClusterRequest(); request.Name, request.Remark = p["name"], p["remark"]; return request


def update_request(models, p, cluster_id):
    request = models.ModifyRocketMQClusterRequest(); request.ClusterId, request.ClusterName, request.Remark = cluster_id, p["name"], p["remark"]; return request


def delete_request(models, cluster_id):
    request = models.DeleteRocketMQClusterRequest(); request.ClusterId = cluster_id; return request


def sanitize(value):
    return {key: item for key, item in (value or {}).items() if key not in SENSITIVE_FIELDS}


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRocketMQClusters, describe_request(models, p, offset)); items = list(response.ClusterList or [])
        matches = []
        for item in items:
            raw = item._serialize(allow_none=True); value = sanitize(raw.get("Info") or {})
            if (p.get("cluster_id") and value.get("ClusterId") == p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName") == p["name"]):
                value["Status"] = raw.get("Status"); matches.append(value)
        if matches:
            if len(matches) > 1: module.fail_json(msg="multiple RocketMQ clusters matched name; specify cluster_id")
            return matches[0]
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def comparable(value):
    return {"ClusterName": value.get("ClusterName"), "Remark": value.get("Remark") or ""}


def desired(p):
    return {"ClusterName": p["name"], "Remark": p["remark"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "cluster_id": {}, "name": {"required": True}, "remark": {"default": ""}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, cluster=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRocketMQCluster, delete_request(models, current["ClusterId"]))
            module.exit_json(changed=True, **(diff or {}), cluster=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, cluster=current)
        diff = maybe_diff(module, before, target)
        if not current and p.get("cluster_id"):
            module.fail_json(msg="RocketMQ cluster_id was not found; omit cluster_id to create a new cluster")
        if current and before["ClusterName"] != target["ClusterName"] and not p.get("cluster_id"):
            module.fail_json(msg="cluster_id is required to rename a RocketMQ cluster")
        if not module.check_mode:
            if current: module.sdk_call(client.ModifyRocketMQCluster, update_request(models, p, current["ClusterId"]))
            else: module.sdk_call(client.CreateRocketMQCluster, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), cluster=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
