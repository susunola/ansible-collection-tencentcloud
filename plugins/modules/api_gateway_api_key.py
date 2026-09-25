#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: api_gateway_api_key
short_description: Manage Tencent Cloud API Gateway API keys
version_added: "0.14.0"
description:
  - Creates, rotates and deletes API Gateway client credentials.
  - The API returns a generated secret only in the response that creates the key, so
    the creation task is the only chance to read it. Credential material is redacted
    from results by default; set C(reveal_secret_value=true) on that task when the
    secret has to be captured, and give the task C(no_log=true).
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  access_key_id:
    description:
      - Existing or manually assigned key ID.
    type: str
  access_key_secret:
    description:
      - Secret for a manual key or secret rotation.
    type: str
  name:
    description:
      - Key display name.
    type: str
  key_type:
    description:
      - Credential generation mode.
    type: str
    choices: [auto, manual]
    default: auto
  reveal_secret_value:
    description:
      - Return the generated secret on the run that creates the key. The API never exposes it
        again, so a key created without this is unusable unless the secret was supplied with
        I(key_type=manual).
      - Off by default, because the value is written to the task result and from there to any
        log the play keeps. Set it together with task-level C(no_log=true).
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
  - module: susunola.tencentcloud.api_gateway_api_key_info
    description: Gather information about Tencent Cloud APIGATEWAY api keys.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- name: Create an API key
  susunola.tencentcloud.api_gateway_api_key:
    name: production-client
    key_type: auto
  register: api_key

- name: Create an API key and capture its generated secret
  susunola.tencentcloud.api_gateway_api_key:
    name: production-client
    key_type: auto
    reveal_secret_value: true
  no_log: true
  register: api_key_secret

- name: Delete an API key
  susunola.tencentcloud.api_gateway_api_key:
    name: production-client
    state: absent
"""
RETURN = r"""api_key:
  description:
    - API key metadata. C(AccessKeySecret) is present only on the run that created the key,
      and only when I(reveal_secret_value=true).
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    AccessKeyId: AKID-2001
    SecretName: production-client
    AccessKeyType: auto
    AccessKeySecret: secret-3001
    Status: 1
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models

    return models, apigateway_client


def build_get(models, key_id):
    request = models.DescribeApiKeyRequest()
    request.AccessKeyId = key_id
    return request


def build_list(models, name):
    request = models.DescribeApiKeysStatusRequest()
    request.Offset, request.Limit = 0, 100
    if name:
        item = models.Filter()
        item.Name, item.Values = "SecretName", [name]
        request.Filters = [item]
    return request


def build_create(models, p):
    request = models.CreateApiKeyRequest()
    request.SecretName, request.AccessKeyType = p["name"], p["key_type"]
    if p["key_type"] == "manual":
        request.AccessKeyId, request.AccessKeySecret = p["access_key_id"], p["access_key_secret"]
    return request


def build_update(models, key_id, secret):
    request = models.UpdateApiKeyRequest()
    request.AccessKeyId, request.AccessKeySecret = key_id, secret
    return request


def build_delete(models, key_id):
    request = models.DeleteApiKeyRequest()
    request.AccessKeyId = key_id
    return request


def safe(value):
    if not value:
        return value
    result = dict(value)
    result.pop("AccessKeySecret", None)
    return result


def find(module, client, models, key_id, name):
    if key_id:
        try:
            result = module.sdk_call(client.DescribeApiKey, build_get(models, key_id)).Result
            return safe(result._serialize(allow_none=True)) if result else None
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
    result = module.sdk_call(client.DescribeApiKeysStatus, build_list(models, name)).Result
    matches = [safe(x._serialize(allow_none=True)) for x in list(result.ApiKeySet or []) if x.SecretName == name]
    if len(matches) > 1:
        module.fail_json(msg="Multiple API keys have the requested name", name=name)
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "access_key_id": {"no_log": True},
            "access_key_secret": {"no_log": True},
            "name": {},
            "key_type": {"choices": ["auto", "manual"], "default": "auto"},
            "reveal_secret_value": {"type": "bool", "default": False},
        },
        required_one_of=[("access_key_id", "name")],
        required_if=[("key_type", "manual", ["access_key_id", "access_key_secret"])],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["access_key_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, api_key=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteApiKey, build_delete(models, current["AccessKeyId"]))
            module.exit_json(changed=True, **(diff or {}), api_key=current if module.check_mode else None)
        if current:
            if not p.get("access_key_secret"):
                module.exit_json(changed=False, api_key=current)
            diff = maybe_diff(module, {"AccessKeyId": current["AccessKeyId"]}, {"AccessKeyId": current["AccessKeyId"], "SecretRotated": True})
            if not module.check_mode:
                module.sdk_call(client.UpdateApiKey, build_update(models, current["AccessKeyId"], p["access_key_secret"]))
            module.exit_json(changed=True, **(diff or {}), api_key=current)
        target = {"SecretName": p["name"], "AccessKeyType": p["key_type"]}
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            result = module.sdk_call(client.CreateApiKey, build_create(models, p)).Result
            current = result._serialize(allow_none=True)
            # CreateApiKey is the only response that carries the generated
            # secret: DescribeApiKey and DescribeApiKeysStatus do not return
            # it. Redacting unconditionally, as this did, produced a key whose
            # credential the caller could never learn.
            if not p["reveal_secret_value"]:
                current = safe(current)
        module.exit_json(changed=True, **(diff or {}), api_key=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
