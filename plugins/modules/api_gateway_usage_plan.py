#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: api_gateway_usage_plan
short_description: Manage Tencent Cloud API Gateway usage plans
version_added: "0.14.0"
description: Creates, updates and deletes API Gateway usage plans.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  usage_plan_id: {type: str, description: Existing usage plan ID.}
  name: {type: str, description: Usage plan name.}
  description: {type: str, default: '', description: Usage plan description.}
  qps: {type: int, default: -1, description: Requests per second limit; -1 means unlimited.}
  max_request_num: {type: int, default: -1, description: Total request limit; -1 means unlimited.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.api_gateway_usage_plan:
    name: production-clients
    qps: 100
    max_request_num: 1000000
'''
RETURN = r'''usage_plan: {description: Usage plan metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models
    return models, apigateway_client


def build_get(models, usage_plan_id):
    request = models.DescribeUsagePlanRequest()
    request.UsagePlanId = usage_plan_id
    return request


def build_list(models, name, offset=0):
    request = models.DescribeUsagePlansStatusRequest()
    request.Offset, request.Limit = offset, 100
    if name:
        item = models.Filter()
        item.Name, item.Values = "UsagePlanName", [name]
        request.Filters = [item]
    return request


def find(module, client, models, plan_id, name):
    if plan_id:
        try:
            result = module.sdk_call(client.DescribeUsagePlan, build_get(models, plan_id)).Result
            return result._serialize(allow_none=True) if result else None
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
    result = module.sdk_call(client.DescribeUsagePlansStatus, build_list(models, name)).Result
    matches = [x._serialize(allow_none=True) for x in list(getattr(result, "UsagePlanStatusSet", None) or []) if x.UsagePlanName == name]
    if len(matches) > 1:
        module.fail_json(msg="Multiple usage plans have the requested name", name=name)
    if not matches:
        return None
    result = module.sdk_call(client.DescribeUsagePlan, build_get(models, matches[0]["UsagePlanId"])).Result
    return result._serialize(allow_none=True)


def apply(request, p, plan_id=None):
    request.UsagePlanName, request.UsagePlanDesc = p["name"], p["description"]
    request.MaxRequestNumPreSec, request.MaxRequestNum = p["qps"], p["max_request_num"]
    if plan_id:
        request.UsagePlanId = plan_id
    return request


def build_create(models, p):
    return apply(models.CreateUsagePlanRequest(), p)


def build_update(models, p, plan_id):
    return apply(models.ModifyUsagePlanRequest(), p, plan_id)


def build_delete(models, plan_id):
    request = models.DeleteUsagePlanRequest()
    request.UsagePlanId = plan_id
    return request


def desired(p):
    return {"UsagePlanName": p["name"], "UsagePlanDesc": p["description"], "MaxRequestNumPreSec": p["qps"], "MaxRequestNum": p["max_request_num"]}


def comparable(value):
    return {"UsagePlanName": value.get("UsagePlanName"), "UsagePlanDesc": value.get("UsagePlanDesc") or "", "MaxRequestNumPreSec": int(value.get("MaxRequestNumPreSec", -1)), "MaxRequestNum": int(value.get("MaxRequestNum", -1))}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "usage_plan_id": {}, "name": {}, "description": {"default": ""},
        "qps": {"type": "int", "default": -1}, "max_request_num": {"type": "int", "default": -1},
    }, required_one_of=[("usage_plan_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["usage_plan_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, usage_plan=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteUsagePlan, build_delete(models, current["UsagePlanId"]))
            module.exit_json(changed=True, **(diff or {}), usage_plan=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, usage_plan=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyUsagePlan, build_update(models, p, current["UsagePlanId"]))
                plan_id = current["UsagePlanId"]
            else:
                plan_id = module.sdk_call(client.CreateUsagePlan, build_create(models, p)).Result.UsagePlanId
            current = find(module, client, models, plan_id, None)
        module.exit_json(changed=True, **(diff or {}), usage_plan=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
