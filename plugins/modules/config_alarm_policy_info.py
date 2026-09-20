#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: config_alarm_policy_info
short_description: Gather Tencent Cloud Config alarm policies
version_added: "1.4.0"
description: Lists observable Config non-compliance notification policies.
options:
  alarm_policy_id: {description: Alarm policy ID., type: int}
  name: {description: Exact alarm policy name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.config_alarm_policy_info:
    region: ap-guangzhou
    name: high-risk-compliance
'''
RETURN = r'''
alarm_policies: {description: Matching alarm policies., returned: always, type: list, elements: dict}
alarm_policy: {description: The single matching policy when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec


def list_request(models, offset=0, limit=100):
    request = models.ListAlarmPolicyRequest()
    request.Offset, request.Limit = offset, limit
    return request


def run_module():
    spec = tencentcloud_argument_spec()
    spec.update({"alarm_policy_id": {"type": "int"}, "name": {"type": "str"}})
    module = AnsibleModule(argument_spec=spec, mutually_exclusive=[("alarm_policy_id", "name")], supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    p = module.params
    client = config_client.ConfigClient(create_credential(module), p["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    offset, policies, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.ListAlarmPolicy, list_request(models, offset))
        request_id = getattr(response, "RequestId", None)
        page = list(getattr(response, "AlarmPolicyList", None) or [])
        for item in page:
            value = serialize_sdk_object(item)
            if (p.get("alarm_policy_id") is None or value.get("AlarmPolicyId") == p["alarm_policy_id"]) and (p.get("name") is None or value.get("Name") == p["name"]):
                policies.append(value)
        offset += len(page)
        if not page or offset >= int(getattr(response, "Total", 0) or 0):
            break
    module.exit_json(changed=False, alarm_policies=policies, alarm_policy=policies[0] if len(policies) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
