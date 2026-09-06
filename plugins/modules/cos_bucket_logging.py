#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_logging
short_description: Manage Tencent Cloud COS bucket access logging
version_added: "0.14.0"
description: Reconciles the access log destination of a COS bucket.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Source bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  target_bucket: {type: str, description: Full destination bucket name for access logs.}
  target_prefix: {type: str, default: '', description: Object key prefix for generated access logs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_logging:
    name: application-data
    target_bucket: audit-logs-1250000000
    target_prefix: cos/application-data/
"""
RETURN = r"""logging: {description: Effective logging configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if not value:
        return None
    root = value.get("BucketLoggingStatus", value)
    enabled = root.get("LoggingEnabled")
    if not enabled:
        return None
    return {"LoggingEnabled": {"TargetBucket": enabled.get("TargetBucket"), "TargetPrefix": enabled.get("TargetPrefix") or ""}}


def get_logging(client, bucket):
    try:
        return normalize(client.get_bucket_logging(Bucket=bucket))
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
            "target_bucket": {},
            "target_prefix": {"default": ""},
        },
        required_if=[("state", "present", ["target_bucket"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_logging(client, bucket)
        target = normalize({"LoggingEnabled": {"TargetBucket": module.params.get("target_bucket"), "TargetPrefix": module.params.get("target_prefix") or ""}})
        if module.params["state"] == "absent":
            target = None
        if current == target:
            module.exit_json(changed=False, logging=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_logging(Bucket=bucket, BucketLoggingStatus=target or {})
        module.exit_json(changed=True, **(diff or {}), logging=current if module.check_mode else target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
