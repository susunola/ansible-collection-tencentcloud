#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ssm_ssh_key_pair_secret
short_description: Manage Tencent Cloud SSM SSH key-pair secrets
version_added: "0.14.0"
description:
  - Creates an SSH key pair and stores its private key in SSM without returning private material.
  - Reconciles description, enabled state, recovery and scheduled deletion.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  secret_name:
    description:
      - SSM secret name.
    type: str
    required: true
  ssh_key_name:
    description:
      - CVM key-pair name; required for creation and immutable afterward.
    type: str
  project_id:
    description:
      - Tencent Cloud project ID.
    type: int
    default: 0
  description:
    description:
      - Secret description.
    type: str
    default: managed by Ansible
  kms_key_id:
    description:
      - Customer KMS key ID.
    type: str
  kms_hsm_cluster_id:
    description:
      - Dedicated KMS HSM cluster ID.
    type: str
  encrypt_type:
    description:
      - KMS or software-key encryption.
    type: int
    choices: [0, 1]
    default: 0
  tags:
    description:
      - Creation tags.
    type: dict
    default:
      {}
  enabled:
    description:
      - Whether the secret is enabled.
    type: bool
    default: true
  recovery_window_days:
    description:
      - Deletion recovery window from 0 through 30 days.
    type: int
    default: 7

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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_ssh_key_pair_secret:
    secret_name: prod-bastion-key
    ssh_key_name: prod_bastion
    project_id: 0
    tags: {env: prod}
"""
RETURN = r"""
secret:
  description:
    - Effective metadata without private key material.
  returned: always
  type: dict
ssh_key_id:
  description:
    - Created CVM key-pair ID; returned only on creation.
  returned: changed
  type: str
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client

    return models, ssm_client


def request(models, class_name, **values):
    result = getattr(models, class_name)()
    for key, value in values.items():
        if value is not None:
            setattr(result, key, value)
    return result


def tags(models, values):
    result = []
    for key, value in sorted(values.items()):
        item = models.Tag()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def create_request(models, p):
    return request(
        models,
        "CreateSSHKeyPairSecretRequest",
        SecretName=p["secret_name"],
        ProjectId=p["project_id"],
        Description=p["description"],
        KmsKeyId=p.get("kms_key_id"),
        Tags=tags(models, p["tags"]),
        SSHKeyName=p["ssh_key_name"],
        KmsHsmClusterId=p.get("kms_hsm_cluster_id"),
        EncryptType=p["encrypt_type"],
    )


def find(module, client, models, name):
    try:
        return module.sdk_call(client.DescribeSecret, request(models, "DescribeSecretRequest", SecretName=name))._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def comparable(value):
    return {
        "SecretName": value.get("SecretName"),
        "Description": value.get("Description") or "",
        "ResourceName": value.get("ResourceName"),
        "ProjectID": int(value.get("ProjectID") or 0),
        "SecretType": int(value.get("SecretType") or 0),
        "Enabled": value.get("Status") == "Enabled",
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "secret_name": {"required": True},
            "ssh_key_name": {},
            "project_id": {"type": "int", "default": 0},
            "description": {"default": "managed by Ansible"},
            "kms_key_id": {},
            "kms_hsm_cluster_id": {},
            "encrypt_type": {"type": "int", "choices": [0, 1], "default": 0},
            "tags": {"type": "dict", "default": {}},
            "enabled": {"type": "bool", "default": True},
            "recovery_window_days": {"type": "int", "default": 7},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not 0 <= p["recovery_window_days"] <= 30:
        module.fail_json(msg="recovery_window_days must be between 0 and 30")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["secret_name"])
        if p["state"] == "absent":
            if not current or current.get("Status") == "PendingDelete":
                module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(
                    client.DeleteSecret, request(models, "DeleteSecretRequest", SecretName=p["secret_name"], RecoveryWindowInDays=p["recovery_window_days"])
                )
                current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current)
        restored = bool(current and current.get("Status") == "PendingDelete")
        if restored and not module.check_mode:
            module.sdk_call(client.RestoreSecret, request(models, "RestoreSecretRequest", SecretName=p["secret_name"]))
            current = find(module, client, models, p["secret_name"])
        if current:
            before = comparable(current)
            if before["SecretType"] != 2:
                module.fail_json(msg="existing secret is not an SSH key-pair secret", current_secret_type=before["SecretType"])
            if p.get("ssh_key_name") is not None and before["ResourceName"] != p["ssh_key_name"]:
                module.fail_json(msg="ssh_key_name is immutable after creation", current_ssh_key_name=before["ResourceName"])
            if before["ProjectID"] != p["project_id"]:
                module.fail_json(msg="project_id is immutable after creation", current_project_id=before["ProjectID"])
            target = dict(before)
            target.update({"Description": p["description"], "Enabled": p["enabled"]})
            if before == target and not restored:
                module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, before, target)
            if not module.check_mode:
                if before["Description"] != target["Description"]:
                    module.sdk_call(
                        client.UpdateDescription, request(models, "UpdateDescriptionRequest", SecretName=p["secret_name"], Description=p["description"])
                    )
                if before["Enabled"] != target["Enabled"]:
                    module.sdk_call(
                        client.EnableSecret if p["enabled"] else client.DisableSecret,
                        request(models, "EnableSecretRequest" if p["enabled"] else "DisableSecretRequest", SecretName=p["secret_name"]),
                    )
                current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current if not module.check_mode else target)
        if not p.get("ssh_key_name"):
            module.fail_json(msg="ssh_key_name is required when creating an SSH key-pair secret")
        target = {
            "SecretName": p["secret_name"],
            "Description": p["description"],
            "ResourceName": p["ssh_key_name"],
            "ProjectID": p["project_id"],
            "SecretType": 2,
            "Enabled": p["enabled"],
        }
        diff = maybe_diff(module, None, target)
        ssh_key_id = None
        if not module.check_mode:
            response = module.sdk_call(client.CreateSSHKeyPairSecret, create_request(models, p))
            ssh_key_id = response.SSHKeyID
            current = find(module, client, models, p["secret_name"])
            if not p["enabled"]:
                module.sdk_call(client.DisableSecret, request(models, "DisableSecretRequest", SecretName=p["secret_name"]))
                current = find(module, client, models, p["secret_name"])
        module.exit_json(changed=True, **(diff or {}), secret=current if not module.check_mode else target, ssh_key_id=ssh_key_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
