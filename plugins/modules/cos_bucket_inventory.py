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
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Bucket short name or full name.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud AppId used in the bucket suffix.
    type: str
  inventory_id:
    description:
      - Inventory rule identifier.
    type: str
    required: true
  configuration:
    description:
      - Complete COS SDK-compatible InventoryConfiguration document.
    type: dict

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
      - 'Can run in C(check_mode): the module reads the current state and
        predicts the result without issuing a write API call.'
    support: full
  idempotency:
    description:
      - 'Reconciles the resource against its live state: running again with
        the same arguments leaves it unchanged and reports C(changed=false).'
    support: full
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import (
    get_bucket_inventory, normalize_bucket_inventory as normalize,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


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
        current = get_bucket_inventory(client, bucket, inventory_id)
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
