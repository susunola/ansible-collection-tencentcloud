#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: api_gateway_usage_plan_key_binding
short_description: Bind API Gateway keys to usage plans
version_added: "0.14.0"
description: Idempotently binds or unbinds an API key and usage plan.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  usage_plan_id: {type: str, required: true, description: Usage plan ID.}
  access_key_id: {type: str, required: true, description: API key ID.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.api_gateway_usage_plan_key_binding:
    usage_plan_id: usagePlan-xxxxxxxx
    access_key_id: AKIDxxxxxxxx
"""
RETURN = r"""binding: {description: Normalized key binding., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models

    return models, apigateway_client


def build_describe(models, plan_id):
    request = models.DescribeUsagePlanSecretIdsRequest()
    request.UsagePlanId, request.Offset, request.Limit = plan_id, 0, 100
    return request


def build_bind(models, plan_id, key_id):
    request = models.BindSecretIdsRequest()
    request.UsagePlanId, request.AccessKeyIds = plan_id, [key_id]
    return request


def build_unbind(models, plan_id, key_id):
    request = models.UnBindSecretIdsRequest()
    request.UsagePlanId, request.AccessKeyIds = plan_id, [key_id]
    return request


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeUsagePlanSecretIds, build_describe(models, p["usage_plan_id"])).Result
    for item in list(result.AccessKeyList or []):
        if item.AccessKeyId == p["access_key_id"]:
            return {"UsagePlanId": p["usage_plan_id"], "AccessKeyId": p["access_key_id"]}
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "usage_plan_id": {"required": True},
            "access_key_id": {"required": True, "no_log": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        target = {"UsagePlanId": p["usage_plan_id"], "AccessKeyId": p["access_key_id"]}
        present = p["state"] == "present"
        if (present and current) or (not present and not current):
            module.exit_json(changed=False, binding=current)
        diff = maybe_diff(module, current, target if present else None)
        if not module.check_mode:
            module.sdk_call(
                client.BindSecretIds if present else client.UnBindSecretIds,
                build_bind(models, p["usage_plan_id"], p["access_key_id"]) if present else build_unbind(models, p["usage_plan_id"], p["access_key_id"]),
            )
        module.exit_json(changed=True, **(diff or {}), binding=target if present else None)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
