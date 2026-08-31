#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwdoris_user_workload_group
short_description: Bind a Tencent Cloud CDW Doris user to a workload group
version_added: "0.14.0"
description: Declaratively moves every host identity of a Doris user from its current workload group to the requested group.
options:
  instance_id: {type: str, required: true, description: CDW Doris instance ID.}
  user_name: {type: str, required: true, description: Doris database user name.}
  hosts: {type: list, elements: str, required: true, description: Every host identity belonging to this user.}
  workload_group: {type: str, required: true, description: Desired workload group name.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwdoris_user_workload_group:
    instance_id: cdwdoris-xxxxxxxx
    user_name: analyst
    hosts: ['%', '10.0.0.%']
    workload_group: interactive
'''
RETURN = r'''binding: {description: Effective user-to-workload-group binding., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdwdoris.v20211228 import models, cdwdoris_client
    return models, cdwdoris_client


def normalized_hosts(hosts):
    return sorted(set(hosts or []))


def describe(module, client, models, instance_id, user_name):
    request = models.DescribeUserBindWorkloadGroupRequest(); request.InstanceId = instance_id
    response = module.sdk_call(client.DescribeUserBindWorkloadGroup, request)
    if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
    matches = [item._serialize(allow_none=True) for item in response.UserBindInfos or [] if item.UserName == user_name]
    if len(matches) > 1: module.fail_json(msg="Multiple workload-group bindings matched the Doris user", user_name=user_name)
    return matches[0] if matches else None


def modify_request(models, params, old_group):
    request = models.ModifyUserBindWorkloadGroupRequest(); request.InstanceId = params["instance_id"]
    request.BindUsers = []
    for host in normalized_hosts(params["hosts"]):
        item = models.BindUser(); item.UserName = params["user_name"]; item.Host = host; request.BindUsers.append(item)
    request.OldWorkloadGroupName = old_group; request.NewWorkloadGroupName = params["workload_group"]
    return request


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "user_name": {"required": True},
        "hosts": {"type": "list", "elements": "str", "required": True},
        "workload_group": {"required": True},
    }, supports_check_mode=True)
    params = module.params
    if not normalized_hosts(params["hosts"]): module.fail_json(msg="hosts must contain every host identity for the Doris user")
    module.require_sdk(); models, client_module = _load(); client = module.create_client(client_module.CdwdorisClient, "cdwdoris.tencentcloudapi.com")
    try:
        current = describe(module, client, models, params["instance_id"], params["user_name"])
        target = {"UserName": params["user_name"], "WorkloadGroupName": params["workload_group"]}
        if current and current.get("WorkloadGroupName") == params["workload_group"]:
            module.exit_json(changed=False, binding=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            response = module.sdk_call(client.ModifyUserBindWorkloadGroup, modify_request(models, params, (current or {}).get("WorkloadGroupName")))
            if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
            current = describe(module, client, models, params["instance_id"], params["user_name"]) or target
        module.exit_json(changed=True, **(diff or {}), binding=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
