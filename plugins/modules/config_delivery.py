#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: config_delivery
short_description: Manage Tencent Cloud Config delivery settings
version_added: "0.14.0"
description: Reconciles Config change and resource-list delivery to a COS or CLS target ARN.
options:
  enabled: {type: bool, default: true, description: Whether configuration delivery is enabled.}
  name: {type: str, required: true, description: Delivery service name.}
  target_arn: {type: str, required: true, description: Six-part COS or CLS target resource ARN.}
  prefix: {type: str, default: config, description: Delivery object or log prefix.}
  delivery_type: {type: str, required: true, description: Config delivery target type accepted by the API.}
  content_type: {type: int, choices: [1, 2, 3], default: 3, description: "One for changes, two for resource lists or three for both."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Deliver Config changes and resource inventories to COS
  susunola.tencentcloud.config_delivery:
    region: ap-guangzhou
    name: compliance-archive
    target_arn: qcs::cos:ap-guangzhou:100000000001:prefix/1250000000/config-archive
    delivery_type: COS
    content_type: 3
"""

RETURN = r"""delivery: {description: Config delivery configuration., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client

    return models, config_client


def describe_request(models):
    return models.DescribeConfigDeliverRequest()


def update_request(models, p):
    request = models.UpdateConfigDeliverRequest()
    request.Status, request.DeliverName, request.TargetArn = int(p["enabled"]), p["name"], p["target_arn"]
    request.DeliverPrefix, request.DeliverType, request.DeliverContentType = p["prefix"], p["delivery_type"], p["content_type"]
    return request


def find_delivery(module, client, models):
    response = module.sdk_call(client.DescribeConfigDeliver, describe_request(models))
    value = response._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "enabled": {"type": "bool", "default": True},
            "name": {"required": True},
            "target_arn": {"required": True},
            "prefix": {"default": "config"},
            "delivery_type": {"required": True},
            "content_type": {"type": "int", "choices": [1, 2, 3], "default": 3},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_delivery(module, client, models)
        desired = {
            "Status": int(p["enabled"]),
            "DeliverName": p["name"],
            "TargetArn": p["target_arn"],
            "DeliverPrefix": p["prefix"],
            "DeliverType": p["delivery_type"],
            "DeliverContentType": p["content_type"],
        }
        before = {key: current.get(key) for key in desired}
        if before == desired:
            module.exit_json(changed=False, delivery=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            module.sdk_call(client.UpdateConfigDeliver, update_request(models, p))
            current = find_delivery(module, client, models)
        module.exit_json(changed=True, **(diff or {}), delivery=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
