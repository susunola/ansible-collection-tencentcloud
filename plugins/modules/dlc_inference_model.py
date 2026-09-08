#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_inference_model
short_description: Ensure and reconcile Tencent Cloud DLC inference models
version_added: "0.14.0"
description:
  - Ensures that a DLC inference model exists and reconciles mutable model metadata.
  - The DLC API does not expose model deletion; this module deliberately provides presence management only.
  - Model type, provider, tasks and storage settings are creation-time fields and immutable drift is reported explicitly.
options:
  name: {type: str, required: true, description: Exact model name.}
  model_uid: {type: str, description: Stable model UID; used as identity when supplied.}
  model_type: {type: str, description: Model type such as LLM, Embedding or Reranker; required on creation.}
  initial_version: {type: str, description: Initial version label; required on creation and not treated as drift after later versions are published.}
  provider: {type: str, description: Creation-time model provider.}
  description: {type: str, description: Mutable model description.}
  parameter_size: {type: str, description: Mutable parameter-size label such as 7B.}
  tags: {type: list, elements: str, description: Exact order-insensitive model tag set.}
  tasks: {type: list, elements: str, description: Creation-time task set.}
  storage_uri: {type: str, description: Creation-time model storage URI.}
  use_custom_storage: {type: bool, description: Whether creation uses customer storage.}
  storage_type: {type: str, choices: [Local, COS, CFS, CFSTurbo, GooseFS], description: Creation-time storage source type.}
  goosefs_config: {type: dict, description: Creation-time GooseFSConfig-compatible object.}
  resource_tags:
    type: list
    elements: dict
    description: Exact Tencent Cloud resource tag set.
    options:
      key: {type: str, required: true, description: Tag key.}
      value: {type: str, required: true, description: Tag value.}
  wait: {type: bool, default: true, description: Wait for model presence and mutable-field convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_inference_model:
    name: embedding-bge
    model_uid: model-bge-managed
    model_type: Embedding
    initial_version: v1
    provider: BAAI
    parameter_size: 1.5B
    tasks: [Embedding]
    storage_type: COS
    storage_uri: cos://model-bucket/bge/v1/
    resource_tags:
      - {key: environment, value: production}
"""
RETURN = r"""
model: {description: Effective DLC inference model metadata., type: dict, returned: always}
model_uid: {description: Stable model UID., type: str, returned: always}
model_id: {description: DLC numeric or internal model ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def resource_tags(value):
    result = [{"TagKey": x.get("TagKey", x.get("key")), "TagValue": x.get("TagValue", x.get("value"))} for x in (value or [])]
    return sorted(result, key=lambda x: (x["TagKey"], x["TagValue"]))


def normalize(value):
    result = dict(value or {})
    for key in ("Tags", "Tasks", "SupportedEngines"):
        if result.get(key) is not None:
            result[key] = sorted(result[key])
    result["ResourceTags"] = resource_tags(result.get("ResourceTags"))
    if result.get("StorageType") is not None:
        result["StorageType"] = str(result["StorageType"]).upper()
    return result


def list_request(models, page=1):
    request = models.ListInferenceModelsRequest()
    request.Page, request.PageSize = page, 200
    return request


def find(module, client, models, p):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListInferenceModels, list_request(models, page))
        items = response.Items or []
        for item in items:
            if (p.get("model_uid") and item.ModelUid == p["model_uid"]) or (not p.get("model_uid") and item.Name == p["name"]):
                matches.append(item._serialize(allow_none=True))
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC inference models matched the requested identity", name=p["name"], model_uid=p.get("model_uid"))
    current = normalize(matches[0]) if matches else None
    if current and current.get("Name") != p["name"]:
        module.fail_json(msg="DLC model_uid exists with a different name", requested_name=p["name"], model=current)
    return current


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p["name"]
    if p.get("model_uid") is not None:
        result["ModelUid"] = p["model_uid"]
    for source, target in (
        ("model_type", "ModelType"),
        ("provider", "Provider"),
        ("description", "Description"),
        ("parameter_size", "ParameterSize"),
        ("storage_type", "StorageType"),
        ("use_custom_storage", "HasCustomStorage"),
    ):
        if p.get(source) is not None:
            result[target] = str(p[source]).upper() if source == "storage_type" else p[source]
    if p.get("tags") is not None:
        result["Tags"] = sorted(p["tags"])
    if p.get("tasks") is not None:
        result["Tasks"] = sorted(p["tasks"])
    if p.get("resource_tags") is not None:
        result["ResourceTags"] = resource_tags(p["resource_tags"])
    return result


def mutable_drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("description", "Description"), ("parameter_size", "ParameterSize"), ("tags", "Tags"), ("resource_tags", "ResourceTags")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def immutable_drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (
        ("model_type", "ModelType"),
        ("provider", "Provider"),
        ("tasks", "Tasks"),
        ("storage_type", "StorageType"),
        ("use_custom_storage", "HasCustomStorage"),
    ):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def create_request(models, p):
    request = models.CreateInferenceModelRequest()
    request.Name, request.ModelType, request.InitialVersion = p["name"], p["model_type"], p["initial_version"]
    mapping = {
        "model_uid": "ModelUid",
        "provider": "Provider",
        "description": "Description",
        "parameter_size": "ParameterSize",
        "storage_uri": "StorageUri",
        "use_custom_storage": "UseCustomStorage",
        "storage_type": "StorageType",
        "goosefs_config": "GooseFSConfig",
    }
    for source, target in mapping.items():
        if p.get(source) is not None:
            setattr(request, target, p[source] if source != "goosefs_config" else _model(models.GooseFSConfig, p[source]))
    if p.get("tags") is not None:
        request.Tags = sorted(p["tags"])
    if p.get("tasks") is not None:
        request.Tasks = sorted(p["tasks"])
    if p.get("resource_tags") is not None:
        request.ResourceTags = [_model(models.Tag, x) for x in resource_tags(p["resource_tags"])]
    return request


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def update_request(models, p, model_uid):
    request = models.UpdateInferenceModelRequest()
    request.ModelUid = model_uid
    if p.get("description") is not None:
        request.Description = p["description"]
    if p.get("parameter_size") is not None:
        request.ParameterSize = p["parameter_size"]
    if p.get("tags") is not None:
        request.Tags = sorted(p["tags"])
    if p.get("resource_tags") is not None:
        request.ResourceTags = [_model(models.Tag, x) for x in resource_tags(p["resource_tags"])]
    return request


def wait_model(module, client, models, p, expected=None):
    def poll():
        current = find(module, client, models, p)
        if current is None:
            return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    tag = {"key": {"required": True}, "value": {"required": True}}
    spec = {
        "name": {"required": True},
        "model_uid": {},
        "model_type": {},
        "initial_version": {},
        "provider": {},
        "description": {},
        "parameter_size": {},
        "tags": {"type": "list", "elements": "str"},
        "tasks": {"type": "list", "elements": "str"},
        "storage_uri": {},
        "use_custom_storage": {"type": "bool"},
        "storage_type": {"choices": ["Local", "COS", "CFS", "CFSTurbo", "GooseFS"]},
        "goosefs_config": {"type": "dict"},
        "resource_tags": {"type": "list", "elements": "dict", "options": tag},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if len(p["name"]) > 256:
        module.fail_json(msg="name must not exceed 256 characters")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if not current:
            missing = [key for key in ("model_type", "initial_version") if not p.get(key)]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC inference model", missing=missing)
            target, diff_value, uid, model_id = desired(p), maybe_diff(module, None, desired(p)), p.get("model_uid"), None
            if not module.check_mode:
                response = module.sdk_call(client.CreateInferenceModel, create_request(models, p))
                uid, model_id = response.ModelUid, response.ModelId
                if not p.get("model_uid"):
                    p["model_uid"] = uid
                if p["wait"]:
                    wait_model(module, client, models, p)
                current = find(module, client, models, p)
            module.exit_json(
                changed=True,
                **(diff_value or {}),
                model=current if not module.check_mode else target,
                model_uid=(current or {}).get("ModelUid") or uid,
                model_id=(current or {}).get("ModelId") or model_id,
            )
        fixed = immutable_drift(p, current)
        if fixed:
            module.fail_json(msg="DLC inference model type, provider, tasks and storage settings are immutable", model=current, immutable_drift=fixed)
        changes = mutable_drift(p, current)
        if not changes:
            module.exit_json(changed=False, model=current, model_uid=current.get("ModelUid"), model_id=current.get("ModelId"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.UpdateInferenceModel, update_request(models, p, current["ModelUid"]))
            if p["wait"]:
                wait_model(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p)
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            model=current if not module.check_mode else after,
            model_uid=current.get("ModelUid"),
            model_id=current.get("ModelId"),
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
