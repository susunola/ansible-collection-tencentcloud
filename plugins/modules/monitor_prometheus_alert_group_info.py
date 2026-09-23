#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_prometheus_alert_group_info
short_description: Gather Managed Prometheus alert groups
version_added: "1.4.0"
description: Returns the alert groups and rules of a Managed Prometheus instance.
options:
  instance_id: {description: Prometheus instance ID., type: str, required: true}
  group_id: {description: Exact alert-group ID., type: str}
  name: {description: Exact alert-group name; filtering is performed locally because the API uses substring matching., type: str}
  page_size: {description: Number of groups requested per API call., type: int, default: 100}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_alert_group_info:
    region: ap-guangzhou
    instance_id: prom-xxxxxxxx
'''
RETURN = r'''
alert_groups: {description: Matching alert groups, including rules and receivers., returned: always, type: list, elements: dict}
total_count: {description: Number of matching groups., returned: always, type: int}
request_id: {description: Request ID of the last API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, params, offset):
    request = models.DescribePrometheusAlertGroupsRequest()
    request.InstanceId = params["instance_id"]
    request.GroupId = params.get("group_id")
    request.GroupName = params.get("name") if not request.GroupId else None
    request.Offset = offset
    request.Limit = params["page_size"]
    return request


def gather(module, client, models, params):
    groups, offset, request_id = [], 0, None
    while True:
        response = module.sdk_call(client.DescribePrometheusAlertGroups,
                                   build_request(models, params, offset))
        page = list(response.AlertGroupSet or [])
        request_id = getattr(response, "RequestId", None)
        for item in page:
            value = item._serialize(allow_none=True)
            if (params.get("group_id") and value.get("GroupId") != params["group_id"]):
                continue
            if (params.get("name") and value.get("GroupName") != params["name"]):
                continue
            groups.append(value)
        offset += len(page)
        total = getattr(response, "TotalCount", None)
        if not page or (total is not None and offset >= total) or (total is None and len(page) < params["page_size"]):
            break
    return groups, request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "group_id": {}, "name": {},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if not 1 <= params["page_size"] <= 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        groups, request_id = gather(module, client, models, params)
        module.exit_json(changed=False, alert_groups=groups,
                         total_count=len(groups), request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
