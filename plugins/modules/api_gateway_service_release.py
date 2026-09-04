#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: api_gateway_service_release
short_description: Manage Tencent Cloud API Gateway service releases
version_added: "0.14.0"
description: Publishes or unpublishes an API Gateway service environment.
options:
  state: {description: Desired release state., type: str, choices: [present, absent], default: present}
  service_id: {description: API Gateway service ID., type: str, required: true}
  environment: {description: Release environment., type: str, choices: [test, prepub, release], default: release}
  description: {description: Release description., type: str, default: Managed by Ansible}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.api_gateway_service_release:
    service_id: service-xxxxxxxx
    environment: release
    description: production release
'''
RETURN = r'''release: {description: Service environment release metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models
    return models, apigateway_client


def build_describe(models, service_id):
    request = models.DescribeServiceEnvironmentListRequest()
    request.ServiceId = service_id
    return request


def find(module, client, models, service_id, environment):
    result = module.sdk_call(client.DescribeServiceEnvironmentList, build_describe(models, service_id)).Result
    for item in list(getattr(result, "EnvironmentList", None) or []):
        value = item._serialize(allow_none=True)
        if value.get("EnvironmentName") == environment and int(value.get("Status") or 0) == 1:
            return value
    return None


def build_release(models, p):
    request = models.ReleaseServiceRequest()
    request.ServiceId, request.EnvironmentName = p["service_id"], p["environment"]
    request.ReleaseDesc = p["description"]
    return request


def build_unrelease(models, p):
    request = models.UnReleaseServiceRequest()
    request.ServiceId, request.EnvironmentName = p["service_id"], p["environment"]
    return request


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "service_id": {"required": True},
        "environment": {"choices": ["test", "prepub", "release"], "default": "release"},
        "description": {"default": "Managed by Ansible"},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["service_id"], p["environment"])
        target = {"ServiceId": p["service_id"], "EnvironmentName": p["environment"], "Status": 1}
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, release=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.UnReleaseService, build_unrelease(models, p))
            module.exit_json(changed=True, **(diff or {}), release=current if module.check_mode else None)
        if current is not None:
            module.exit_json(changed=False, release=current)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            module.sdk_call(client.ReleaseService, build_release(models, p))
            current = find(module, client, models, p["service_id"], p["environment"])
        module.exit_json(changed=True, **(diff or {}), release=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
