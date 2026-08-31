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
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  rules: {type: list, elements: dict, description: Complete COS SDK-compatible OriginRule list.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
"""
RETURN = r"""origin: {description: Effective origin configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if not value:
        return None
    root = value.get("OriginConfiguration", value)
    rules = root.get("OriginRule") or []
    if isinstance(rules, dict):
        rules = [rules]
    return {"OriginRule": sorted(rules, key=lambda item: int(item.get("RulePriority") or 0))}


def get_origin(client, bucket):
    try:
        return normalize(client.get_bucket_origin(Bucket=bucket))
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
