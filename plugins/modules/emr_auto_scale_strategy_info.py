#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: emr_auto_scale_strategy_info
short_description: Gather Tencent Cloud EMR automatic scaling strategies
version_added: "1.4.0"
description: Returns observable load-based or time-based automatic scaling strategies for an EMR cluster and scaling group.
options:
  cluster_id: {description: EMR cluster ID., type: str, required: true}
  group_id: {description: EMR scaling group ID., type: int}
  strategy_type: {description: Scaling strategy type., type: str, choices: [load, time], required: true}
  name: {description: Exact strategy name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.emr_auto_scale_strategy_info:
    region: ap-guangzhou
    cluster_id: emr-xxxxxxxx
    group_id: 2
    strategy_type: load
'''
RETURN = r'''
strategies: {description: Matching automatic scaling strategies., returned: always, type: list, elements: dict}
strategy: {description: The single matching strategy when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, cluster_id, group_id=None):
    request = models.DescribeAutoScaleStrategiesRequest()
    request.InstanceId, request.GroupId = cluster_id, group_id
    return request

def select(response, strategy_type):
    values = response.LoadAutoScaleStrategies if strategy_type == "load" else response.TimeBasedAutoScaleStrategies
    return [item._serialize(allow_none=True) for item in (values or [])]

def run_module():
    module = TencentCloudModule(argument_spec={
        "cluster_id": {"required": True}, "group_id": {"type": "int"},
        "strategy_type": {"choices": ["load", "time"], "required": True}, "name": {},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.emr.v20190103 import emr_client, models
        client = module.create_client(emr_client.EmrClient, "emr.tencentcloudapi.com")
        response = module.sdk_call(client.DescribeAutoScaleStrategies, describe_request(models, p["cluster_id"], p.get("group_id")))
        values = select(response, p["strategy_type"])
        if p.get("name"):
            values = [item for item in values if item.get("StrategyName") == p["name"]]
        module.exit_json(changed=False, strategies=values, strategy=values[0] if len(values) == 1 else None, request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
