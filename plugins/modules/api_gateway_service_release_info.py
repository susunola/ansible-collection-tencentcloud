#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: api_gateway_service_release_info
short_description: Gather information about Tencent Cloud API Gateway service releases
version_added: "1.4.0"
description:
  - Returns the published environments of an API Gateway service.
  - This module is the read side for C(api_gateway_service_release) and lets
    playbooks verify release state without changing it.
options:
  service_id:
    description: API Gateway service ID.
    type: str
    required: true
  environment:
    description: Optional service environment name to return.
    type: str
    choices: [test, prepub, release]
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List API Gateway service releases
  susunola.tencentcloud.api_gateway_service_release_info:
    region: ap-guangzhou
    service_id: service-xxxxxxxx

- name: Find the production release
  susunola.tencentcloud.api_gateway_service_release_info:
    region: ap-guangzhou
    service_id: service-xxxxxxxx
    environment: release
'''

RETURN = r'''
releases:
  description: Matching service environment releases.
  returned: always
  type: list
  elements: dict
release:
  description: First matching service environment release when C(environment) is supplied.
  returned: always
  type: dict
request_id:
  description: Request ID returned by the API, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, service_id):
    request = models.DescribeServiceEnvironmentListRequest()
    request.ServiceId = service_id
    return request


def _released(item):
    return int(item.get("Status") or 0) == 1


def _matches(item, environment):
    if not _released(item):
        return False
    if environment and item.get("EnvironmentName") != environment:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "service_id": {"type": "str", "required": True},
        "environment": {"type": "str", "choices": ["test", "prepub", "release"]},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.apigateway.v20180808 import apigateway_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-apigateway package is required.")

    client = apigateway_client.ApigatewayClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "apigateway.tencentcloudapi.com"),
    )
    response = sdk_call(
        module,
        client.DescribeServiceEnvironmentList,
        build_request(models, module.params["service_id"]),
    )
    result = response.Result
    environment_list = getattr(result, "EnvironmentList", None) if result is not None else None
    releases = [
        item for item in (serialize_sdk_object(value) for value in list(environment_list or []))
        if _matches(item, module.params["environment"])
    ]
    release = releases[0] if module.params["environment"] and releases else None
    module.exit_json(
        changed=False,
        releases=releases,
        release=release,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
