#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: redis_parameter_template
short_description: Manage Tencent Cloud Redis parameter templates
version_added: "0.14.0"
description: Creates, updates and deletes reusable Redis parameter templates.
options:

  state:
    description:
      - C(present) creates the parameter template with V(CreateParamTemplate) when it does not exist and updates
        it with V(ModifyParamTemplate) when it differs. C(absent) deletes it with V(DeleteParamTemplate).
    type: str
    choices: [present, absent]
    default: present
  template_id:
    description:
      - Identifies the parameter template to manage; one of this or O(name) is required, and the module matches
        on the id when it is given.
    type: str
  name:
    description:
      - Identifies the parameter template to manage; one of this or O(template_id) is required, and the name
        is only used when O(template_id) is not given.
    type: str
  description:
    description:
      - Template description.
    type: str
    default: ''
  product_type:
    description:
      - Redis product type required at creation.
    type: int
  parameters:
    description:
      - Exact parameter name and value mapping.
    type: dict
    default: {}
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
  - module: susunola.tencentcloud.redis_parameter_template_info
    description: Gather information about Tencent Cloud Redis parameter templates.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.redis_parameter_template:
    name: production-redis
    product_type: 2
    parameters: {timeout: '300'}

- name: Delete the parameter template
  susunola.tencentcloud.redis_parameter_template:
    state: absent
    name: production-redis
"""
RETURN = r"""parameter_template:
  description:
    - Redis parameter template metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    TemplateId: tmpl-1a2b3c4d
    Name: production-redis
    Description: ''
    ProductType: 2
    Items:
      - Name: maxmemory-policy
        CurrentValue: allkeys-lru
      - Name: timeout
        CurrentValue: '300'
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.redis.v20180412 import models, redis_client

    return models, redis_client


def param_list(models, values):
    result = []
    for name, value in sorted(values.items()):
        item = models.InstanceParam()
        item.Key, item.Value = str(name), str(value)
        result.append(item)
    return result


def find(module, client, models, template_id, name):
    request = models.DescribeParamTemplatesRequest()
    request.Limit, request.Offset = 100, 0
    if template_id:
        request.TemplateIds = [template_id]
    elif name:
        request.TemplateNames = [name]
    items = module.sdk_call(client.DescribeParamTemplates, request).Items or []
    matches = [x for x in items if (template_id and str(x.TemplateId) == str(template_id)) or (not template_id and x.Name == name)]
    if len(matches) > 1:
        module.fail_json(msg="Multiple Redis parameter templates have the requested name", name=name)
    if not matches:
        return None
    request = models.DescribeParamTemplateInfoRequest()
    request.TemplateId = matches[0].TemplateId
    return module.sdk_call(client.DescribeParamTemplateInfo, request)._serialize(allow_none=True)


def normalize(value):
    return {
        "Name": value.get("Name"),
        "Description": value.get("Description") or "",
        "ProductType": value.get("ProductType"),
        "Parameters": {x.get("Name"): x.get("CurrentValue") for x in value.get("Items") or []},
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "template_id": {},
            "name": {},
            "description": {"default": ""},
            "product_type": {"type": "int"},
            "parameters": {"type": "dict", "default": {}},
        },
        required_one_of=[("template_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.RedisClient, "redis.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["template_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, parameter_template=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteParamTemplateRequest()
                request.TemplateId = current["TemplateId"]
                module.sdk_call(client.DeleteParamTemplate, request)
            module.exit_json(changed=True, **(diff or {}), parameter_template=current if module.check_mode else None)
        target = {
            "Name": p["name"],
            "Description": p["description"],
            "ProductType": p["product_type"] if p["product_type"] is not None else (current or {}).get("ProductType"),
            "Parameters": {str(k): str(v) for k, v in p["parameters"].items()},
        }
        before = normalize(current) if current else None
        if before == target:
            module.exit_json(changed=False, parameter_template=current)
        if current:
            require_immutable_unchanged(module, before, target, ("ProductType",), "Redis parameter template")
        elif p["product_type"] is None:
            module.fail_json(msg="product_type is required when creating a Redis parameter template")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                request = models.ModifyParamTemplateRequest()
                request.TemplateId = current["TemplateId"]
            else:
                request = models.CreateParamTemplateRequest()
                request.ProductType = p["product_type"]
            request.Name, request.Description, request.ParamList = p["name"], p["description"], param_list(models, p["parameters"])
            response = module.sdk_call(client.ModifyParamTemplate if current else client.CreateParamTemplate, request)
            p["template_id"] = current["TemplateId"] if current else response.TemplateId
            current = find(module, client, models, p["template_id"], None)
        module.exit_json(changed=True, **(diff or {}), parameter_template=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
