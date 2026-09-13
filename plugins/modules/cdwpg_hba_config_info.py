#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwpg_hba_config_info
short_description: Gather Tencent Cloud CDW PostgreSQL HBA rules
version_added: "1.4.0"
description:
  - Returns the ordered user-managed pg_hba rule list for a CDW PostgreSQL instance.
options:
  instance_id:
    description: CDW PostgreSQL instance ID.
    type: str
    required: true
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read CDW PostgreSQL HBA rules
  susunola.tencentcloud.cdwpg_hba_config_info:
    region: ap-guangzhou
    instance_id: cdwpg-xxxxxxxx
'''

RETURN = r'''
rules:
  description: Ordered user-managed HBA rules.
  returned: always
  type: list
  elements: dict
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
    tencentcloud_argument_spec,
)

FIELDS = (("type", "Type"), ("database", "Database"), ("user", "User"), ("address", "Address"), ("method", "Method"), ("mask", "Mask"))


def build_request(models, instance_id):
    request = models.DescribeUserHbaConfigRequest()
    request.InstanceId = instance_id
    return request


def normalize(values):
    result = []
    for item in values or []:
        raw = item._serialize(allow_none=True) if hasattr(item, "_serialize") else dict(item)
        value = {}
        for key, sdk in FIELDS:
            field_value = raw.get(key) if key in raw else raw.get(sdk)
            if field_value is not None:
                value[sdk] = field_value
        result.append(value)
    return result


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"instance_id": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cdwpg.v20201230 import cdwpg_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cdwpg package is required.")

    client = cdwpg_client.CdwpgClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cdwpg.tencentcloudapi.com"),
    )
    response = sdk_call(module, client.DescribeUserHbaConfig, build_request(models, module.params["instance_id"]))
    module.exit_json(changed=False, rules=normalize(getattr(response, "HbaConfigs", None)), request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
