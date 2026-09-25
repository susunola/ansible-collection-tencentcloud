#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_inference_service
short_description: Manage Tencent Cloud DLC inference-service runtime state
version_added: "0.14.0"
description:
  - Creates a DLC inference service and reconciles its operational state between C(running) and C(stopped).
  - The DLC API exposes no service update or deletion operation; readable creation-field conflicts fail explicitly and service removal is not claimed.
options:
  state:
    description:
      - Desired operational state.
    type: str
    choices: [running, stopped]
    default: running
  name:
    description:
      - Exact service name and identity.
    type: str
    required: true
  model_uid:
    description:
      - Parent inference-model UID; required on creation.
    type: str
  model_version:
    description:
      - Immutable model version.
    type: str
  engine:
    description:
      - Inference engine; required on creation.
    type: str
    choices: [vllm, xgboost]
  replicas:
    description:
      - Initial deployment replica count.
    type: int
  resource_partition_id:
    description:
      - Initial resource partition ID.
    type: str
  image:
    description:
      - Ray Serve deployment image.
    type: str
  model_identifier:
    description:
      - Immutable OpenAI-compatible model identifier.
    type: str
  queue:
    description:
      - Initial K8s namespace or queue.
    type: str
  deployment_name:
    description:
      - Initial deployment name.
    type: str
  head_high_availability_enabled:
    description:
      - Enable Ray head high availability at creation.
    type: bool
  advanced_params:
    description:
      - Initial advanced parameter JSON.
    type: str
  image_pull_policy:
    description:
      - Initial image pull policy.
    type: str
    choices: [Always, IfNotPresent, Never]
  autoscaling_enabled:
    description:
      - Enable initial autoscaling.
    type: bool
  min_replicas:
    description:
      - Initial autoscaling minimum.
    type: int
  max_replicas:
    description:
      - Initial autoscaling maximum.
    type: int
  autoscaler_options:
    description:
      - Initial autoscaler JSON.
    type: str
  api_key_ids:
    description:
      - API key IDs bound during creation.
    type: list
    elements: str
  advanced_options:
    description:
      - Initial flattened RayService options JSON.
    type: str
  is_custom:
    description:
      - Whether this is custom Ray Serve code.
    type: bool
  runtime_env:
    description:
      - Initial Python runtime environment JSON.
    type: str
  resource_tags:
    type: list
    elements: dict
    description: Exact readable Tencent Cloud resource tag set.
    suboptions:
      key:
        description:
          - Tag key.
        type: str
        required: true
      value:
        description:
          - Tag value.
        type: str
        required: true
  wait:
    description:
      - Wait for Running or Stopped convergence.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between polls.
    type: int
    default: 10
  waiter_timeout:
    description:
      - Overall deployment convergence timeout.
    type: int
    default: 1800

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
  - module: susunola.tencentcloud.dlc_inference_service_info
    description: Gather Tencent Cloud DLC inference services.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_inference_service:
    name: bge-openai
    state: running
    model_uid: model-bge-managed
    model_version: v2
    engine: vllm
    replicas: 2
    resource_partition_id: rp-xxxxxxxx
    image: ccr.ccs.tencentyun.com/inference/vllm:stable
    model_identifier: bge-production
    queue: inference
    autoscaling_enabled: true
    min_replicas: 1
    max_replicas: 5

- susunola.tencentcloud.dlc_inference_service:
    name: bge-openai
    state: stopped
"""
RETURN = r"""
inference_service:
  description:
    - Effective inference-service metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    ServiceId: isvc-new-001
    Name: bge-openai
    Status: Running
    ModelUid: model-bge-managed
    Engine: vllm
    Replicas: 2
    ResourcePartitionId: rp-00000001
    Image: ccr.ccs.tencentyun.com/inference/vllm:stable
    ModelIdentifier: bge-production
    Queue: inference
    ResourceTags:
      - TagKey: env
        TagValue: prod
      - TagKey: team
        TagValue: ml
service_id:
  description:
    - Stable DLC inference-service ID.
  returned: always
  type: str
  sample: isvc-8b0a1c2d
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

CREATE_FIELDS = {
    "model_uid": "ModelUid",
    "engine": "Engine",
    "replicas": "Replicas",
    "resource_partition_id": "ResourcePartitionId",
    "image": "Image",
    "model_identifier": "ModelIdentifier",
    "queue": "Queue",
    "deployment_name": "DeploymentName",
    "model_version": "ModelVersion",
    "head_high_availability_enabled": "HeadHighAvailabilityEnabled",
    "advanced_params": "AdvancedParams",
    "image_pull_policy": "ImagePullPolicy",
    "autoscaling_enabled": "AutoscalingEnabled",
    "min_replicas": "MinReplicas",
    "max_replicas": "MaxReplicas",
    "autoscaler_options": "AutoscalerOptions",
    "api_key_ids": "ApiKeyIds",
    "advanced_options": "AdvancedOptions",
    "is_custom": "IsCustom",
    "runtime_env": "RuntimeEnv",
}
JSON_FIELDS = {"advanced_params", "autoscaler_options", "advanced_options", "runtime_env"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def canonical(value):
    if value is None:
        return None
    try:
        return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return value


def tags(value):
    result = [{"TagKey": x.get("TagKey", x.get("key")), "TagValue": x.get("TagValue", x.get("value"))} for x in (value or [])]
    return sorted(result, key=lambda x: (x["TagKey"], x["TagValue"]))


def normalize(value):
    result = dict(value or {})
    result["ResourceTags"] = tags(result.get("ResourceTags"))
    for key in ("ResourceConfig", "AdvancedOptions"):
        if result.get(key) is not None:
            result[key] = canonical(result[key])
    return result


def list_request(models, page=1):
    request = models.ListInferenceServicesRequest()
    request.Page, request.PageSize = page, 200
    return request


def get_request(models, service_id):
    request = models.GetInferenceServiceRequest()
    request.ServiceId = service_id
    return request


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListInferenceServices, list_request(models, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name)
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC inference services matched the exact name", name=name)
    if not matches:
        return None
    response = module.sdk_call(client.GetInferenceService, get_request(models, matches[0]["ServiceId"]))
    return normalize(response._serialize(allow_none=True))


def readable_conflict(p, current):
    changes = {}
    for source, key in (("model_uid", "ModelUid"), ("model_version", "ModelVersion"), ("model_identifier", "ModelIdentifier"), ("is_custom", "IsCustom")):
        if p.get(source) is not None and current.get(key) != p[source]:
            changes[key] = (current.get(key), p[source])
    if p.get("resource_tags") is not None and current.get("ResourceTags") != tags(p["resource_tags"]):
        changes["ResourceTags"] = (current.get("ResourceTags"), tags(p["resource_tags"]))
    return changes


def create_request(models, p):
    request = models.CreateInferenceServiceRequest()
    request.Name = p["name"]
    for source, target in CREATE_FIELDS.items():
        if p.get(source) is not None:
            setattr(request, target, canonical(p[source]) if source in JSON_FIELDS else p[source])
    if p.get("resource_tags") is not None:
        request.ResourceTags = []
        for value in tags(p["resource_tags"]):
            item = models.Tag()
            item.from_json_string(json.dumps(value))
            request.ResourceTags.append(item)
    return request


def state_request(cls, service_id):
    request = cls()
    request.ServiceId = service_id
    return request


def wait_service(module, client, models, p, expected):
    def poll():
        current = find(module, client, models, p["name"])
        if current is None:
            return "absent"
        status = str(current.get("Status") or "").lower()
        if status in ("failed", "error"):
            module.fail_json(msg="DLC inference service entered a failed state", inference_service=current)
        return status

    wait_for_state(module, poll, [expected], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    tag = {"key": {"required": True, "no_log": False}, "value": {"required": True}}
    spec = {"state": {"choices": ["running", "stopped"], "default": "running"}, "name": {"required": True}}
    for key in CREATE_FIELDS:
        spec[key] = {}
    spec.update(
        {
            "engine": {"choices": ["vllm", "xgboost"]},
            "replicas": {"type": "int"},
            "head_high_availability_enabled": {"type": "bool"},
            "image_pull_policy": {"choices": ["Always", "IfNotPresent", "Never"]},
            "autoscaling_enabled": {"type": "bool"},
            "min_replicas": {"type": "int"},
            "max_replicas": {"type": "int"},
            "api_key_ids": {"type": "list", "elements": "str", "no_log": False},
            "is_custom": {"type": "bool"},
            "resource_tags": {"type": "list", "elements": "dict", "options": tag},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 10},
            "waiter_timeout": {"type": "int", "default": 1800},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("min_replicas") is not None and p.get("max_replicas") is not None and p["min_replicas"] > p["max_replicas"]:
        module.fail_json(msg="min_replicas must not exceed max_replicas")
    for key in JSON_FIELDS:
        if p.get(key) is not None:
            try:
                json.loads(p[key])
            except (TypeError, ValueError):
                module.fail_json(msg="%s must be valid JSON" % key)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if not current:
            required = ("model_uid", "engine", "replicas", "resource_partition_id", "image", "model_identifier", "queue")
            missing = [key for key in required if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC inference service", missing=missing)
            if p["state"] == "stopped" and not p["wait"]:
                module.fail_json(msg="wait=true is required when creating an inference service directly into stopped state")
            target = {"Name": p["name"], "Status": p["state"].capitalize()}
            diff_value = maybe_diff(module, None, target)
            service_id = None
            if not module.check_mode:
                response = module.sdk_call(client.CreateInferenceService, create_request(models, p))
                service_id = response.ServiceId
                if p["wait"]:
                    wait_service(module, client, models, p, "running")
                current = find(module, client, models, p["name"])
                if p["state"] == "stopped":
                    module.sdk_call(client.StopInferenceService, state_request(models.StopInferenceServiceRequest, service_id))
                    if p["wait"]:
                        wait_service(module, client, models, p, "stopped")
                    current = find(module, client, models, p["name"])
            module.exit_json(
                changed=True,
                **(diff_value or {}),
                inference_service=current if not module.check_mode else target,
                service_id=(current or {}).get("ServiceId") or service_id,
            )
        fixed = readable_conflict(p, current)
        if fixed:
            module.fail_json(
                msg="DLC inference-service creation fields are immutable because the service exposes no update API",
                inference_service=current,
                immutable_drift=fixed,
            )
        status = str(current.get("Status") or "").lower()
        if status in ("failed", "error"):
            module.fail_json(msg="DLC inference service is in a failed state", inference_service=current)
        if status in ("deploying", "starting", "restarting"):
            if not p["wait"]:
                module.fail_json(
                    msg="DLC inference service is still transitioning; enable wait to converge before another state action", inference_service=current
                )
            wait_service(module, client, models, p, "running")
            current = find(module, client, models, p["name"])
            status = "running"
        elif status == "stopping":
            if not p["wait"]:
                module.fail_json(msg="DLC inference service is still stopping; enable wait to converge", inference_service=current)
            wait_service(module, client, models, p, "stopped")
            current = find(module, client, models, p["name"])
            status = "stopped"
        elif status not in ("running", "stopped"):
            module.fail_json(msg="DLC inference service returned an unsupported operational state", status=current.get("Status"), inference_service=current)
        if status == p["state"]:
            module.exit_json(changed=False, inference_service=current, service_id=current.get("ServiceId"))
        diff_value = maybe_diff(module, current, dict(current, Status=p["state"].capitalize()))
        if not module.check_mode:
            method = client.RestartInferenceService if p["state"] == "running" else client.StopInferenceService
            cls = models.RestartInferenceServiceRequest if p["state"] == "running" else models.StopInferenceServiceRequest
            module.sdk_call(method, state_request(cls, current["ServiceId"]))
            if p["wait"]:
                wait_service(module, client, models, p, p["state"])
            current = find(module, client, models, p["name"])
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            inference_service=current if not module.check_mode else dict(current, Status=p["state"].capitalize()),
            service_id=current.get("ServiceId"),
        )
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
