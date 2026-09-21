#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gaap_listener_real_servers_info
short_description: Gather Tencent Cloud GAAP listener origin bindings
version_added: "1.4.0"
description: Returns the complete normalized origin binding set of a GAAP TCP or UDP listener.
options:
  listener_id: {description: GAAP TCP or UDP listener ID., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gaap_listener_real_servers_info:
    region: ap-guangzhou
    listener_id: listener-xxxxxxxx
'''
RETURN = r'''
real_servers: {description: Complete normalized listener binding set., returned: always, type: list, elements: dict}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_listener_real_servers import describe

def run_module():
    module = TencentCloudModule(argument_spec={"listener_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.gaap.v20180529 import gaap_client, models
        client = module.create_client(gaap_client.GaapClient, "gaap.tencentcloudapi.com")
        values = describe(module, client, models, module.params["listener_id"])
        module.exit_json(changed=False, real_servers=values)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
