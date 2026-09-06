#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_model_service
short_description: Manage a Tencent Cloud TSE AI gateway model service
version_added: "0.14.0"
description:
  - Creates, updates and deletes an AI gateway LLM model service.
  - C(config) uses the SDK request field names. ServiceType, ModelProvider, ModelProtocol and SecretKeyIds are immutable after creation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  model_service_id: {type: str, description: Existing model service ID.}
  name: {type: str, description: Instance-unique model service name.}
  config: {type: dict, description: Model service configuration in SDK field shape, excluding Name and GatewayId.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_model_service:
    gateway_id: gateway-xxxxxxxx
    name: openai-primary
    config:
      ServiceType: LLMService
      ModelProvider: OpenAI
      ModelProtocol: OpenAI/v1
      ModelSelector: Specify
      SecretKeyIds: [secret-key-xxxxxxxx]
      DefaultModel: gpt-4.1
      ConnectTimeout: 10000
      ReadTimeout: 60000
"""
RETURN = r"""model_service: {description: Effective model service metadata and configuration., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


IMMUTABLE = ("ServiceType", "ModelProvider", "ModelProtocol", "SecretKeyIds")
MODIFIABLE = (
    "Name",
    "DefaultModel",
    "ModelSelector",
    "EnableModelFallback",
    "ModelFallbackRule",
    "EnableModelParamCheck",
    "ModelParamCheckRule",
    "Description",
    "UpstreamURL",
    "ConnectTimeout",
    "WriteTimeout",
    "ReadTimeout",
    "Retries",
    "UpstreamUrlMode",
    "SNI",
    "QuotaLimit",
    "Tags",
    "ModelRewriteRules",
    "SourceId",
    "Namespace",
    "ServiceName",
    "Protocol",
    "ExtParams",
    "KeyRotationEnabled",
    "KeyRotationPeriodDays",
    "ExternalInstanceId",
    "CustomProviderName",
    "LoadBalanceConfig",
)
CREATE_FIELDS = IMMUTABLE + tuple(item for item in MODIFIABLE if item != "Name")


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def json_request(cls, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewayLLMModelServicesRequest()
    r.GatewayId, r.Offset, r.Limit = p["gateway_id"], offset, 100
    return r


def detail_request(models, p, model_service_id):
    r = models.DescribeCloudNativeAPIGatewayLLMModelServiceRequest()
    r.GatewayId, r.ModelServiceId = p["gateway_id"], model_service_id
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayLLMModelServiceRequest()
    r.GatewayId, r.ModelServiceId = p["gateway_id"], current["Id"]
    return r


def create_payload(p):
    config = p["config"]
    return dict({"GatewayId": p["gateway_id"], "Name": p["name"]}, **{key: config[key] for key in CREATE_FIELDS if key in config})


def modify_payload(p, current):
    config = p.get("config") or {}
    payload = {"GatewayId": p["gateway_id"], "ModelServiceId": current["Id"]}
    for key in MODIFIABLE:
        payload[key] = (p.get("name") or current.get("Name")) if key == "Name" else (config[key] if key in config else current.get(key))
    return payload


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayLLMModelServices, list_request(models, p, offset)).Result
        values = result.DataList if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if (p.get("model_service_id") and value.get("Id") == p["model_service_id"]) or (not p.get("model_service_id") and value.get("Name") == p["name"]):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE model services matched; specify model_service_id")
    if not matches:
        return None
    result = module.sdk_call(client.DescribeCloudNativeAPIGatewayLLMModelService, detail_request(models, p, matches[0]["Id"])).Result
    return result._serialize(allow_none=True) if result else matches[0]


def validate_create(module, p):
    if not p.get("name"):
        module.fail_json(msg="name is required for a new TSE model service")
    config = p.get("config") or {}
    missing = [key for key in ("ServiceType", "ModelProvider", "ModelProtocol", "ModelSelector") if not config.get(key)]
    if missing:
        module.fail_json(msg="Required model service config fields: %s" % ", ".join(missing))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "model_service_id": {},
            "name": {},
            "config": {"type": "dict"},
        },
        required_one_of=[("model_service_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, model_service=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayLLMModelService, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), model_service=None)
        if not current:
            validate_create(module, p)
        config = p.get("config") or {}
        unknown = set(config) - set(CREATE_FIELDS)
        if unknown:
            module.fail_json(msg="Unsupported model service config fields: %s" % ", ".join(sorted(unknown)))
        if current:
            drift = {key: (current.get(key), config[key]) for key in IMMUTABLE if key in config and current.get(key) != config[key]}
            if drift:
                module.fail_json(msg="Immutable model service configuration differs", immutable_drift=drift)
            target = {"Name": p.get("name") or current.get("Name")}
            target.update(config)
            if contains(current, target):
                module.exit_json(changed=False, model_service=current)
            diff = maybe_diff(module, {key: current.get(key) for key in target}, target)
            if not module.check_mode:
                module.sdk_call(
                    client.ModifyCloudNativeAPIGatewayLLMModelService,
                    json_request(models.ModifyCloudNativeAPIGatewayLLMModelServiceRequest, modify_payload(p, current)),
                )
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), model_service=current if not module.check_mode else target)
        target = create_payload(p)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            response = module.sdk_call(
                client.CreateCloudNativeAPIGatewayLLMModelService, json_request(models.CreateCloudNativeAPIGatewayLLMModelServiceRequest, target)
            )
            p["model_service_id"] = response.ModelServiceId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), model_service=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
