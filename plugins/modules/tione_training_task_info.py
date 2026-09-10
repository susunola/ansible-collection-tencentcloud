#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_training_task_info
short_description: Gather Tencent Cloud TIONE training tasks
version_added: "0.14.0"
description:
  - Returns one exact training task or lists tasks with workspace, state, identity and tag filters.
  - Exact lookup can select a historical task instance; list mode uses bounded offset pagination.
options:
  task_id: {type: str, description: Exact training task ID; switches to detail mode.}
  instance_id: {type: str, description: Optional historical training-task instance ID; requires task_id.}
  project_id: {type: str, description: Optional TI workspace ID.}
  filters: {type: dict, default: {}, description: Training-task API filters used in list mode.}
  tag_filters: {type: dict, default: {}, description: Tag keys mapped to values or value lists in list mode.}
  order_field: {type: str, choices: [CreateTime, UpdateTime, StartTime], default: UpdateTime, description: List sort field.}
  order: {type: str, choices: [ASC, DESC], default: DESC, description: List sort direction.}
  page_size: {type: int, default: 50, description: 'Tasks requested per page, from 1 to 50.'}
  max_pages: {type: int, default: 1000, description: 'Maximum pages fetched, from 1 to 1000.'}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_training_task_info:
    task_id: train-xxxxxxxx

- susunola.tencentcloud.tione_training_task_info:
    filters:
      Status: [RUNNING, FAILED]
      ChargeType: POSTPAID_BY_HOUR
    tag_filters:
      team: ml-platform
"""
RETURN = r"""
training_task: {description: Exact training-task detail., type: dict, returned: when task_id is provided}
training_tasks: {description: Matching training tasks., type: list, elements: dict, returned: in list mode}
total_count: {description: Number of tasks reported by the API., type: int, returned: in list mode}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: in list mode}
request_id: {description: Request ID from the exact request or final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def detail_request(models, p):
    request = models.DescribeTrainingTaskRequest()
    request.Id = p["task_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p.get("instance_id") is not None:
        request.InstanceId = p["instance_id"]
    return request


def list_request(models, p, offset):
    request = models.DescribeTrainingTasksRequest()
    request.Offset, request.Limit = offset, p["page_size"]
    request.Order, request.OrderField = p["order"], p["order_field"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p["filters"]:
        request.Filters = []
        for name, values in sorted(p["filters"].items()):
            item = models.Filter()
            item.Name, item.Values = name, values if isinstance(values, list) else [values]
            request.Filters.append(item)
    if p["tag_filters"]:
        request.TagFilters = []
        for key, values in sorted(p["tag_filters"].items()):
            item = models.TagFilter()
            item.TagKey, item.TagValues = key, values if isinstance(values, list) else [values]
            request.TagFilters.append(item)
    return request


def read_list(module, client, models, p):
    values, total, request_id, truncated, offset = [], 0, None, False, 0
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeTrainingTasks, list_request(models, p, offset))
        items = response.TrainingTaskSet or []
        values.extend(item._serialize(allow_none=True) for item in items)
        total, request_id = int(response.TotalCount or 0), response.RequestId
        offset += len(items)
        if not items or offset >= total:
            break
    else:
        truncated = True
    return values, total, truncated, request_id


def run_module():
    spec = {
        "task_id": {},
        "instance_id": {},
        "project_id": {},
        "filters": {"type": "dict", "default": {}},
        "tag_filters": {"type": "dict", "default": {}},
        "order_field": {"choices": ["CreateTime", "UpdateTime", "StartTime"], "default": "UpdateTime"},
        "order": {"choices": ["ASC", "DESC"], "default": "DESC"},
        "page_size": {"type": "int", "default": 50},
        "max_pages": {"type": "int", "default": 1000},
    }
    module = TencentCloudModule(
        argument_spec=spec,
        supports_check_mode=True,
        required_by={"instance_id": "task_id"},
        mutually_exclusive=[("task_id", "filters"), ("task_id", "tag_filters")],
    )
    p = module.params
    if not 1 <= p["page_size"] <= 50:
        module.fail_json(msg="page_size must be between 1 and 50")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        if p.get("task_id"):
            response = module.sdk_call(client.DescribeTrainingTask, detail_request(models, p))
            value = response.TrainingTaskDetail._serialize(allow_none=True) if response.TrainingTaskDetail else None
            module.exit_json(changed=False, training_task=value, request_id=response.RequestId)
        values, total, truncated, request_id = read_list(module, client, models, p)
        module.exit_json(changed=False, training_tasks=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
