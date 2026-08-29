#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vpc_flow_log
short_description: Manage Tencent Cloud VPC flow logs
version_added: "0.14.0"
description:
  - Creates, updates, enables, disables and deletes VPC flow logs.
  - Connects ENI, NAT, CCN or direct-connect traffic telemetry to a CLS topic.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  flow_log_id: {description: Existing flow log ID., type: str}
  name: {description: Flow log name., type: str}
  vpc_id: {description: VPC ID., type: str, required: true}
  resource_type: {description: Observed resource type., type: str, choices: [NETWORKINTERFACE, NAT, CCN, DCG]}
  resource_id: {description: Observed resource ID., type: str}
  traffic_type: {description: Captured traffic decision., type: str, choices: [ACCEPT, REJECT, ALL], default: ALL}
  cls_topic_id: {description: CLS topic ID receiving records., type: str}
  cls_region: {description: Region containing the CLS topic., type: str}
  description: {description: Flow log description., type: str, default: ''}
  enabled: {description: Whether collection is enabled., type: bool, default: true}
  period: {description: CCN collection period in seconds., type: int, choices: [60, 300, 600]}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.vpc_flow_log:
    name: app-eni-traffic
    vpc_id: vpc-xxxxxxxx
    resource_type: NETWORKINTERFACE
    resource_id: eni-xxxxxxxx
    cls_topic_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    traffic_type: ALL
'''

RETURN = r'''
flow_log: {description: Flow log metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client

    return models, vpc_client


def build_describe_request(models, vpc_id, flow_log_id=None, name=None, offset=0):
    request = models.DescribeFlowLogsRequest()
    request.VpcId, request.Offset, request.Limit = vpc_id, offset, 100
    request.FlowLogId, request.FlowLogName = flow_log_id, name
    return request


def build_create_request(models, params):
    request = models.CreateFlowLogRequest()
    request.FlowLogName, request.VpcId = params["name"], params["vpc_id"]
    request.ResourceType, request.ResourceId = params["resource_type"], params["resource_id"]
    request.TrafficType, request.CloudLogId = params["traffic_type"], params["cls_topic_id"]
    request.FlowLogDescription, request.StorageType = params["description"], "cls"
    if params.get("cls_region"):
        request.CloudLogRegion = params["cls_region"]
    if params.get("period") is not None:
        request.Period = params["period"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, flow_log_id, params):
    request = models.ModifyFlowLogAttributeRequest()
    request.FlowLogId, request.VpcId = flow_log_id, params["vpc_id"]
    request.FlowLogName, request.FlowLogDescription = params["name"], params["description"]
    if params.get("period") is not None:
        request.Period = params["period"]
    return request


def build_toggle_request(models, enabled, flow_log_id):
    request = models.EnableFlowLogsRequest() if enabled else models.DisableFlowLogsRequest()
    request.FlowLogIds = [flow_log_id]
    return request


def build_delete_request(models, vpc_id, flow_log_id):
    request = models.DeleteFlowLogRequest()
    request.VpcId, request.FlowLogId = vpc_id, flow_log_id
    return request


def find_flow_log(module, client, models, vpc_id, flow_log_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeFlowLogs, build_describe_request(models, vpc_id, flow_log_id, name, offset))
        items = list(getattr(response, "FlowLog", None) or getattr(response, "FlowLogSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if flow_log_id or not items or offset >= int(getattr(response, "TotalNum", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple flow logs match; specify flow_log_id")
    return matches[0] if matches else None


def wait_for_flow_log(module, client, models, vpc_id, flow_log_id, enabled=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_flow_log(module, client, models, vpc_id, flow_log_id, None)
        if absent and current is None:
            return None
        if not absent and current and (enabled is None or bool(current.get("Enable")) == enabled):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for flow log convergence", flow_log=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "flow_log_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str", "required": True},
            "resource_type": {"type": "str", "choices": ["NETWORKINTERFACE", "NAT", "CCN", "DCG"]},
            "resource_id": {"type": "str"},
            "traffic_type": {"type": "str", "choices": ["ACCEPT", "REJECT", "ALL"], "default": "ALL"},
            "cls_topic_id": {"type": "str"},
            "cls_region": {"type": "str"},
            "description": {"type": "str", "default": ""},
            "enabled": {"type": "bool", "default": True},
            "period": {"type": "int", "choices": [60, 300, 600]},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("flow_log_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_flow_log(module, client, models, p["vpc_id"], p["flow_log_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, flow_log=None, msg="Flow log is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), flow_log=current, msg="Would delete flow log")
            module.sdk_call(client.DeleteFlowLog, build_delete_request(models, p["vpc_id"], current["FlowLogId"]))
            wait_for_flow_log(module, client, models, p["vpc_id"], current["FlowLogId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), flow_log=None, msg="Flow log deleted")
        was_created = current is None
        if was_created:
            missing = [key for key in ("name", "resource_type", "resource_id", "cls_topic_id") if not p[key]]
            if missing:
                module.fail_json(msg="Required when creating: %s" % ", ".join(missing))
            desired = {
                "FlowLogName": p["name"],
                "ResourceType": p["resource_type"],
                "ResourceId": p["resource_id"],
                "TrafficType": p["traffic_type"],
                "CloudLogId": p["cls_topic_id"],
                "FlowLogDescription": p["description"],
                "Enable": p["enabled"],
            }
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), flow_log=None, msg="Would create flow log")
            response = module.sdk_call(client.CreateFlowLog, build_create_request(models, p))
            current = wait_for_flow_log(module, client, models, p["vpc_id"], response.FlowLog.FlowLogId)
        mutable = {"FlowLogName": p["name"], "FlowLogDescription": p["description"]}
        if p["period"] is not None:
            mutable["Period"] = p["period"]
        attr_drift = any(current.get(k) != v for k, v in mutable.items())
        enabled_drift = bool(current.get("Enable")) != p["enabled"]
        if not was_created and not attr_drift and not enabled_drift:
            module.exit_json(changed=False, flow_log=current, msg="Flow log is up to date")
        diff = maybe_diff(module, current, dict(mutable, Enable=p["enabled"]))
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), flow_log=current, msg="Would update flow log")
        if attr_drift:
            module.sdk_call(client.ModifyFlowLogAttribute, build_update_request(models, current["FlowLogId"], p))
        if enabled_drift:
            operation = client.EnableFlowLogs if p["enabled"] else client.DisableFlowLogs
            module.sdk_call(operation, build_toggle_request(models, p["enabled"], current["FlowLogId"]))
        current = wait_for_flow_log(module, client, models, p["vpc_id"], current["FlowLogId"], p["enabled"])
        module.exit_json(changed=True, **(diff or {}), flow_log=current, msg="Flow log updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
