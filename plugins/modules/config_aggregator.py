#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: config_aggregator
short_description: Manage creation of Tencent Cloud Config account aggregators
version_added: "0.14.0"
description:
  - Creates and discovers cross-account Config aggregators.
  - The current Config API exposes no aggregator update or delete operation;
    name, type and account membership are therefore treated as immutable.
options:
  account_group_id: {type: str, description: Existing aggregator account-group ID; preferred for lookup.}
  name: {type: str, required: true, description: "Aggregator name, also used for lookup."}
  description: {type: str, default: '', description: Aggregator description.}
  aggregator_type: {type: str, required: true, description: Aggregator type accepted by Tencent Cloud Config.}
  accounts:
    description: Exact immutable member-account set used at creation.
    type: list
    elements: dict
    default: []
    suboptions:
      member_uin: {type: int, required: true, description: Member account UIN.}
      member_name: {type: str, required: true, description: Member account display name.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Create an organization Config aggregator
  susunola.tencentcloud.config_aggregator:
    region: ap-guangzhou
    name: organization-security
    aggregator_type: CUSTOM
    accounts:
      - member_uin: 100000000002
        member_name: production
"""

RETURN = r"""aggregator: {description: Config aggregator metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client

    return models, config_client


def list_request(models, offset=0):
    request = models.ListAggregatorsRequest()
    request.Offset, request.Limit = offset, 100
    return request


def describe_request(models, group_id):
    request = models.DescribeAggregatorRequest()
    request.AccountGroupId = group_id
    return request


def create_request(models, p):
    request = models.CreateAggregatorRequest()
    request.Name, request.Description, request.Type = p["name"], p["description"], p["aggregator_type"]
    request.AggregatorAccounts = []
    for value in p["accounts"]:
        item = models.AggregatorAccount()
        item.MemberUin, item.MemberName = value["member_uin"], value["member_name"]
        request.AggregatorAccounts.append(item)
    return request


def _accounts(values):
    return sorted(
        (
            {"MemberUin": item.get("MemberUin") or item.get("member_uin"), "MemberName": item.get("MemberName") or item.get("member_name")}
            for item in values or []
        ),
        key=lambda item: item["MemberUin"],
    )


def find_aggregator(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.ListAggregators, list_request(models, offset))
        values = list(response.Items or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("account_group_id") and item.get("AccountGroupId") == p["account_group_id"]:
                matches.append(item)
            elif not p.get("account_group_id") and item.get("Name") == p["name"]:
                matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Config aggregators matched; specify account_group_id")
    if not matches:
        return None
    response = module.sdk_call(client.DescribeAggregator, describe_request(models, matches[0]["AccountGroupId"]))
    value = response._serialize(allow_none=True)
    value.pop("RequestId", None)
    value["AccountGroupId"] = matches[0]["AccountGroupId"]
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "account_group_id": {},
            "name": {"required": True},
            "description": {"default": ""},
            "aggregator_type": {"required": True},
            "accounts": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {"member_uin": {"type": "int", "required": True}, "member_name": {"required": True}},
            },
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_aggregator(module, client, models, p)
        desired = {"Name": p["name"], "Description": p["description"], "Type": p["aggregator_type"], "AggregatorAccounts": _accounts(p["accounts"])}
        if current:
            before = {
                "Name": current.get("Name"),
                "Description": current.get("Description") or "",
                "Type": current.get("Type"),
                "AggregatorAccounts": _accounts(current.get("AggregatorAccounts")),
            }
            if before == desired:
                module.exit_json(changed=False, aggregator=current)
            module.fail_json(
                msg="Config aggregator attributes are immutable because the API exposes no update or delete operation", aggregator=current, desired=desired
            )
        diff = maybe_diff(module, None, desired)
        if not module.check_mode:
            p["account_group_id"] = module.sdk_call(client.CreateAggregator, create_request(models, p)).AccountGroupId
            current = find_aggregator(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), aggregator=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
