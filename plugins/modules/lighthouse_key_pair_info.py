#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_key_pair_info
short_description: Gather Tencent Cloud Lighthouse key pairs
version_added: "1.4.0"
description: Lists Lighthouse key pairs with optional ID or exact-name filtering, including observable instance associations.
options:
  key_id: {description: Key-pair ID., type: str}
  name: {description: Exact key-pair name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_key_pair_info:
    region: ap-guangzhou
    name: deploy-key
'''
RETURN = r'''
key_pairs: {description: Matching key pairs., returned: always, type: list, elements: dict}
key_pair: {description: The single matching key pair when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_key_pair import describe_request

def run_module():
    module = TencentCloudModule(argument_spec={"key_id": {}, "name": {}}, mutually_exclusive=[("key_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.lighthouse.v20200324 import lighthouse_client, models
        client = module.create_client(lighthouse_client.LighthouseClient, "lighthouse.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeKeyPairs, describe_request(models, p, offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.KeyPairSet or [])
            for item in page:
                value = item._serialize(allow_none=True)
                if p.get("name") is None or value.get("KeyName") == p["name"]:
                    values.append(value)
            offset += len(page)
            if not page or offset >= int(response.TotalCount or 0):
                break
        module.exit_json(changed=False, key_pairs=values, key_pair=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
