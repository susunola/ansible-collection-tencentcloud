#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_replication
short_description: Manage Tencent Cloud COS bucket replication
version_added: "0.14.0"
description: Reconciles the complete cross-region replication configuration of a COS bucket.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Source bucket short name or full name.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud AppId used in the bucket suffix.
    type: str
  role:
    description:
      - CAM role QCS used by COS replication.
    type: str
  rules:
    description:
      - Complete COS SDK-compatible replication Rule list.
    type: list
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
  - module: susunola.tencentcloud.cos_bucket_replication_info
    description: Gather Tencent Cloud COS bucket replication.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_replication:
    name: source-data
    role: qcs::cam::uin/100000000001:roleName/COSReplicationRole
    rules:
      - ID: archive
        Status: Enabled
        Prefix: logs/
        Destination: {Bucket: qcs::cos:ap-shanghai::archive-1250000000, StorageClass: STANDARD}
"""
RETURN = r"""replication:
  description:
    - Effective replication configuration.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_replication as normalize, get_replication
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "role": {},
            "rules": {"type": "list", "elements": "dict"},
        },
        required_if=[("state", "present", ["role", "rules"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_replication(client, bucket)
        target = normalize({"Role": module.params.get("role"), "Rule": module.params.get("rules") or []})
        if module.params["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, replication=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                client.delete_bucket_replication(Bucket=bucket)
            module.exit_json(changed=True, **(diff or {}), replication=current if module.check_mode else None)
        if current == target:
            module.exit_json(changed=False, replication=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_replication(Bucket=bucket, ReplicationConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), replication=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
