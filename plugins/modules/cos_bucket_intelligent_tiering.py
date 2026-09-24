#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cos_bucket_intelligent_tiering
short_description: Manage Tencent Cloud COS bucket intelligent tiering
version_added: "0.14.0"
description:
  - Enables the default COS intelligent-tiering rule.
  - The default rule cannot be disabled after enablement; C(state=absent) fails when it already exists.
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
  transition_days:
    description:
      - Inactive days before transition to the infrequent-access tier.
    type: int
    choices: [30, 60, 90]
    default: 30
  request_frequent:
    description:
      - Maximum access count during the transition window.
    type: int
    default: 1

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
- name: Transition cold objects after sixty days
  susunola.tencentcloud.cos_bucket_intelligent_tiering:
    region: ap-guangzhou
    name: archive
    transition_days: 60
"""
RETURN = r"""intelligent_tiering: {description: Effective intelligent-tiering rule., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import get_rule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "transition_days": {"type": "int", "choices": [30, 60, 90], "default": 30},
            "request_frequent": {"type": "int", "default": 1},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["request_frequent"] < 1:
        module.fail_json(msg="request_frequent must be positive")
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(p["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_rule(client, bucket)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, intelligent_tiering=None)
            module.fail_json(msg="the COS default intelligent-tiering rule cannot be disabled after enablement", intelligent_tiering=current)
        target = {
            "Id": "default",
            "Status": "Enabled",
            "Tiering": {"AccessTier": "INFREQUENT", "Days": p["transition_days"], "RequestFrequent": p["request_frequent"]},
        }
        if current == target:
            module.exit_json(changed=False, intelligent_tiering=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_intelligenttiering_v2(Bucket=bucket, Id="default", IntelligentTieringConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), intelligent_tiering=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
