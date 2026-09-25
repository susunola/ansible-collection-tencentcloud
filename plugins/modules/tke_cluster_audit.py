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
description:
  - Enables or disables Kubernetes audit logging to a CLS topic.
  - Reads the nested audit switch and verifies the requested CLS destination.
  - An enabled audit switch cannot be retargeted in place; disable it explicitly
    before enabling it with another destination.
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
import time

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
    items = getattr(response, "SwitchSet", None)
    if items is None:
        raise ValueError("DescribeLogSwitches did not return SwitchSet")
    matches = [item for item in items if getattr(item, "ClusterId", None) == cluster_id]
    if len(matches) != 1:
        raise ValueError("DescribeLogSwitches did not return exactly one switch for the requested cluster")
    audit = getattr(matches[0], "Audit", None)
    if audit is None:
        raise ValueError("DescribeLogSwitches did not return the cluster Audit switch")
    value = audit._serialize(allow_none=True)
    if not isinstance(value.get("Enable"), bool):
        raise ValueError("DescribeLogSwitches returned an indeterminate Audit enable state")
    if value.get("ErrorMsg"):
        raise ValueError("DescribeLogSwitches reported an Audit switch error: %s" % value["ErrorMsg"])
    return value


def destination_drift(current, params):
    fields = {"LogsetId": params["logset_id"], "TopicId": params["topic_id"]}
    if params.get("topic_region"):
        fields["TopicRegion"] = params["topic_region"]
    return [field for field, desired in fields.items() if current.get(field) != desired]


def converged(current, params):
    enabled = params["state"] == "enabled"
    if current["Enable"] != enabled:
        return False
    status = current.get("Status")
    if status and status != ("opened" if enabled else "closed"):
        return False
    return not (enabled and destination_drift(current, params))


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
        target_enabled = p["state"] == "enabled"
        if target_enabled and current["Enable"]:
            drift = destination_drift(current, p)
            if drift:
                module.fail_json(msg="TKE audit is already enabled with a different CLS destination; disable it explicitly before retargeting",
                                 cluster_id=p["cluster_id"], drift_fields=drift, audit=current)
        if converged(current, p):
            module.exit_json(changed=False, audit=current)
        target = {"Enable": target_enabled, "LogsetId": p.get("logset_id"), "TopicId": p.get("topic_id"), "TopicRegion": p.get("topic_region")}
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if current["Enable"] != target_enabled:
                module.sdk_call(
                    client.EnableClusterAudit if target_enabled else client.DisableClusterAudit,
                    build_enable(models, p) if target_enabled else build_disable(models, p),
                )
            deadline = time.monotonic() + p["waiter_timeout"]
            while True:
                current = find(module, client, models, p["cluster_id"])
                if converged(current, p):
                    break
                if time.monotonic() >= deadline:
                    module.fail_json(msg="TKE audit switch did not converge to the requested state",
                                     cluster_id=p["cluster_id"], audit=current)
                time.sleep(p["waiter_delay"])
        module.exit_json(changed=True, **(diff or {}), audit=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
