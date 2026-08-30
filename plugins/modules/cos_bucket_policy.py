#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_policy
short_description: Manage Tencent Cloud COS bucket policies
version_added: "0.14.0"
description: Reconciles the complete access policy document of a COS bucket.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  policy: {type: dict, description: Complete COS bucket policy document.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_policy:
    name: application-data
    policy:
      version: '2.0'
      statement:
        - effect: allow
          principal: {qcs: ['qcs::cam::uin/100000000001:uin/100000000001']}
          action: [name/cos:GetObject]
          resource: ['qcs::cos:ap-guangzhou:uid/1250000000:application-data-1250000000/*']
'''
RETURN = r'''policy: {description: Effective normalized bucket policy., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if value is None: return None
    if isinstance(value, str): value = json.loads(value)
    if isinstance(value, dict) and "Policy" in value: value = value["Policy"]
    if isinstance(value, str): value = json.loads(value)
    return value


def get_policy(client, bucket):
    try: return normalize(client.get_bucket_policy(Bucket=bucket))
    except Exception as exc:
        if cos.is_not_found(exc): return None
        raise


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True}, "appid": {}, "policy": {"type": "dict"}}, required_if=[("state", "present", ["policy"])], supports_check_mode=True)
    cos.require_cos_sdk(module); bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module)); client = cos.create_cos_client(module)
    try:
        current = get_policy(client, bucket); target = normalize(module.params.get("policy"))
        if module.params["state"] == "absent":
            if current is None: module.exit_json(changed=False, policy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: client.delete_bucket_policy(Bucket=bucket)
            module.exit_json(changed=True, **(diff or {}), policy=current if module.check_mode else None)
        if current == target: module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode: client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(target, sort_keys=True, separators=(",", ":")))
        module.exit_json(changed=True, **(diff or {}), policy=target)
    except Exception as exc: cos.fail_on_cos_error(module, exc)


def main(): run_module()
if __name__ == "__main__": main()
