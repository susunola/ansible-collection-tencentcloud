#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_referer
short_description: Manage Tencent Cloud COS hotlink protection
version_added: "0.14.0"
description: Reconciles the complete referer allowlist or denylist of a COS bucket.
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
  referer_type:
    description:
      - Referer rule mode.
    type: str
    choices: [White-List, Black-List]
  allow_empty:
    description:
      - Whether requests with an empty Referer are allowed.
    type: bool
    default: true
  domains:
    description:
      - Referer domain patterns managed as an exact set.
    type: list
    elements: str

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
- susunola.tencentcloud.cos_bucket_referer:
    name: public-assets
    referer_type: White-List
    allow_empty: false
    domains: ['*.example.com', example.com]
"""
RETURN = r"""referer: {description: Effective hotlink-protection configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import (
    get_bucket_referer, normalize_bucket_referer as normalize,
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
            "referer_type": {"choices": ["White-List", "Black-List"]},
            "allow_empty": {"type": "bool", "default": True},
            "domains": {"type": "list", "elements": "str"},
        },
        required_if=[("state", "present", ["referer_type", "domains"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_bucket_referer(client, bucket)
        target = normalize(
            {
                "Status": "Enabled",
                "RefererType": module.params.get("referer_type"),
                "EmptyReferConfiguration": "Allow" if module.params["allow_empty"] else "Deny",
                "DomainList": {"Domain": module.params.get("domains") or []},
            }
        )
        if module.params["state"] == "absent":
            target = None
        if current == target:
            module.exit_json(changed=False, referer=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if target is None:
                client.delete_bucket_referer(Bucket=bucket)
            else:
                client.put_bucket_referer(Bucket=bucket, RefererConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), referer=current if module.check_mode else target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
