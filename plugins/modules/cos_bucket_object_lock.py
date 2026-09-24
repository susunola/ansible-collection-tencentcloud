#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cos_bucket_object_lock
short_description: Manage Tencent Cloud COS bucket object lock
version_added: "0.14.0"
description:
  - Enables COS object lock and manages its default retention rule.
  - Object lock cannot be disabled after it has been enabled on a bucket; requesting C(state=absent) fails instead of reporting a false change.
options:
  state:
    description:
      - Desired object-lock state.
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
  retention_mode:
    description:
      - Default retention mode.
    type: str
    choices: [GOVERNANCE, COMPLIANCE]
  retention_days:
    description:
      - Default retention period in days.
    type: int
  retention_years:
    description:
      - Default retention period in years.
    type: int

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
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Enable compliance retention for seven years
  susunola.tencentcloud.cos_bucket_object_lock:
    region: ap-guangzhou
    name: audit-archive
    retention_mode: COMPLIANCE
    retention_years: 7
"""

RETURN = r"""object_lock: {description: Effective object-lock configuration., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import (
    get_bucket_object_lock,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def desired(p):
    result = {"ObjectLockEnabled": "Enabled"}
    if p.get("retention_mode"):
        retention = {"Mode": p["retention_mode"]}
        if p.get("retention_days") is not None:
            retention["Days"] = p["retention_days"]
        if p.get("retention_years") is not None:
            retention["Years"] = p["retention_years"]
        result["Rule"] = {"DefaultRetention": retention}
    return result


# ---- bucket_origin (moved out of plugins/modules/cos_bucket_origin.py so the matching
#      _info module can reuse it without importing a module) ----
def normalize_bucket_origin(value):
    if not value:
        return None
    root = value.get("OriginConfiguration", value)
    rules = root.get("OriginRule") or []
    if isinstance(rules, dict):
        rules = [rules]
    return {"OriginRule": sorted(rules, key=lambda item: int(item.get("RulePriority") or 0))}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "retention_mode": {"choices": ["GOVERNANCE", "COMPLIANCE"]},
            "retention_days": {"type": "int"},
            "retention_years": {"type": "int"},
        },
        mutually_exclusive=[("retention_days", "retention_years")],
        supports_check_mode=True,
    )
    p = module.params
    has_period = p.get("retention_days") is not None or p.get("retention_years") is not None
    if bool(p.get("retention_mode")) != has_period:
        module.fail_json(msg="retention_mode and exactly one retention period must be specified together")
    if (p.get("retention_days") is not None and p["retention_days"] < 1) or (p.get("retention_years") is not None and p["retention_years"] < 1):
        module.fail_json(msg="retention period must be positive")
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(p["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_bucket_object_lock(client, bucket)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, object_lock=None)
            module.fail_json(msg="COS object lock is irreversible and cannot be disabled after enablement", object_lock=current)
        target = desired(p)
        if current == target:
            module.exit_json(changed=False, object_lock=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_object_lock(Bucket=bucket, ObjectLockConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), object_lock=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
