#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: waf_host
short_description: Manage Tencent Cloud WAF protected hosts
version_added: "0.14.0"
description: Creates, updates and deletes a protected WAF host on an instance.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: WAF instance ID.}
  domain: {type: str, required: true, description: Protected domain name.}
  domain_id: {type: str, description: Existing protected-domain ID.}
  host: {type: dict, description: Complete SDK-compatible HostRecord configuration.}
  tags: {type: dict, default: {}, description: Tags applied when creating the host.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_host:
    instance_id: waf_2xxxxxxxx
    domain: api.example.com
    host:
      Domain: api.example.com
      Edition: clb-waf
      Region: ap-guangzhou
      LoadBalancerSet: []
      FlowMode: 1
'''
RETURN = r'''waf_host: {description: Effective protected-host metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client
def _model(models, name, value): item = getattr(models, name)(); item._deserialize(value); return item
def build_get(models, p): request = models.DescribeHostRequest(); request.Domain, request.DomainId, request.InstanceID = p["domain"], p.get("domain_id"), p["instance_id"]; return request
def _record(models, p):
    value = dict(p["host"] or {}); value["Domain"] = p["domain"]
    if p.get("domain_id"): value["DomainId"] = p["domain_id"]
    return _model(models, "HostRecord", value)
def _tags(models, values):
    result = []
    for key, value in sorted(values.items()): item = models.TagInfo(); item.TagKey, item.TagValue = str(key), str(value); result.append(item)
    return result
def build_create(models, p): request = models.CreateHostRequest(); request.Host, request.InstanceID, request.Tags = _record(models, p), p["instance_id"], _tags(models, p["tags"]); return request
def build_update(models, p): request = models.ModifyHostRequest(); request.Host, request.InstanceID = _record(models, p), p["instance_id"]; return request
def build_delete(models, p):
    request = models.DeleteHostRequest(); item = models.HostDel(); item.Domain, item.DomainId, item.InstanceID = p["domain"], p.get("domain_id"), p["instance_id"]; request.HostsDel = [item]; return request


def find(module, client, models, p):
    try:
        item = module.sdk_call(client.DescribeHost, build_get(models, p)).Host
        return item._serialize(allow_none=True) if item else None
    except Exception as exc:
        if is_not_found(exc): return None
        raise


def desired(p):
    result = dict(p["host"] or {}); result["Domain"] = p["domain"]
    if p.get("domain_id"): result["DomainId"] = p["domain_id"]
    return result


def comparable(current, target): return {k: current.get(k) for k in target}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "domain": {"required": True}, "domain_id": {}, "host": {"type": "dict"}, "tags": {"type": "dict", "default": {}}}, required_if=[("state", "present", ["host"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, waf_host=None)
            p["domain_id"] = current.get("DomainId") or p.get("domain_id"); diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteHost, build_delete(models, p))
            module.exit_json(changed=True, **(diff or {}), waf_host=current if module.check_mode else None)
        target = desired(p)
        if current and comparable(current, target) == target: module.exit_json(changed=False, waf_host=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, target)
        if not module.check_mode:
            if current:
                p["domain_id"] = current.get("DomainId") or p.get("domain_id"); module.sdk_call(client.ModifyHost, build_update(models, p))
            else: module.sdk_call(client.CreateHost, build_create(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), waf_host=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
