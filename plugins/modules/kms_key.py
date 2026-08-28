#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: kms_key
short_description: Manage a Tencent Cloud KMS key
version_added: "0.13.0"
description: Creates and manages the enabled state, description and scheduled deletion of a customer master key.
options:
  state: {description: Desired lifecycle state., type: str, choices: [present, absent], default: present}
  key_id: {description: Existing KMS key ID; required for updates and deletion., type: str}
  alias: {description: Alias used when creating the key., type: str}
  description: {description: Human-readable key description., type: str, default: ''}
  key_usage: {description: Cryptographic use of the key., type: str, choices: [ENCRYPT_DECRYPT, ASYMMETRIC_DECRYPT_RSA_2048, ASYMMETRIC_DECRYPT_SM2, ASYMMETRIC_SIGN_VERIFY_ECC, ASYMMETRIC_SIGN_VERIFY_SM2], default: ENCRYPT_DECRYPT}
  key_type: {description: KMS key origin type., type: int, choices: [1, 2], default: 1}
  enabled: {description: Whether the key is enabled., type: bool, default: true}
  deletion_window_days: {description: Waiting period before permanent deletion., type: int, default: 7}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

EXAMPLES = r'''
- susunola.tencentcloud.kms_key:
    alias: production-data
    description: Encrypt production data
'''
RETURN = r'''
key:
  description: KMS key metadata or null when deletion is scheduled.
  type: dict
  returned: always
'''


def _load_kms():
    from tencentcloud.kms.v20190118 import kms_client, models

    return models, kms_client


def _dict(value):
    return json.loads(value.to_json_string()) if value else None


def describe_key(module, client, models, key_id):
    if not key_id:
        return None
    request = models.DescribeKeyRequest()
    request.KeyId = key_id
    response = module.sdk_call(client.DescribeKey, request)
    return _dict(getattr(response, "KeyMetadata", None))


def build_create_request(models, params):
    request = models.CreateKeyRequest()
    request.Alias = params["alias"]
    request.Description, request.KeyUsage, request.Type = params["description"], params["key_usage"], params["key_type"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "key_id": {"type": "str"},
            "alias": {"type": "str"},
            "description": {"type": "str", "default": ""},
            "key_usage": {
                "type": "str",
                "choices": [
                    "ENCRYPT_DECRYPT",
                    "ASYMMETRIC_DECRYPT_RSA_2048",
                    "ASYMMETRIC_DECRYPT_SM2",
                    "ASYMMETRIC_SIGN_VERIFY_ECC",
                    "ASYMMETRIC_SIGN_VERIFY_SM2",
                ],
                "default": "ENCRYPT_DECRYPT",
            },
            "key_type": {"type": "int", "choices": [1, 2], "default": 1},
            "enabled": {"type": "bool", "default": True},
            "deletion_window_days": {"type": "int", "default": 7},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["key_id"] and not p["alias"]:
        module.fail_json(msg="alias is required to create a KMS key")
    if p["state"] == "absent" and not p["key_id"]:
        module.fail_json(msg="key_id is required when state=absent")
    if not 7 <= p["deletion_window_days"] <= 30:
        module.fail_json(msg="deletion_window_days must be between 7 and 30")
    module.require_sdk()
    models, kms_client = _load_kms()
    client = module.create_client(kms_client.KmsClient, "kms.tencentcloudapi.com")
    try:
        current = describe_key(module, client, models, p["key_id"])
        if p["state"] == "absent":
            if current and str(current.get("KeyState", "")).lower() in ("pendingdelete", "pending_delete"):
                module.exit_json(changed=False, key=None, msg="KMS key deletion already scheduled")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), key=current, msg="Would schedule KMS key deletion")
            request = models.ScheduleKeyDeletionRequest()
            request.KeyId, request.PendingWindowInDays = p["key_id"], p["deletion_window_days"]
            module.sdk_call(client.ScheduleKeyDeletion, request)
            module.exit_json(changed=True, **(diff or {}), key=None, msg="KMS key deletion scheduled")
        if current is None:
            desired = {"Alias": p["alias"], "Description": p["description"], "KeyUsage": p["key_usage"], "Enabled": p["enabled"]}
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), key=None, msg="Would create KMS key")
            response = module.sdk_call(client.CreateKey, build_create_request(models, p))
            p["key_id"] = getattr(response, "KeyId", None)
            current = describe_key(module, client, models, p["key_id"])
            if not p["enabled"]:
                request = models.DisableKeyRequest()
                request.KeyId = p["key_id"]
                module.sdk_call(client.DisableKey, request)
                current = describe_key(module, client, models, p["key_id"])
            module.exit_json(changed=True, **(diff or {}), key=current, msg="KMS key created")
        changes = []
        if (current.get("Description") or "") != p["description"]:
            changes.append("description")
        is_enabled = str(current.get("KeyState", "")).lower() in ("enabled", "enable")
        if is_enabled != p["enabled"]:
            changes.append("enabled")
        if not changes:
            module.exit_json(changed=False, key=current, msg="KMS key is up to date")
        diff = maybe_diff(module, current, {"Description": p["description"], "Enabled": p["enabled"]})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), key=current, msg="Would update KMS key")
        if "description" in changes:
            request = models.UpdateKeyDescriptionRequest()
            request.KeyId, request.Description = p["key_id"], p["description"]
            module.sdk_call(client.UpdateKeyDescription, request)
        if "enabled" in changes:
            request = models.EnableKeyRequest() if p["enabled"] else models.DisableKeyRequest()
            request.KeyId = p["key_id"]
            module.sdk_call(client.EnableKey if p["enabled"] else client.DisableKey, request)
        module.exit_json(changed=True, **(diff or {}), key=describe_key(module, client, models, p["key_id"]), msg="KMS key updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
