#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_template_info
short_description: Gather Tencent Cloud TSE configuration file templates
version_added: "0.14.0"
description: Returns the configuration templates available to a TSE registry-engine instance.
options:
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotency:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_config_file_template_info:
    instance_id: ins-xxxxxxxx
  register: config_templates
'''
RETURN = r'''
templates: {description: Available configuration file templates., type: list, elements: dict, returned: always}
total_count: {description: Template count reported by Tencent Cloud., type: int, returned: always}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def request(models, instance_id):
    value = models.DescribeAllConfigFileTemplatesRequest()
    value.InstanceId = instance_id
    return value


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeAllConfigFileTemplates,
                                   request(models, module.params["instance_id"]))
        templates = [item._serialize(allow_none=True) for item in (response.ConfigFileTemplates or [])]
        module.exit_json(changed=False, templates=templates,
                         total_count=response.TotalCount if response.TotalCount is not None else len(templates),
                         request_id=response.RequestId)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
