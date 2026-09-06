#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_job_savepoint
short_description: Create Tencent Cloud Oceanus job savepoints
version_added: "0.14.0"
description:
  - Triggers a savepoint for a running Oceanus job and optionally waits until it is usable.
  - The description is an idempotency key; an existing active or in-progress savepoint with the same description is reused unless C(force=true).
options:
  job_id: {type: str, required: true, description: Oceanus job ID.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  description: {type: str, required: true, description: Stable savepoint description used for idempotent reconciliation.}
  force: {type: bool, default: false, description: Trigger another savepoint even when the description already exists.}
  wait: {type: bool, default: true, description: Wait for the savepoint to become active.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between savepoint status polls.}
  waiter_timeout: {type: int, default: 600, description: Overall savepoint wait timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_job_savepoint:
    job_id: cql-xxxxxxxx
    workspace_id: space-xxxxxxxx
    description: before-release-2026-08-31
"""
RETURN = r"""savepoint: {description: Existing or newly created savepoint metadata., type: dict, returned: always}
savepoint_id: {description: Savepoint serial ID., type: str, returned: when available}
savepoint_path: {description: Savepoint restore path., type: str, returned: when available}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_task


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def describe_request(models, p, offset=0):
    r = models.DescribeJobSavepointRequest()
    r.JobId, r.WorkSpaceId = p["job_id"], p["workspace_id"]
    r.Offset, r.Limit, r.RecordTypes = offset, 100, [1]
    return r


def list_savepoints(module, client, models, p):
    offset = 0
    values = []
    seen = set()
    while True:
        response = module.sdk_call(client.DescribeJobSavepoint, describe_request(models, p, offset))
        page = response.Savepoint or []
        for item in list(response.RunningSavepoint or []) + list(page):
            value = item._serialize(allow_none=True)
            identity = value.get("SerialId") or value.get("Id")
            if identity not in seen:
                seen.add(identity)
                values.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalNumber or 0):
            break
    return values


def matching(values, description, statuses=(1, 3)):
    candidates = [value for value in values if value.get("Description") == description and value.get("Status") in statuses]
    return max(candidates, key=lambda value: (value.get("CreateTime") or 0, value.get("Id") or 0)) if candidates else None


def find_by_id(values, savepoint_id):
    return next((value for value in values if str(value.get("SerialId") or value.get("Id")) == str(savepoint_id)), None)


def trigger_request(models, p):
    r = models.TriggerJobSavepointRequest()
    r.JobId, r.WorkSpaceId, r.Description = p["job_id"], p["workspace_id"], p["description"]
    return r


def run_module():
    spec = {
        "job_id": {"required": True},
        "workspace_id": {"required": True},
        "description": {"required": True},
        "force": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        current = matching(list_savepoints(module, client, models, p), p["description"])
        if current and not p["force"]:
            module.exit_json(changed=False, savepoint=current, savepoint_id=current.get("SerialId"), savepoint_path=current.get("Path"))
        target = {"Description": p["description"], "Status": 3, "RecordType": 1}
        if module.check_mode:
            module.exit_json(changed=True, savepoint=target, savepoint_id=None, savepoint_path=None)
        response = module.sdk_call(client.TriggerJobSavepoint, trigger_request(models, p))
        if not response.SavepointTrigger:
            module.fail_json(msg="Oceanus rejected the savepoint trigger", error=response.ErrorMsg)
        savepoint_id = response.SavepointId

        def poll():
            values = list_savepoints(module, client, models, p)
            value = find_by_id(values, savepoint_id) or matching(values, p["description"], (1, 3, 4, 5))
            return ((value or {}).get("Status"), (value or {}).get("Description"), value)

        current = (
            wait_for_task(module, poll, timeout=p["waiter_timeout"], delay=p["waiter_delay"], success_statuses=(1,), failure_statuses=(4, 5))
            if p["wait"]
            else find_by_id(list_savepoints(module, client, models, p), savepoint_id)
        )
        module.exit_json(
            changed=True, savepoint=current or target, savepoint_id=savepoint_id, savepoint_path=(current or {}).get("Path") or response.FinalSavepointPath
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
