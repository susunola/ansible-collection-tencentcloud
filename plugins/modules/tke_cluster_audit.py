#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tke_cluster_audit
short_description: Manage Tencent Cloud TKE cluster audit logging
version_added: "0.14.0"
description: Enables or disables Kubernetes audit logging to a CLS topic.
options:
  state:
    description:
      - Desired audit state.
    type: str
    choices: [enabled, disabled]
    default: enabled
  cluster_id:
    description:
      - TKE cluster ID.
    type: str
    required: true
  logset_id:
    description:
      - Destination CLS logset ID.
    type: str
  topic_id:
    description:
      - Destination CLS topic ID.
    type: str
  topic_region:
    description:
      - Region of the CLS topic.
    type: str
  delete_logset_and_topic:
    description:
      - Delete automatically created CLS resources when disabling.
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
- susunola.tencentcloud.tke_cluster_audit:
    cluster_id: cls-xxxxxxxx
    logset_id: logset-xxxxxxxx
    topic_id: topic-xxxxxxxx
    topic_region: ap-guangzhou
"""
RETURN = r"""audit: {description: Effective audit switch metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def build_describe(models, cluster_id):
    request = models.DescribeLogSwitchesRequest()
    request.ClusterIds, request.ClusterType = [cluster_id], "tke"
    return request


def build_enable(models, p):
    request = models.EnableClusterAuditRequest()
    request.ClusterId, request.LogsetId, request.TopicId, request.TopicRegion = p["cluster_id"], p["logset_id"], p["topic_id"], p.get("topic_region")
    return request


def build_disable(models, p):
    request = models.DisableClusterAuditRequest()
    request.ClusterId, request.DeleteLogSetAndTopic = p["cluster_id"], p["delete_logset_and_topic"]
    return request


def find(module, client, models, cluster_id):
    response = module.sdk_call(client.DescribeLogSwitches, build_describe(models, cluster_id))
    items = list(response.SwitchSet or [])
    if not items:
        return {"Enable": False}
    return items[0]._serialize(allow_none=True)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["enabled", "disabled"], "default": "enabled"},
            "cluster_id": {"required": True},
            "logset_id": {},
            "topic_id": {},
            "topic_region": {},
            "delete_logset_and_topic": {"type": "bool", "default": False},
        },
        required_if=[("state", "enabled", ["logset_id", "topic_id"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["cluster_id"])
        enabled = bool(current.get("Enable"))
        target_enabled = p["state"] == "enabled"
        if enabled == target_enabled:
            module.exit_json(changed=False, audit=current)
        target = {"Enable": target_enabled, "LogsetId": p.get("logset_id"), "TopicId": p.get("topic_id"), "TopicRegion": p.get("topic_region")}
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(
                client.EnableClusterAudit if target_enabled else client.DisableClusterAudit,
                build_enable(models, p) if target_enabled else build_disable(models, p),
            )
            current = find(module, client, models, p["cluster_id"])
        module.exit_json(changed=True, **(diff or {}), audit=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
