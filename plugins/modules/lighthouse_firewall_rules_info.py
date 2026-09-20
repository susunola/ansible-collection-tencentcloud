#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_firewall_rules_info
short_description: Gather Tencent Cloud Lighthouse firewall rules
version_added: "1.4.0"
description: Returns the complete normalized firewall-rule set and concurrency version for a Lighthouse instance.
options:
  instance_id: {description: Lighthouse instance ID., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_firewall_rules_info:
    region: ap-guangzhou
    instance_id: lhins-xxxxxxxx
'''
RETURN = r'''
rules: {description: Complete normalized firewall-rule set., returned: always, type: list, elements: dict}
firewall_version: {description: Firewall rule-set concurrency version., returned: always, type: int}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_firewall_rules import describe

def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.lighthouse.v20200324 import lighthouse_client, models
        client = module.create_client(lighthouse_client.LighthouseClient, "lighthouse.tencentcloudapi.com")
        rules, version = describe(module, client, models, module.params["instance_id"])
        module.exit_json(changed=False, rules=rules, firewall_version=version)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
