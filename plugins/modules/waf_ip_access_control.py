#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: waf_ip_access_control
short_description: Manage Tencent Cloud WAF IP access-control rules
version_added: "0.14.0"
description: Creates, updates and deletes WAF IP allowlist or blocklist rules.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  rule_id: {description: Existing WAF rule ID., type: int}
  domain: {description: Protected domain name., type: str, required: true}
  action: {description: IP rule action., type: str, choices: [allow, block], required: true}
  ip_list: {description: Exact list of IP addresses and CIDRs., type: list, elements: str}
  note: {description: Rule note., type: str, default: ''}
  valid_until: {description: Unix timestamp when the rule expires. Zero means permanent., type: int, default: 0}
  instance_id: {description: WAF instance ID., type: str}
  edition: {description: WAF edition identifier., type: str}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_ip_access_control:
    domain: api.example.com
    action: block
    ip_list: [203.0.113.0/24, 198.51.100.10]
    note: Known abusive sources
'''
RETURN = r'''
rule: {description: WAF IP access-control rule metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

ACTION = {"allow": 40, "block": 42}


def _load_waf():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client


def build_describe_request(models, params, offset=0):
    request = models.DescribeIpAccessControlRequest()
    request.Domain, request.ActionType = params["domain"], ACTION[params["action"]]
    request.OffSet, request.Limit = offset, 100
    if params.get("rule_id") is not None:
        request.RuleId = params["rule_id"]
    return request


def _apply(request, params):
    request.Domain, request.IpList = params["domain"], sorted(params.get("ip_list") or [])
    request.ActionType, request.ValidTS = ACTION[params["action"]], params["valid_until"]
    request.Note = params["note"]
    if params.get("instance_id"):
        request.InstanceId = params["instance_id"]
    if params.get("edition"):
        request.Edition = params["edition"]
    return request


def build_create_request(models, params):
    return _apply(models.CreateIpAccessControlRequest(), params)


def build_update_request(models, params):
    request = _apply(models.ModifyIpAccessControlRequest(), params)
    request.RuleId = params["rule_id"]
    return request


def build_delete_request(models, params):
    request = models.DeleteIpAccessControlRequest()
    request.Domain, request.ActionType = params["domain"], ACTION[params["action"]]
    request.Items, request.IsId = [str(params["rule_id"])], True
    return request


def find_rule(module, client, models, params):
    response = module.sdk_call(client.DescribeIpAccessControl, build_describe_request(models, params))
    data = getattr(response, "Data", None)
    for item in list(getattr(data, "Res", None) or []):
        value = item._serialize(allow_none=True)
        if params.get("rule_id") is not None and int(value.get("RuleId") or value.get("Id") or 0) == params["rule_id"]:
            return value
        if params.get("rule_id") is None and sorted(value.get("IpList") or []) == sorted(params.get("ip_list") or []) and (value.get("Note") or "") == params["note"]:
            return value
    return None


def _desired(params):
    return {"ActionType": ACTION[params["action"]], "IpList": sorted(params.get("ip_list") or []), "Note": params["note"], "ValidTs": params["valid_until"]}


def _matches(current, desired):
    return current.get("ActionType") == desired["ActionType"] and sorted(current.get("IpList") or []) == desired["IpList"] and (current.get("Note") or "") == desired["Note"] and int(current.get("ValidTs") or 0) == desired["ValidTs"]


def wait_for_rule(module, client, models, params, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_rule(module, client, models, params)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for WAF IP rule convergence", rule=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "rule_id": {"type": "int"}, "domain": {"type": "str", "required": True}, "action": {"type": "str", "choices": ["allow", "block"], "required": True}, "ip_list": {"type": "list", "elements": "str"}, "note": {"type": "str", "default": ""}, "valid_until": {"type": "int", "default": 0}, "instance_id": {"type": "str"}, "edition": {"type": "str"}}, required_if=[("state", "present", ["ip_list"])], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_waf()
    client = module.create_client(client_module.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, rule=None, msg="WAF IP rule is absent")
            actual_id = int(current.get("RuleId") or current.get("Id"))
            p["rule_id"] = actual_id
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), rule=current, msg="Would delete WAF IP rule")
            module.sdk_call(client.DeleteIpAccessControl, build_delete_request(models, p))
            wait_for_rule(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), rule=None, msg="WAF IP rule deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), rule=None, msg="Would create WAF IP rule")
            response = module.sdk_call(client.CreateIpAccessControl, build_create_request(models, p))
            p["rule_id"] = int(response.RuleId)
            current = wait_for_rule(module, client, models, p, desired)
            module.exit_json(changed=True, **(diff or {}), rule=current, msg="WAF IP rule created")
        p["rule_id"] = int(current.get("RuleId") or current.get("Id"))
        if _matches(current, desired):
            module.exit_json(changed=False, rule=current, msg="WAF IP rule is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), rule=current, msg="Would update WAF IP rule")
        module.sdk_call(client.ModifyIpAccessControl, build_update_request(models, p))
        current = wait_for_rule(module, client, models, p, desired)
        module.exit_json(changed=True, **(diff or {}), rule=current, msg="WAF IP rule updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
