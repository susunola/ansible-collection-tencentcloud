#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ssm_secret_version
short_description: Manage Tencent Cloud SSM secret versions
version_added: "0.14.0"
description: Creates and deletes explicitly named versions of an existing Tencent Cloud SSM secret.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  secret_name:
    description:
      - Parent SSM secret name.
    type: str
    required: true
  version_id:
    description:
      - Explicit immutable version identifier.
    type: str
    required: true
  secret_string:
    description:
      - Plain-text secret value.
    type: str
  secret_binary:
    description:
      - Base64-encoded binary secret value.
    type: str
  force_replace:
    description:
      - Delete and recreate the version when its immutable value differs.
    type: bool
    default: false

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
  - module: susunola.tencentcloud.ssm_secret_version_info
    description: Gather Tencent Cloud Secrets Manager versions.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_secret_version:
    secret_name: prod/database
    version_id: release-2026-08-30
    secret_string: "{{ vault_database_password }}"

- name: Delete the version
  susunola.tencentcloud.ssm_secret_version:
    state: absent
    secret_name: prod/database
    version_id: release-2026-08-30
"""
RETURN = r"""version:
  description:
    - Secret version metadata without its sensitive value.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    SecretName: prod/database
    VersionId: release-2026-08-30
    SecretString: vault-password-value
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client

    return models, ssm_client


def list_request(models, secret_name):
    request = models.ListSecretVersionIdsRequest()
    request.SecretName = secret_name
    return request


def get_request(models, p):
    request = models.GetSecretValueRequest()
    request.SecretName, request.VersionId = p["secret_name"], p["version_id"]
    return request


def create_request(models, p):
    request = models.PutSecretValueRequest()
    request.SecretName, request.VersionId = p["secret_name"], p["version_id"]
    request.SecretString, request.SecretBinary = p.get("secret_string"), p.get("secret_binary")
    return request


def delete_request(models, p):
    request = models.DeleteSecretVersionRequest()
    request.SecretName, request.VersionId = p["secret_name"], p["version_id"]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.ListSecretVersionIds, list_request(models, p["secret_name"]))
    for item in list(response.Versions or []):
        if item.VersionId == p["version_id"]:
            return item._serialize(allow_none=True)
    return None


def value_matches(module, client, models, p):
    response = module.sdk_call(client.GetSecretValue, get_request(models, p))
    if p.get("secret_string") is not None:
        return response.SecretString == p["secret_string"]
    return response.SecretBinary == p.get("secret_binary")


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "secret_name": {"required": True},
            "version_id": {"required": True},
            "secret_string": {"no_log": True},
            "secret_binary": {"no_log": True},
            "force_replace": {"type": "bool", "default": False},
        },
        mutually_exclusive=[("secret_string", "secret_binary")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and p.get("secret_string") is None and p.get("secret_binary") is None:
        module.fail_json(msg="secret_string or secret_binary is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, version=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteSecretVersion, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), version=current if module.check_mode else None)
        replace = bool(current and not value_matches(module, client, models, p))
        if current and not replace:
            module.exit_json(changed=False, version=current)
        if replace and not p["force_replace"]:
            module.fail_json(msg="secret version values are immutable; set force_replace=true to delete and recreate the version")
        diff = maybe_diff(module, current, {"VersionId": p["version_id"]})
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteSecretVersion, delete_request(models, p))
            module.sdk_call(client.PutSecretValue, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), version=current if not module.check_mode else {"VersionId": p["version_id"]})
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
