#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: emr_cluster_info
short_description: Gather Tencent Cloud EMR clusters
version_added: "1.4.0"
description: Lists EMR clusters with complete pagination and optional cluster ID or exact-name filtering.
options:
  cluster_id: {description: EMR cluster ID., type: str}
  name: {description: Exact cluster name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.emr_cluster_info:
    region: ap-guangzhou
    name: analytics
'''
RETURN = r'''
clusters: {description: Matching EMR clusters., returned: always, type: list, elements: dict}
cluster: {description: The single matching cluster when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.emr_cluster import describe_request

def matches(value, cluster_id=None, name=None):
    return (cluster_id is None or value.get("ClusterId") == cluster_id) and (name is None or value.get("ClusterName") == name)

def run_module():
    module = TencentCloudModule(argument_spec={"cluster_id": {}, "name": {}}, mutually_exclusive=[("cluster_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.emr.v20190103 import emr_client, models
        client = module.create_client(emr_client.EmrClient, "emr.tencentcloudapi.com")
        offset, clusters, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.DescribeInstances, describe_request(models, p.get("cluster_id"), offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.ClusterList or [])
            clusters.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("cluster_id"), p.get("name")))
            offset += len(page)
            if not page or offset >= int(response.TotalCnt or 0):
                break
        module.exit_json(changed=False, clusters=clusters, cluster=clusters[0] if len(clusters) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
