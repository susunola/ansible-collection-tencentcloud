#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_datahub_task
short_description: Manage Tencent Cloud CKafka Datahub tasks
version_added: "0.14.0"
description: Creates, updates, pauses, resumes and deletes CKafka Datahub source or sink tasks.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired existence state.}
  task_id: {type: str, description: Existing task ID; preferred for rename and deletion.}
  name: {type: str, required: true, description: Task name.}
  task_type: {type: str, required: true, choices: [SOURCE, SINK], description: Immutable task direction.}
  source_resource: {type: dict, required: true, description: SDK-compatible DatahubResource source configuration.}
  target_resource: {type: dict, required: true, description: SDK-compatible DatahubResource target configuration.}
  transform: {type: dict, description: SDK-compatible legacy TransformParam configuration.}
  transforms: {type: dict, description: SDK-compatible TransformsParam configuration.}
  schema_id: {type: str, description: Immutable bound schema ID.}
  description: {type: str, default: '', description: Task description.}
  desired_status: {type: str, choices: [running, paused], default: running, description: Desired operational status.}
  tasks_max: {type: int, default: 1, description: Maximum task concurrency.}
  sync_throttle_limit: {type: int, default: 20, description: Synchronization throttle in MB/s.}
  auto_expand: {type: bool, default: true, description: Enable automatic capacity expansion.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_datahub_task:
    name: mysql-orders-to-datahub
    task_type: SOURCE
    source_resource:
      Type: MYSQL
      MySQLParam: {Resource: resource-xxxxxxxx, Database: orders, Table: '*'}
    target_resource:
      Type: TOPIC
      TopicParam: {Resource: 1250000000-orders}
    tasks_max: 2
"""
RETURN = r"""datahub_task: {description: CKafka Datahub task metadata with credential fields removed., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload

SENSITIVE = ("password", "secret", "token", "credential", "privatekey", "accesskey")


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def describe_request(models, task_id):
    request = models.DescribeDatahubTaskRequest()
    request.TaskId = task_id
    return request


def list_request(models, p, offset=0):
    request = models.DescribeDatahubTasksRequest()
    request.Limit, request.Offset, request.SearchWord, request.TaskType = 100, offset, p["name"], p["task_type"]
    return request


def create_request(models, p):
    request = models.CreateDatahubTaskRequest()
    request.TaskName, request.TaskType = p["name"], p["task_type"]
    request.SourceResource, request.TargetResource = _model(models, "DatahubResource", p["source_resource"]), _model(
        models, "DatahubResource", p["target_resource"]
    )
    if p.get("transform") is not None:
        request.TransformParam = _model(models, "TransformParam", p["transform"])
    if p.get("transforms") is not None:
        request.TransformsParam = _model(models, "TransformsParam", p["transforms"])
    request.SchemaId, request.Description = p.get("schema_id"), p["description"]
    return request


def update_request(models, p, task_id):
    request = models.ModifyDatahubTaskRequest()
    request.TaskId, request.TaskName, request.Description = task_id, p["name"], p["description"]
    request.TasksMax, request.SyncThrottleLimit, request.AutoExpandFlag = p["tasks_max"], p["sync_throttle_limit"], p["auto_expand"]
    return request


def delete_request(models, task_id):
    request = models.DeleteDatahubTaskRequest()
    request.TaskId = task_id
    return request


def pause_request(models, task_id):
    request = models.PauseDatahubTaskRequest()
    request.TaskId = task_id
    return request


def resume_request(models, task_id):
    request = models.ResumeDatahubTaskRequest()
    request.TaskId = task_id
    return request


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not any(part in k.lower() for part in SENSITIVE)}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def project(value, shape):
    if isinstance(shape, dict):
        return {k: project((value or {}).get(k), v) for k, v in shape.items()}
    if isinstance(shape, list):
        return value or []
    return value


def detail(module, client, models, task_id):
    try:
        response = module.sdk_call(client.DescribeDatahubTask, describe_request(models, task_id))
        return scrub(response.Result._serialize(allow_none=True)) if response.Result else None
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def find(module, client, models, p):
    if p.get("task_id"):
        return detail(module, client, models, p["task_id"])
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeDatahubTasks, list_request(models, p, offset))
        result = response.Result
        items = list(result.TaskList or []) if result else []
        matches = [item for item in items if item.TaskName == p["name"] and item.TaskType == p["task_type"]]
        if matches:
            if len(matches) > 1:
                module.fail_json(msg="multiple CKafka Datahub tasks matched name and type; specify task_id")
            return detail(module, client, models, matches[0].TaskId)
        offset += len(items)
        if not items or offset >= int(result.TotalCount or 0):
            return None


def comparable(value, p):
    return {
        "TaskName": value.get("TaskName"),
        "TaskType": value.get("TaskType"),
        "SourceResource": project(value.get("SourceResource") or {}, scrub(p["source_resource"])),
        "TargetResource": project(value.get("TargetResource") or {}, scrub(p["target_resource"])),
        "TransformParam": project(value.get("TransformParam") or {}, scrub(p.get("transform") or {})),
        "TransformsParam": project(value.get("TransformsParam") or {}, scrub(p.get("transforms") or {})),
        "SchemaId": value.get("SchemaId"),
        "Description": value.get("Description") or "",
        "TasksMax": int(value.get("TaskMax") or 1),
        "SyncThrottleLimit": int(value.get("SyncThrottleLimit") or 20),
        "AutoExpandFlag": bool(value.get("AutoExpandFlag")),
        "DesiredStatus": "paused" if int(value.get("Status") or 0) in (5, 6, 7) else "running",
    }


def desired(p):
    return {
        "TaskName": p["name"],
        "TaskType": p["task_type"],
        "SourceResource": scrub(p["source_resource"]),
        "TargetResource": scrub(p["target_resource"]),
        "TransformParam": scrub(p.get("transform") or {}),
        "TransformsParam": scrub(p.get("transforms") or {}),
        "SchemaId": p.get("schema_id"),
        "Description": p["description"],
        "TasksMax": p["tasks_max"],
        "SyncThrottleLimit": p["sync_throttle_limit"],
        "AutoExpandFlag": p["auto_expand"],
        "DesiredStatus": p["desired_status"],
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "task_id": {},
        "name": {"required": True},
        "task_type": {"required": True, "choices": ["SOURCE", "SINK"]},
        "source_resource": {"type": "dict", "required": True, "no_log": True},
        "target_resource": {"type": "dict", "required": True, "no_log": True},
        "transform": {"type": "dict"},
        "transforms": {"type": "dict"},
        "schema_id": {},
        "description": {"default": ""},
        "desired_status": {"choices": ["running", "paused"], "default": "running"},
        "tasks_max": {"type": "int", "default": 1},
        "sync_throttle_limit": {"type": "int", "default": 20},
        "auto_expand": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, datahub_task=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDatahubTask, delete_request(models, current["TaskId"]))
            module.exit_json(changed=True, **(diff or {}), datahub_task=current if module.check_mode else None)
        target, before = desired(p), comparable(current, p) if current else None
        if before == target:
            module.exit_json(changed=False, datahub_task=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(
                module, before, target, ("TaskType", "SourceResource", "TargetResource", "TransformParam", "TransformsParam", "SchemaId"), "CKafka Datahub task"
            )
        if not current and p.get("task_id"):
            module.fail_json(msg="CKafka task_id was not found; omit it to create a new task")
        if not module.check_mode:
            if current:
                task_id = current["TaskId"]
            else:
                response = module.sdk_call(client.CreateDatahubTask, create_request(models, p))
                task_id = response.Result.TaskId
                p["task_id"] = task_id
            module.sdk_call(client.ModifyDatahubTask, update_request(models, p, task_id))
            status = int(current.get("Status") or 0) if current else 1
            if p["desired_status"] == "paused" and status not in (5, 6, 7):
                module.sdk_call(client.PauseDatahubTask, pause_request(models, task_id))
            if p["desired_status"] == "running" and status in (5, 6, 7):
                module.sdk_call(client.ResumeDatahubTask, resume_request(models, task_id))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), datahub_task=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
