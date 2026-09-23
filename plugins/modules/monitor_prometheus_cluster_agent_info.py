#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_prometheus_cluster_agent_info
short_description: Gather Managed Prometheus associated clusters
version_added: "1.4.0"
description: Returns Kubernetes clusters bound as collection agents to a Managed Prometheus instance.
options:
  instance_id: {description: Prometheus instance ID., type: str, required: true}
  cluster_id: {description: Exact bound cluster ID., type: str}
  cluster_type: {description: Exact bound cluster type., type: str}
  page_size: {description: Number of agents requested per API call., type: int, default: 100}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_cluster_agent_info:
    region: ap-guangzhou
    instance_id: prom-xxxxxxxx
'''
RETURN = r'''
agents: {description: Matching associated clusters., returned: always, type: list, elements: dict}
total_count: {description: Number of matching associated clusters., returned: always, type: int}
request_id: {description: Request ID of the last API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, params, offset):
    request = models.DescribePrometheusClusterAgentsRequest()
    request.InstanceId = params["instance_id"]
    request.ClusterIds = [params["cluster_id"]] if params.get("cluster_id") else None
    request.ClusterTypes = [params["cluster_type"]] if params.get("cluster_type") else None
    request.Offset = offset
    request.Limit = params["page_size"]
    return request


def gather(module, client, models, params):
    agents, offset, request_id = [], 0, None
    while True:
        response = module.sdk_call(client.DescribePrometheusClusterAgents,
                                   build_request(models, params, offset))
        page = list(response.Agents or [])
        request_id = getattr(response, "RequestId", None)
        for item in page:
            value = item._serialize(allow_none=True)
            if params.get("cluster_id") and value.get("ClusterId") != params["cluster_id"]:
                continue
            if params.get("cluster_type") and value.get("ClusterType") != params["cluster_type"]:
                continue
            agents.append(value)
        offset += len(page)
        total = getattr(response, "Total", None)
        if not page or (total is not None and offset >= total) or (total is None and len(page) < params["page_size"]):
            break
    return agents, request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "cluster_id": {}, "cluster_type": {},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if not 1 <= params["page_size"] <= 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        agents, request_id = gather(module, client, models, params)
        module.exit_json(changed=False, agents=agents,
                         total_count=len(agents), request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
