#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dnspod_domain_info
short_description: Gather Tencent Cloud DNSPod domains
version_added: "1.4.0"
description: Lists DNSPod domains with complete pagination and optional domain ID or exact-name filtering.
options:
  domain_id: {description: DNSPod domain ID., type: int}
  name: {description: Exact domain name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dnspod_domain_info:
    name: example.com
'''
RETURN = r'''
domains: {description: Matching DNSPod domains., returned: always, type: list, elements: dict}
domain: {description: The single matching domain when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def list_request(models, name=None, offset=0, limit=100):
    request = models.DescribeDomainListRequest()
    request.Type, request.Offset, request.Limit = "ALL", offset, limit
    request.Keyword = name
    return request

def matches(value, domain_id=None, name=None):
    return (domain_id is None or value.get("DomainId") == domain_id) and (name is None or value.get("Name") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"domain_id": {"type": "int"}, "name": {}}, mutually_exclusive=[("domain_id", "name")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.dnspod.v20210323 import dnspod_client, models
        client = module.create_client(dnspod_client.DnspodClient, "dnspod.tencentcloudapi.com")
        offset, domains, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeDomainList, list_request(models, p.get("name"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.DomainList or [])
            domains.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("domain_id"), p.get("name")))
            offset += len(page)
            total = int((response.DomainCountInfo.DomainTotal if response.DomainCountInfo else 0) or 0)
            if not page or offset >= total:
                break
        module.exit_json(changed=False, domains=domains, domain=domains[0] if len(domains) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
