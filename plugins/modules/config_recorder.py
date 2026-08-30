#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_recorder
short_description: Manage Tencent Cloud Config resource recorder
version_added: "0.14.0"
description: Enables or disables the Config recorder and reconciles the exact monitored resource-type set.
options:
  enabled: {type: bool, default: true, description: Whether resource configuration recording is enabled.}
  resource_types: {type: list, elements: str, default: [], description: Exact set of Tencent Cloud resource-type identifiers to record.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Record core infrastructure resource types
  susunola.tencentcloud.config_recorder:
    region: ap-guangzhou
    enabled: true
    resource_types:
      - QCS::CVM::Instance
      - QCS::VPC::VPC
      - QCS::CBS::Disk
'''

RETURN = r'''recorder: {description: Config recorder state and monitored resource types., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client
    return models, config_client


def describe_request(models):
    return models.DescribeConfigRecorderRequest()


def update_request(models, resource_types):
    request = models.UpdateConfigRecorderRequest(); request.ResourceTypes = sorted(set(resource_types)); return request


def open_request(models):
    return models.OpenConfigRecorderRequest()


def close_request(models):
    return models.CloseConfigRecorderRequest()


def find_recorder(module, client, models):
    response = module.sdk_call(client.DescribeConfigRecorder, describe_request(models))
    value = response._serialize(allow_none=True); value.pop("RequestId", None)
    value["ResourceTypes"] = sorted(set(item.ResourceType for item in response.Items or [] if item.ResourceType))
    return value


def run_module():
    module = TencentCloudModule(argument_spec={"enabled": {"type": "bool", "default": True}, "resource_types": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True)
    p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_recorder(module, client, models)
        before = {"Enabled": int(current.get("Status") or 0) == 1, "ResourceTypes": current["ResourceTypes"]}
        desired = {"Enabled": p["enabled"], "ResourceTypes": sorted(set(p["resource_types"]))}
        if before == desired: module.exit_json(changed=False, recorder=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if before["ResourceTypes"] != desired["ResourceTypes"]: module.sdk_call(client.UpdateConfigRecorder, update_request(models, desired["ResourceTypes"]))
            if before["Enabled"] != desired["Enabled"]:
                if desired["Enabled"]: module.sdk_call(client.OpenConfigRecorder, open_request(models))
                else: module.sdk_call(client.CloseConfigRecorder, close_request(models))
            current = find_recorder(module, client, models)
        module.exit_json(changed=True, **(diff or {}), recorder=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
