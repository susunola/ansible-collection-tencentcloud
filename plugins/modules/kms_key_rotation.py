#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: kms_key_rotation
short_description: Manage automatic rotation for a Tencent Cloud KMS key
version_added: "0.13.0"
description: Enables or disables automatic rotation and reconciles its period independently from key lifecycle.
options:
  key_id: {description: KMS key ID., type: str, required: true}
  enabled: {description: Whether automatic rotation is enabled., type: bool, default: true}
  rotation_days: {description: Rotation period in days when enabled., type: int, default: 365}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.kms_key_rotation:
    key_id: key-abc123
    enabled: true
    rotation_days: 90
'''
RETURN = r'''
rotation:
  description: Effective rotation configuration.
  type: dict
  returned: always
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_kms():
    from tencentcloud.kms.v20190118 import kms_client, models
    return models, kms_client


def build_status_request(models, key_id):
    request = models.GetKeyRotationStatusRequest()
    request.KeyId = key_id
    return request


def build_update_request(models, key_id, enabled, rotation_days):
    request = models.EnableKeyRotationRequest() if enabled else models.DisableKeyRotationRequest()
    request.KeyId = key_id
    if enabled:
        request.RotateDays = rotation_days
    return request


def build_describe_request(models, key_id):
    request = models.DescribeKeyRequest()
    request.KeyId = key_id
    return request


def get_rotation(module, client, models, key_id):
    response = module.sdk_call(client.GetKeyRotationStatus, build_status_request(models, key_id))
    key_response = module.sdk_call(client.DescribeKey, build_describe_request(models, key_id))
    metadata = getattr(key_response, "KeyMetadata", None)
    return {
        "enabled": bool(getattr(response, "KeyRotationEnabled", False)),
        "rotation_days": getattr(metadata, "RotateDays", None),
        "last_rotation_time": getattr(metadata, "LastRotateTime", None),
        "next_rotation_time": getattr(metadata, "NextRotateTime", None),
    }


def wait_for_rotation(module, client, models, key_id, enabled, rotation_days):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = get_rotation(module, client, models, key_id)
        if current["enabled"] == enabled and (
            not enabled or current["rotation_days"] in (None, rotation_days)
        ):
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for KMS key rotation",
                rotation=current,
                expected={"enabled": enabled, "rotation_days": rotation_days},
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "key_id": {"type": "str", "required": True},
            "enabled": {"type": "bool", "default": True},
            "rotation_days": {"type": "int", "default": 365},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not 7 <= p["rotation_days"] <= 365:
        module.fail_json(msg="rotation_days must be between 7 and 365")
    module.require_sdk()
    models, kms_client = _load_kms()
    client = module.create_client(kms_client.KmsClient, "kms.tencentcloudapi.com")
    try:
        current = get_rotation(module, client, models, p["key_id"])
        desired = {"enabled": p["enabled"], "rotation_days": p["rotation_days"] if p["enabled"] else current["rotation_days"]}
        changed = current["enabled"] != p["enabled"] or (
            p["enabled"] and current["rotation_days"] not in (None, p["rotation_days"])
        )
        if not changed:
            module.exit_json(changed=False, rotation=current, msg="KMS key rotation is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), rotation=current, msg="Would update KMS key rotation")
        request = build_update_request(models, p["key_id"], p["enabled"], p["rotation_days"])
        module.sdk_call(client.EnableKeyRotation if p["enabled"] else client.DisableKeyRotation, request)
        current = wait_for_rotation(module, client, models, p["key_id"], p["enabled"], p["rotation_days"])
        module.exit_json(changed=True, **(diff or {}), rotation=current, msg="KMS key rotation updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed", error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
