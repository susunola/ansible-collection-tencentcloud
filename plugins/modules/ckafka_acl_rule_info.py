#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_acl_rule_info
short_description: Gather a Tencent Cloud CKafka ACL rule
version_added: "1.4.0"
description: Returns an ACL rule using the exact identity accepted by C(ckafka_acl_rule).
options:
  instance_id: {description: CKafka instance ID., type: str, required: true}
  name: {description: ACL rule name., type: str, required: true}
  pattern_type: {description: Prefix matching or preset policy., type: str, choices: [PREFIXED, PRESET], default: PREFIXED}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read an ACL rule
  susunola.tencentcloud.ckafka_acl_rule_info:
    region: ap-guangzhou
    instance_id: ckafka-xxxxxxxx
    name: orders-producers
    pattern_type: PREFIXED
'''

RETURN = r'''
acl_rules: {description: Matching ACL rules., returned: always, type: list, elements: dict}
acl_rule: {description: The matching ACL rule or null., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)


def build_request(models, instance_id, name, pattern_type):
    request = models.DescribeAclRuleRequest()
    request.InstanceId, request.RuleName, request.PatternType = instance_id, name, pattern_type
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "name": {"type": "str", "required": True},
        "pattern_type": {"type": "str", "choices": ["PREFIXED", "PRESET"], "default": "PREFIXED"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")
    p = module.params
    client = ckafka_client.CkafkaClient(create_credential(module), p["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeAclRule, build_request(models, p["instance_id"], p["name"], p["pattern_type"]))
    result = getattr(response, "Result", None)
    rules = [serialize_sdk_object(item) for item in (getattr(result, "AclRuleList", None) or [])]
    rules = [item for item in rules if item.get("RuleName") == p["name"]]
    module.exit_json(changed=False, acl_rules=rules, acl_rule=rules[0] if rules else None, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
