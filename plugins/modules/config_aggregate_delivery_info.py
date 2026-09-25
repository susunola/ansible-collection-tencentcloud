#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: config_aggregate_delivery_info
short_description: Gather Tencent Cloud Config aggregate delivery settings
version_added: "1.4.0"
description: Returns the complete observable delivery configuration for one Config account aggregator.
options:
  account_group_id:
    description:
      - Config aggregator account-group ID.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.config_aggregate_delivery_info:
    region: ap-guangzhou
    account_group_id: ag-xxxxxxxx
'''
RETURN = r'''
deliveries: {description: Aggregate delivery configuration as a single-element list., returned: always, type: list, elements: dict}
delivery: {description: Aggregate Config delivery configuration., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, account_group_id):
    request = models.DescribeAggregateConfigDeliverRequest()
    request.AccountGroupId = account_group_id
    return request


def run_module():
    spec = tencentcloud_argument_spec()
    spec.update({"account_group_id": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=spec, supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    p = module.params
    client = config_client.ConfigClient(create_credential(module), p["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeAggregateConfigDeliver, build_request(models, p["account_group_id"]))
    delivery = serialize_sdk_object(response)
    delivery.pop("RequestId", None)
    module.exit_json(changed=False, deliveries=[delivery], delivery=delivery, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
