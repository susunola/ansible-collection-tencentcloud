#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: ssm_secret_version_info
short_description: Gather Tencent Cloud Secrets Manager versions
version_added: "0.14.0"
description:
  - Lists version metadata or retrieves one exact version.
  - Secret material is read only when C(include_secret_value=true); use task-level C(no_log=true) in that mode.
options:
  secret_name: {type: str, required: true, description: Secret name.}
  version_id: {type: str, description: Exact version ID.}
  include_secret_value: {type: bool, default: false, description: Retrieve sensitive SecretString or SecretBinary for version_id.}
  encryption_public_key: {type: str, description: Optional public key used by supported encrypted-response flows.}
  encryption_algorithm: {type: str, description: Optional encrypted-response algorithm.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_secret_version_info:
    secret_name: prod/database
- susunola.tencentcloud.ssm_secret_version_info:
    secret_name: prod/database
    version_id: SSM_Current
    include_secret_value: true
  no_log: true
"""
RETURN = r"""
versions: {description: Version metadata., type: list, elements: dict, returned: when secret material is not requested}
secret_value: {description: Sensitive exact version response., type: dict, returned: when include_secret_value is true}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client

    return models, ssm_client


def list_request(models, name):
    request = models.ListSecretVersionIdsRequest()
    request.SecretName = name
    return request


def value_request(models, p):
    request = models.GetSecretValueRequest()
    request.SecretName, request.VersionId = p["secret_name"], p["version_id"]
    if p.get("encryption_public_key") is not None:
        request.EncryptionPublicKey = p["encryption_public_key"]
    if p.get("encryption_algorithm") is not None:
        request.EncryptionAlgorithm = p["encryption_algorithm"]
    return request


def run_module():
    spec = {
        "secret_name": {"required": True},
        "version_id": {},
        "include_secret_value": {"type": "bool", "default": False},
        "encryption_public_key": {},
        "encryption_algorithm": {},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["include_secret_value"] and not p.get("version_id"):
        module.fail_json(msg="version_id is required when include_secret_value=true")
    if (p.get("encryption_public_key") or p.get("encryption_algorithm")) and not p["include_secret_value"]:
        module.fail_json(msg="encryption response options require include_secret_value=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        if p["include_secret_value"]:
            response = module.sdk_call(client.GetSecretValue, value_request(models, p))
            value = response._serialize(allow_none=True)
            request_id = value.pop("RequestId", response.RequestId)
            module.exit_json(changed=False, secret_value=value, request_id=request_id)
        response = module.sdk_call(client.ListSecretVersionIds, list_request(models, p["secret_name"]))
        values = [item._serialize(allow_none=True) for item in response.Versions or []]
        if p.get("version_id") is not None:
            values = [item for item in values if item.get("VersionId") == p["version_id"]]
        module.exit_json(changed=False, versions=values, request_id=response.RequestId)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
