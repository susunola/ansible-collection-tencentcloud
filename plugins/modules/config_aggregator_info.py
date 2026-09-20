#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_aggregator_info
short_description: Gather Tencent Cloud Config aggregators
version_added: "1.4.0"
description:
  - Lists Config aggregators and resolves matches to their complete account membership configuration.
  - Results can be filtered by account-group ID or exact name.
options:
  account_group_id: {description: Aggregator account-group ID., type: str}
  name: {description: Exact aggregator name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Read an organization aggregator
  susunola.tencentcloud.config_aggregator_info:
    region: ap-guangzhou
    name: organization-security
'''
RETURN = r'''
aggregators: {description: Matching complete aggregator configurations., returned: always, type: list, elements: dict}
aggregator: {description: The single matching aggregator when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec


def list_request(models, offset=0, limit=100):
    request = models.ListAggregatorsRequest()
    request.Offset, request.Limit = offset, limit
    return request


def detail_request(models, account_group_id):
    request = models.DescribeAggregatorRequest()
    request.AccountGroupId = account_group_id
    return request


def run_module():
    spec = tencentcloud_argument_spec()
    spec.update({"account_group_id": {"type": "str"}, "name": {"type": "str"}})
    module = AnsibleModule(argument_spec=spec, mutually_exclusive=[("account_group_id", "name")], supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    p = module.params
    client = config_client.ConfigClient(create_credential(module), p["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    offset, summaries, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.ListAggregators, list_request(models, offset))
        request_id = getattr(response, "RequestId", None)
        page = list(getattr(response, "Items", None) or [])
        for item in page:
            if (p.get("account_group_id") is None or item.AccountGroupId == p["account_group_id"]) and (p.get("name") is None or item.Name == p["name"]):
                summaries.append(item)
        offset += len(page)
        if not page or offset >= int(getattr(response, "Total", 0) or 0):
            break
    aggregators = []
    for summary in summaries:
        response = sdk_call(module, client.DescribeAggregator, detail_request(models, summary.AccountGroupId))
        request_id = getattr(response, "RequestId", None)
        value = serialize_sdk_object(response)
        value.pop("RequestId", None)
        value["AccountGroupId"] = summary.AccountGroupId
        aggregators.append(value)
    module.exit_json(changed=False, aggregators=aggregators, aggregator=aggregators[0] if len(aggregators) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
