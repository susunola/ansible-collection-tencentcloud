#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_inventory
short_description: Manage Tencent Cloud COS bucket inventory rules
version_added: "0.14.0"
description: Manages one named scheduled COS inventory rule with complete-document reconciliation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  inventory_id: {type: str, required: true, description: Inventory rule identifier.}
  configuration: {type: dict, description: Complete COS SDK-compatible InventoryConfiguration document.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_inventory:
    name: application-data
    inventory_id: daily-objects
    configuration:
      IsEnabled: 'True'
      IncludedObjectVersions: All
      Schedule: {Frequency: Daily}
      Destination:
        COSBucketDestination:
          AccountId: '1250000000'
          Bucket: qcs::cos:ap-guangzhou::inventory-1250000000
          Format: CSV
"""
RETURN = r"""inventory: {description: Effective inventory rule., type: dict, returned: always}"""
import copy
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value, inventory_id):
    if not value:
        return None
    result = copy.deepcopy(value.get("InventoryConfiguration", value))
    result["Id"] = inventory_id
    optional = result.get("OptionalFields")
    if optional and isinstance(optional.get("Field"), list):
        optional["Field"] = sorted(optional["Field"])
    return result


def get_inventory(client, bucket, inventory_id):
    try:
        return normalize(client.get_bucket_inventory(Bucket=bucket, Id=inventory_id), inventory_id)
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "inventory_id": {"required": True},
            "configuration": {"type": "dict"},
        },
        required_if=[("state", "present", ["configuration"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    inventory_id = module.params["inventory_id"]
    try:
        current = get_inventory(client, bucket, inventory_id)
        target = normalize(module.params.get("configuration"), inventory_id)
        if module.params["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, inventory=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                client.delete_bucket_inventory(Bucket=bucket, Id=inventory_id)
            module.exit_json(changed=True, **(diff or {}), inventory=current if module.check_mode else None)
        if current == target:
            module.exit_json(changed=False, inventory=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_inventory(Bucket=bucket, Id=inventory_id, InventoryConfiguration=copy.deepcopy(target))
        module.exit_json(changed=True, **(diff or {}), inventory=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
