#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_job_config
short_description: Manage Tencent Cloud Oceanus job configuration versions
version_added: "0.14.0"
description: Publishes a new immutable job configuration version only when managed fields differ from the latest version, and can explicitly delete a named historical version.
options:
  state: {type: str, choices: [present, absent], default: present, description: Ensure the desired latest configuration or remove a specified version.}
  job_id: {type: str, required: true, description: Oceanus job ID.}
  workspace_id: {type: str, required: true, description: Owning workspace ID.}
  version: {type: int, description: Configuration version required for deletion.}
  entrypoint_class: {type: str, description: JAR or Python entrypoint class.}
  program_args: {type: str, description: SQL text or program arguments.}
  remark: {type: str, description: Version remark.}
  default_parallelism: {type: int, description: Default job parallelism.}
  properties: {type: list, elements: dict, description: SDK Property list.}
  resource_refs: {type: list, elements: dict, description: ResourceRef list binding managed Oceanus resource IDs and immutable versions to this job version.}
  resource_ref_names: {type: list, elements: dict, description: Resource references resolved by unique name inside the workspace; omitted Version selects the latest resource version.}
  auto_delete_oldest: {type: bool, default: false, description: Automatically delete the earliest deletable version at the service limit.}
  cos_bucket: {type: str, description: Job artifact COS bucket.}
  log_collect: {type: bool, description: Enable log collection.}
  log_collect_type: {type: int, choices: [2, 3], description: CLS or COS log destination.}
  cls_logset_id: {type: str, description: CLS logset ID.}
  cls_topic_id: {type: str, description: CLS topic ID.}
  log_level: {type: str, description: Job log level.}
  python_version: {type: str, description: PyFlink runtime Python version.}
  job_manager_spec: {type: float, description: Legacy JobManager CU specification.}
  task_manager_spec: {type: float, description: Legacy TaskManager CU specification.}
  clazz_levels: {type: list, elements: dict, description: Per-class SDK ClazzLevel logging overrides.}
  expert_mode_on: {type: bool, description: Enable expert-mode operator configuration.}
  expert_mode_configuration: {type: dict, description: SDK ExpertModeConfiguration payload.}
  trace_mode_on: {type: bool, description: Enable operator trace collection.}
  trace_mode_configuration: {type: dict, description: SDK TraceModeConfiguration payload.}
  job_graph: {type: dict, description: SDK JobGraph operator topology configuration.}
  es_serverless_index: {type: str, description: Elasticsearch Serverless log index.}
  es_serverless_space: {type: str, description: Elasticsearch Serverless log space.}
  auto_recover: {type: bool, description: Enable platform recovery.}
  checkpoint_retained: {type: int, description: Number of retained checkpoints.}
  checkpoint_timeout: {type: int, description: Checkpoint timeout in seconds.}
  checkpoint_interval: {type: int, description: Checkpoint interval in seconds.}
  job_manager_cpu: {type: float, description: JobManager CPU.}
  job_manager_memory: {type: float, description: JobManager memory.}
  task_manager_cpu: {type: float, description: TaskManager CPU.}
  task_manager_memory: {type: float, description: TaskManager memory.}
  flink_version: {type: str, description: Flink runtime version.}
  jdk_version: {type: str, description: JDK runtime version.}
  variable_replace_mode: {type: int, choices: [0, 1], description: Table-variable or global SQL-variable replacement mode.}
  state_cos_bucket: {type: str, description: COS bucket used for Flink state.}
  config_scope: {type: int, choices: [0, 1, 2], default: 0, description: 'Full, development-only or operations-only scope.'}
  allow_delete: {type: bool, default: false, description: Explicitly authorize deletion of a historical configuration version.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_job_config:
    job_id: cql-xxxxxxxx
    workspace_id: space-xxxxxxxx
    program_args: SELECT * FROM orders
    default_parallelism: 4
    checkpoint_interval: 60
    auto_recover: true
    resource_ref_names:
      - {Name: orders-processor, Type: 1}
"""
RETURN = r"""job_config: {description: Effective configuration version., type: dict, returned: always}
version: {description: Effective configuration version number., type: int, returned: when present}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "entrypoint_class": "EntrypointClass",
    "program_args": "ProgramArgs",
    "remark": "Remark",
    "default_parallelism": "DefaultParallelism",
    "properties": "Properties",
    "resource_refs": "ResourceRefDetails",
    "cos_bucket": "COSBucket",
    "log_collect": "LogCollect",
    "log_collect_type": "LogCollectType",
    "cls_logset_id": "ClsLogsetId",
    "cls_topic_id": "ClsTopicId",
    "log_level": "LogLevel",
    "python_version": "PythonVersion",
    "job_manager_spec": "JobManagerSpec",
    "task_manager_spec": "TaskManagerSpec",
    "clazz_levels": "ClazzLevels",
    "expert_mode_on": "ExpertModeOn",
    "expert_mode_configuration": "ExpertModeConfiguration",
    "trace_mode_on": "TraceModeOn",
    "trace_mode_configuration": "TraceModeConfiguration",
    "job_graph": "JobGraph",
    "es_serverless_index": "EsServerlessIndex",
    "es_serverless_space": "EsServerlessSpace",
    "checkpoint_retained": "CheckpointRetainedNum",
    "checkpoint_timeout": "CheckpointTimeoutSecond",
    "checkpoint_interval": "CheckpointIntervalSecond",
    "job_manager_cpu": "JobManagerCpu",
    "job_manager_memory": "JobManagerMem",
    "task_manager_cpu": "TaskManagerCpu",
    "task_manager_memory": "TaskManagerMem",
    "flink_version": "FlinkVersion",
    "jdk_version": "JdkVersion",
    "variable_replace_mode": "VariableReplaceMode",
    "state_cos_bucket": "StateCOSBucket",
}


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def desired(p):
    value = {sdk: p[key] for key, sdk in FIELDS.items() if p.get(key) is not None}
    if "ResourceRefDetails" in value:
        value["ResourceRefDetails"] = normalize_resource_refs(value["ResourceRefDetails"])
    if p.get("auto_recover") is not None:
        value["AutoRecover"] = 1 if p["auto_recover"] else -1
    return value


def normalize_resource_refs(values):
    return sorted(
        ({key: item.get(key) for key in ("ResourceId", "Version", "Type")} for item in values or []),
        key=lambda item: (item.get("Type", 0), item.get("ResourceId", "") or "", item.get("Version", -1)),
    )


def managed_value(current, target):
    if isinstance(target, dict):
        current = current if isinstance(current, dict) else {}
        return {key: managed_value(current.get(key), value) for key, value in target.items()}
    if isinstance(target, list):
        current = current if isinstance(current, list) else []
        return [managed_value(current[index] if index < len(current) else None, value) for index, value in enumerate(target)]
    return current


def observed(current, target):
    value = managed_value(current, target)
    if "LogCollect" in target:
        value["LogCollect"] = current.get("LogCollect") not in (None, 0)
    if "LogCollectType" in target:
        value["LogCollectType"] = {1: 2, 4: 3}.get(current.get("LogCollect"))
    if "ResourceRefDetails" in target:
        value["ResourceRefDetails"] = normalize_resource_refs(current.get("ResourceRefDetails"))
    return value


def named_refs(resources, refs):
    by_name = {}
    for resource in resources:
        by_name.setdefault(resource.get("Name"), []).append(resource)
    result = []
    for ref in refs:
        matches = by_name.get(ref["Name"], [])
        if not matches:
            raise ValueError("Oceanus resource not found by name: %s" % ref["Name"])
        if len(matches) > 1:
            raise ValueError("Oceanus resource name is ambiguous: %s" % ref["Name"])
        resource = matches[0]
        result.append(
            {
                "ResourceId": resource["ResourceId"],
                "Version": ref.get("Version") if ref.get("Version") is not None else resource["LatestResourceConfigVersion"],
                "Type": ref["Type"],
            }
        )
    return normalize_resource_refs(result)


def resolve_named_refs(module, client, models, p):
    offset = 0
    resources = []
    while True:
        r = models.DescribeResourcesRequest()
        r.WorkSpaceId, r.SystemResource, r.Offset, r.Limit = p["workspace_id"], 0, offset, 100
        response = module.sdk_call(client.DescribeResources, r)
        page = response.ResourceSet or []
        resources.extend(item._serialize(allow_none=True) for item in page)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    return named_refs(resources, p["resource_ref_names"])


def describe(module, client, models, p, version=None):
    r = models.DescribeJobConfigsRequest()
    r.JobId = p["job_id"]
    r.WorkSpaceId = p["workspace_id"]
    r.Offset, r.Limit = 0, 100
    if version is not None:
        r.JobConfigVersions = [version]
    response = module.sdk_call(client.DescribeJobConfigs, r)
    values = [x._serialize(allow_none=True) for x in response.JobConfigSet or []]
    if version is not None:
        return next((x for x in values if x.get("Version") == version), None)
    return max(values, key=lambda x: x.get("Version", -1)) if values else None


def create_request(models, p, target):
    r = models.CreateJobConfigRequest()
    payload = dict(target)
    if "ResourceRefDetails" in payload:
        payload["ResourceRefs"] = payload.pop("ResourceRefDetails")
    payload.update(
        {"JobId": p["job_id"], "WorkSpaceId": p["workspace_id"], "AutoDelete": 1 if p["auto_delete_oldest"] else 0, "ConfigScope": p["config_scope"]}
    )
    r.from_json_string(json.dumps(payload))
    return r


def delete_request(models, p):
    r = models.DeleteJobConfigsRequest()
    r.JobId = p["job_id"]
    r.WorkSpaceId = p["workspace_id"]
    r.JobConfigVersions = [p["version"]]
    r.ConfigScope = p["config_scope"]
    return r


def wait_config(module, client, models, p, version, present):
    wait_for_state(
        module,
        lambda: "present" if describe(module, client, models, p, version) is not None else "absent",
        ["present" if present else "absent"],
        timeout=p["waiter_timeout"],
        delay=p["waiter_delay"],
    )


def run_module():
    ref_options = {
        "ResourceId": {"required": True},
        "Version": {"type": "int", "required": True},
        "Type": {"type": "int", "choices": [0, 1, 2, 3, 4], "required": True},
    }
    named_ref_options = {"Name": {"required": True}, "Version": {"type": "int"}, "Type": {"type": "int", "choices": [0, 1, 2, 3, 4], "required": True}}
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "job_id": {"required": True},
        "workspace_id": {"required": True},
        "version": {"type": "int"},
        "entrypoint_class": {},
        "program_args": {},
        "remark": {},
        "default_parallelism": {"type": "int"},
        "properties": {"type": "list", "elements": "dict"},
        "resource_refs": {"type": "list", "elements": "dict", "options": ref_options},
        "resource_ref_names": {"type": "list", "elements": "dict", "options": named_ref_options},
        "auto_delete_oldest": {"type": "bool", "default": False},
        "cos_bucket": {},
        "log_collect": {"type": "bool"},
        "log_collect_type": {"type": "int", "choices": [2, 3]},
        "cls_logset_id": {},
        "cls_topic_id": {},
        "log_level": {},
        "python_version": {},
        "job_manager_spec": {"type": "float"},
        "task_manager_spec": {"type": "float"},
        "clazz_levels": {"type": "list", "elements": "dict"},
        "expert_mode_on": {"type": "bool"},
        "expert_mode_configuration": {"type": "dict"},
        "trace_mode_on": {"type": "bool"},
        "trace_mode_configuration": {"type": "dict"},
        "job_graph": {"type": "dict"},
        "es_serverless_index": {},
        "es_serverless_space": {},
        "auto_recover": {"type": "bool"},
        "checkpoint_retained": {"type": "int"},
        "checkpoint_timeout": {"type": "int"},
        "checkpoint_interval": {"type": "int"},
        "job_manager_cpu": {"type": "float"},
        "job_manager_memory": {"type": "float"},
        "task_manager_cpu": {"type": "float"},
        "task_manager_memory": {"type": "float"},
        "flink_version": {},
        "jdk_version": {},
        "variable_replace_mode": {"type": "int", "choices": [0, 1]},
        "state_cos_bucket": {},
        "config_scope": {"type": "int", "choices": [0, 1, 2], "default": 0},
        "allow_delete": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(
        argument_spec=spec,
        required_if=[("state", "absent", ["version"])],
        mutually_exclusive=[("resource_refs", "resource_ref_names")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        if p["state"] == "absent":
            current = describe(module, client, models, p, p["version"])
            if not current:
                module.exit_json(changed=False, job_config=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting an Oceanus job configuration version", version=p["version"])
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteJobConfigs, delete_request(models, p))
                wait_config(module, client, models, p, p["version"], False)
            module.exit_json(changed=True, **(diff or {}), job_config=None)
        if p.get("resource_ref_names") is not None:
            p["resource_refs"] = resolve_named_refs(module, client, models, p)
        target = desired(p)
        if not target:
            module.fail_json(msg="at least one managed configuration field is required to publish an Oceanus job configuration")
        current = describe(module, client, models, p)
        before = observed(current, target) if current else None
        if before == target:
            module.exit_json(changed=False, job_config=current, version=current.get("Version"))
        diff = maybe_diff(module, before, target)
        version = None
        if not module.check_mode:
            version = module.sdk_call(client.CreateJobConfig, create_request(models, p, target)).Version
            wait_config(module, client, models, p, version, True)
            current = describe(module, client, models, p, version)
        module.exit_json(changed=True, **(diff or {}), job_config=current if not module.check_mode else target, version=version)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
