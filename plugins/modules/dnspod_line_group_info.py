#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dnspod_line_group_info
short_description: Gather DNSPod custom line groups
version_added: "1.4.0"
description: Lists domain-scoped DNSPod custom line groups with complete pagination and optional exact identity filtering.
options:
  domain: {description: Domain name., type: str}
  domain_id: {description: Domain ID, which takes precedence over domain., type: int}
  line_group_id: {description: Line group ID., type: int}
  name: {description: Exact line group name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dnspod_line_group_info:
    domain: example.com
'''
RETURN = r'''
line_groups: {description: Matching custom line groups., returned: always, type: list, elements: dict}
line_group: {description: The single matching group when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_line_group import describe_request

def matches(value, group_id=None, name=None):
    return (group_id is None or value.get("Id") == group_id) and (name is None or value.get("Name") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"domain": {}, "domain_id": {"type": "int"}, "line_group_id": {"type": "int"}, "name": {}},
        required_one_of=[("domain", "domain_id")], mutually_exclusive=[("line_group_id", "name")], supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.dnspod.v20210323 import dnspod_client, models
        client = module.create_client(dnspod_client.DnspodClient, "dnspod.tencentcloudapi.com")
        offset, groups, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeLineGroupList, describe_request(models, p, offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.LineGroups or [])
            groups.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("line_group_id"), p.get("name")))
            offset += len(page)
            total = int(getattr(response.Info, "Total", 0) or 0) if response.Info else 0
            if not page or offset >= total:
                break
        module.exit_json(changed=False, line_groups=groups, line_group=groups[0] if len(groups) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
