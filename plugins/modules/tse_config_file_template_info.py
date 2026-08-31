#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_template_info
short_description: Gather Tencent Cloud TSE configuration file templates
version_added: "0.14.0"
description: Returns the configuration templates available to a TSE registry-engine instance.
options:
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
