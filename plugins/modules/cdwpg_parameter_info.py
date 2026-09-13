#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwpg_parameter_info
short_description: Gather Tencent Cloud CDW PostgreSQL parameters
version_added: "1.4.0"
description:
  - Returns CN or DN parameters for a CDW PostgreSQL instance.
options:
  instance_id:
    description: CDW PostgreSQL instance ID.
    type: str
    required: true
  node_type:
    description: Node type whose parameters are returned.
    type: str
    choices: [cn, dn]
    required: true
  name:
    description: Optional parameter name to return.
    type: str
  page_size:
    description: Number of parameter details requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read CDW PostgreSQL CN parameters
  susunola.tencentcloud.cdwpg_parameter_info:
    region: ap-guangzhou
    instance_id: cdwpg-xxxxxxxx
    node_type: cn
'''

RETURN = r'''
parameters:
  description: Matching parameter details.
  returned: always
  type: list
  elements: dict
parameter:
  description: First matching parameter when C(name) is supplied.
  returned: always
  type: dict
total_count:
  description: Number of parameter details reported by the API.
  returned: always
  type: int
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
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


def build_request(models, instance_id, node_type, offset, limit):
    request = models.DescribeDBParamsRequest()
    request.InstanceId = instance_id
    request.NodeTypes = [node_type]
    request.Offset = offset
    request.Limit = limit
    return request


def effective_value(detail):
    return detail.get("LatestValue") if detail.get("LatestValue") not in (None, "") else detail.get("RunningValue")


def _extract_parameters(response, node_type, name):
    parameters = []
    seen = 0
    for group in getattr(response, "Items", None) or []:
        if str(getattr(group, "NodeType", "")).lower() != node_type:
            continue
        for detail in getattr(group, "Details", None) or []:
            seen += 1
            value = serialize_sdk_object(detail)
            param_name = value.get("ParamName") or value.get("ParameterName")
            if name and param_name != name:
                continue
            value["EffectiveValue"] = effective_value(value)
            parameters.append(value)
    return parameters, seen


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "node_type": {"type": "str", "choices": ["cn", "dn"], "required": True},
        "name": {"type": "str"},
        "page_size": {"type": "int", "default": 100},
    })
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
    parameters = []
    total_count = None
    request_id = None
    offset = 0
    while True:
        response = sdk_call(
            module,
            client.DescribeDBParams,
            build_request(models, module.params["instance_id"], module.params["node_type"], offset, module.params["page_size"]),
        )
        request_id = getattr(response, "RequestId", None)
        total_count = getattr(response, "TotalCount", total_count)
        batch, seen = _extract_parameters(response, module.params["node_type"], module.params["name"])
        parameters.extend(batch)
        offset += seen
        if total_count is not None and offset >= int(total_count or 0):
            break
        if seen < module.params["page_size"]:
            break
    module.exit_json(
        changed=False,
        parameters=parameters,
        parameter=parameters[0] if module.params["name"] and parameters else None,
        total_count=total_count if total_count is not None else len(parameters),
        request_id=request_id,
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
