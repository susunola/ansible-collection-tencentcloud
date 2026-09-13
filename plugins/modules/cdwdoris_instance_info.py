#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwdoris_instance_info
short_description: Gather information about Tencent Cloud CDW Doris instances
version_added: "1.4.0"
description:
  - Returns CDW Doris instances visible in a Tencent Cloud region.
  - Optionally attaches the service-reported instance state for each matched instance.
options:
  instance_id:
    description: CDW Doris instance ID to return.
    type: str
  name:
    description: Instance name used to narrow the returned instances.
    type: str
  include_state:
    description: Whether to call C(DescribeInstanceState) for matched instances.
    type: bool
    default: true
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List CDW Doris instances
  susunola.tencentcloud.cdwdoris_instance_info:
    region: ap-guangzhou

- name: Find a CDW Doris instance by name
  susunola.tencentcloud.cdwdoris_instance_info:
    region: ap-guangzhou
    name: analytics-doris
'''

RETURN = r'''
instances:
  description: Matching CDW Doris instances.
  returned: always
  type: list
  elements: dict
instance:
  description: First matching instance when C(instance_id) or C(name) is supplied.
  returned: always
  type: dict
total_count:
  description: Number of instances reported by the API.
  returned: always
  type: int
request_id:
  description: Request ID of the last list call, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_list_request(models, instance_id, name, offset, limit):
    request = models.DescribeInstancesRequest()
    request.SearchInstanceId = instance_id
    request.SearchInstanceName = None if instance_id else name
    request.Offset = offset
    request.Limit = limit
    return request


def build_state_request(models, instance_id):
    request = models.DescribeInstanceStateRequest()
    request.InstanceId = instance_id
    return request


def _matches(item, instance_id, name):
    if instance_id and item.get("InstanceId") != instance_id:
        return False
    if name and item.get("InstanceName") != name:
        return False
    return True


def _attach_state(module, client, models, item):
    instance_id = item.get("InstanceId")
    if not instance_id:
        return item
    response = sdk_call(module, client.DescribeInstanceState, build_state_request(models, instance_id))
    value = dict(item)
    value["InstanceState"] = getattr(response, "InstanceState", None)
    value["FlowMsg"] = getattr(response, "FlowMsg", None)
    return value


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str"},
        "name": {"type": "str"},
        "include_state": {"type": "bool", "default": True},
        "page_size": {"type": "int", "default": 100},
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
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_list_request(models, module.params["instance_id"], module.params["name"], offset, limit),
        lambda request: sdk_call(module, client.DescribeInstances, request),
        lambda response: getattr(response, "InstancesList", None),
        lambda response: getattr(response, "TotalCount", None),
    )
    item_set, total_count = paginator.fetch_all()
    instances = []
    for item in item_set:
        value = serialize_sdk_object(item)
        if _matches(value, module.params["instance_id"], module.params["name"]):
            if module.params["include_state"]:
                value = _attach_state(module, client, models, value)
            instances.append(value)
    selected = instances[0] if (module.params["instance_id"] or module.params["name"]) and instances else None
    module.exit_json(
        changed=False,
        instances=instances,
        instance=selected,
        total_count=total_count,
        request_id=paginator.request_id,
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
