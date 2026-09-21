#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gaap_real_server_info
short_description: Gather Tencent Cloud GAAP real servers
version_added: "1.4.0"
description: Lists GAAP real servers with complete pagination and optional ID or exact-address filtering.
options:
  real_server_id: {description: GAAP real server ID., type: str}
  address: {description: Exact real server IP address or domain., type: str}
  project_id: {description: Project ID, or -1 for all projects., type: int, default: -1}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gaap_real_server_info:
    region: ap-guangzhou
    address: 203.0.113.10
'''
RETURN = r'''
real_servers: {description: Matching GAAP real servers., returned: always, type: list, elements: dict}
real_server: {description: The single matching real server when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, project_id=-1, address=None, offset=0, limit=50):
    request = models.DescribeRealServersRequest()
    request.ProjectId, request.SearchValue = project_id, address
    request.Offset, request.Limit = offset, limit
    return request

def matches(value, real_server_id=None, address=None):
    return (real_server_id is None or value.get("RealServerId") == real_server_id) and (address is None or value.get("RealServerIP") == address)

def run_module():
    module = TencentCloudModule(
        argument_spec={"real_server_id": {}, "address": {}, "project_id": {"type": "int", "default": -1}},
        mutually_exclusive=[("real_server_id", "address")], supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.gaap.v20180529 import gaap_client, models
        client = module.create_client(gaap_client.GaapClient, "gaap.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeRealServers, describe_request(models, p["project_id"], p.get("address"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.RealServerSet or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("real_server_id"), p.get("address")))
            offset += len(page)
            if not page or offset >= int(response.TotalCount or 0):
                break
        module.exit_json(changed=False, real_servers=values, real_server=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
