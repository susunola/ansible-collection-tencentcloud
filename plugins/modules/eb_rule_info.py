#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_rule_info
short_description: Gather Tencent Cloud EventBridge rules
version_added: "1.4.0"
description: Lists EventBridge rules and resolves matches through the rule detail API.
options:
  event_bus_id: {description: Event bus ID., type: str, required: true}
  rule_id: {description: Rule ID., type: str}
  name: {description: Exact rule name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_rule_info:
    region: ap-guangzhou
    event_bus_id: eb-l65vlc2
    name: route-orders
'''
RETURN = r'''
rules: {description: Matching complete rules., returned: always, type: list, elements: dict}
rule: {description: The single matching rule when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.eb_rule import get_request

def list_request(models, event_bus_id, offset=0, limit=100):
    request = models.ListRulesRequest()
    request.EventBusId, request.Offset, request.Limit = event_bus_id, offset, limit
    return request

def run_module():
    module = TencentCloudModule(
        argument_spec={"event_bus_id": {"required": True}, "rule_id": {}, "name": {}},
        mutually_exclusive=[("rule_id", "name")], supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.eb.v20210416 import eb_client, models
        client = module.create_client(eb_client.EbClient, "eb.tencentcloudapi.com")
        offset, summaries, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.ListRules, list_request(models, p["event_bus_id"], offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.Rules or [])
            for item in page:
                value = item._serialize(allow_none=True)
                if (p.get("rule_id") is None or value.get("RuleId") == p["rule_id"]) and (p.get("name") is None or value.get("RuleName") == p["name"]):
                    summaries.append(value)
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        rules = []
        for summary in summaries:
            response = module.sdk_call(client.GetRule, get_request(models, p, summary["RuleId"]))
            request_id = getattr(response, "RequestId", None)
            value = response._serialize(allow_none=True)
            value.pop("RequestId", None)
            rules.append(value)
        module.exit_json(changed=False, rules=rules, rule=rules[0] if len(rules) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
