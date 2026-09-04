#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: api_gateway_usage_plan_binding
short_description: Bind API Gateway usage plans to service environments or APIs
version_added: "0.14.0"
description: Idempotently manages a usage-plan environment binding.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  usage_plan_id: {type: str, required: true, description: Usage plan ID.}
  service_id: {type: str, required: true, description: Service ID.}
  environment: {type: str, choices: [test, prepub, release], default: release, description: Service environment.}
  api_id: {type: str, description: API ID. Omit for a service-level binding.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.api_gateway_usage_plan_binding:
    usage_plan_id: usagePlan-xxxxxxxx
    service_id: service-xxxxxxxx
    environment: release
'''
RETURN = r'''binding: {description: Normalized usage plan binding., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models
    return models, apigateway_client


def build_describe(models, usage_plan_id):
    request = models.DescribeUsagePlanEnvironmentsRequest()
    request.UsagePlanId, request.Offset, request.Limit = usage_plan_id, 0, 100
    return request


def target(p):
    return {"UsagePlanId": p["usage_plan_id"], "ServiceId": p["service_id"], "Environment": p["environment"], "ApiId": p.get("api_id")}


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeUsagePlanEnvironments, build_describe(models, p["usage_plan_id"])).Result
    for item in list(getattr(result, "EnvironmentList", None) or []):
        value = item._serialize(allow_none=True)
        if value.get("ServiceId") == p["service_id"] and value.get("EnvironmentName") == p["environment"]:
            current_api = value.get("ApiId") or None
            if current_api == (p.get("api_id") or None):
                return target(p)
    return None


def build_change(models, p, unbind=False):
    request = models.UnBindEnvironmentRequest() if unbind else models.BindEnvironmentRequest()
    request.UsagePlanIds = [p["usage_plan_id"]]
    request.BindType = "API" if p.get("api_id") else "SERVICE"
    request.ServiceId, request.Environment = p["service_id"], p["environment"]
    if p.get("api_id"):
        request.ApiIds = [p["api_id"]]
    return request


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "usage_plan_id": {"required": True}, "service_id": {"required": True},
        "environment": {"choices": ["test", "prepub", "release"], "default": "release"}, "api_id": {},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current, desired = find(module, client, models, p), target(p)
        present = p["state"] == "present"
        if (present and current) or (not present and not current):
            module.exit_json(changed=False, binding=current)
        diff = maybe_diff(module, current, desired if present else None)
        if not module.check_mode:
            operation = client.BindEnvironment if present else client.UnBindEnvironment
            module.sdk_call(operation, build_change(models, p, unbind=not present))
        module.exit_json(changed=True, **(diff or {}), binding=desired if present else None)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
