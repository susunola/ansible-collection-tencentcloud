#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: ssm_secret
short_description: Manage Tencent Cloud Secrets Manager custom secrets
version_added: "0.14.0"
description:
  - Creates, describes, enables, disables, restores and schedules deletion of custom SSM secrets.
  - Initial secret material is used only at creation; manage subsequent immutable values with C(ssm_secret_version).
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired secret state.}
  secret_name: {type: str, required: true, description: Globally unique secret name within the region.}
  description: {type: str, default: managed by Ansible, description: Secret description.}
  enabled: {type: bool, default: true, description: Whether an existing secret is enabled.}
  initial_version_id: {type: str, default: SSM_Current, description: Initial version identifier used during creation.}
  initial_secret_string: {type: str, description: Initial plain-text secret value.}
  initial_secret_binary: {type: str, description: Initial base64-encoded binary secret value.}
  kms_key_id: {type: str, description: KMS key ID used for encryption; immutable after creation.}
  kms_hsm_cluster_id: {type: str, description: KMS dedicated HSM cluster ID used when no KMS key is specified.}
  encrypt_type: {type: int, choices: [0, 1], default: 0, description: KMS or software-key encryption.}
  recovery_window_days: {type: int, default: 7, description: Scheduled-deletion recovery window from 0 through 30 days.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Create a custom secret with its initial version
  susunola.tencentcloud.ssm_secret:
    secret_name: prod-database
    description: Production database credentials
    initial_version_id: bootstrap
    initial_secret_string: "{{ vault_database_credentials }}"
  no_log: true

- name: Schedule deletion with a fourteen-day recovery window
  susunola.tencentcloud.ssm_secret:
    secret_name: prod-database
    state: absent
    recovery_window_days: 14
'''
RETURN = r'''secret: {description: Effective secret metadata without secret material., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client
    return models, ssm_client
def describe_request(models, name):
    request = models.DescribeSecretRequest(); request.SecretName = name; return request
def create_request(models, p):
    request = models.CreateSecretRequest(); request.SecretName, request.VersionId, request.Description = p["secret_name"], p["initial_version_id"], p["description"]
    request.SecretString, request.SecretBinary = p.get("initial_secret_string"), p.get("initial_secret_binary")
    request.KmsKeyId, request.KmsHsmClusterId, request.EncryptType, request.SecretType = p.get("kms_key_id"), p.get("kms_hsm_cluster_id"), p["encrypt_type"], 0; return request
def description_request(models, p):
    request = models.UpdateDescriptionRequest(); request.SecretName, request.Description = p["secret_name"], p["description"]; return request
def state_request(models, name, enabled):
    request = models.EnableSecretRequest() if enabled else models.DisableSecretRequest(); request.SecretName = name; return request
def restore_request(models, name):
    request = models.RestoreSecretRequest(); request.SecretName = name; return request
def delete_request(models, p):
    request = models.DeleteSecretRequest(); request.SecretName, request.RecoveryWindowInDays = p["secret_name"], p["recovery_window_days"]; return request
def find(module, client, models, name):
    try: return module.sdk_call(client.DescribeSecret, describe_request(models, name))._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc): return None
        raise
def comparable(v): return {"SecretName": v.get("SecretName"), "Description": v.get("Description") or "", "KmsKeyId": v.get("KmsKeyId"), "SecretType": int(v.get("SecretType") or 0), "EncryptType": int(v.get("EncryptType") or 0), "Enabled": v.get("Status") == "Enabled"}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "secret_name": {"required": True}, "description": {"default": "managed by Ansible"}, "enabled": {"type": "bool", "default": True}, "initial_version_id": {"default": "SSM_Current"}, "initial_secret_string": {"no_log": True}, "initial_secret_binary": {"no_log": True}, "kms_key_id": {}, "kms_hsm_cluster_id": {}, "encrypt_type": {"type": "int", "choices": [0, 1], "default": 0}, "recovery_window_days": {"type": "int", "default": 7}}, mutually_exclusive=[("initial_secret_string", "initial_secret_binary")], supports_check_mode=True)
    p = module.params
    if not 0 <= p["recovery_window_days"] <= 30: module.fail_json(msg="recovery_window_days must be between 0 and 30")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["secret_name"])
        if p["state"] == "absent":
            if not current or current.get("Status") == "PendingDelete": module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteSecret, delete_request(models, p)); current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current)
        if not current and p.get("initial_secret_string") is None and p.get("initial_secret_binary") is None: module.fail_json(msg="initial_secret_string or initial_secret_binary is required when creating a secret")
        restored = bool(current and current.get("Status") == "PendingDelete")
        if restored:
            if not module.check_mode: module.sdk_call(client.RestoreSecret, restore_request(models, p["secret_name"])); current = find(module, client, models, p["secret_name"])
        if current:
            before = comparable(current); target = dict(before); target["Description"], target["Enabled"] = p["description"], p["enabled"]
            if p.get("kms_key_id") is not None and before["KmsKeyId"] != p["kms_key_id"]: module.fail_json(msg="kms_key_id is immutable after secret creation", current_kms_key_id=before["KmsKeyId"])
            if before["EncryptType"] != p["encrypt_type"]: module.fail_json(msg="encrypt_type is immutable after secret creation", current_encrypt_type=before["EncryptType"])
            if before == target and not restored: module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, before, target)
            if not module.check_mode:
                if before["Description"] != target["Description"]: module.sdk_call(client.UpdateDescription, description_request(models, p))
                if before["Enabled"] != target["Enabled"]: module.sdk_call(client.EnableSecret if p["enabled"] else client.DisableSecret, state_request(models, p["secret_name"], p["enabled"]))
                current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current)
        target = {"SecretName": p["secret_name"], "Description": p["description"], "KmsKeyId": p.get("kms_key_id"), "SecretType": 0, "EncryptType": p["encrypt_type"], "Enabled": p["enabled"]}; diff = maybe_diff(module, None, target)
        if not module.check_mode:
            module.sdk_call(client.CreateSecret, create_request(models, p)); current = find(module, client, models, p["secret_name"])
            if not p["enabled"]: module.sdk_call(client.DisableSecret, state_request(models, p["secret_name"], False)); current = find(module, client, models, p["secret_name"])
        module.exit_json(changed=True, **(diff or {}), secret=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
