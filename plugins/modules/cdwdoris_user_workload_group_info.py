#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwdoris_user_workload_group_info
short_description: Gather Tencent Cloud CDW Doris user workload-group bindings
version_added: "1.4.0"
description:
  - Returns Doris user-to-workload-group bindings for an instance.
options:
  instance_id:
    description: CDW Doris instance ID.
    type: str
    required: true
  user_name:
    description: Optional Doris user name to return.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List Doris user workload-group bindings
  susunola.tencentcloud.cdwdoris_user_workload_group_info:
    region: ap-guangzhou
    instance_id: cdwdoris-xxxxxxxx
'''

RETURN = r'''
bindings:
  description: Matching user workload-group bindings.
  returned: always
  type: list
  elements: dict
binding:
  description: First matching binding when C(user_name) is supplied.
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


def build_request(models, instance_id):
    request = models.DescribeUserBindWorkloadGroupRequest()
    request.InstanceId = instance_id
    return request


def _filter_by_user(values, user_name):
    return [item for item in values if not user_name or item.get("UserName") == user_name]


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "user_name": {"type": "str"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cdwdoris.v20211228 import cdwdoris_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cdwdoris package is required.")

    client = cdwdoris_client.CdwdorisClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cdwdoris.tencentcloudapi.com"),
    )
    response = sdk_call(module, client.DescribeUserBindWorkloadGroup, build_request(models, module.params["instance_id"]))
    if getattr(response, "ErrorMsg", None):
        module.fail_json(msg=response.ErrorMsg)
    bindings = _filter_by_user([serialize_sdk_object(item) for item in getattr(response, "UserBindInfos", None) or []], module.params["user_name"])
    module.exit_json(
        changed=False,
        bindings=bindings,
        binding=bindings[0] if module.params["user_name"] and bindings else None,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
