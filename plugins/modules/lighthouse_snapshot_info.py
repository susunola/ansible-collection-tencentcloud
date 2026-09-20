#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_snapshot_info
short_description: Gather Tencent Cloud Lighthouse snapshots
version_added: "1.4.0"
description: Lists Lighthouse snapshots with optional ID, instance or exact-name filtering.
options:
  snapshot_id: {description: Snapshot ID., type: str}
  instance_id: {description: Source Lighthouse instance ID., type: str}
  name: {description: Exact snapshot name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_snapshot_info:
    region: ap-guangzhou
    instance_id: lhins-xxxxxxxx
'''
RETURN = r'''
snapshots: {description: Matching snapshots., returned: always, type: list, elements: dict}
snapshot: {description: The single matching snapshot when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_snapshot import describe_request

def run_module():
    module = TencentCloudModule(argument_spec={"snapshot_id": {}, "instance_id": {}, "name": {}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.lighthouse.v20200324 import lighthouse_client, models
        client = module.create_client(lighthouse_client.LighthouseClient, "lighthouse.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeSnapshots, describe_request(models, p, offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.SnapshotSet or [])
            values.extend(item._serialize(allow_none=True) for item in page)
            offset += len(page)
            if not page or offset >= int(response.TotalCount or 0):
                break
        module.exit_json(changed=False, snapshots=values, snapshot=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
