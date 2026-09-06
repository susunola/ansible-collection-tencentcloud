#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_training_task
short_description: Manage Tencent Cloud TIONE training tasks
version_added: "0.14.0"
description:
  - Creates immutable TIONE training-task definitions and reconciles started, stopped or absent state.
  - A successfully completed task satisfies C(state=started) and is never restarted automatically.
  - Failed tasks are surfaced explicitly; readable creation drift is reported because TIONE exposes no task update API.
options:
  state: {type: str, choices: [started, stopped, absent], default: started, description: Desired task lifecycle state.}
  name: {type: str, description: Exact training-task name; required for creation.}
  task_id: {type: str, description: Stable training-task ID; optional for lookup and required for deletion.}
  project_id: {type: str, description: Optional TI workspace ID.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], description: Billing mode; required for creation.}
  resource_configs: {type: list, elements: dict, description: ResourceConfigInfo-compatible role resources; required for creation.}
  framework_name: {type: str, description: Training framework name.}
  framework_version: {type: str, description: Training framework version.}
  framework_environment: {type: str, description: Framework runtime environment.}
  resource_group_id: {type: str, description: Prepaid resource-group ID.}
  tags: {type: list, elements: dict, description: Tag-compatible task tags.}
  image_info: {type: dict, description: ImageInfo-compatible custom image.}
  code_package_path: {type: dict, description: CosPathInfo-compatible code package.}
  start_cmd_info: {type: dict, description: StartCmdInfo-compatible command.}
  encoded_start_cmd_info: {type: dict, description: EncodedStartCmdInfo-compatible command, taking precedence over start_cmd_info.}
  training_mode: {type: str, description: Distributed training mode.}
  data_configs: {type: list, elements: dict, description: DataConfig-compatible input mounts, at most ten.}
  data_source: {type: str, description: Data source type such as DATASET, COS, CFS, CFSTurbo, HDFS or GooseFSx.}
  vpc_id: {type: str, description: VPC ID.}
  subnet_id: {type: str, description: Subnet ID.}
  output: {type: dict, description: CosPathInfo-compatible training output.}
  log_config: {type: dict, description: LogConfig-compatible CLS destination.}
  tuning_parameters: {type: str, description: Training tuning parameters.}
  log_enable: {type: bool, description: Enable log reporting.}
  remark: {type: str, description: Task remark.}
  callback_url: {type: str, description: Asynchronous lifecycle callback URL.}
  code_repos: {type: list, elements: dict, description: CodeRepoConfig-compatible repositories.}
  expose_network_config: {type: dict, description: ExposeNetworkConfig-compatible network exposure.}
  envs: {type: list, elements: dict, description: EnvVar-compatible environment variables.}
  train_tool_config: {type: dict, description: TrainToolConfig-compatible diagnostics.}
  resource_supply_attribute: {type: dict, description: ResourceSupplyAttribute-compatible supply settings.}
  queues: {type: list, elements: str, description: Queue IDs.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}
  wait: {type: bool, default: true, description: Wait for lifecycle convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between state checks.}
  waiter_timeout: {type: int, default: 7200, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_training_task:
    name: customer-support-sft
    state: started
    charge_type: POSTPAID_BY_HOUR
    framework_name: PYTORCH
    framework_version: "2.4"
    framework_environment: torch2.4-py3.10-cuda12.1-gpu
    resource_configs:
      - {Role: WORKER, InstanceType: TI.GN10X.2XLARGE40.POST, InstanceNum: 1}
    data_source: DATASET
    data_configs:
      - {MappingPath: /data, DataSourceId: ds-xxxxxxxx}
    output: {Bucket: ml-output-1250000000, Region: ap-guangzhou, Paths: [/sft/]}

- susunola.tencentcloud.tione_training_task:
    state: absent
    task_id: train-xxxxxxxx
    allow_delete: true
"""
RETURN = r"""
training_task: {description: Effective training-task detail., type: dict, returned: always}
task_id: {description: Stable training-task ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "name": ("Name", None, True),
    "charge_type": ("ChargeType", None, True),
    "resource_configs": ("ResourceConfigInfos", "ResourceConfigInfo", True),
    "framework_name": ("FrameworkName", None, True),
    "framework_version": ("FrameworkVersion", None, True),
    "framework_environment": ("FrameworkEnvironment", None, True),
    "resource_group_id": ("ResourceGroupId", None, True),
    "tags": ("Tags", "Tag", True),
    "image_info": ("ImageInfo", "ImageInfo", True),
    "code_package_path": ("CodePackagePath", "CosPathInfo", True),
    "start_cmd_info": ("StartCmdInfo", "StartCmdInfo", True),
    "training_mode": ("TrainingMode", None, True),
    "data_configs": ("DataConfigs", "DataConfig", True),
    "vpc_id": ("VpcId", None, True),
    "subnet_id": ("SubnetId", None, True),
    "output": ("Output", "CosPathInfo", True),
    "log_config": ("LogConfig", "LogConfig", True),
    "tuning_parameters": ("TuningParameters", None, True),
    "log_enable": ("LogEnable", None, True),
    "remark": ("Remark", None, True),
    "data_source": ("DataSource", None, True),
    "callback_url": ("CallbackUrl", None, True),
    "encoded_start_cmd_info": ("EncodedStartCmdInfo", "EncodedStartCmdInfo", False),
    "code_repos": ("CodeRepos", "CodeRepoConfig", True),
    "expose_network_config": ("ExposeNetworkConfig", "ExposeNetworkConfig", True),
    "envs": ("Envs", "EnvVar", False),
    "train_tool_config": ("TrainToolConfig", "TrainToolConfig", False),
    "resource_supply_attribute": ("ResourceSupplyAttribute", "ResourceSupplyAttribute", False),
    "queues": ("Queues", None, False),
}
ACTIVE = {"submitting", "pending", "starting", "running", "stopping"}
FAILED = {"failed", "submit_failed"}


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def normalize(value):
    result = dict(value or {})
    if result.get("Tags") is not None:
        result["Tags"] = sorted(result["Tags"], key=lambda x: json.dumps(x, sort_keys=True))
    return result


def detail_request(models, task_id, project_id=None):
    request = models.DescribeTrainingTaskRequest()
    request.Id = task_id
    if project_id is not None:
        request.TiProjectId = project_id
    return request


def get(module, client, models, task_id, project_id=None):
    try:
        response = module.sdk_call(client.DescribeTrainingTask, detail_request(models, task_id, project_id))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    return normalize(response.TrainingTaskDetail._serialize(allow_none=True)) if response.TrainingTaskDetail else None


def list_request(models, p, offset):
    request = models.DescribeTrainingTasksRequest()
    request.Offset, request.Limit = offset, 50
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    item = models.Filter()
    item.Name, item.Values = "Name", [p["name"]]
    request.Filters = [item]
    return request


def find(module, client, models, p):
    if p.get("task_id"):
        return get(module, client, models, p["task_id"], p.get("project_id"))
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeTrainingTasks, list_request(models, p, offset))
        items = response.TrainingTaskSet or []
        matches.extend(item.Id for item in items if item.Name == p["name"])
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE training tasks matched the exact name", name=p["name"])
    return get(module, client, models, matches[0], p.get("project_id")) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    for source, (key, _, _) in FIELDS.items():
        if p.get(source) is not None:
            result[key] = p[source]
    return normalize(result)


def conflicts(p, current):
    target, result = desired(p, current), {}
    for source, (key, _, readable) in FIELDS.items():
        if readable and p.get(source) is not None and current.get(key) != target.get(key):
            result[key] = (current.get(key), target.get(key))
    return result


def create_request(models, p):
    request = models.CreateTrainingTaskRequest()
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    for source, (key, cls_name, _) in FIELDS.items():
        value = p.get(source)
        if value is None:
            continue
        if cls_name and isinstance(value, list):
            value = [_model(getattr(models, cls_name), item) for item in value]
        elif cls_name:
            value = _model(getattr(models, cls_name), value)
        setattr(request, key, value)
    return request


def action_request(cls, p):
    request = cls()
    request.Id = p["task_id"]
    if hasattr(request, "TiProjectId") and p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def task_status(value):
    return str((value or {}).get("Status") or "").lower()


def wait_task(module, client, models, p, accepted):
    def poll():
        current = get(module, client, models, p["task_id"], p.get("project_id"))
        if current is None:
            return "absent"
        actual = task_status(current)
        if actual in FAILED:
            module.fail_json(msg="TIONE training task failed", training_task=current)
        return actual

    wait_for_state(module, poll, accepted, timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {"state": {"choices": ["started", "stopped", "absent"], "default": "started"}, "task_id": {}, "project_id": {}}
    for source in FIELDS:
        spec[source] = {}
    spec.update(
        {
            "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"]},
            "resource_configs": {"type": "list", "elements": "dict"},
            "tags": {"type": "list", "elements": "dict"},
            "image_info": {"type": "dict"},
            "code_package_path": {"type": "dict"},
            "start_cmd_info": {"type": "dict"},
            "encoded_start_cmd_info": {"type": "dict"},
            "data_configs": {"type": "list", "elements": "dict"},
            "output": {"type": "dict"},
            "log_config": {"type": "dict"},
            "log_enable": {"type": "bool"},
            "code_repos": {"type": "list", "elements": "dict"},
            "expose_network_config": {"type": "dict"},
            "envs": {"type": "list", "elements": "dict"},
            "train_tool_config": {"type": "dict"},
            "resource_supply_attribute": {"type": "dict"},
            "queues": {"type": "list", "elements": "str"},
            "allow_delete": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 10},
            "waiter_timeout": {"type": "int", "default": 7200},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("data_configs") is not None and len(p["data_configs"]) > 10:
        module.fail_json(msg="data_configs accepts at most ten entries")
    if p["state"] == "absent" and not p.get("task_id"):
        module.fail_json(msg="task_id is required for safe deletion")
    if p["state"] != "absent" and not (p.get("name") or p.get("task_id")):
        module.fail_json(msg="name or task_id is required")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, training_task=None, task_id=p["task_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE training task", training_task=current)
            if task_status(current) in ACTIVE and not p["wait"]:
                module.fail_json(msg="wait=true is required to stop an active training task before deletion", training_task=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                if task_status(current) in ACTIVE:
                    module.sdk_call(client.StopTrainingTask, action_request(models.StopTrainingTaskRequest, p))
                    wait_task(module, client, models, p, ["stopped", "succeed"])
                module.sdk_call(client.DeleteTrainingTask, action_request(models.DeleteTrainingTaskRequest, p))
                if p["wait"]:
                    wait_task(module, client, models, p, ["absent"])
            module.exit_json(changed=True, **(diff_value or {}), training_task=None, task_id=p["task_id"])
        if not current:
            if p.get("task_id"):
                module.fail_json(msg="the requested TIONE task_id does not exist; omit it to create by name", task_id=p["task_id"])
            missing = [key for key in ("name", "charge_type", "resource_configs") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a TIONE training task", missing=missing)
            target = desired(p)
            target["Status"] = "RUNNING" if p["state"] == "started" else "STOPPED"
            diff_value = maybe_diff(module, None, target)
            task_id = None
            if not module.check_mode:
                response = module.sdk_call(client.CreateTrainingTask, create_request(models, p))
                task_id = response.Id
                p = dict(p, task_id=task_id)
                if p["wait"]:
                    wait_task(module, client, models, p, ["running", "succeed"])
                current = get(module, client, models, task_id, p.get("project_id"))
                if p["state"] == "stopped" and task_status(current) not in ("stopped", "succeed"):
                    module.sdk_call(client.StopTrainingTask, action_request(models.StopTrainingTaskRequest, p))
                    if p["wait"]:
                        wait_task(module, client, models, p, ["stopped", "succeed"])
                    current = get(module, client, models, task_id, p.get("project_id"))
            module.exit_json(
                changed=True, **(diff_value or {}), training_task=current if not module.check_mode else target, task_id=(current or {}).get("Id") or task_id
            )
        p = dict(p, task_id=current["Id"])
        changed_fields = conflicts(p, current)
        if changed_fields:
            module.fail_json(
                msg="TIONE training tasks expose no update API and the existing definition has immutable drift",
                training_task=current,
                immutable_drift=changed_fields,
            )
        actual = task_status(current)
        if actual in FAILED:
            module.fail_json(msg="TIONE training task is in a failed terminal state and will not be restarted automatically", training_task=current)
        converged = actual in ({"running", "submitting", "pending", "starting", "succeed"} if p["state"] == "started" else {"stopped", "succeed"})
        if converged:
            module.exit_json(changed=False, training_task=current, task_id=current["Id"])
        target = dict(current, Status="RUNNING" if p["state"] == "started" else "STOPPED")
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            if p["state"] == "started":
                module.sdk_call(client.StartTrainingTask, action_request(models.StartTrainingTaskRequest, p))
                if p["wait"]:
                    wait_task(module, client, models, p, ["running", "succeed"])
            elif actual in ACTIVE:
                module.sdk_call(client.StopTrainingTask, action_request(models.StopTrainingTaskRequest, p))
                if p["wait"]:
                    wait_task(module, client, models, p, ["stopped", "succeed"])
            else:
                module.fail_json(msg="TIONE training task returned an unsupported state transition", status=current.get("Status"), training_task=current)
            current = get(module, client, models, p["task_id"], p.get("project_id"))
        module.exit_json(changed=True, **(diff_value or {}), training_task=current if not module.check_mode else target, task_id=current["Id"])
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
