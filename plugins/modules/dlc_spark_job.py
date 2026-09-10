#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_spark_job
short_description: Manage Tencent Cloud DLC Spark job definitions
version_added: "0.14.0"
description:
  - Creates, updates and deletes reusable DLC Spark batch or streaming job definitions.
  - Manages the definition only; submitting tasks remains a separate operation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact job name and immutable module identity.}
  app_type: {type: int, choices: [1, 2], description: 'Job type, 1 batch or 2 streaming.'}
  data_engine: {type: str, description: DLC data engine name.}
  app_file: {type: str, description: COS program package path.}
  role_arn: {type: int, description: DLC data-access role ID.}
  driver_size: {type: str, choices: [small, medium, large, xlarge], description: Driver CU specification.}
  executor_size: {type: str, choices: [small, medium, large, xlarge], description: Executor CU specification.}
  executor_nums: {type: int, description: Initial executor count.}
  executor_max_nums: {type: int, description: Maximum executor count for dynamic allocation.}
  main_class: {type: str, description: Application main class.}
  app_conf: {type: str, description: Newline-separated Spark configuration.}
  cmd_args: {type: str, description: Space-separated application arguments.}
  max_retries: {type: int, description: Maximum streaming-job retries.}
  data_source: {type: str, description: Bound DLC data-source name.}
  package_source: {type: str, choices: [cos, lakefs], description: Main and dependency package source.}
  jars: {type: str, description: Comma-separated dependency JAR paths.}
  files: {type: str, description: Comma-separated dependency file paths.}
  python_files: {type: str, description: Comma-separated PySpark dependency paths.}
  archives: {type: str, description: Comma-separated archive paths.}
  spark_image: {type: str, description: Spark image ID.}
  spark_image_version: {type: str, description: Spark image version name.}
  inherit_engine_config: {type: bool, description: Inherit the engine resource template.}
  session_id: {type: str, description: Associated query-script session ID.}
  session_started: {type: bool, description: Run SQL from the associated session script.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize definition deletion.}
  allow_delete_running: {type: bool, default: false, description: Explicitly authorize deletion while tasks are active.}
  wait: {type: bool, default: true, description: Wait for definition convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_spark_job:
    name: daily-customer-etl
    app_type: 1
    data_engine: production-spark
    app_file: cosn://analytics/jobs/customer-etl.jar
    role_arn: 100000000001
    driver_size: medium
    executor_size: large
    executor_nums: 2
    executor_max_nums: 10
    main_class: com.example.CustomerEtl
    package_source: cos

- susunola.tencentcloud.dlc_spark_job:
    name: daily-customer-etl
    state: absent
    allow_delete: true
"""
RETURN = r"""
spark_job:
  description: Effective Spark job-definition metadata.
  type: dict
  returned: always
spark_job_id:
  description: Spark job-definition ID.
  type: str
  returned: when present
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "app_type": ("AppType", "JobType"),
    "data_engine": ("DataEngine", "DataEngine"),
    "app_file": ("AppFile", "JobFile"),
    "role_arn": ("RoleArn", "RoleArn"),
    "driver_size": ("AppDriverSize", "JobDriverSize"),
    "executor_size": ("AppExecutorSize", "JobExecutorSize"),
    "executor_nums": ("AppExecutorNums", "JobExecutorNums"),
    "executor_max_nums": ("AppExecutorMaxNumbers", "JobExecutorMaxNumbers"),
    "main_class": ("MainClass", "MainClass"),
    "app_conf": ("AppConf", "JobConf"),
    "cmd_args": ("CmdArgs", "CmdArgs"),
    "max_retries": ("MaxRetries", "JobMaxAttempts"),
    "data_source": ("DataSource", "DataSource"),
    "jars": ("AppJars", "JobJars"),
    "files": ("AppFiles", "JobFiles"),
    "python_files": ("AppPythonFiles", "JobPythonFiles"),
    "archives": ("AppArchives", "JobArchives"),
    "spark_image": ("SparkImage", "SparkImage"),
    "spark_image_version": ("SparkImageVersion", "SparkImageVersion"),
    "session_id": ("SessionId", "SessionId"),
    "session_started": ("IsSessionStarted", "IsSessionStarted"),
    "inherit_engine_config": ("IsInherit", "IsInherit"),
}
SOURCE_FIELDS = {"jars": "IsLocalJars", "files": "IsLocalFiles", "python_files": "IsLocalPythonFiles", "archives": "IsLocalArchives"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def describe_request(models, name=None, job_id=None):
    request = models.DescribeSparkAppJobRequest()
    request.JobId, request.JobName = job_id, None if job_id else name
    return request


def find(module, client, models, name=None, job_id=None):
    response = module.sdk_call(client.DescribeSparkAppJob, describe_request(models, name, job_id))
    if not response.IsExists or response.Job is None:
        return None
    current = response.Job._serialize(allow_none=True)
    if name and current.get("JobName") != name:
        module.fail_json(msg="DLC returned a Spark job with an unexpected name", expected=name, spark_job=current)
    return current


def request_payload(p, job_id=None):
    payload = {"AppName": p["name"]}
    if job_id:
        payload["SparkAppId"] = job_id
    for source, (target, _) in FIELDS.items():
        if p.get(source) is not None:
            payload[target] = int(p[source]) if source == "inherit_engine_config" else p[source]
    if p.get("package_source") is not None:
        payload["IsLocal"] = p["package_source"]
    for source, target in SOURCE_FIELDS.items():
        if p.get(source) is not None:
            payload[target] = p["package_source"]
    return payload


def make_request(models, p, update=False, job_id=None):
    import json

    request = models.ModifySparkAppRequest() if update else models.CreateSparkAppRequest()
    request.from_json_string(json.dumps(request_payload(p, job_id)))
    return request


def delete_request(models, name):
    request = models.DeleteSparkAppRequest()
    request.AppName = name
    return request


def desired(p, current=None):
    result = dict(current or {})
    result["JobName"] = p["name"]
    for source, (_, target) in FIELDS.items():
        if p.get(source) is not None:
            result[target] = int(p[source]) if source == "inherit_engine_config" else p[source]
    if p.get("package_source") is not None:
        result["IsLocal"] = p["package_source"]
    for source, target in SOURCE_FIELDS.items():
        if p.get(source) is not None:
            result[target] = p["package_source"]
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    keys = [read for _, read in FIELDS.values()]
    if p.get("package_source") is not None:
        keys.append("IsLocal")
    keys.extend(target for source, target in SOURCE_FIELDS.items() if p.get(source) is not None)
    for key in keys:
        if current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def wait_job(module, client, models, p, job_id=None, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"], job_id)
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "app_type": {"type": "int", "choices": [1, 2]},
        "data_engine": {},
        "app_file": {},
        "role_arn": {"type": "int"},
        "driver_size": {"choices": ["small", "medium", "large", "xlarge"]},
        "executor_size": {"choices": ["small", "medium", "large", "xlarge"]},
        "executor_nums": {"type": "int"},
        "executor_max_nums": {"type": "int"},
        "main_class": {},
        "app_conf": {},
        "cmd_args": {},
        "max_retries": {"type": "int"},
        "data_source": {},
        "package_source": {"choices": ["cos", "lakefs"]},
        "jars": {},
        "files": {},
        "python_files": {},
        "archives": {},
        "spark_image": {},
        "spark_image_version": {},
        "inherit_engine_config": {"type": "bool"},
        "session_id": {},
        "session_started": {"type": "bool"},
        "allow_delete": {"type": "bool", "default": False},
        "allow_delete_running": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("executor_nums") is not None and p.get("executor_max_nums") is not None and p["executor_nums"] > p["executor_max_nums"]:
        module.fail_json(msg="executor_nums must not exceed executor_max_nums")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, spark_job=None, spark_job_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC Spark job definition", spark_job=current)
            if int(current.get("TaskNum") or 0) > 0 and not p["allow_delete_running"]:
                module.fail_json(
                    msg="set allow_delete_running=true to delete a Spark job definition with active tasks", active_tasks=current["TaskNum"], spark_job=current
                )
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteSparkApp, delete_request(models, p["name"]))
                if p["wait"]:
                    wait_job(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), spark_job=None, spark_job_id=None)
        if not current:
            required = ("app_type", "data_engine", "app_file", "role_arn", "driver_size", "executor_size", "executor_nums", "package_source")
            missing = [key for key in required if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC Spark job definition", missing=missing)
            after, diff_value = desired(p), maybe_diff(module, None, desired(p))
            job_id = None
            if not module.check_mode:
                job_id = module.sdk_call(client.CreateSparkApp, make_request(models, p)).SparkAppId
                if p["wait"]:
                    wait_job(module, client, models, p, job_id=job_id, expected={k: v for k, v in after.items() if k != "JobName"})
                current = find(module, client, models, job_id=job_id)
            module.exit_json(
                changed=True, **(diff_value or {}), spark_job=current if not module.check_mode else after, spark_job_id=(current or {}).get("JobId") or job_id
            )
        changes = drift(p, current)
        if not changes:
            module.exit_json(changed=False, spark_job=current, spark_job_id=current.get("JobId"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.ModifySparkApp, make_request(models, p, update=True, job_id=current["JobId"]))
            if p["wait"]:
                wait_job(module, client, models, p, job_id=current["JobId"], expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, job_id=current["JobId"])
        module.exit_json(changed=True, **(diff_value or {}), spark_job=current if not module.check_mode else after, spark_job_id=current.get("JobId"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
