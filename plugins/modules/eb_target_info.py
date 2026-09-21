#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_target_info
short_description: Gather Tencent Cloud EventBridge targets
version_added: "1.4.0"
description: Lists all targets for an EventBridge rule with optional target identity filtering.
options:
  event_bus_id: {description: Event bus ID., type: str, required: true}
  rule_id: {description: EventBridge rule ID., type: str, required: true}
  target_id: {description: Target ID., type: str}
  target_type: {description: Target service type., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_target_info:
    region: ap-guangzhou
    event_bus_id: eb-l65vlc2
    rule_id: rule-xxxxxxxx
'''
RETURN = r'''
targets: {description: Matching targets., returned: always, type: list, elements: dict}
target: {description: The single matching target when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def list_request(models, event_bus_id, rule_id, offset=0, limit=100):
    request = models.ListTargetsRequest()
    request.EventBusId, request.RuleId = event_bus_id, rule_id
    request.Offset, request.Limit = offset, limit
    return request

def matches(value, target_id=None, target_type=None):
    return (target_id is None or value.get("TargetId") == target_id) and (target_type is None or value.get("Type") == target_type)

def run_module():
    module = TencentCloudModule(
        argument_spec={"event_bus_id": {"required": True}, "rule_id": {"required": True}, "target_id": {}, "target_type": {}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.eb.v20210416 import eb_client, models
        client = module.create_client(eb_client.EbClient, "eb.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.ListTargets, list_request(models, p["event_bus_id"], p["rule_id"], offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.Targets or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("target_id"), p.get("target_type")))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, targets=values, target=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
