#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_model_api
short_description: Manage a Tencent Cloud TSE AI gateway model API
version_added: "0.14.0"
description:
  - Creates, updates and deletes an AI gateway Model API.
  - C(config) uses SDK request field names. SceneType, RequestProtocol and RouteList are immutable after creation.
  - Service associations are normalized from direct, weighted and model-name routes for idempotent comparison.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  model_api_id: {type: str, description: Existing Model API ID.}
  name: {type: str, description: Instance-unique Model API name.}
  config: {type: dict, description: Model API configuration in SDK field shape, excluding Name and GatewayId.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_model_api:
    gateway_id: gateway-xxxxxxxx
    name: chat-completions
    config:
      SceneType: Chat
      RequestProtocol: OpenAI
      ListModelServiceId: [model-service-xxxxxxxx]
      BasePath: /v1
      ModelServiceRoute:
        SelectedTypes: [Weighted]
        WeightedConfig: [{ModelServiceId: model-service-xxxxxxxx, Weight: 100}]
"""
RETURN = r"""model_api: {description: Effective Model API metadata and configuration., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


IMMUTABLE = ("SceneType", "RequestProtocol", "RouteList")
MODIFIABLE = (
    "Name",
    "BasePath",
    "Description",
    "ListModelServiceId",
    "ModelServiceRoute",
    "MatchHeaders",
    "EnableCrossServiceFallback",
    "CrossServiceFallbackConfig",
    "TagFilter",
    "LogConfig",
    "MaxDocumentsConfig",
    "SensitiveWordRoute",
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
    r = models.DescribeCloudNativeAPIGatewayLLMModelAPIsRequest()
    r.GatewayId, r.Offset, r.Limit = p["gateway_id"], offset, 100
    return r


def detail_request(models, p, model_api_id):
    r = models.DescribeCloudNativeAPIGatewayLLMModelAPIRequest()
    r.GatewayId, r.ModelAPIId = p["gateway_id"], model_api_id
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayLLMModelAPIRequest()
    r.GatewayId, r.ModelAPIId = p["gateway_id"], current["Id"]
    return r


def service_ids(value):
    found = set()
    if value.get("ModelServiceId"):
        found.add(value["ModelServiceId"])
    route = value.get("ModelServiceRoute") or {}
    for field in ("WeightedConfig", "ModelNameConfig"):
        for item in route.get(field) or []:
            if item.get("ModelServiceId"):
                found.add(item["ModelServiceId"])
    return sorted(found)


def create_payload(p):
    config = p["config"]
    return dict({"GatewayId": p["gateway_id"], "Name": p["name"]}, **{key: config[key] for key in CREATE_FIELDS if key in config})


def modify_payload(p, current):
    config = p.get("config") or {}
    payload = {"GatewayId": p["gateway_id"], "ModelAPIId": current["Id"]}
    for key in MODIFIABLE:
        if key == "Name":
            payload[key] = p.get("name") or current.get("Name")
        elif key == "ListModelServiceId":
            payload[key] = config[key] if key in config else service_ids(current)
        else:
            payload[key] = config[key] if key in config else current.get(key)
    return payload


def normalized_current(current, key):
    return service_ids(current) if key == "ListModelServiceId" else current.get(key)


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayLLMModelAPIs, list_request(models, p, offset)).Result
        values = result.DataList if result else []
        for item in values or []:
            value = item._serialize(allow_none=True)
            if (p.get("model_api_id") and value.get("Id") == p["model_api_id"]) or (not p.get("model_api_id") and value.get("Name") == p["name"]):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE Model APIs matched; specify model_api_id")
    if not matches:
        return None
    result = module.sdk_call(client.DescribeCloudNativeAPIGatewayLLMModelAPI, detail_request(models, p, matches[0]["Id"])).Result
    return result._serialize(allow_none=True) if result else matches[0]


def validate_create(module, p):
    if not p.get("name"):
        module.fail_json(msg="name is required for a new TSE Model API")
    config = p.get("config") or {}
    missing = [key for key in ("SceneType", "RequestProtocol", "ListModelServiceId") if not config.get(key)]
    if missing:
        module.fail_json(msg="Required Model API config fields: %s" % ", ".join(missing))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "gateway_id": {"required": True},
            "model_api_id": {},
            "name": {},
            "config": {"type": "dict"},
        },
        required_one_of=[("model_api_id", "name")],
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
                module.exit_json(changed=False, model_api=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayLLMModelAPI, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), model_api=None)
        if not current:
            validate_create(module, p)
        config = p.get("config") or {}
        unknown = set(config) - set(CREATE_FIELDS)
        if unknown:
            module.fail_json(msg="Unsupported Model API config fields: %s" % ", ".join(sorted(unknown)))
        if current:
            drift = {key: (current.get(key), config[key]) for key in IMMUTABLE if key in config and current.get(key) != config[key]}
            if drift:
                module.fail_json(msg="Immutable Model API configuration differs", immutable_drift=drift)
            target = {"Name": p.get("name") or current.get("Name")}
            target.update(config)
            before = {key: normalized_current(current, key) for key in target}
            comparable = dict(target)
            if "ListModelServiceId" in comparable:
                comparable["ListModelServiceId"] = sorted(comparable["ListModelServiceId"])
            if contains(before, comparable):
                module.exit_json(changed=False, model_api=current)
            diff = maybe_diff(module, before, comparable)
            if not module.check_mode:
                module.sdk_call(
                    client.ModifyCloudNativeAPIGatewayLLMModelAPI,
                    json_request(models.ModifyCloudNativeAPIGatewayLLMModelAPIRequest, modify_payload(p, current)),
                )
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), model_api=current if not module.check_mode else target)
        target = create_payload(p)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            response = module.sdk_call(
                client.CreateCloudNativeAPIGatewayLLMModelAPI, json_request(models.CreateCloudNativeAPIGatewayLLMModelAPIRequest, target)
            )
            p["model_api_id"] = response.ModelAPIId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), model_api=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
