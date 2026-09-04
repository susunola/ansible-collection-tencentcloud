#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ssm_rotation
short_description: Manage Tencent Cloud SSM secret rotation settings
version_added: "0.14.0"
description: Reconciles automatic rotation status and schedule for an existing supported SSM secret.
options:
  secret_name: {type: str, required: true, description: Existing SSM secret name.}
  enabled: {type: bool, default: true, description: Whether automatic rotation is enabled.}
  frequency: {type: int, default: 30, description: Rotation frequency in days.}
  begin_time: {type: str, description: RFC3339 timestamp for the first rotation window.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_rotation:
    secret_name: prod/database-managed
    enabled: true
    frequency: 30
    begin_time: '2026-09-01T02:00:00Z'
"""
RETURN = r"""rotation: {description: Effective SSM rotation configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client

    return models, ssm_client


def describe_request(models, secret_name):
    request = models.DescribeRotationDetailRequest()
    request.SecretName = secret_name
    return request


def update_request(models, p):
    request = models.UpdateRotationStatusRequest()
    request.SecretName, request.EnableRotation, request.Frequency = p["secret_name"], p["enabled"], p["frequency"]
    if p.get("begin_time"):
        request.RotationBeginTime = p["begin_time"]
    return request


def comparable(response):
    return {"EnableRotation": bool(response.EnableRotation), "Frequency": int(response.Frequency or 0)}


def result(response):
    value = comparable(response)
    value["LatestRotateTime"], value["NextRotateBeginTime"] = response.LatestRotateTime, response.NextRotateBeginTime
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "secret_name": {"required": True},
            "enabled": {"type": "bool", "default": True},
            "frequency": {"type": "int", "default": 30},
            "begin_time": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeRotationDetail, describe_request(models, p["secret_name"]))
        current = comparable(response)
        target = {"EnableRotation": p["enabled"], "Frequency": p["frequency"]}
        if current == target:
            module.exit_json(changed=False, rotation=result(response))
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateRotationStatus, update_request(models, p))
            response = module.sdk_call(client.DescribeRotationDetail, describe_request(models, p["secret_name"]))
            current = result(response)
        module.exit_json(changed=True, **(diff or {}), rotation=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
