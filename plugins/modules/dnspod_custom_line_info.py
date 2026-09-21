#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dnspod_custom_line_info
short_description: Gather DNSPod domain custom lines
version_added: "1.4.0"
description: Lists observable domain-scoped DNSPod custom routing lines with optional exact-name filtering.
options:
  domain: {description: Domain name., type: str}
  domain_id: {description: Domain ID, which takes precedence over domain., type: int}
  name: {description: Exact custom line name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dnspod_custom_line_info:
    domain: example.com
    name: office-network
'''
RETURN = r'''
custom_lines: {description: Matching custom lines., returned: always, type: list, elements: dict}
custom_line: {description: The single matching line when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_custom_line import describe_request

def run_module():
    module = TencentCloudModule(
        argument_spec={"domain": {}, "domain_id": {"type": "int"}, "name": {}}, required_one_of=[("domain", "domain_id")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.dnspod.v20210323 import dnspod_client, models
        client = module.create_client(dnspod_client.DnspodClient, "dnspod.tencentcloudapi.com")
        response = module.sdk_call(client.DescribeDomainCustomLineList, describe_request(models, p))
        lines = [item._serialize(allow_none=True) for item in (response.LineList or [])]
        if p.get("name"):
            lines = [item for item in lines if item.get("Name") == p["name"]]
        module.exit_json(changed=False, custom_lines=lines, custom_line=lines[0] if len(lines) == 1 else None, request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
