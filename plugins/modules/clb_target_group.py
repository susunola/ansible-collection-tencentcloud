#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_target_group
short_description: Manage Tencent Cloud CLB target groups and members
version_added: "0.14.0"
description:
  - Creates, updates and deletes CLB target groups.
  - Reconciles backend IP, port and weight as an exact set.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  target_group_id: {description: Existing target group ID., type: str}
  name: {description: Target group name., type: str}
  vpc_id: {description: VPC ID., type: str}
  port: {description: Default backend port., type: int}
  type: {description: Target group generation., type: str, choices: [v1, v2], default: v2}
  protocol: {description: Backend protocol for a v2 target group., type: str, choices: [TCP, UDP, HTTP, HTTPS, GRPC], default: TCP}
  schedule_algorithm: {description: Scheduling algorithm., type: str, choices: [WRR, LEAST_CONN, IP_HASH]}
  weight: {description: Default backend weight., type: int}
  instances:
    description: Exact backend member set.
    type: list
    elements: dict
    suboptions:
      ip: {description: Backend private IP., type: str, required: true}
      port: {description: Backend port., type: int, required: true}
      weight: {description: Backend weight from 0 to 100., type: int, default: 10}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.clb_target_group:
    name: api-backends
    vpc_id: vpc-xxxxxxxx
    protocol: HTTP
    port: 8080
    instances:
      - {ip: 10.0.1.10, port: 8080, weight: 20}
      - {ip: 10.0.1.11, port: 8080, weight: 20}
'''

RETURN = r'''
target_group: {description: Target group metadata including Instances., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_clb():
    from tencentcloud.clb.v20180317 import clb_client, models

    return models, clb_client


def build_describe_request(models, target_group_id=None, name=None, vpc_id=None, offset=0):
    request = models.DescribeTargetGroupsRequest()
    request.Offset, request.Limit = offset, 100
    if target_group_id:
        request.TargetGroupIds = [target_group_id]
    else:
        filters = []
        for key, value in (("TargetGroupName", name), ("VpcId", vpc_id)):
            if value:
                item = models.Filter()
                item.Name, item.Values = key, [value]
                filters.append(item)
        if filters:
            request.Filters = filters
    return request


def build_instances_request(models, target_group_id, instances, operation):
    request = operation()
    request.TargetGroupId = target_group_id
    request.TargetGroupInstances = []
    for value in instances:
        item = models.TargetGroupInstance()
        item.BindIP, item.Port, item.Weight = value["ip"], value["port"], value.get("weight", 10)
        request.TargetGroupInstances.append(item)
    return request


def build_create_request(models, params):
    request = models.CreateTargetGroupRequest()
    request.TargetGroupName, request.VpcId = params["name"], params["vpc_id"]
    request.Type, request.Protocol = params["type"], params["protocol"]
    if params.get("port") is not None:
        request.Port = params["port"]
    if params.get("schedule_algorithm") is not None:
        request.ScheduleAlgorithm = params["schedule_algorithm"]
    if params.get("weight") is not None:
        request.Weight = params["weight"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.TagInfo()
            tag.TagKey, tag.TagValue = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, target_group_id, params):
    request = models.ModifyTargetGroupAttributeRequest()
    request.TargetGroupId, request.TargetGroupName = target_group_id, params["name"]
    for api, key in (("Port", "port"), ("ScheduleAlgorithm", "schedule_algorithm"), ("Weight", "weight")):
        if params.get(key) is not None:
            setattr(request, api, params[key])
    return request


def build_delete_request(models, target_group_id):
    request = models.DeleteTargetGroupsRequest()
    request.TargetGroupIds = [target_group_id]
    return request


def _dict(value):
    return value._serialize(allow_none=True)


def find_group(module, client, models, target_group_id, name, vpc_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeTargetGroups, build_describe_request(models, target_group_id, name, vpc_id, offset))
        items = list(getattr(response, "TargetGroupSet", None) or [])
        matches.extend(_dict(item) for item in items)
        offset += len(items)
        if target_group_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple target groups match; specify target_group_id")
    return matches[0] if matches else None


def find_instances(module, client, models, target_group_id):
    offset, result = 0, []
    while True:
        request = models.DescribeTargetGroupInstancesRequest()
        request.Offset, request.Limit = offset, 100
        item = models.Filter()
        item.Name, item.Values = "TargetGroupId", [target_group_id]
        request.Filters = [item]
        response = module.sdk_call(client.DescribeTargetGroupInstances, request)
        values = list(getattr(response, "TargetGroupInstanceSet", None) or [])
        result.extend(_dict(value) for value in values)
        offset += len(values)
        if not values or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    return result


def _members(values):
    return sorted(
        (
            {"ip": x.get("BindIP") or x.get("ip"), "port": x.get("Port") or x.get("port"), "weight": x.get("Weight", x.get("weight", 10))}
            for x in (values or [])
        ),
        key=lambda x: (x["ip"], x["port"]),
    )


def reconcile_instances(module, client, models, target_group_id, current, desired):
    old = {(x["ip"], x["port"], x["weight"]): x for x in _members(current)}
    new = {(x["ip"], x["port"], x["weight"]): x for x in _members(desired)}
    remove, add = list((old.keys() - new.keys())), list((new.keys() - old.keys()))
    if remove:
        values = [{"ip": ip, "port": port, "weight": weight} for ip, port, weight in remove]
        request = build_instances_request(models, target_group_id, values, models.DeregisterTargetGroupInstancesRequest)
        module.sdk_call(client.DeregisterTargetGroupInstances, request)
    if add:
        values = [{"ip": ip, "port": port, "weight": weight} for ip, port, weight in add]
        request = build_instances_request(models, target_group_id, values, models.RegisterTargetGroupInstancesRequest)
        module.sdk_call(client.RegisterTargetGroupInstances, request)


def wait_for_group(module, client, models, target_group_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_group(module, client, models, target_group_id, None, None)
        if absent and current is None:
            return None
        if not absent and current:
            members = _members(find_instances(module, client, models, target_group_id))
            if all(current.get(k) == v for k, v in desired["attributes"].items()) and members == desired["instances"]:
                current["Instances"] = members
                return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for target group convergence", target_group=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "target_group_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "port": {"type": "int"},
            "type": {"type": "str", "choices": ["v1", "v2"], "default": "v2"},
            "protocol": {"type": "str", "choices": ["TCP", "UDP", "HTTP", "HTTPS", "GRPC"], "default": "TCP"},
            "schedule_algorithm": {"type": "str", "choices": ["WRR", "LEAST_CONN", "IP_HASH"]},
            "weight": {"type": "int"},
            "instances": {
                "type": "list",
                "elements": "dict",
                "options": {"ip": {"type": "str", "required": True}, "port": {"type": "int", "required": True}, "weight": {"type": "int", "default": 10}},
            },
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("target_group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_clb()
    client = module.create_client(client_module.ClbClient, "clb.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, p["target_group_id"], p["name"], p["vpc_id"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, target_group=None, msg="Target group is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), target_group=current, msg="Would delete target group")
            module.sdk_call(client.DeleteTargetGroups, build_delete_request(models, current["TargetGroupId"]))
            wait_for_group(module, client, models, current["TargetGroupId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), target_group=None, msg="Target group deleted")
        if current is None and (not p["name"] or not p["vpc_id"]):
            module.fail_json(msg="name and vpc_id are required when creating a target group")
        attributes = {"TargetGroupName": p["name"]}
        for api, key in (("Port", "port"), ("ScheduleAlgorithm", "schedule_algorithm"), ("Weight", "weight")):
            if p[key] is not None:
                attributes[api] = p[key]
        desired = {"attributes": attributes, "instances": _members(p["instances"] or [])}
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), target_group=None, msg="Would create target group")
            response = module.sdk_call(client.CreateTargetGroup, build_create_request(models, p))
            target_group_id = response.TargetGroupId
            if desired["instances"]:
                reconcile_instances(module, client, models, target_group_id, [], desired["instances"])
            current = wait_for_group(module, client, models, target_group_id, desired)
            module.exit_json(changed=True, **(diff or {}), target_group=current, msg="Target group created")
        current_instances = _members(find_instances(module, client, models, current["TargetGroupId"]))
        attr_drift = any(current.get(k) != v for k, v in attributes.items())
        member_drift = current_instances != desired["instances"]
        if not attr_drift and not member_drift:
            current["Instances"] = current_instances
            module.exit_json(changed=False, target_group=current, msg="Target group is up to date")
        diff = maybe_diff(module, dict(current, Instances=current_instances), desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), target_group=current, msg="Would update target group")
        if attr_drift:
            module.sdk_call(client.ModifyTargetGroupAttribute, build_update_request(models, current["TargetGroupId"], p))
        if member_drift:
            reconcile_instances(module, client, models, current["TargetGroupId"], current_instances, desired["instances"])
        current = wait_for_group(module, client, models, current["TargetGroupId"], desired)
        module.exit_json(changed=True, **(diff or {}), target_group=current, msg="Target group updated")
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
