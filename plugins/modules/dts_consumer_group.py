#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: dts_consumer_group
short_description: Manage Tencent Cloud DTS consumer groups
version_added: "0.14.0"
description: Creates, updates and deletes Kafka consumer groups for DTS data subscriptions.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  subscribe_id: {description: DTS subscription instance ID., type: str, required: true}
  consumer_group_name: {description: Consumer group suffix or full generated name., type: str, required: true}
  account_name: {description: Consumer account suffix or full generated name., type: str, required: true}
  password: {description: Password used only when creating the consumer group., type: str}
  description: {description: Consumer group description., type: str, default: ''}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dts_consumer_group:
    subscribe_id: subs-xxxxxxxx
    consumer_group_name: analytics
    account_name: analytics-reader
    password: secure-password
    description: Analytics consumers
'''
RETURN = r'''
consumer_group: {description: DTS consumer group metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_dts():
    from tencentcloud.dts.v20211206 import dts_client, models
    return models, dts_client


def build_describe_request(models, subscribe_id, offset=0):
    request = models.DescribeConsumerGroupsRequest()
    request.SubscribeId, request.Offset, request.Limit = subscribe_id, offset, 100
    return request


def build_create_request(models, params):
    request = models.CreateConsumerGroupRequest()
    request.SubscribeId = params["subscribe_id"]
    request.ConsumerGroupName, request.AccountName = params["consumer_group_name"], params["account_name"]
    request.Password, request.Description = params["password"], params["description"]
    return request


def build_update_request(models, subscribe_id, consumer_group_name, account_name, description):
    request = models.ModifyConsumerGroupDescriptionRequest()
    request.SubscribeId, request.ConsumerGroupName = subscribe_id, consumer_group_name
    request.AccountName, request.Description = account_name, description
    return request


def build_delete_request(models, subscribe_id, consumer_group_name, account_name):
    request = models.DeleteConsumerGroupRequest()
    request.SubscribeId, request.ConsumerGroupName = subscribe_id, consumer_group_name
    request.AccountName = account_name
    return request


def _name_matches(actual, requested, prefix):
    return actual == requested or actual == "%s-%s" % (prefix, requested) or actual.endswith("-%s" % requested)


def find_group(module, client, models, subscribe_id, consumer_group_name, account_name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeConsumerGroups, build_describe_request(models, subscribe_id, offset))
        items = list(response.Items or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if _name_matches(value.get("ConsumerGroupName", ""), consumer_group_name, "consumer-grp-%s" % subscribe_id) and _name_matches(value.get("Account", ""), account_name, "account-%s" % subscribe_id):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DTS consumer groups match the requested names", consumer_group_name=consumer_group_name, account_name=account_name)
    return matches[0] if matches else None


def _desired(params):
    return {"Description": params["description"]}


def wait_for_group(module, client, models, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    p = module.params
    while True:
        current = find_group(module, client, models, p["subscribe_id"], p["consumer_group_name"], p["account_name"])
        if absent and current is None:
            return None
        if not absent and current and current.get("Description") == desired["Description"]:
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for DTS consumer group convergence", consumer_group=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "subscribe_id": {"type": "str", "required": True}, "consumer_group_name": {"type": "str", "required": True}, "account_name": {"type": "str", "required": True}, "password": {"type": "str", "no_log": True}, "description": {"type": "str", "default": ""}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_dts()
    client = module.create_client(client_module.DtsClient, "dts.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, p["subscribe_id"], p["consumer_group_name"], p["account_name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, consumer_group=None, msg="DTS consumer group is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), consumer_group=current, msg="Would delete DTS consumer group")
            module.sdk_call(client.DeleteConsumerGroup, build_delete_request(models, p["subscribe_id"], current["ConsumerGroupName"], current["Account"]))
            wait_for_group(module, client, models, absent=True)
            module.exit_json(changed=True, **(diff or {}), consumer_group=None, msg="DTS consumer group deleted")
        desired = _desired(p)
        if current is None:
            if not p["password"]:
                module.fail_json(msg="password is required when creating a DTS consumer group")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), consumer_group=None, msg="Would create DTS consumer group")
            module.sdk_call(client.CreateConsumerGroup, build_create_request(models, p))
            current = wait_for_group(module, client, models, desired)
            module.exit_json(changed=True, **(diff or {}), consumer_group=current, msg="DTS consumer group created")
        if current.get("Description") == desired["Description"]:
            module.exit_json(changed=False, consumer_group=current, msg="DTS consumer group is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), consumer_group=current, msg="Would update DTS consumer group")
        module.sdk_call(client.ModifyConsumerGroupDescription, build_update_request(models, p["subscribe_id"], current["ConsumerGroupName"], current["Account"], p["description"]))
        current = wait_for_group(module, client, models, desired)
        module.exit_json(changed=True, **(diff or {}), consumer_group=current, msg="DTS consumer group updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
