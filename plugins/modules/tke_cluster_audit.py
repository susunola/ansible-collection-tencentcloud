#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tke_cluster_audit
short_description: Manage Tencent Cloud TKE cluster audit logging
version_added: "0.14.0"
description: Enables or disables Kubernetes audit logging to a CLS topic.
options:
  state: {type: str, choices: [enabled, disabled], default: enabled, description: Desired audit state.}
  cluster_id: {type: str, required: true, description: TKE cluster ID.}
  logset_id: {type: str, description: Destination CLS logset ID.}
  topic_id: {type: str, description: Destination CLS topic ID.}
  topic_region: {type: str, description: Region of the CLS topic.}
  delete_logset_and_topic: {type: bool, default: false, description: Delete automatically created CLS resources when disabling.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tke_cluster_audit:
    cluster_id: cls-xxxxxxxx
    logset_id: logset-xxxxxxxx
    topic_id: topic-xxxxxxxx
    topic_region: ap-guangzhou
'''
RETURN = r'''audit: {description: Effective audit switch metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client
def build_describe(models, cluster_id): request = models.DescribeLogSwitchesRequest(); request.ClusterIds, request.ClusterType = [cluster_id], "tke"; return request
def build_enable(models, p): request = models.EnableClusterAuditRequest(); request.ClusterId, request.LogsetId, request.TopicId, request.TopicRegion = p["cluster_id"], p["logset_id"], p["topic_id"], p.get("topic_region"); return request
def build_disable(models, p): request = models.DisableClusterAuditRequest(); request.ClusterId, request.DeleteLogSetAndTopic = p["cluster_id"], p["delete_logset_and_topic"]; return request


def find(module, client, models, cluster_id):
    response = module.sdk_call(client.DescribeLogSwitches, build_describe(models, cluster_id)); items = list(response.SwitchSet or [])
    if not items: return {"Enable": False}
    return items[0]._serialize(allow_none=True)


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["enabled", "disabled"], "default": "enabled"}, "cluster_id": {"required": True}, "logset_id": {}, "topic_id": {}, "topic_region": {}, "delete_logset_and_topic": {"type": "bool", "default": False}}, required_if=[("state", "enabled", ["logset_id", "topic_id"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["cluster_id"]); enabled = bool(current.get("Enable")); target_enabled = p["state"] == "enabled"
        if enabled == target_enabled: module.exit_json(changed=False, audit=current)
        target = {"Enable": target_enabled, "LogsetId": p.get("logset_id"), "TopicId": p.get("topic_id"), "TopicRegion": p.get("topic_region")}; diff = maybe_diff(module, current, target)
        if not module.check_mode: module.sdk_call(client.EnableClusterAudit if target_enabled else client.DisableClusterAudit, build_enable(models, p) if target_enabled else build_disable(models, p)); current = find(module, client, models, p["cluster_id"])
        module.exit_json(changed=True, **(diff or {}), audit=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
