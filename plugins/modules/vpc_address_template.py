#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: vpc_address_template
short_description: Manage Tencent Cloud VPC address templates
version_added: "0.14.0"
description: Creates, updates and deletes reusable VPC IP address templates.
options:
  state:
    description:
      - C(present) creates the address template with V(CreateAddressTemplate) when it does not exist and updates
        it with V(ModifyAddressTemplateAttribute) when it differs. C(absent) deletes it with V(DeleteAddressTemplate).
    type: str
    choices: [present, absent]
    default: present
  template_id:
    description:
      - Existing address-template ID.
    type: str
  name:
    description:
      - Identifies the address template to manage; one of this or O(template_id) is required.
    type: str
  addresses:
    description:
      - Exact set of IPv4 addresses, CIDRs or ranges.
    type: list
    default: []
    elements: str
  address_extra:
    description:
      - Exact SDK-compatible extended address entries.
    type: list
    default: []
    elements: dict

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
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.vpc_address_template_info
    description: Gather information about Tencent Cloud VPC address templates.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.vpc_address_template:
    name: office-networks
    addresses: [10.10.0.0/16, 192.0.2.10]
"""
RETURN = r"""address_template:
  description:
    - Effective address-template metadata.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.vpc.v20170312 import models, vpc_client

    return models, vpc_client


def describe_request(models, offset=0):
    request = models.DescribeAddressTemplatesRequest()
    request.Offset, request.Limit, request.NeedMemberInfo = str(offset), "100", True
    return request


def _extra(models, values):
    result = []
    for value in values:
        item = models.AddressInfo()
        item._deserialize(value)
        result.append(item)
    return result


def create_request(models, p):
    request = models.CreateAddressTemplateRequest()
    request.AddressTemplateName, request.Addresses = p["name"], sorted(p["addresses"])
    request.AddressesExtra = _extra(models, p["address_extra"])
    return request


def update_request(models, p, template_id):
    request = models.ModifyAddressTemplateAttributeRequest()
    request.AddressTemplateId, request.AddressTemplateName = template_id, p["name"]
    request.Addresses, request.AddressesExtra = sorted(p["addresses"]), _extra(models, p["address_extra"])
    return request


def delete_request(models, template_id):
    request = models.DeleteAddressTemplateRequest()
    request.AddressTemplateId = template_id
    return request


def _sorted_extra(values):
    return sorted(values or [], key=lambda x: tuple(sorted((k, str(v)) for k, v in x.items())))


def comparable(v):
    return {
        "AddressTemplateName": v.get("AddressTemplateName"),
        "AddressSet": sorted(v.get("AddressSet") or []),
        "AddressExtraSet": _sorted_extra(v.get("AddressExtraSet")),
    }


def desired(p):
    return {"AddressTemplateName": p["name"], "AddressSet": sorted(p["addresses"]), "AddressExtraSet": _sorted_extra(p["address_extra"])}


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeAddressTemplates, describe_request(models, offset))
        values = list(response.AddressTemplateSet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("template_id") and value.get("AddressTemplateId") == p["template_id"]) or (
                not p.get("template_id") and value.get("AddressTemplateName") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple VPC address templates matched; specify template_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "template_id": {},
            "name": {},
            "addresses": {"type": "list", "elements": "str", "default": []},
            "address_extra": {"type": "list", "elements": "dict", "default": []},
        },
        required_one_of=[("template_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("name") or (not p["addresses"] and not p["address_extra"])):
        module.fail_json(msg="name and at least one address entry are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, address_template=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAddressTemplate, delete_request(models, current["AddressTemplateId"]))
            module.exit_json(changed=True, **(diff or {}), address_template=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, address_template=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyAddressTemplateAttribute, update_request(models, p, current["AddressTemplateId"]))
            else:
                p["template_id"] = module.sdk_call(client.CreateAddressTemplate, create_request(models, p)).AddressTemplate.AddressTemplateId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), address_template=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
