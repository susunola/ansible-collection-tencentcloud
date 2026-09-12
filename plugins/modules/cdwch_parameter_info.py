#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwch_parameter_info
short_description: Gather Tencent Cloud TCHouse-C instance parameters
version_added: "1.4.0"
description:
  - Returns configured and available key/value parameters for a TCHouse-C instance.
  - This module is the read side for C(cdwch_parameter).
options:
  instance_id:
    description: TCHouse-C instance ID.
    type: str
    required: true
  name:
    description: Optional configuration key to return.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read a TCHouse-C parameter
  susunola.tencentcloud.cdwch_parameter_info:
    region: ap-guangzhou
    instance_id: cdwch-xxxxxxxx
    name: max_concurrent_queries
'''

RETURN = r'''
configured:
  description: Configured parameter values.
  returned: always
  type: list
  elements: dict
available:
  description: Available but currently unconfigured parameter values.
  returned: always
  type: list
  elements: dict
parameter:
  description: First matching configured parameter when C(name) is supplied.
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


def build_request(models, instance_id, name):
    request = models.DescribeInstanceKeyValConfigsRequest()
    request.InstanceId = instance_id
    request.SearchConfigName = name
    return request


def _filter_by_name(values, name):
    return [item for item in values if not name or item.get("ConfKey") == name]


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "name": {"type": "str"},
    })
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
    response = sdk_call(module, client.DescribeInstanceKeyValConfigs, build_request(models, module.params["instance_id"], module.params["name"]))
    if getattr(response, "ErrorMsg", None):
        module.fail_json(msg=response.ErrorMsg)
    configured = _filter_by_name([serialize_sdk_object(item) for item in getattr(response, "ConfigItems", None) or []], module.params["name"])
    available = _filter_by_name([serialize_sdk_object(item) for item in getattr(response, "UnConfigItems", None) or []], module.params["name"])
    module.exit_json(
        changed=False,
        configured=configured,
        available=available,
        parameter=configured[0] if module.params["name"] and configured else None,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
