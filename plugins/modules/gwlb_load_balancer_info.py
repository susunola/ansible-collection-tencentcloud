#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gwlb_load_balancer_info
short_description: Gather Tencent Cloud Gateway Load Balancers
version_added: "1.4.0"
description: Lists Gateway Load Balancers with complete pagination and optional ID or exact-name filtering.
options:
  load_balancer_id: {description: Gateway Load Balancer ID., type: str}
  name: {description: Exact Gateway Load Balancer name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gwlb_load_balancer_info:
    region: ap-guangzhou
    name: inspection-gwlb
'''
RETURN = r'''
load_balancers: {description: Matching Gateway Load Balancers., returned: always, type: list, elements: dict}
load_balancer: {description: The single matching load balancer when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, load_balancer_id=None, offset=0, limit=100):
    request = models.DescribeGatewayLoadBalancersRequest()
    request.Offset, request.Limit = offset, limit
    if load_balancer_id:
        request.LoadBalancerIds = [load_balancer_id]
    return request

def matches(value, load_balancer_id=None, name=None):
    return (load_balancer_id is None or value.get("LoadBalancerId") == load_balancer_id) and (name is None or value.get("LoadBalancerName") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"load_balancer_id": {}, "name": {}}, mutually_exclusive=[("load_balancer_id", "name")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.gwlb.v20240906 import gwlb_client, models
        client = module.create_client(gwlb_client.GwlbClient, "gwlb.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeGatewayLoadBalancers, describe_request(models, p.get("load_balancer_id"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.LoadBalancerSet or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("load_balancer_id"), p.get("name")))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, load_balancers=values, load_balancer=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
