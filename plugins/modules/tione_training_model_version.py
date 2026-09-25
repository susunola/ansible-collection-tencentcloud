#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_training_model_version
short_description: Manage versions of an existing Tencent Cloud TIONE training model
version_added: "0.14.0"
description:
  - Imports immutable versions into an existing TIONE training model identified by stable parent ID.
  - Exact version-label discovery is always scoped to C(model_id); conflicting readable metadata is reported.
  - Version deletion requires a stable C(version_id), an explicit guard and a separate COS cleanup choice.
options:
  state:
    description:
      - Desired model-version presence.
    type: str
    choices: [present, absent]
    default: present
  model_id:
    description:
      - Stable parent training-model ID; required for presence.
    type: str
  version_id:
    description:
      - Stable model-version ID; optional for lookup and required for deletion.
    type: str
  version:
    description:
      - Exact model-version label; required for creation.
    type: str
  import_method:
    description:
      - Import a new version or register an existing version.
    type: str
    choices: [VERSION, EXIST]
    default: VERSION
  reasoning_environment_source:
    description:
      - Inference-environment source.
    type: str
    choices: [SYSTEM, CUSTOM]
  training_job_name:
    description:
      - Source training-task name.
    type: str
  training_job_id:
    description:
      - Source training-task ID.
    type: str
  training_job_version:
    description:
      - Source training-task version.
    type: str
  training_model_cos_path:
    description:
      - CosPathInfo-compatible source model directory.
    type: dict
  model_output_path:
    description:
      - CosPathInfo-compatible target model directory.
    type: dict
  training_model_source:
    description:
      - Model source.
    type: str
    choices: [JOB, COS]
  algorithm_framework:
    description:
      - Training framework the model version was produced with.
    type: str
  reasoning_environment:
    description:
      - Inference environment.
    type: str
  reasoning_environment_id:
    description:
      - Inference image ID.
    type: str
  reasoning_image_info:
    description:
      - ImageInfo-compatible custom inference image.
    type: dict
  training_model_index:
    description:
      - Model metrics or index metadata.
    type: str
  model_move_mode:
    description:
      - Source model move mode.
    type: str
    choices: [CUT, COPY]
  training_preference:
    description:
      - Training environment the version was produced in.
    type: str
  model_version_type:
    description:
      - Kind of model version being registered.
    type: str
    choices: [NORMAL, ACCELERATE]
    default: NORMAL
  model_format:
    description:
      - Model serialization format.
    type: str
  auto_clean:
    description:
      - Automatic version cleanup switch.
    type: str
    choices: ['true', 'false']
  max_reserved_models:
    description:
      - Maximum retained versions, from 1 to 24.
    type: int
  model_clean_period:
    description:
      - Cleanup interval in minutes, from 1 to 1440.
    type: int
  is_qat:
    description:
      - Whether this is a quantization-aware-training model.
    type: bool
  delete_cos:
    description:
      - Also remove version model files from COS.
    type: bool
    default: false
  allow_delete:
    description:
      - Explicit destructive-operation guard.
    type: bool
    default: false
  wait:
    description:
      - Wait for import completion or deletion disappearance.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between state checks.
    type: int
    default: 10
  waiter_timeout:
    description:
      - Overall convergence timeout.
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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_training_model_version:
    model_id: model-xxxxxxxx
    version: v2
    training_model_source: JOB
    training_job_id: train-xxxxxxxx
    training_job_version: instance-xxxxxxxx
    algorithm_framework: PYTORCH
    model_format: PYTORCH
    reasoning_environment_source: SYSTEM
    reasoning_environment_id: ti-infer-pytorch

- susunola.tencentcloud.tione_training_model_version:
    state: absent
    version_id: modelversion-xxxxxxxx
    allow_delete: true
    delete_cos: false
"""
RETURN = r"""
model_version:
  description:
    - Effective TIONE training-model version.
  returned: always
  type: dict
model_id:
  description:
    - Stable parent model ID.
  returned: when available
  type: str
version_id:
  description:
    - Stable model-version ID.
  returned: when available
  type: str
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "version": ("TrainingModelVersion", None),
    "reasoning_environment_source": ("ReasoningEnvironmentSource", None),
    "training_job_name": ("TrainingJobName", None),
    "training_model_cos_path": ("TrainingModelCosPath", "CosPathInfo"),
    "algorithm_framework": ("AlgorithmFramework", None),
    "reasoning_environment": ("ReasoningEnvironment", None),
    "training_model_index": ("TrainingModelIndex", None),
    "reasoning_image_info": ("ReasoningImageInfo", "ImageInfo"),
    "training_job_id": ("TrainingJobId", None),
    "model_output_path": ("ModelOutputPath", "CosPathInfo"),
    "training_model_source": ("TrainingModelSource", None),
    "training_preference": ("TrainingPreference", None),
    "training_job_version": ("TrainingJobVersion", None),
    "model_format": ("ModelFormat", None),
    "reasoning_environment_id": ("ReasoningEnvironmentId", None),
    "auto_clean": ("AutoClean", None),
    "max_reserved_models": ("MaxReservedModels", None),
    "model_clean_period": ("ModelCleanPeriod", None),
    "is_qat": ("IsQAT", None),
}


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def detail_request(models, version_id):
    request = models.DescribeTrainingModelVersionRequest()
    request.TrainingModelVersionId = version_id
    return request


def get(module, client, models, version_id):
    try:
        response = module.sdk_call(client.DescribeTrainingModelVersion, detail_request(models, version_id))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    return response.TrainingModelVersion._serialize(allow_none=True) if response.TrainingModelVersion else None


def list_request(models, model_id):
    request = models.DescribeTrainingModelVersionsRequest()
    request.TrainingModelId = model_id
    return request


def find(module, client, models, p):
    if p.get("version_id"):
        return get(module, client, models, p["version_id"])
    response = module.sdk_call(client.DescribeTrainingModelVersions, list_request(models, p["model_id"]))
    matches = []
    for item in response.TrainingModelVersions or []:
        if item.TrainingModelVersion == p["version"]:
            matches.append(item._serialize(allow_none=True))
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE model versions matched the exact label within one parent", model_id=p["model_id"], version=p["version"])
    return matches[0] if matches else None


def desired(p, current=None):
    result = dict(current or {})
    for source, (key, _) in FIELDS.items():
        if p.get(source) is not None:
            result[key] = p[source]
    if p.get("model_version_type") is not None:
        result["VersionType"] = p["model_version_type"]
    return result


def conflicts(p, current):
    target, changes = desired(p, current), {}
    for source, (key, _) in FIELDS.items():
        if p.get(source) is not None and key in current and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    if p.get("model_version_type") is not None and current.get("VersionType") != p["model_version_type"]:
        changes["VersionType"] = (current.get("VersionType"), p["model_version_type"])
    return changes


def create_request(models, p):
    request = models.CreateTrainingModelRequest()
    request.ImportMethod, request.TrainingModelId = p["import_method"], p["model_id"]
    request.ModelVersionType = p["model_version_type"]
    if p.get("model_move_mode") is not None:
        request.ModelMoveMode = p["model_move_mode"]
    for source, (key, cls_name) in FIELDS.items():
        value = p.get(source)
        if value is None:
            continue
        if cls_name:
            value = _model(getattr(models, cls_name), value)
        setattr(request, key, value)
    return request


def delete_request(models, p):
    request = models.DeleteTrainingModelVersionRequest()
    request.TrainingModelVersionId, request.EnableDeleteCos = p["version_id"], p["delete_cos"]
    return request


def wait_version(module, client, models, p, present):
    def poll():
        current = get(module, client, models, p["version_id"])
        if current is None:
            return "absent"
        actual = str(current.get("TrainingModelStatus") or "").lower()
        if actual == "status_failed":
            module.fail_json(msg="TIONE model-version import failed", model_version=current)
        return actual

    wait_for_state(module, poll, ["status_success"] if present else ["absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "model_id": {},
        "version_id": {},
        "version": {},
        "import_method": {"choices": ["VERSION", "EXIST"], "default": "VERSION"},
    }
    for source in FIELDS:
        spec[source] = {}
    spec.update(
        {
            "reasoning_environment_source": {"choices": ["SYSTEM", "CUSTOM"]},
            "training_model_cos_path": {"type": "dict"},
            "reasoning_image_info": {"type": "dict"},
            "model_output_path": {"type": "dict"},
            "training_model_source": {"choices": ["JOB", "COS"]},
            "model_move_mode": {"choices": ["CUT", "COPY"]},
            "model_version_type": {"choices": ["NORMAL", "ACCELERATE"], "default": "NORMAL"},
            "auto_clean": {"choices": ["true", "false"]},
            "max_reserved_models": {"type": "int"},
            "model_clean_period": {"type": "int"},
            "is_qat": {"type": "bool"},
            "delete_cos": {"type": "bool", "default": False},
            "allow_delete": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 10},
            "waiter_timeout": {"type": "int", "default": 1800},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p.get("model_id"):
        module.fail_json(msg="model_id is required to manage a model version")
    if p["state"] == "present" and not (p.get("version") or p.get("version_id")):
        module.fail_json(msg="version or version_id is required")
    if p["state"] == "absent" and not p.get("version_id"):
        module.fail_json(msg="version_id is required for safe model-version deletion")
    if p.get("max_reserved_models") is not None and not 1 <= p["max_reserved_models"] <= 24:
        module.fail_json(msg="max_reserved_models must be between 1 and 24")
    if p.get("model_clean_period") is not None and not 1 <= p["model_clean_period"] <= 1440:
        module.fail_json(msg="model_clean_period must be between 1 and 1440")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, model_version=None, model_id=None, version_id=p["version_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE model version", model_version=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTrainingModelVersion, delete_request(models, p))
                if p["wait"]:
                    wait_version(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), model_version=None, model_id=current.get("TrainingModelId"), version_id=p["version_id"])
        if current:
            changes = conflicts(p, current)
            if changes:
                module.fail_json(
                    msg="TIONE model versions are immutable and the existing version has conflicting metadata", model_version=current, immutable_drift=changes
                )
            actual = str(current.get("TrainingModelStatus") or "").lower()
            if actual == "status_failed":
                module.fail_json(msg="TIONE model version is in a failed import state", model_version=current)
            module.exit_json(
                changed=False, model_version=current, model_id=current.get("TrainingModelId") or p["model_id"], version_id=current.get("TrainingModelVersionId")
            )
        if p.get("version_id"):
            module.fail_json(msg="the requested model version ID does not exist; omit it to create by label", version_id=p["version_id"])
        target, diff_value, version_id = desired(p), maybe_diff(module, None, desired(p)), None
        if not module.check_mode:
            response = module.sdk_call(client.CreateTrainingModel, create_request(models, p))
            version_id = response.TrainingModelVersionId
            p = dict(p, version_id=version_id)
            if p["wait"]:
                wait_version(module, client, models, p, True)
            current = get(module, client, models, version_id)
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            model_version=current if not module.check_mode else target,
            model_id=(current or {}).get("TrainingModelId") or p["model_id"],
            version_id=(current or {}).get("TrainingModelVersionId") or version_id,
        )
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
