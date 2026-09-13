#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_internet_acl_rule_info
short_description: Gather Tencent Cloud Cloud Firewall internet border ACL rules
version_added: "1.4.0"
description:
  - Returns internet border access-control rules from Cloud Firewall.
options:
  rule_uuid:
    description: Optional rule UUID to return.
    type: int
  description:
    description: Optional rule description used to narrow returned rules.
    type: str
  page_size:
    description: Number of rules requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List Cloud Firewall internet border ACL rules
  susunola.tencentcloud.cfw_internet_acl_rule_info:
    region: ap-guangzhou

- name: Find a Cloud Firewall internet border ACL rule
  susunola.tencentcloud.cfw_internet_acl_rule_info:
    region: ap-guangzhou
    description: allow-trusted-https
'''

RETURN = r'''
rules:
  description: Matching internet border ACL rules.
  returned: always
  type: list
  elements: dict
rule:
  description: First matching rule when C(rule_uuid) or C(description) is supplied.
  returned: always
  type: dict
total_count:
  description: Number of rules reported by the API.
  returned: always
  type: int
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, offset, limit):
    request = models.DescribeAclRuleRequest()
    request.Offset = offset
    request.Limit = limit
    return request


def _matches(item, rule_uuid, description):
    if rule_uuid is not None and item.get("Uuid") != rule_uuid:
        return False
    if description and item.get("Description") != description:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "rule_uuid": {"type": "int"},
        "description": {"type": "str"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cfw.v20190904 import cfw_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cfw package is required.")

    client = cfw_client.CfwClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cfw.tencentcloudapi.com"),
    )
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_request(models, offset, limit),
        lambda request: sdk_call(module, client.DescribeAclRule, request),
        lambda response: getattr(response, "Data", None),
        lambda response: getattr(response, "Total", None),
    )
    item_set, total_count = paginator.fetch_all()
    rules = [
        item for item in (serialize_sdk_object(value) for value in item_set)
        if _matches(item, module.params["rule_uuid"], module.params["description"])
    ]
    selected = rules[0] if (module.params["rule_uuid"] is not None or module.params["description"]) and rules else None
    module.exit_json(changed=False, rules=rules, rule=selected, total_count=total_count, request_id=paginator.request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
