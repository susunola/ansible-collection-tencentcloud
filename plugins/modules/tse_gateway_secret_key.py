#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_secret_key
short_description: Manage a Tencent Cloud TSE API gateway secret key
version_added: "0.14.0"
description:
  - Creates, enables, disables, rotates and deletes API gateway credentials.
  - Credential material is redacted from normal results. Set C(reveal_secret_value=true) only when a protected downstream task must capture it.
  - Protocol and credential configuration changes require explicit destructive rotation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  secret_key_id: {type: str, description: Existing secret key ID.}
  name: {type: str, description: Instance-unique secret key name.}
  secret_type: {type: str, choices: [ApiKey, Basic, Hmac, OAuth2, JWT], description: Credential protocol.}
  generate_type: {type: str, choices: [System, Custom, KMS], description: Credential generation mode.}
  resource_type: {type: str, choices: [Consumer, ModelService], description: Owning resource type.}
  status: {type: str, choices: [Enable, Disable], description: Credential status; creation defaults to Enable.}
  secret_value: {type: str, no_log: true, description: Custom secret material.}
  kms_key_name: {type: str, description: KMS key name.}
  kms_key_version: {type: str, description: KMS key version.}
  description: {type: str, description: Credential description.}
  provider: {type: str, description: External provider, for example Dify.}
  jwt_credential_config: {type: dict, description: JWT credential configuration passed to the API.}
  oauth_credential_config: {type: dict, description: OAuth credential configuration passed to the API.}
  oidc_credential_config: {type: dict, description: OIDC credential configuration passed to the API.}
  aksk_credential_config: {type: dict, description: AK/SK credential configuration passed to the API.}
  cam_credential_config: {type: dict, description: CAM credential configuration passed to the API.}
  bearer_token_credential_config: {type: dict, description: Bearer token configuration passed to the API.}
  basic_credential_config: {type: dict, description: Basic Auth configuration passed to the API.}
  custom_header_credential_config: {type: dict, description: Custom header credential configuration passed to the API.}
  query_param_credential_config: {type: dict, description: Query parameter credential configuration passed to the API.}
  rotate_secret: {type: bool, default: false, description: Delete and recreate an existing credential.}
  allow_recreate: {type: bool, default: false, description: Required safety guard for destructive rotation.}
  reveal_secret_value: {type: bool, default: false, description: Explicitly return plaintext secret_value.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_secret_key:
    gateway_id: gateway-xxxxxxxx
    name: mobile-api-key
    secret_type: ApiKey
    generate_type: System
    resource_type: Consumer
"""
RETURN = r"""
secret_key: {description: Effective credential metadata with secret material redacted., type: dict, returned: always}
secret_value: {description: Plaintext credential value when explicitly requested., type: str, returned: reveal_secret_value is true}
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


CONFIG_FIELDS = {
    "jwt_credential_config": "JWTCredentialConfig",
    "oauth_credential_config": "OAuthCredentialConfig",
    "oidc_credential_config": "OIDCCredentialConfig",
    "aksk_credential_config": "AKSKCredentialConfig",
    "cam_credential_config": "CAMCredentialConfig",
    "bearer_token_credential_config": "BearerTokenCredentialConfig",
    "basic_credential_config": "BasicCredentialConfig",
    "custom_header_credential_config": "CustomHeaderCredentialConfig",
    "query_param_credential_config": "QueryParamCredentialConfig",
}
IMMUTABLE_FIELDS = ["Name", "SecretType", "GenerateType", "ResourceType", "KmsKeyName", "KmsKeyVersion", "Description", "Provider"] + list(
    CONFIG_FIELDS.values()
)


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def scrub_secret(value):
    sensitive = ("SecretValue", "Secret", "ClientSecret", "SecretAccessKey", "SecretKey", "Token", "Password", "HeaderValue", "ParamValue")
    if isinstance(value, dict):
        return {k: scrub_secret(v) for k, v in value.items() if k not in sensitive}
    if isinstance(value, list):
        return [scrub_secret(item) for item in value]
    return value


def create_payload(p):
    payload = {
        "GatewayId": p["gateway_id"],
        "SecretType": p["secret_type"],
        "Name": p["name"],
        "GenerateType": p["generate_type"],
        "ResourceType": p["resource_type"],
    }
    mapping = {
        "kms_key_name": "KmsKeyName",
        "kms_key_version": "KmsKeyVersion",
        "secret_value": "SecretValue",
        "description": "Description",
        "provider": "Provider",
    }
    mapping.update(CONFIG_FIELDS)
    for source, target in mapping.items():
        if p.get(source) is not None:
            payload[target] = p[source]
    return payload


def create_request(models, p):
    r = models.CreateCloudNativeAPIGatewaySecretKeyRequest()
    r.from_json_string(json.dumps(create_payload(p)))
    return r


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewaySecretKeyListRequest()
    r.GatewayId, r.Offset, r.Limit, r.ResourceType = p["gateway_id"], offset, 20, p.get("resource_type")
    return r


def detail_request(models, p, secret_id):
    r = models.DescribeCloudNativeAPIGatewaySecretKeyRequest()
    r.GatewayId, r.SecretKeyId = p["gateway_id"], secret_id
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewaySecretKeyRequest()
    r.GatewayId, r.SecretKeyId = p["gateway_id"], current["SecretKeyId"]
    return r


def status_request(models, p, current, status):
    r = models.ModifyCloudNativeAPIGatewaySecretKeyStatusRequest()
    r.GatewayId, r.SecretKeyId, r.Status = p["gateway_id"], current["SecretKeyId"], status
    return r


def value_request(models, p, current):
    r = models.DescribeCloudNativeAPIGatewaySecretKeyValueRequest()
    r.GatewayId, r.SecretKeyId = p["gateway_id"], current["SecretKeyId"]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewaySecretKeyList, list_request(models, p, offset)).Result
        values = result.SecretKeys if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if (p.get("secret_key_id") and value.get("SecretKeyId") == p["secret_key_id"]) or (not p.get("secret_key_id") and value.get("Name") == p["name"]):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway secret keys matched; specify secret_key_id")
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeCloudNativeAPIGatewaySecretKey, detail_request(models, p, matches[0]["SecretKeyId"])).Result
    return scrub_secret(detail._serialize(allow_none=True) if detail else matches[0])


def validate_creation(module, p):
    missing = [key for key in ("name", "secret_type", "generate_type", "resource_type") if not p.get(key)]
    if missing:
        module.fail_json(msg="Required for secret key creation: %s" % ", ".join(missing))
    if p["generate_type"] == "Custom" and not p.get("secret_value"):
        module.fail_json(msg="secret_value is required when generate_type=Custom")
    if p["generate_type"] == "KMS" and (not p.get("kms_key_name") or not p.get("kms_key_version")):
        module.fail_json(msg="kms_key_name and kms_key_version are required when generate_type=KMS")


def desired_immutable(p, current):
    target = {}
    reverse = {value: key for key, value in CONFIG_FIELDS.items()}
    standard = {
        "Name": "name",
        "SecretType": "secret_type",
        "GenerateType": "generate_type",
        "ResourceType": "resource_type",
        "KmsKeyName": "kms_key_name",
        "KmsKeyVersion": "kms_key_version",
        "Description": "description",
        "Provider": "provider",
    }
    for field in IMMUTABLE_FIELDS:
        source = reverse.get(field) or standard[field]
        target[field] = p.get(source) if p.get(source) is not None else (current or {}).get(field)
    return target


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "secret_key_id": {},
        "name": {},
        "secret_type": {"choices": ["ApiKey", "Basic", "Hmac", "OAuth2", "JWT"]},
        "generate_type": {"choices": ["System", "Custom", "KMS"]},
        "resource_type": {"choices": ["Consumer", "ModelService"]},
        "status": {"choices": ["Enable", "Disable"]},
        "secret_value": {"no_log": True},
        "kms_key_name": {},
        "kms_key_version": {},
        "description": {},
        "provider": {},
        "rotate_secret": {"type": "bool", "default": False},
        "allow_recreate": {"type": "bool", "default": False},
        "reveal_secret_value": {"type": "bool", "default": False},
    }
    spec.update({key: {"type": "dict", "no_log": True} for key in CONFIG_FIELDS})
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("secret_key_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, secret_key=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewaySecretKey, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), secret_key=None)
        if p["rotate_secret"] and not p["allow_recreate"]:
            module.fail_json(msg="rotate_secret=true requires allow_recreate=true because rotation deletes the existing credential")
        if not current or p["rotate_secret"]:
            validate_creation(module, p)
        immutable = desired_immutable(p, current)
        before = {key: (current or {}).get(key) for key in immutable}
        drift = current and before != immutable
        if drift and not p["rotate_secret"]:
            module.fail_json(
                msg="Immutable secret key configuration differs; use rotate_secret=true and allow_recreate=true to replace it",
                immutable_before=before,
                immutable_after=immutable,
            )
        desired_status = p.get("status") or ((current or {}).get("Status") if current else "Enable")
        changed = not current or bool(p["rotate_secret"]) or (current.get("Status") != desired_status)
        if not changed:
            result = {"changed": False, "secret_key": current}
        else:
            diff = maybe_diff(module, current, dict(immutable, Status=desired_status))
            if not module.check_mode:
                if current and p["rotate_secret"]:
                    module.sdk_call(client.DeleteCloudNativeAPIGatewaySecretKey, delete_request(models, p, current))
                    current = None
                if not current:
                    response = module.sdk_call(client.CreateCloudNativeAPIGatewaySecretKey, create_request(models, p))
                    p["secret_key_id"] = response.Result.ID
                    current = find(module, client, models, p)
                if current.get("Status") != desired_status:
                    module.sdk_call(client.ModifyCloudNativeAPIGatewaySecretKeyStatus, status_request(models, p, current, desired_status))
                    current = find(module, client, models, p)
            result = {"changed": True, "secret_key": current if not module.check_mode else dict(immutable, Status=desired_status)}
            result.update(diff or {})
        if p["reveal_secret_value"] and not module.check_mode and result["secret_key"]:
            result["secret_value"] = module.sdk_call(client.DescribeCloudNativeAPIGatewaySecretKeyValue, value_request(models, p, result["secret_key"])).Result
        module.exit_json(**result)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
