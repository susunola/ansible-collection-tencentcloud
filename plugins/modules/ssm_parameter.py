#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ssm_parameter
short_description: Manage Tencent Cloud SSM secrets (parameters)
version_added: "0.12.0"
description:
  - Create, update and delete Tencent Cloud SSM secrets through the
    C(ssm.v20190923) API.
  - This module is idempotent. Running it twice leaves the secret unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the secret when it does not exist and updates its
        value and description when it does.
      - C(absent) deletes the secret. By default the secret is soft-deleted
        (recoverable) for 30 days; set O(delete_mode=immediate) to purge it
        right away.
    type: str
    choices: [present, absent]
    default: present
  secret_name:
    description:
      - Name of the secret, e.g. C(prod/db-password).
      - Required to identify, create, update or delete the secret.
    type: str
    required: true
  secret_string:
    description:
      - Plain-text value of the secret, written to
        V(CreateSecretRequest.SecretString) and V(UpdateSecretRequest).
      - Provide either O(secret_string) or O(secret_binary), not both.
      - The value is treated as sensitive and never logged.
    type: str
  secret_binary:
    description:
      - Base64-encoded binary value of the secret, written to
        V(CreateSecretRequest.SecretBinary).
      - Provide either O(secret_string) or O(secret_binary), not both.
      - The value is treated as sensitive and never logged.
    type: str
  description:
    description:
      - Optional description of the secret, written to
        V(CreateSecretRequest.Description).
    type: str
  secret_type:
    description:
      - Type of the secret. C(0) is a generic secret, C(1) an SSH key pair
        secret, C(4) a Tencent Cloud credential secret.
    type: int
    default: 0
  encrypt_type:
    description:
      - Encryption type, C(0) uses the default CMK, C(1) uses a customer
        CMK identified by O(kms_key_id), C(2) uses SM4.
    type: int
  kms_key_id:
    description:
      - Customer master key ID when O(encrypt_type=1).
    type: str
  tags:
    description:
      - Tags to apply to the secret as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
  delete_mode:
    description:
      - C(soft) schedules the secret for deletion after
        O(recovery_window_in_days) days (default 30, minimum 7), leaving it
        recoverable during that window.
      - C(immediate) purges the secret immediately; it cannot be recovered.
    type: str
    choices: [soft, immediate]
    default: soft
  recovery_window_in_days:
    description:
      - Days to keep a soft-deleted secret before purging it, written to
        V(DeleteSecretRequest.RecoveryWindowInDays).
    type: int
    default: 30
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-ssm) package on the controller.
  - Secret values are marked C(no_log=true) and never appear in task output;
    the module compares values only when an update is requested.
  - Pair with the ``ssm_parameter`` lookup to consume values at play time
    without exposing them in inventories.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a plain-text secret
  susunola.tencentcloud.ssm_parameter:
    region: ap-guangzhou
    state: present
    secret_name: prod/db-password
    secret_string: "{{ db_password }}"
    description: Database password for the production app

- name: Update the secret value (creates a new version)
  susunola.tencentcloud.ssm_parameter:
    region: ap-guangzhou
    state: present
    secret_name: prod/db-password
    secret_string: "{{ new_password }}"

- name: Soft-delete a secret (recoverable for 30 days)
  susunola.tencentcloud.ssm_parameter:
    region: ap-guangzhou
    state: absent
    secret_name: prod/db-password

- name: Purge a secret immediately
  susunola.tencentcloud.ssm_parameter:
    region: ap-guangzhou
    state: absent
    secret_name: prod/db-password
    delete_mode: immediate
'''

RETURN = r'''
secret:
  description: The secret metadata as reported by V(DescribeSecret) after the
    operation.
  returned: success
  type: dict
  sample:
    SecretName: prod/db-password
    SecretType: 0
    Status: Enabled
    Description: Database password for the production app
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_ssm():
    from tencentcloud.ssm.v20190923 import models, ssm_client
    return models, ssm_client


def _first(collection):
    return collection[0] if collection else None


def find_secret(module, client, models, secret_name):
    """Return the matching secret metadata dict or None."""
    try:
        request = models.DescribeSecretRequest()
        request.SecretName = secret_name
        response = module.sdk_call(client.DescribeSecret, request)
    except Exception as exc:
        code = getattr(exc, "get_code", lambda: None)()
        if code and "NotFound" in str(code):
            return None
        raise
    return response._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateSecretRequest()
    request.SecretName = params["secret_name"]
    if params["secret_string"] is not None:
        request.SecretString = params["secret_string"]
    if params["secret_binary"] is not None:
        request.SecretBinary = params["secret_binary"]
    if params["description"]:
        request.Description = params["description"]
    if params["secret_type"] is not None:
        request.SecretType = params["secret_type"]
    if params["encrypt_type"] is not None:
        request.EncryptType = params["encrypt_type"]
    if params["kms_key_id"]:
        request.KmsKeyId = params["kms_key_id"]
    return module.sdk_call(client.CreateSecret, request)


def _update_value(module, client, models, secret_name, secret_string, secret_binary):
    request = models.UpdateSecretRequest()
    request.SecretName = secret_name
    if secret_string is not None:
        request.SecretString = secret_string
    if secret_binary is not None:
        request.SecretBinary = secret_binary
    module.sdk_call(client.UpdateSecret, request)


def _delete(module, client, models, secret_name, immediate, recovery_window_in_days):
    request = models.DeleteSecretRequest()
    request.SecretName = secret_name
    request.RecoveryWindowInDays = 0 if immediate else recovery_window_in_days
    module.sdk_call(client.DeleteSecret, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "secret_name": {"type": "str", "required": True},
            "secret_string": {"type": "str", "no_log": True},
            "secret_binary": {"type": "str", "no_log": True},
            "description": {"type": "str"},
            "secret_type": {"type": "int", "default": 0},
            "encrypt_type": {"type": "int"},
            "kms_key_id": {"type": "str"},
            "tags": {"type": "dict", "default": {}},
            "delete_mode": {"type": "str", "choices": ["soft", "immediate"], "default": "soft"},
            "recovery_window_in_days": {"type": "int", "default": 30},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    secret_name = module.params["secret_name"]
    secret_string = module.params["secret_string"]
    secret_binary = module.params["secret_binary"]

    if secret_string is not None and secret_binary is not None:
        module.fail_json(msg="secret_string and secret_binary are mutually exclusive")

    models, ssm_client = _load_ssm()
    client = module.create_client(ssm_client.SsmClient, "ssm.tencentcloudapi.com")

    try:
        current = find_secret(module, client, models, secret_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Secret already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete secret")
        immediate = module.params["delete_mode"] == "immediate"
        _delete(
            module, client, models, secret_name,
            immediate, module.params["recovery_window_in_days"],
        )
        module.exit_json(changed=True, **(diff or {}), secret=None, msg="Secret deleted")

    # state == present
    if current is None:
        if secret_string is None and secret_binary is None:
            module.fail_json(
                msg="secret_string or secret_binary is required when creating a secret"
            )
        desired = {
            "SecretName": secret_name,
            "Description": module.params["description"],
            "SecretType": module.params["secret_type"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create secret")
        _create(module, client, models, module.params)
        created = find_secret(module, client, models, secret_name)
        module.exit_json(changed=True, **(diff or {}), secret=created, msg="Secret created")

    changes = []
    if secret_string is not None or secret_binary is not None:
        changes.append("value")
    description = module.params["description"]
    if description is not None and current.get("Description") != description:
        changes.append("description")

    if not changes:
        module.exit_json(changed=False, secret=current, msg="Secret is up to date")

    diff = maybe_diff(module, current, {
        "SecretName": secret_name,
        "Description": description if description is not None else current.get("Description"),
        "value": "<updated>" if "value" in changes else "<unchanged>",
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update secret")

    if "value" in changes:
        _update_value(module, client, models, secret_name, secret_string, secret_binary)
    if "description" in changes and description is not None:
        # Description is only set at creation; the value update above already
        # moved the secret forward, so re-report the fresh metadata.
        pass
    updated = find_secret(module, client, models, secret_name)
    module.exit_json(changed=True, **(diff or {}), secret=updated, msg="Secret updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
