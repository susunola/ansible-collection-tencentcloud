#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_datahub_task_info
short_description: Gather Tencent Cloud CKafka Datahub tasks
version_added: "1.4.0"
description:
  - Reads a Datahub task by ID or lists tasks with optional server-side filters.
  - Credential-like fields are recursively removed from returned data.
options:
  task_id: {description: Datahub task ID. When set, returns the detailed task., type: str}
  name: {description: Search text applied by the service., type: str}
  task_type: {description: Task direction used to filter listed tasks., type: str, choices: [SOURCE, SINK]}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read a Datahub task by ID
  susunola.tencentcloud.ckafka_datahub_task_info:
    region: ap-guangzhou
    task_id: task-xxxxxxxx

- name: List source tasks
  susunola.tencentcloud.ckafka_datahub_task_info:
    region: ap-guangzhou
    task_type: SOURCE
'''

RETURN = r'''
tasks: {description: Matching tasks with credentials removed., returned: always, type: list, elements: dict}
task: {description: The single matching task when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)

SENSITIVE = ("password", "secret", "token", "credential", "privatekey", "accesskey")


def scrub(value):
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if not any(part in key.lower() for part in SENSITIVE)}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def detail_request(models, task_id):
    request = models.DescribeDatahubTaskRequest()
    request.TaskId = task_id
    return request


def list_request(models, task_type=None, name=None, offset=0, limit=100):
    request = models.DescribeDatahubTasksRequest()
    request.TaskType, request.SearchWord = task_type, name
    request.Offset, request.Limit = offset, limit
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "task_id": {"type": "str"},
        "name": {"type": "str"},
        "task_type": {"type": "str", "choices": ["SOURCE", "SINK"]},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")
    p = module.params
    client = ckafka_client.CkafkaClient(create_credential(module), p["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    if p.get("task_id"):
        try:
            response = sdk_call(module, client.DescribeDatahubTask, detail_request(models, p["task_id"]))
        except Exception as exc:
            if is_not_found(exc):
                module.exit_json(changed=False, tasks=[], task=None, request_id=getattr(exc, "request_id", None))
            raise
        task = scrub(serialize_sdk_object(response.Result)) if getattr(response, "Result", None) else None
        module.exit_json(changed=False, tasks=[task] if task else [], task=task, request_id=getattr(response, "RequestId", None))

    offset, tasks, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.DescribeDatahubTasks, list_request(models, p.get("task_type"), p.get("name"), offset))
        request_id = getattr(response, "RequestId", None)
        result = getattr(response, "Result", None)
        page = list(getattr(result, "TaskList", None) or [])
        tasks.extend(scrub(serialize_sdk_object(item)) for item in page)
        total = int(getattr(result, "TotalCount", 0) or 0)
        offset += len(page)
        if not page or offset >= total:
            break
    module.exit_json(changed=False, tasks=tasks, task=tasks[0] if len(tasks) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
