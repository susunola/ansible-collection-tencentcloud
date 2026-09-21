#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gwlb_target_group_instances_info
short_description: Gather Tencent Cloud GWLB target group instances
version_added: "1.4.0"
description: Returns the complete normalized backend instance set of a GWLB target group.
options:
  target_group_id: {description: GWLB target group ID., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gwlb_target_group_instances_info:
    region: ap-guangzhou
    target_group_id: lbtg-xxxxxxxx
'''
RETURN = r'''
instances: {description: Complete normalized backend instance set., returned: always, type: list, elements: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, target_group_id, offset=0, limit=100):
    request = models.DescribeTargetGroupInstancesRequest()
    request.Offset, request.Limit = offset, limit
    item = models.Filter()
    item.Name, item.Values = "TargetGroupId", [target_group_id]
    request.Filters = [item]
    return request

def normalize(values):
    return sorted([{"ip": item.BindIP, "port": item.Port, "weight": item.Weight} for item in values], key=lambda item: (item["ip"], item["port"]))

def run_module():
    module = TencentCloudModule(argument_spec={"target_group_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.gwlb.v20240906 import gwlb_client, models
        client = module.create_client(gwlb_client.GwlbClient, "gwlb.tencentcloudapi.com")
        offset, instances, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeTargetGroupInstances, describe_request(models, module.params["target_group_id"], offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.TargetGroupInstanceSet or [])
            instances.extend(page)
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, instances=normalize(instances), request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
