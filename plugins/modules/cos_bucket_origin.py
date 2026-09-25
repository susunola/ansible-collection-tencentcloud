#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_origin
short_description: Manage Tencent Cloud COS bucket origin rules
version_added: "0.14.0"
description: Reconciles the complete origin-rule set of a COS bucket.
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
  rules:
    description:
      - Complete COS SDK-compatible OriginRule list.
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
  - module: susunola.tencentcloud.cos_bucket_origin_info
    description: Gather Tencent Cloud COS bucket origin rules.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_origin:
    region: ap-guangzhou
    name: media
    rules:
      - RulePriority: 1
        OriginType: Mirror
        OriginCondition: {HTTPStatusCode: 404, Prefix: images/}
        OriginParameter: {Protocol: https, FollowRedirect: 'true', HttpRedirectCode: 302}

- name: Delete the origin
  susunola.tencentcloud.cos_bucket_origin:
    state: absent
    name: media
"""
RETURN = r"""origin:
  description:
    - Effective origin configuration.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_origin as normalize, get_origin
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "rules": {"type": "list", "elements": "dict"},
        },
        required_if=[("state", "present", ["rules"])],
        supports_check_mode=True,
    )
    p = module.params
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(p["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_origin(client, bucket)
        target = normalize({"OriginRule": p.get("rules") or []}) if p["state"] == "present" else None
        if current == target:
            module.exit_json(changed=False, origin=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if target is None:
                client.delete_bucket_origin(Bucket=bucket)
            else:
                client.put_bucket_origin(Bucket=bucket, OriginConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), origin=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
