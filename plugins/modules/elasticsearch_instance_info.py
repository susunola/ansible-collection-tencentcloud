#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: elasticsearch_instance_info
short_description: Gather Tencent Cloud Elasticsearch instances
version_added: "1.4.0"
description: Lists Elasticsearch instances with complete pagination and optional ID or exact-name filtering.
options:
  instance_id: {description: Elasticsearch instance ID., type: str}
  name: {description: Exact instance name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.elasticsearch_instance_info:
    region: ap-guangzhou
    name: production-search
'''
RETURN = r'''
instances: {description: Matching Elasticsearch instances., returned: always, type: list, elements: dict}
instance: {description: The single matching instance when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, instance_id=None, name=None, offset=0, limit=100):
    request = models.DescribeInstancesRequest()
    request.Offset, request.Limit = offset, limit
    if instance_id:
        request.InstanceIds = [instance_id]
    elif name:
        request.InstanceNames = [name]
    return request

def matches(value, instance_id=None, name=None):
    return (instance_id is None or value.get("InstanceId") == instance_id) and (name is None or value.get("InstanceName") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"instance_id": {}, "name": {}}, mutually_exclusive=[("instance_id", "name")], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.es.v20180416 import es_client, models
        client = module.create_client(es_client.EsClient, "es.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeInstances, describe_request(models, p.get("instance_id"), p.get("name"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.InstanceList or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("instance_id"), p.get("name")))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, instances=values, instance=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
