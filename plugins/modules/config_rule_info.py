#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_rule_info
short_description: Gather Tencent Cloud Config compliance rules
version_added: "1.4.0"
description:
  - Reads a Config rule by ID or lists rules with an optional exact-name filter.
  - List results are resolved through the detail API so trigger and scope configuration is observable.
options:
  rule_id: {description: Config rule ID., type: str}
  name: {description: Exact Config rule name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Read a rule by ID
  susunola.tencentcloud.config_rule_info:
    region: ap-guangzhou
    rule_id: rule-xxxxxxxx

- name: List rules named require-encrypted-disks
  susunola.tencentcloud.config_rule_info:
    region: ap-guangzhou
    name: require-encrypted-disks
'''
RETURN = r'''
rules: {description: Matching complete compliance rules., returned: always, type: list, elements: dict}
rule: {description: The single matching rule when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec


def list_request(models, name=None, offset=0, limit=200):
    request = models.ListConfigRulesRequest()
    request.Offset, request.Limit = offset, limit
    request.RuleName = name
    return request


def detail_request(models, rule_id):
    request = models.DescribeConfigRuleRequest()
    request.RuleId = rule_id
    return request


def read_detail(module, client, models, rule_id):
    response = sdk_call(module, client.DescribeConfigRule, detail_request(models, rule_id))
    value = getattr(response, "ConfigRule", None)
    return serialize_sdk_object(value) if value else None, getattr(response, "RequestId", None)


def run_module():
    spec = tencentcloud_argument_spec()
    spec.update({"rule_id": {"type": "str"}, "name": {"type": "str"}})
    module = AnsibleModule(argument_spec=spec, mutually_exclusive=[("rule_id", "name")], supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    p = module.params
    client = config_client.ConfigClient(create_credential(module), p["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    if p.get("rule_id"):
        try:
            rule, request_id = read_detail(module, client, models, p["rule_id"])
        except Exception as exc:
            if is_not_found(exc):
                module.exit_json(changed=False, rules=[], rule=None, request_id=getattr(exc, "request_id", None))
            raise
        module.exit_json(changed=False, rules=[rule] if rule else [], rule=rule, request_id=request_id)

    offset, summaries, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.ListConfigRules, list_request(models, p.get("name"), offset))
        request_id = getattr(response, "RequestId", None)
        page = list(getattr(response, "Items", None) or [])
        summaries.extend(item for item in page if p.get("name") is None or item.RuleName == p["name"])
        offset += len(page)
        if not page or offset >= int(getattr(response, "Total", 0) or 0):
            break
    rules = []
    for summary in summaries:
        rule, request_id = read_detail(module, client, models, summary.ConfigRuleId)
        if rule:
            rules.append(rule)
    module.exit_json(changed=False, rules=rules, rule=rules[0] if len(rules) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
