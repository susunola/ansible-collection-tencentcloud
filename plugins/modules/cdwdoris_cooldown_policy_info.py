#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwdoris_cooldown_policy_info
short_description: Gather Tencent Cloud CDW Doris cooldown policies
version_added: "1.4.0"
description:
  - Returns hot/cold tiering cooldown policies for a CDW Doris instance.
options:
  instance_id:
    description: CDW Doris instance ID.
    type: str
    required: true
  name:
    description: Optional cooldown policy name to return.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List Doris cooldown policies
  susunola.tencentcloud.cdwdoris_cooldown_policy_info:
    region: ap-guangzhou
    instance_id: cdwdoris-xxxxxxxx
'''

RETURN = r'''
policies:
  description: Matching cooldown policies.
  returned: always
  type: list
  elements: dict
policy:
  description: First matching policy when C(name) is supplied.
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
    request = models.DescribeCoolDownPoliciesRequest()
    request.InstanceId = instance_id
    return request


def _filter_by_name(values, name):
    return [item for item in values if not name or item.get("PolicyName") == name]


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "name": {"type": "str"},
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
    response = sdk_call(module, client.DescribeCoolDownPolicies, build_request(models, module.params["instance_id"]))
    if getattr(response, "ErrorMsg", None):
        module.fail_json(msg=response.ErrorMsg)
    policies = _filter_by_name([serialize_sdk_object(item) for item in getattr(response, "List", None) or []], module.params["name"])
    module.exit_json(
        changed=False,
        policies=policies,
        policy=policies[0] if module.params["name"] and policies else None,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
