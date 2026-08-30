#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_firewall_rules
short_description: Manage Tencent Cloud Lighthouse instance firewall rules
version_added: "0.14.0"
description:
  - Reconciles the complete set of user-managed firewall rules on one Lighthouse instance.
  - Rules omitted from O(rules) are deleted; include every rule that should remain.
options:
  instance_id: {type: str, required: true, description: Lighthouse instance ID.}
  rules: {type: list, elements: dict, default: [], description: Complete desired SDK-compatible FirewallRule list.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_firewall_rules:
    instance_id: lhins-xxxxxxxx
    rules:
      - {Protocol: TCP, Port: '22', CidrBlock: 10.0.0.0/8, Action: ACCEPT, FirewallRuleDescription: administration}
      - {Protocol: TCP, Port: '443', CidrBlock: 0.0.0.0/0, Action: ACCEPT, FirewallRuleDescription: HTTPS}
'''
RETURN = r'''
rules: {description: Effective normalized firewall rule set., type: list, elements: dict, returned: always}
firewall_version: {description: Optimistic-concurrency version returned by Lighthouse., type: int, returned: always}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


FIELDS = ("Protocol", "Port", "CidrBlock", "Ipv6CidrBlock", "Action", "FirewallRuleDescription")


def _load():
    from tencentcloud.lighthouse.v20200324 import models, lighthouse_client
    return models, lighthouse_client
def _rule(models, value):
    item = models.FirewallRule(); item._deserialize({key: value.get(key) for key in FIELDS if value.get(key) is not None}); return item
def normalize_rule(value): return {key: value.get(key) or "" for key in FIELDS}
def rule_key(value): return tuple(normalize_rule(value)[key] for key in FIELDS)
def normalize_rules(values): return sorted((normalize_rule(value) for value in values or []), key=rule_key)
def describe_request(models, instance_id, offset=0):
    request = models.DescribeFirewallRulesRequest(); request.InstanceId, request.Offset, request.Limit = instance_id, offset, 100; return request
def create_request(models, instance_id, rules, version):
    request = models.CreateFirewallRulesRequest(); request.InstanceId, request.FirewallRules, request.FirewallVersion = instance_id, [_rule(models, value) for value in rules], version; return request
def delete_request(models, instance_id, rules, version):
    request = models.DeleteFirewallRulesRequest(); request.InstanceId, request.FirewallRules, request.FirewallVersion = instance_id, [_rule(models, value) for value in rules], version; return request
def describe(module, client, models, instance_id):
    offset = 0; result = []; version = None
    while True:
        response = module.sdk_call(client.DescribeFirewallRules, describe_request(models, instance_id, offset)); values = list(response.FirewallRuleSet or []); version = response.FirewallVersion
        result.extend(item._serialize(allow_none=True) for item in values); offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    return normalize_rules(result), version


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "rules": {"type": "list", "elements": "dict", "default": []}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.LighthouseClient, "lighthouse.tencentcloudapi.com")
    try:
        current, version = describe(module, client, models, p["instance_id"]); target = normalize_rules(p["rules"]); current_set, target_set = {rule_key(v): v for v in current}, {rule_key(v): v for v in target}
        remove = [current_set[key] for key in sorted(set(current_set) - set(target_set))]; add = [target_set[key] for key in sorted(set(target_set) - set(current_set))]
        if not remove and not add: module.exit_json(changed=False, rules=current, firewall_version=version)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if remove:
                module.sdk_call(client.DeleteFirewallRules, delete_request(models, p["instance_id"], remove, version)); current, version = describe(module, client, models, p["instance_id"])
            if add: module.sdk_call(client.CreateFirewallRules, create_request(models, p["instance_id"], add, version))
            current, version = describe(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff or {}), rules=current if not module.check_mode else target, firewall_version=version)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
