#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_job
short_description: Manage Tencent Cloud Oceanus jobs
version_added: "0.14.0"
description: Creates, updates, starts, pauses, stops and deletes Oceanus SQL or JAR jobs inside a workspace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  job_id: {type: str, description: Existing job ID.}
  name: {type: str, description: Job name.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  job_type: {type: int, choices: [1, 2], description: SQL or JAR job type; immutable after creation.}
  cluster_type: {type: int, choices: [1, 2], description: Shared or dedicated cluster type; defaults to shared during creation.}
  cluster_id: {type: str, description: Dedicated cluster ID; required for cluster_type 2 and immutable after creation.}
  cu_memory: {type: int, choices: [2, 4, 8, 16], description: Memory per CU in GiB; defaults to 4 during creation.}
  folder_id: {type: str, description: Initial folder ID; defaults to root during creation.}
  flink_version: {type: str, description: Flink version; immutable after creation.}
  jdk_version: {type: str, description: JDK version; immutable after creation.}
  remark: {type: str, description: Job remark.}
  description: {type: str, description: Job description.}
  default_alarm: {type: bool, default: false, description: Enable the default alarm during creation.}
  continue_alarm: {type: bool, description: Continue alarming for a stopped job.}
  tags: {type: dict, description: Tags applied during creation.}
  desired_status: {type: str, choices: [running, stopped, paused], description: Desired runtime state.}
  job_config_version: {type: int, description: Published configuration version to run.}
  start_mode: {type: str, default: LATEST, description: SQL source start mode.}
  savepoint_id: {type: str, description: Savepoint ID used when restoring a paused job.}
  savepoint_path: {type: str, description: Savepoint path used when restoring a paused job.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_job:
    name: orders-stream
    workspace_id: space-xxxxxxxx
    job_type: 1
    cluster_type: 1
    flink_version: Flink-1.17
    desired_status: stopped
"""
RETURN = r"""job: {description: Effective Oceanus job metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def describe_request(models, p, offset=0):
    r = models.DescribeJobsRequest()
    r.Offset, r.Limit, r.WorkSpaceId = offset, 100, p["workspace_id"]
    if p.get("job_id"):
        r.JobIds = [p["job_id"]]
    elif p.get("name"):
        f = models.Filter()
        f.Name, f.Values = "Name", [p["name"]]
        r.Filters = [f]
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def create_request(models, p):
    r = models.CreateJobRequest()
    r.Name, r.JobType, r.WorkSpaceId = p["name"], p["job_type"], p["workspace_id"]
    r.ClusterType, r.ClusterId, r.CuMem = p.get("cluster_type") or 1, p.get("cluster_id"), p.get("cu_memory") or 4
    r.Remark, r.Description, r.FolderId = p.get("remark"), p.get("description"), p.get("folder_id") or "root"
    r.FlinkVersion, r.JdkVersion, r.OpenJobDefaultAlarm, r.Tags = (
        p.get("flink_version"),
        p.get("jdk_version"),
        1 if p["default_alarm"] else 0,
        _tags(models, p.get("tags")),
    )
    return r


def modify_request(models, p, job_id, name, remark, description, folder_id):
    r = models.ModifyJobRequest()
    r.JobId, r.WorkSpaceId, r.Name = job_id, p["workspace_id"], name
    r.Remark, r.Description, r.TargetFolderId = remark, description, folder_id
    r.ContinueAlarm = None if p.get("continue_alarm") is None else int(p["continue_alarm"])
    return r


def run_request(models, p, job_id, resume=False):
    item = models.RunJobDescription()
    item.JobId, item.RunType, item.StartMode = job_id, 2 if resume else 1, p["start_mode"]
    item.JobConfigVersion, item.SavepointId, item.SavepointPath = p.get("job_config_version"), p.get("savepoint_id"), p.get("savepoint_path")
    r = models.RunJobsRequest()
    r.WorkSpaceId, r.RunJobDescriptions = p["workspace_id"], [item]
    return r


def stop_request(models, p, job_id, pause=False):
    item = models.StopJobDescription()
    item.JobId, item.StopType = job_id, 2 if pause else 1
    r = models.StopJobsRequest()
    r.WorkSpaceId, r.StopJobDescriptions = p["workspace_id"], [item]
    return r


def delete_request(models, p, job_id, name):
    r = models.DeleteJobsRequest()
    r.WorkSpaceId, r.JobIds, r.JobNames = p["workspace_id"], [job_id], [name]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeJobs, describe_request(models, p))
    matches = []
    for item in response.JobSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("job_id") and value.get("JobId") == p["job_id"]) or (not p.get("job_id") and value.get("Name") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple Oceanus jobs matched; specify job_id")
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: (find(module, client, models, p) or {}).get("Status"),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "job_id": {},
        "name": {},
        "workspace_id": {"required": True},
        "job_type": {"type": "int", "choices": [1, 2]},
        "cluster_type": {"type": "int", "choices": [1, 2]},
        "cluster_id": {},
        "cu_memory": {"type": "int", "choices": [2, 4, 8, 16]},
        "folder_id": {},
        "flink_version": {},
        "jdk_version": {},
        "remark": {},
        "description": {},
        "default_alarm": {"type": "bool", "default": False},
        "continue_alarm": {"type": "bool"},
        "tags": {"type": "dict"},
        "desired_status": {"choices": ["running", "stopped", "paused"]},
        "job_config_version": {"type": "int"},
        "start_mode": {"default": "LATEST"},
        "savepoint_id": {},
        "savepoint_path": {},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("job_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, job=None)
            diff = maybe_diff(module, current, None)
            job_id = current["JobId"]
            if not module.check_mode:
                if current.get("Status") in (3, 4, 6):
                    module.sdk_call(client.StopJobs, stop_request(models, p, job_id))
                    p["job_id"] = job_id
                    _wait(module, client, models, p, [5])
                module.sdk_call(client.DeleteJobs, delete_request(models, p, job_id, current["Name"]))
            module.exit_json(changed=True, **(diff or {}), job=None)
        if not current:
            if not p.get("name") or p.get("job_type") is None:
                module.fail_json(msg="name and job_type are required to create an Oceanus job")
            if p.get("cluster_type") == 2 and not p.get("cluster_id"):
                module.fail_json(msg="cluster_id is required for a dedicated Oceanus job")
            target = {
                "Name": p["name"],
                "JobType": p["job_type"],
                "ClusterType": p.get("cluster_type") or 1,
                "ClusterId": p.get("cluster_id"),
                "CuMem": p.get("cu_memory") or 4,
                "WorkSpaceId": p["workspace_id"],
                "Status": 5,
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["job_id"] = module.sdk_call(client.CreateJob, create_request(models, p)).JobId
                current = find(module, client, models, p)
            else:
                current = target
            changed = True
        else:
            changed, diff = False, None
        immutable = {
            "JobType": p.get("job_type"),
            "ClusterType": p.get("cluster_type"),
            "ClusterId": p.get("cluster_id"),
            "CuMem": p.get("cu_memory"),
            "FlinkVersion": p.get("flink_version"),
            "JdkVersion": p.get("jdk_version"),
        }
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift:
            module.fail_json(msg="Oceanus job engine and cluster placement are immutable", immutable_drift=drift)
        desired = {
            "Name": p.get("name") or current.get("Name"),
            "Remark": p.get("remark") if p.get("remark") is not None else current.get("Remark"),
            "Description": p.get("description") if p.get("description") is not None else current.get("Description"),
            "ContinueAlarm": p.get("continue_alarm") if p.get("continue_alarm") is not None else current.get("ContinueAlarm"),
        }
        before = {k: current.get(k) for k in desired}
        if before != desired:
            changed = True
            diff = maybe_diff(module, before, desired)
            if not module.check_mode:
                module.sdk_call(client.ModifyJob, modify_request(models, p, current["JobId"], desired["Name"], desired["Remark"], desired["Description"], None))
                p["job_id"] = current["JobId"]
                current = find(module, client, models, p)
        status_target = {"running": 4, "stopped": 5, "paused": 6}.get(p.get("desired_status"))
        if status_target is not None and current.get("Status") != status_target:
            changed = True
            job_id = current.get("JobId") or p.get("job_id")
            if not module.check_mode:
                if status_target == 4:
                    module.sdk_call(client.RunJobs, run_request(models, p, job_id, current.get("Status") == 6))
                else:
                    module.sdk_call(client.StopJobs, stop_request(models, p, job_id, status_target == 6))
                p["job_id"] = job_id
                _wait(module, client, models, p, [status_target])
                current = find(module, client, models, p)
        module.exit_json(changed=changed, **(diff or {}), job=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
