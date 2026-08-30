#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: waf_auto_deny
short_description: Manage Tencent Cloud WAF automatic IP blocking
version_added: "0.14.0"
description: Reconciles automatic attack-source IP blocking for one protected domain.
options:
  domain: {type: str, required: true, description: Protected domain.}
  enabled: {type: bool, default: true, description: Whether automatic blocking is active.}
  attack_threshold: {type: int, default: 10, description: "Attacks required to trigger blocking, from 2 through 100."}
  time_threshold: {type: int, default: 5, description: "Observation window in minutes, from 1 through 60."}
  deny_time_threshold: {type: int, default: 60, description: "Blocking duration in minutes, from 5 through 360."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_auto_deny:
    domain: api.example.com
    attack_threshold: 20
    time_threshold: 5
    deny_time_threshold: 120
'''
RETURN = r'''auto_deny: {description: Effective automatic-blocking policy., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client
def describe_request(models, p):
    request = models.DescribeWafAutoDenyRulesRequest(); request.Domain = p["domain"]; return request
def update_request(models, p):
    request = models.ModifyWafAutoDenyRulesRequest(); request.Domain = p["domain"]
    request.AttackThreshold, request.TimeThreshold, request.DenyTimeThreshold = p["attack_threshold"], p["time_threshold"], p["deny_time_threshold"]
    request.DefenseStatus = 1 if p["enabled"] else 0; return request
def desired(p): return {"AttackThreshold": p["attack_threshold"], "TimeThreshold": p["time_threshold"], "DenyTimeThreshold": p["deny_time_threshold"], "DefenseStatus": 1 if p["enabled"] else 0}
def current(response): return {key: int(getattr(response, key) or 0) for key in ("AttackThreshold", "TimeThreshold", "DenyTimeThreshold", "DefenseStatus")}


def run_module():
    module = TencentCloudModule(argument_spec={"domain": {"required": True}, "enabled": {"type": "bool", "default": True}, "attack_threshold": {"type": "int", "default": 10}, "time_threshold": {"type": "int", "default": 5}, "deny_time_threshold": {"type": "int", "default": 60}}, supports_check_mode=True)
    p = module.params
    if not 2 <= p["attack_threshold"] <= 100: module.fail_json(msg="attack_threshold must be between 2 and 100")
    if not 1 <= p["time_threshold"] <= 60: module.fail_json(msg="time_threshold must be between 1 and 60")
    if not 5 <= p["deny_time_threshold"] <= 360: module.fail_json(msg="deny_time_threshold must be between 5 and 360")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        before = current(module.sdk_call(client.DescribeWafAutoDenyRules, describe_request(models, p))); target = desired(p)
        if before == target: module.exit_json(changed=False, auto_deny=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.ModifyWafAutoDenyRules, update_request(models, p))
        module.exit_json(changed=True, **(diff or {}), auto_deny=target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
