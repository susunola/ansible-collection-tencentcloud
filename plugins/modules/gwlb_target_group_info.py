#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gwlb_target_group_info
short_description: Gather Tencent Cloud Gateway Load Balancer target groups
version_added: "1.4.0"
description: Lists GWLB target groups with complete pagination and optional ID or exact-name filtering.
options:
  target_group_id: {description: Target group ID., type: str}
  name: {description: Exact target group name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gwlb_target_group_info:
    region: ap-guangzhou
    name: inspection-appliances
'''
RETURN = r'''
target_groups: {description: Matching target groups., returned: always, type: list, elements: dict}
target_group: {description: The single matching group when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, target_group_id=None, offset=0, limit=100):
    request = models.DescribeTargetGroupsRequest()
    request.Offset, request.Limit = offset, limit
    if target_group_id:
        request.TargetGroupIds = [target_group_id]
    return request

def matches(value, target_group_id=None, name=None):
    return (target_group_id is None or value.get("TargetGroupId") == target_group_id) and (name is None or value.get("TargetGroupName") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"target_group_id": {}, "name": {}}, mutually_exclusive=[("target_group_id", "name")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.gwlb.v20240906 import gwlb_client, models
        client = module.create_client(gwlb_client.GwlbClient, "gwlb.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeTargetGroups, describe_request(models, p.get("target_group_id"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.TargetGroupSet or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("target_group_id"), p.get("name")))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, target_groups=values, target_group=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
