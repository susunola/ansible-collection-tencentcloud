#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdwch_instance_info
short_description: Gather information about Tencent Cloud TCHouse-C instances
version_added: "1.4.0"
description:
  - Returns TCHouse-C instances visible in a Tencent Cloud region.
  - When an instance ID or name is supplied, the module also attaches detailed
    instance metadata from C(DescribeInstance).
options:
  instance_id:
    description: TCHouse-C instance ID to return.
    type: str
  name:
    description: Instance name used to narrow the returned instances.
    type: str
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List TCHouse-C instances
  susunola.tencentcloud.cdwch_instance_info:
    region: ap-guangzhou

- name: Find a TCHouse-C instance by name
  susunola.tencentcloud.cdwch_instance_info:
    region: ap-guangzhou
    name: production-clickhouse
'''

RETURN = r'''
instances:
  description: Matching TCHouse-C instances.
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
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
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
    request = models.DescribeInstancesNewRequest()
    request.Offset = offset
    request.Limit = limit
    request.IsSimple = False
    request.SearchInstanceId = instance_id
    request.SearchInstanceName = name if not instance_id else None
    return request


def build_detail_request(models, instance_id):
    request = models.DescribeInstanceRequest()
    request.InstanceId = instance_id
    request.IsOpenApi = True
    return request


def _matches(item, instance_id, name):
    if instance_id and item.get("InstanceId") != instance_id:
        return False
    if name and item.get("InstanceName") != name:
        return False
    return True


def _with_detail(module, client, models, item):
    instance_id = item.get("InstanceId")
    if not instance_id:
        return item
    response = sdk_call(module, client.DescribeInstance, build_detail_request(models, instance_id))
    detail = serialize_sdk_object(response.InstanceInfo) if getattr(response, "InstanceInfo", None) else {}
    value = dict(item)
    value.update(detail)
    return value


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str"},
        "name": {"type": "str"},
        "page_size": {"type": "int", "default": 100},
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
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_list_request(models, module.params["instance_id"], module.params["name"], offset, limit),
        lambda request: sdk_call(module, client.DescribeInstancesNew, request),
        lambda response: getattr(response, "InstancesList", None),
        lambda response: getattr(response, "TotalCount", None),
    )
    item_set, total_count = paginator.fetch_all()
    instances = []
    for item in item_set:
        value = serialize_sdk_object(item)
        if _matches(value, module.params["instance_id"], module.params["name"]):
            instances.append(value)
    if module.params["instance_id"] or module.params["name"]:
        instances = [_with_detail(module, client, models, item) for item in instances]
    instance = instances[0] if (module.params["instance_id"] or module.params["name"]) and instances else None
    module.exit_json(
        changed=False,
        instances=instances,
        instance=instance,
        total_count=total_count,
        request_id=paginator.request_id,
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
