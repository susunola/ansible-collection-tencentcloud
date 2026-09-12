#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwch_backup_config_info
short_description: Gather Tencent Cloud TCHouse-C backup configuration
version_added: "1.4.0"
description:
  - Returns the backup switch, metadata schedule, data schedule and selected
    table backup scope for a TCHouse-C instance.
options:
  instance_id:
    description: TCHouse-C instance ID.
    type: str
    required: true
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read TCHouse-C backup configuration
  susunola.tencentcloud.cdwch_backup_config_info:
    region: ap-guangzhou
    instance_id: cdwch-xxxxxxxx
'''

RETURN = r'''
backup_config:
  description: Effective backup configuration.
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
    tencentcloud_argument_spec,
)


def build_request(models, instance_id):
    request = models.DescribeBackUpScheduleRequest()
    request.InstanceId = instance_id
    return request


def normalize_tables(values):
    result = [{"Database": item.get("Database", item.get("database")), "Table": item.get("Table", item.get("table"))} for item in values or []]
    return sorted(result, key=lambda item: (item.get("Database") or "", item.get("Table") or ""))


def serialize_config(module, response):
    if getattr(response, "ErrorMsg", None):
        module.fail_json(msg=response.ErrorMsg)
    return {
        "enabled": bool(getattr(response, "BackUpOpened", False)),
        "meta_strategy": response.MetaStrategy._serialize(allow_none=True) if getattr(response, "MetaStrategy", None) else None,
        "data_strategy": response.DataStrategy._serialize(allow_none=True) if getattr(response, "DataStrategy", None) else None,
        "backup_tables": normalize_tables([item._serialize(allow_none=True) for item in getattr(response, "BackUpContents", None) or []]),
    }


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"instance_id": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cdwch.v20200915 import cdwch_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cdwch package is required.")

    client = cdwch_client.CdwchClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cdwch.tencentcloudapi.com"),
    )
    response = sdk_call(module, client.DescribeBackUpSchedule, build_request(models, module.params["instance_id"]))
    module.exit_json(changed=False, backup_config=serialize_config(module, response), request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
