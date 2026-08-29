#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: as_scaling_group
short_description: Manage Tencent Cloud Auto Scaling groups
version_added: "0.14.0"
description: Creates, updates and deletes Auto Scaling groups without creating instances unless desired capacity is explicitly positive.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  scaling_group_id: {description: Existing Auto Scaling group ID., type: str}
  name: {description: Auto Scaling group name., type: str}
  launch_configuration_id: {description: Launch configuration ID., type: str}
  vpc_id: {description: VPC ID., type: str}
  subnet_ids: {description: Ordered subnet priority list., type: list, elements: str}
  min_size: {description: Minimum instance count., type: int, default: 0}
  max_size: {description: Maximum instance count., type: int, default: 0}
  desired_capacity: {description: Desired instance count. A positive value can create billable CVM instances., type: int, default: 0}
  default_cooldown: {description: Default cooldown in seconds., type: int, default: 300}
  termination_policy: {description: Instance termination policy., type: str, choices: [OLDEST_INSTANCE, NEWEST_INSTANCE], default: OLDEST_INSTANCE}
  retry_policy: {description: Scaling retry policy., type: str, choices: [IMMEDIATE_RETRY, INCREMENTAL_INTERVALS, NO_RETRY], default: IMMEDIATE_RETRY}
  subnet_policy: {description: Multi-subnet allocation policy., type: str, choices: [PRIORITY, EQUALITY], default: PRIORITY}
  health_check_type: {description: Instance health check type., type: str, choices: [CVM, CLB], default: CVM}
  capacity_rebalance: {description: Proactively replace interrupted spot instances., type: bool, default: false}
  project_id: {description: Project ID., type: int, default: 0}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.as_scaling_group:
    name: web-fleet
    launch_configuration_id: asc-xxxxxxxx
    vpc_id: vpc-xxxxxxxx
    subnet_ids: [subnet-aaaaaaaa, subnet-bbbbbbbb]
    min_size: 0
    max_size: 10
    desired_capacity: 0
'''
RETURN = r'''
scaling_group: {description: Auto Scaling group metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_autoscaling():
    from tencentcloud.autoscaling.v20180419 import autoscaling_client, models
    return models, autoscaling_client


def build_describe_request(models, scaling_group_id=None, name=None, offset=0):
    request = models.DescribeAutoScalingGroupsRequest()
    request.Offset, request.Limit = offset, 100
    if scaling_group_id:
        request.AutoScalingGroupIds = [scaling_group_id]
    elif name:
        item = models.Filter()
        item.Name, item.Values = "auto-scaling-group-name", [name]
        request.Filters = [item]
    return request


def _apply(request, params):
    request.AutoScalingGroupName = params["name"]
    request.LaunchConfigurationId = params["launch_configuration_id"]
    request.VpcId, request.SubnetIds = params["vpc_id"], params["subnet_ids"]
    request.MinSize, request.MaxSize = params["min_size"], params["max_size"]
    request.DesiredCapacity, request.DefaultCooldown = params["desired_capacity"], params["default_cooldown"]
    request.TerminationPolicies = [params["termination_policy"]]
    request.RetryPolicy, request.MultiZoneSubnetPolicy = params["retry_policy"], params["subnet_policy"]
    request.HealthCheckType, request.CapacityRebalance = params["health_check_type"], params["capacity_rebalance"]
    request.ProjectId = params["project_id"]
    return request


def build_create_request(models, params):
    return _apply(models.CreateAutoScalingGroupRequest(), params)


def build_update_request(models, scaling_group_id, params):
    request = _apply(models.ModifyAutoScalingGroupRequest(), params)
    request.AutoScalingGroupId = scaling_group_id
    return request


def build_delete_request(models, scaling_group_id):
    request = models.DeleteAutoScalingGroupRequest()
    request.AutoScalingGroupId = scaling_group_id
    return request


def find_group(module, client, models, scaling_group_id=None, name=None):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeAutoScalingGroups, build_describe_request(models, scaling_group_id, name, offset))
        items = list(response.AutoScalingGroupSet or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (scaling_group_id and value.get("AutoScalingGroupId") == scaling_group_id) or (not scaling_group_id and value.get("AutoScalingGroupName") == name):
                matches.append(value)
        offset += len(items)
        if scaling_group_id or not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Auto Scaling groups have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {"AutoScalingGroupName": params["name"], "LaunchConfigurationId": params["launch_configuration_id"], "VpcId": params["vpc_id"], "SubnetIdSet": params["subnet_ids"], "MinSize": params["min_size"], "MaxSize": params["max_size"], "DesiredCapacity": params["desired_capacity"], "DefaultCooldown": params["default_cooldown"], "TerminationPolicySet": [params["termination_policy"]], "RetryPolicy": params["retry_policy"], "MultiZoneSubnetPolicy": params["subnet_policy"], "HealthCheckType": params["health_check_type"], "CapacityRebalance": params["capacity_rebalance"], "ProjectId": params["project_id"]}


def _matches(current, desired):
    return all(current.get(key) == value for key, value in desired.items())


def wait_for_group(module, client, models, scaling_group_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_group(module, client, models, scaling_group_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Auto Scaling group convergence", scaling_group=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "scaling_group_id": {"type": "str"}, "name": {"type": "str"}, "launch_configuration_id": {"type": "str"}, "vpc_id": {"type": "str"}, "subnet_ids": {"type": "list", "elements": "str"}, "min_size": {"type": "int", "default": 0}, "max_size": {"type": "int", "default": 0}, "desired_capacity": {"type": "int", "default": 0}, "default_cooldown": {"type": "int", "default": 300}, "termination_policy": {"type": "str", "choices": ["OLDEST_INSTANCE", "NEWEST_INSTANCE"], "default": "OLDEST_INSTANCE"}, "retry_policy": {"type": "str", "choices": ["IMMEDIATE_RETRY", "INCREMENTAL_INTERVALS", "NO_RETRY"], "default": "IMMEDIATE_RETRY"}, "subnet_policy": {"type": "str", "choices": ["PRIORITY", "EQUALITY"], "default": "PRIORITY"}, "health_check_type": {"type": "str", "choices": ["CVM", "CLB"], "default": "CVM"}, "capacity_rebalance": {"type": "bool", "default": False}, "project_id": {"type": "int", "default": 0}}, required_one_of=[("scaling_group_id", "name")], required_if=[("state", "present", ("name", "launch_configuration_id", "vpc_id", "subnet_ids"))], supports_check_mode=True)
    p = module.params
    if not 0 <= p["min_size"] <= p["desired_capacity"] <= p["max_size"] <= 2000:
        module.fail_json(msg="capacity must satisfy 0 <= min_size <= desired_capacity <= max_size <= 2000")
    module.require_sdk()
    models, client_module = _load_autoscaling()
    client = module.create_client(client_module.AutoscalingClient, "as.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, p["scaling_group_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, scaling_group=None, msg="Auto Scaling group is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), scaling_group=current, msg="Would delete Auto Scaling group")
            module.sdk_call(client.DeleteAutoScalingGroup, build_delete_request(models, current["AutoScalingGroupId"]))
            wait_for_group(module, client, models, current["AutoScalingGroupId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), scaling_group=None, msg="Auto Scaling group deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), scaling_group=None, msg="Would create Auto Scaling group")
            response = module.sdk_call(client.CreateAutoScalingGroup, build_create_request(models, p))
            current = wait_for_group(module, client, models, response.AutoScalingGroupId, desired)
            module.exit_json(changed=True, **(diff or {}), scaling_group=current, msg="Auto Scaling group created")
        if _matches(current, desired):
            module.exit_json(changed=False, scaling_group=current, msg="Auto Scaling group is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), scaling_group=current, msg="Would update Auto Scaling group")
        module.sdk_call(client.ModifyAutoScalingGroup, build_update_request(models, current["AutoScalingGroupId"], p))
        current = wait_for_group(module, client, models, current["AutoScalingGroupId"], desired)
        module.exit_json(changed=True, **(diff or {}), scaling_group=current, msg="Auto Scaling group updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
