#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_threat_intelligence
short_description: Manage Tencent Cloud WAF threat-intelligence blocking
version_added: "0.14.0"
description: Reconciles the account-level WAF threat-intelligence blocking configuration.
options:
  enabled: {type: bool, default: true, description: Whether threat-intelligence blocking is active.}
  tags: {type: list, elements: str, default: [], description: Exact threat-intelligence tag set to block.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_threat_intelligence:
    enabled: true
    tags: [botnet, scanner]
"""
RETURN = r"""threat_intelligence: {description: Effective threat-intelligence configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client

    return models, waf_client


def describe_request(models):
    return models.DescribeWafThreatenIntelligenceRequest()


def update_request(models, p):
    detail = models.WafThreatenIntelligenceDetails()
    detail.Tags, detail.DefenseStatus = sorted(p["tags"]), 1 if p["enabled"] else 0
    request = models.ModifyWafThreatenIntelligenceRequest()
    request.WafThreatenIntelligenceDetails = detail
    return request


def normalize(item):
    if not item:
        return None
    return {"Tags": sorted(item.Tags or []), "DefenseStatus": int(item.DefenseStatus or 0)}


def run_module():
    module = TencentCloudModule(
        argument_spec={"enabled": {"type": "bool", "default": True}, "tags": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeWafThreatenIntelligence, describe_request(models))
        before = normalize(response.WafThreatenIntelligenceDetails)
        target = {"Tags": sorted(p["tags"]), "DefenseStatus": 1 if p["enabled"] else 0}
        if before == target:
            module.exit_json(changed=False, threat_intelligence=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyWafThreatenIntelligence, update_request(models, p))
        module.exit_json(changed=True, **(diff or {}), threat_intelligence=target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
