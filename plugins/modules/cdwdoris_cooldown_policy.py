#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cdwdoris_cooldown_policy
short_description: Manage a Tencent Cloud CDW Doris cooldown policy
version_added: "0.14.0"
description:
  - Creates or updates a named hot/cold tiering policy.
  - The service exposes no standalone policy deletion operation; policies are removed with their instance.
options:
  instance_id: {type: str, required: true, description: CDW Doris instance ID.}
  name: {type: str, required: true, description: Cooldown policy name.}
  cooldown_ttl: {type: str, description: Relative cooldown TTL accepted by Doris.}
  cooldown_datetime: {type: str, description: Absolute cooldown datetime accepted by Doris.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cdwdoris_cooldown_policy:
    instance_id: cdwdoris-xxxxxxxx
    name: archive-after-30-days
    cooldown_ttl: 30 DAY
"""
RETURN = r"""policy: {description: Effective cooldown policy., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdwdoris.v20211228 import models, cdwdoris_client

    return models, cdwdoris_client


def desired(params):
    value = {"PolicyName": params["name"]}
    if params.get("cooldown_ttl") is not None:
        value["CooldownTtl"] = params["cooldown_ttl"]
    if params.get("cooldown_datetime") is not None:
        value["CooldownDatetime"] = params["cooldown_datetime"]
    return value


def describe(module, client, models, instance_id, name):
    request = models.DescribeCoolDownPoliciesRequest()
    request.InstanceId = instance_id
    response = module.sdk_call(client.DescribeCoolDownPolicies, request)
    if response.ErrorMsg:
        module.fail_json(msg=response.ErrorMsg)
    matches = [item._serialize(allow_none=True) for item in response.List or [] if item.PolicyName == name]
    if len(matches) > 1:
        module.fail_json(msg="Multiple Doris cooldown policies matched", name=name)
    return matches[0] if matches else None


def request_for(models, params, update=False):
    request = models.ModifyCoolDownPolicyRequest() if update else models.CreateCoolDownPolicyRequest()
    request.InstanceId = params["instance_id"]
    request.PolicyName = params["name"]
    request.CoolDownTtl = params.get("cooldown_ttl")
    request.CoolDownDatetime = params.get("cooldown_datetime")
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "name": {"required": True},
            "cooldown_ttl": {},
            "cooldown_datetime": {},
        },
        required_one_of=[("cooldown_ttl", "cooldown_datetime")],
        mutually_exclusive=[("cooldown_ttl", "cooldown_datetime")],
        supports_check_mode=True,
    )
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.CdwdorisClient, "cdwdoris.tencentcloudapi.com")
    try:
        current = describe(module, client, models, params["instance_id"], params["name"])
        target = desired(params)
        before = {key: current.get(key) for key in target} if current else None
        if before == target:
            module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            method = client.ModifyCoolDownPolicy if current else client.CreateCoolDownPolicy
            response = module.sdk_call(method, request_for(models, params, update=current is not None))
            if response.ErrorMsg:
                module.fail_json(msg=response.ErrorMsg)
            current = describe(module, client, models, params["instance_id"], params["name"]) or target
        module.exit_json(changed=True, **(diff or {}), policy=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
