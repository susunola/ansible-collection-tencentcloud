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
description: Creates, rotates and deletes API Gateway client credentials.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  access_key_id: {type: str, description: Existing or manually assigned key ID.}
  access_key_secret: {type: str, description: Secret for a manual key or secret rotation.}
  name: {type: str, description: Key display name.}
  key_type: {type: str, choices: [auto, manual], default: auto, description: Credential generation mode.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.api_gateway_api_key:
    name: production-client
    key_type: auto
"""
RETURN = r"""api_key: {description: API key metadata. Secret values are redacted., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
            current = safe(result._serialize(allow_none=True))
        module.exit_json(changed=True, **(diff or {}), api_key=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
