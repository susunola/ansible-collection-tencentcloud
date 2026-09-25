#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_job_spec
short_description: Manage reusable Tencent Cloud DLC job specifications
version_added: "0.14.0"
description:
  - Manages reusable DLC job specifications for group, cluster or serverless submission.
  - Reconciles JSON documents and tags semantically and blocks deletion while jobs are running by default.
options:
  state:
    description:
      - Desired lifecycle state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Exact job-specification name and identity.
    type: str
    required: true
  entrypoint:
    description:
      - Job entrypoint command; required on creation.
    type: str
  description:
    description:
      - Job-specification description.
    type: str
  image:
    description:
      - Container image address.
    type: str
  image_pull_type:
    description:
      - Image source type.
    type: str
    choices: [Builtin, Custom]
  image_pull_policy:
    description:
      - When the container image is pulled for the job.
    type: str
    choices: [Always, IfNotPresent, Never]
  resource_config:
    description:
      - Inline resource configuration JSON.
    type: str
  resource_config_id:
    description:
      - Reusable resource-template ID.
    type: str
  runtime_env:
    description:
      - Runtime environment JSON.
    type: str
  catalog:
    description:
      - Volume and mount JSON.
    type: str
  autoscaler_options:
    description:
      - Autoscaler JSON.
    type: str
  advanced_options:
    description:
      - Advanced job options JSON.
    type: str
  resource_partition_id:
    description:
      - Default resource partition ID.
    type: str
  queue:
    description:
      - Default queue name.
    type: str
  group_id:
    description:
      - Default compute-group ID.
    type: str
  cluster_id:
    description:
      - Default persistent cluster ID.
    type: str
  job_package:
    description:
      - Job package URL.
    type: str
  job_package_name:
    description:
      - Name of the job package the specification runs.
    type: str
  priority:
    description:
      - Priority from 1 to 9.
    type: int
  dispatch_strategy:
    description:
      - Group dispatch strategy.
    type: str
    choices: [RANDOM]
  tags:
    type: list
    elements: dict
    description: Exact Tencent Cloud tag set.
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
  allow_delete:
    description:
      - Explicitly authorize deletion.
    type: bool
    default: false
  allow_delete_running:
    description:
      - Explicitly authorize deletion while jobs are running.
    type: bool
    default: false
  wait:
    description:
      - Wait for lifecycle and field convergence.
    type: bool
    default: true
  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 300

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
  - module: susunola.tencentcloud.dlc_job_spec_info
    description: Gather information about Tencent Cloud DLC job specs.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_job_spec:
    name: daily-ray-etl
    entrypoint: python main.py
    image: ccr.ccs.tencentyun.com/analytics/ray:stable
    image_pull_type: Custom
    group_id: cg-xxxxxxxx
    resource_config_id: rc-xxxxxxxx
    priority: 5
    tags:
      - {key: workload, value: etl}

- susunola.tencentcloud.dlc_job_spec:
    name: daily-ray-etl
    state: absent
    allow_delete: true
"""
RETURN = r"""
job_spec:
  description: Effective DLC job specification.
  type: dict
  returned: always
job_spec_id:
  description: DLC job-specification ID.
  type: str
  returned: when present
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "entrypoint": "Entrypoint",
    "description": "Description",
    "image": "Image",
    "image_pull_type": "ImagePullType",
    "image_pull_policy": "ImagePullPolicy",
    "resource_config": "ResourceConfig",
    "runtime_env": "RuntimeEnv",
    "catalog": "Catalog",
    "autoscaler_options": "AutoscalerOptions",
    "resource_partition_id": "ResourcePartitionId",
    "resource_config_id": "ResourceConfigId",
    "queue": "Queue",
    "job_package": "JobPackage",
    "job_package_name": "JobPackageName",
    "advanced_options": "AdvancedOptions",
    "group_id": "GroupId",
    "cluster_id": "ClusterId",
    "priority": "Priority",
    "tags": "Tags",
    "dispatch_strategy": "DispatchStrategy",
}
JSON_FIELDS = {"resource_config", "runtime_env", "catalog", "autoscaler_options", "advanced_options"}


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
    result["Tags"] = tags(result.get("Tags"))
    for key in ("ResourceConfig", "RuntimeEnv", "Catalog", "AutoscalerOptions", "AdvancedOptions"):
        if key in result:
            result[key] = canonical(result[key])
    return result


def list_request(models, page=1):
    request = models.ListJobSpecsRequest()
    request.Page, request.PageSize = page, 200
    return request


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListJobSpecs, list_request(models, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name)
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC job specifications matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p["name"]
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            result[target] = tags(p[source]) if source == "tags" else (canonical(p[source]) if source in JSON_FIELDS else p[source])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in FIELDS.items():
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def make_request(models, p, update=False, spec_id=None):
    request = models.UpdateJobSpecRequest() if update else models.CreateJobSpecRequest()
    payload = {"Name": p["name"]}
    if spec_id:
        payload["SpecId"] = spec_id
    for source, target in FIELDS.items():
        if update and source == "priority":
            continue
        if p.get(source) is not None:
            payload[target] = tags(p[source]) if source == "tags" else (canonical(p[source]) if source in JSON_FIELDS else p[source])
    request.from_json_string(json.dumps(payload))
    return request


def delete_request(models, spec_id):
    request = models.DeleteJobSpecRequest()
    request.SpecId = spec_id
    return request


def priority_request(models, spec_id, priority):
    request = models.UpdateJobSpecPriorityRequest()
    request.SpecId, request.Priority = spec_id, priority
    return request


def wait_spec(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"])
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    tag_options = {"key": {"required": True, "no_log": False}, "value": {"required": True}}
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True}}
    for key in FIELDS:
        spec[key] = {}
    spec.update(
        {
            "priority": {"type": "int"},
            "image_pull_type": {"choices": ["Builtin", "Custom"]},
            "image_pull_policy": {"choices": ["Always", "IfNotPresent", "Never"]},
            "dispatch_strategy": {"choices": ["RANDOM"]},
            "tags": {"type": "list", "elements": "dict", "options": tag_options},
            "allow_delete": {"type": "bool", "default": False},
            "allow_delete_running": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 5},
            "waiter_timeout": {"type": "int", "default": 300},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("priority") is not None and not 1 <= p["priority"] <= 9:
        module.fail_json(msg="priority must be between 1 and 9")
    if p.get("group_id") and p.get("cluster_id"):
        module.fail_json(msg="group_id and cluster_id are mutually exclusive")
    if p.get("resource_config") and p.get("resource_config_id"):
        module.fail_json(msg="resource_config and resource_config_id are mutually exclusive")
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
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, job_spec=None, job_spec_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC job specification", job_spec=current)
            if current.get("HasRunningJobs") and not p["allow_delete_running"]:
                module.fail_json(msg="DLC job specification has running jobs; set allow_delete_running=true to authorize deletion", job_spec=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteJobSpec, delete_request(models, current["Id"]))
                if p["wait"]:
                    wait_spec(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), job_spec=None, job_spec_id=None)
        if not current:
            if not p.get("entrypoint"):
                module.fail_json(msg="entrypoint is required when creating a DLC job specification")
            after, diff_value, spec_id = desired(p), maybe_diff(module, None, desired(p)), None
            if not module.check_mode:
                spec_id = module.sdk_call(client.CreateJobSpec, make_request(models, p)).Id
                if p["wait"]:
                    wait_spec(module, client, models, p, expected={k: v for k, v in after.items() if k != "Name"})
                current = find(module, client, models, p["name"])
            module.exit_json(
                changed=True, **(diff_value or {}), job_spec=current if not module.check_mode else after, job_spec_id=(current or {}).get("Id") or spec_id
            )
        changes = drift(p, current)
        if not changes:
            module.exit_json(changed=False, job_spec=current, job_spec_id=current.get("Id"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            regular_changes = {key: value for key, value in changes.items() if key != "Priority"}
            if regular_changes:
                module.sdk_call(client.UpdateJobSpec, make_request(models, p, update=True, spec_id=current["Id"]))
            if "Priority" in changes:
                module.sdk_call(client.UpdateJobSpecPriority, priority_request(models, current["Id"], p["priority"]))
            if p["wait"]:
                wait_spec(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), job_spec=current if not module.check_mode else after, job_spec_id=current.get("Id"))
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
