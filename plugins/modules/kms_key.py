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
description: Creates and manages the enabled state, description, rotation and scheduled deletion of a customer master key.
options:
  state: {description: Desired lifecycle state., type: str, choices: [present, absent], default: present}
  key_id: {description: Existing KMS key ID. Takes precedence over O(alias)., type: str}
  alias: {description: Alias used to find or create the key. Exact matching is applied to API search results., type: str}
  description: {description: Human-readable key description., type: str, default: ''}
  key_usage: {description: Cryptographic use of the key. Defaults to C(ENCRYPT_DECRYPT) when creating., type: str, choices: [ENCRYPT_DECRYPT, ASYMMETRIC_DECRYPT_RSA_2048, ASYMMETRIC_DECRYPT_SM2, ASYMMETRIC_SIGN_VERIFY_ECC, ASYMMETRIC_SIGN_VERIFY_SM2]}
  key_type: {description: KMS key origin type. Defaults to C(1) when creating., type: int, choices: [1, 2]}
  tags: {description: Tags applied when creating the key., type: dict}
  enabled: {description: Whether the key is enabled., type: bool, default: true}
  rotation_enabled: {description: "Whether automatic rotation is enabled. When omitted, rotation is not managed.", type: bool}
  rotation_days: {description: Automatic rotation period in days., type: int, default: 365}
  deletion_window_days: {description: Waiting period before permanent deletion., type: int, default: 7}
  deletion_protection: {description: Refuse O(state=absent) while enabled., type: bool, default: false}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

import json
import time

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


def build_list_key_request(models, alias, offset=0):
    request = models.ListKeyDetailRequest()
    request.Offset, request.Limit = offset, 200
    request.KeyState, request.SearchKeyAlias = 0, alias
    return request


def find_key_by_alias(module, client, models, alias):
    if not alias:
        return None
    offset, matches = 0, []
    while True:
        request = build_list_key_request(models, alias, offset)
        response = module.sdk_call(client.ListKeyDetail, request)
        items = list(getattr(response, "KeyMetadatas", None) or [])
        matches.extend(item for item in items if getattr(item, "Alias", None) == alias)
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple KMS keys have the requested alias", alias=alias)
    return _dict(matches[0]) if matches else None


def get_rotation(module, client, models, key_id):
    request = build_rotation_request(models, key_id, None, None)
    response = module.sdk_call(client.GetKeyRotationStatus, request)
    return bool(getattr(response, "KeyRotationEnabled", False))


def set_rotation(module, client, models, key_id, enabled, rotation_days):
    request = build_rotation_request(models, key_id, enabled, rotation_days)
    if enabled:
        module.sdk_call(client.EnableKeyRotation, request)
    else:
        module.sdk_call(client.DisableKeyRotation, request)


def build_rotation_request(models, key_id, enabled, rotation_days):
    if enabled is None:
        request = models.GetKeyRotationStatusRequest()
    elif enabled:
        request = models.EnableKeyRotationRequest()
        request.RotateDays = rotation_days
    else:
        request = models.DisableKeyRotationRequest()
    request.KeyId = key_id
    return request


def build_cancel_deletion_request(models, key_id):
    request = models.CancelKeyDeletionRequest()
    request.KeyId = key_id
    return request


def wait_for_key_state(module, client, models, key_id, expected_states):
    expected = {str(state).lower().replace("_", "") for state in expected_states}
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = describe_key(module, client, models, key_id)
        state = str((current or {}).get("KeyState") or "").lower().replace("_", "")
        if state in expected:
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for KMS key state",
                key=current,
                expected_states=sorted(expected_states),
            )
        time.sleep(module.params["waiter_delay"])


def build_create_request(models, params):
    request = models.CreateKeyRequest()
    request.Alias = params["alias"]
    request.Description = params["description"]
    request.KeyUsage, request.Type = params["key_usage"] or "ENCRYPT_DECRYPT", params["key_type"] or 1
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.TagKey, tag.TagValue = str(key), str(value)
            request.Tags.append(tag)
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
            },
            "key_type": {"type": "int", "choices": [1, 2]},
            "tags": {"type": "dict"},
            "enabled": {"type": "bool", "default": True},
            "rotation_enabled": {"type": "bool"},
            "rotation_days": {"type": "int", "default": 365},
            "deletion_window_days": {"type": "int", "default": 7},
            "deletion_protection": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["key_id"] and not p["alias"]:
        module.fail_json(msg="alias is required to create a KMS key")
    if p["state"] == "absent" and not p["key_id"] and not p["alias"]:
        module.fail_json(msg="key_id or alias is required when state=absent")
    if p["state"] == "absent" and p["deletion_protection"]:
        module.fail_json(msg="KMS key deletion is blocked by deletion_protection")
    if not 7 <= p["deletion_window_days"] <= 30:
        module.fail_json(msg="deletion_window_days must be between 7 and 30")
    if not 7 <= p["rotation_days"] <= 365:
        module.fail_json(msg="rotation_days must be between 7 and 365")
    module.require_sdk()
    models, kms_client = _load_kms()
    client = module.create_client(kms_client.KmsClient, "kms.tencentcloudapi.com")
    try:
        current = describe_key(module, client, models, p["key_id"])
        if current is None:
            current = find_key_by_alias(module, client, models, p["alias"])
            if current:
                p["key_id"] = current.get("KeyId")
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, key=None, msg="KMS key is absent")
            if current and str(current.get("KeyState", "")).lower() in ("pendingdelete", "pending_delete"):
                module.exit_json(changed=False, key=None, msg="KMS key deletion already scheduled")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), key=current, msg="Would schedule KMS key deletion")
            request = models.ScheduleKeyDeletionRequest()
            request.KeyId, request.PendingWindowInDays = p["key_id"], p["deletion_window_days"]
            module.sdk_call(client.ScheduleKeyDeletion, request)
            current = wait_for_key_state(module, client, models, p["key_id"], ("PendingDelete",))
            module.exit_json(changed=True, **(diff or {}), key=current, msg="KMS key deletion scheduled")
        if current is None:
            desired = {
                "Alias": p["alias"], "Description": p["description"],
                "KeyUsage": p["key_usage"] or "ENCRYPT_DECRYPT",
                "Type": p["key_type"] or 1, "Enabled": p["enabled"],
            }
            if p["tags"] is not None:
                desired["Tags"] = p["tags"]
            if p["rotation_enabled"] is not None:
                desired["RotationEnabled"] = p["rotation_enabled"]
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), key=None, msg="Would create KMS key")
            response = module.sdk_call(client.CreateKey, build_create_request(models, p))
            p["key_id"] = getattr(response, "KeyId", None)
            current = wait_for_key_state(module, client, models, p["key_id"], ("Enabled",))
            if not p["enabled"]:
                request = models.DisableKeyRequest()
                request.KeyId = p["key_id"]
                module.sdk_call(client.DisableKey, request)
                current = wait_for_key_state(module, client, models, p["key_id"], ("Disabled",))
            if p["rotation_enabled"] is not None:
                set_rotation(module, client, models, p["key_id"], p["rotation_enabled"], p["rotation_days"])
                current = describe_key(module, client, models, p["key_id"])
            module.exit_json(changed=True, **(diff or {}), key=current, msg="KMS key created")
        changes = []
        immutable_drift = {}
        if p["alias"] is not None and current.get("Alias") != p["alias"]:
            immutable_drift["alias"] = {"current": current.get("Alias"), "desired": p["alias"]}
        if p["key_usage"] is not None and current.get("KeyUsage") != p["key_usage"]:
            immutable_drift["key_usage"] = {"current": current.get("KeyUsage"), "desired": p["key_usage"]}
        if p["key_type"] is not None and int(current.get("Type") or 0) != p["key_type"]:
            immutable_drift["key_type"] = {"current": current.get("Type"), "desired": p["key_type"]}
        if immutable_drift:
            module.fail_json(
                msg="KMS key has immutable attribute drift; create a replacement key",
                immutable_drift=immutable_drift,
            )
        pending_delete = str(current.get("KeyState", "")).lower() in ("pendingdelete", "pending_delete")
        if pending_delete:
            changes.append("cancel_deletion")
        if (current.get("Description") or "") != p["description"]:
            changes.append("description")
        is_enabled = str(current.get("KeyState", "")).lower() in ("enabled", "enable")
        if is_enabled != p["enabled"]:
            changes.append("enabled")
        rotation_enabled = None
        if p["rotation_enabled"] is not None:
            rotation_enabled = get_rotation(module, client, models, p["key_id"])
            if rotation_enabled != p["rotation_enabled"]:
                changes.append("rotation")
            elif p["rotation_enabled"] and int(current.get("RotateDays") or 0) != p["rotation_days"]:
                changes.append("rotation")
        if not changes:
            module.exit_json(changed=False, key=current, msg="KMS key is up to date")
        desired = {"Description": p["description"], "Enabled": p["enabled"]}
        if p["rotation_enabled"] is not None:
            desired.update({"RotationEnabled": p["rotation_enabled"], "RotateDays": p["rotation_days"]})
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), key=current, msg="Would update KMS key")
        if "cancel_deletion" in changes:
            request = build_cancel_deletion_request(models, p["key_id"])
            module.sdk_call(client.CancelKeyDeletion, request)
            wait_for_key_state(module, client, models, p["key_id"], ("Enabled", "Disabled"))
        if "description" in changes:
            request = models.UpdateKeyDescriptionRequest()
            request.KeyId, request.Description = p["key_id"], p["description"]
            module.sdk_call(client.UpdateKeyDescription, request)
        if "enabled" in changes:
            request = models.EnableKeyRequest() if p["enabled"] else models.DisableKeyRequest()
            request.KeyId = p["key_id"]
            module.sdk_call(client.EnableKey if p["enabled"] else client.DisableKey, request)
            wait_for_key_state(
                module, client, models, p["key_id"],
                ("Enabled",) if p["enabled"] else ("Disabled",),
            )
        if "rotation" in changes:
            set_rotation(module, client, models, p["key_id"], p["rotation_enabled"], p["rotation_days"])
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
