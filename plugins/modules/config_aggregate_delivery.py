#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_aggregate_delivery
short_description: Manage Tencent Cloud Config cross-account aggregate delivery
version_added: "0.14.0"
description: Reconciles aggregate Config changes and resource inventories to COS or CLS.
options:
  account_group_id: {type: str, required: true, description: Config aggregator account-group ID.}
  enabled: {type: bool, default: true, description: Whether aggregate delivery is enabled.}
  name: {type: str, required: true, description: Delivery service name.}
  target_arn: {type: str, required: true, description: Six-part COS or CLS target resource ARN.}
  prefix: {type: str, default: config, description: Delivery prefix.}
  delivery_type: {type: str, choices: [COS, CLS], required: true, description: Destination service type.}
  delivery_uin: {type: int, default: 0, description: Delegated administrator destination UIN or zero for the administrator account.}
  content_type: {type: int, choices: [1, 2, 3], default: 3, description: "One for changes, two for resource lists or three for both."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Deliver organization-wide Config inventory to COS
  susunola.tencentcloud.config_aggregate_delivery:
    region: ap-guangzhou
    account_group_id: ag-xxxxxxxx
    name: organization-archive
    target_arn: qcs::cos:ap-guangzhou:100000000001:prefix/1250000000/config-org
    delivery_type: COS
'''

RETURN = r'''delivery: {description: Aggregate Config delivery metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client
    return models, config_client


def describe_request(models, group_id):
    request = models.DescribeAggregateConfigDeliverRequest(); request.AccountGroupId = group_id; return request


def update_request(models, p):
    request = models.UpdateAggregateConfigDeliverRequest()
    request.Status, request.AccountGroupId, request.DeliverName = int(p["enabled"]), p["account_group_id"], p["name"]
    request.TargetArn, request.DeliverPrefix, request.DeliverType = p["target_arn"], p["prefix"], p["delivery_type"]
    request.DeliverUin, request.DeliverContentType = p["delivery_uin"], p["content_type"]
    return request


def find_delivery(module, client, models, group_id):
    response = module.sdk_call(client.DescribeAggregateConfigDeliver, describe_request(models, group_id)); value = response._serialize(allow_none=True); value.pop("RequestId", None); return value


def run_module():
    module = TencentCloudModule(argument_spec={"account_group_id": {"required": True}, "enabled": {"type": "bool", "default": True}, "name": {"required": True}, "target_arn": {"required": True}, "prefix": {"default": "config"}, "delivery_type": {"choices": ["COS", "CLS"], "required": True}, "delivery_uin": {"type": "int", "default": 0}, "content_type": {"type": "int", "choices": [1, 2, 3], "default": 3}}, supports_check_mode=True)
    p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_delivery(module, client, models, p["account_group_id"])
        desired = {"Status": int(p["enabled"]), "DeliverName": p["name"], "TargetArn": p["target_arn"], "DeliverPrefix": p["prefix"], "DeliverType": p["delivery_type"], "DeliverUin": p["delivery_uin"], "DeliverContentType": p["content_type"]}
        before = {key: current.get(key) for key in desired}
        if before == desired: module.exit_json(changed=False, delivery=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            module.sdk_call(client.UpdateAggregateConfigDeliver, update_request(models, p)); current = find_delivery(module, client, models, p["account_group_id"])
        module.exit_json(changed=True, **(diff or {}), delivery=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
