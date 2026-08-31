#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dts_migration_job_config
short_description: Configure a Tencent Cloud DTS migration job
version_added: "0.14.0"
description: Reconciles the source, destination, migration options and schedule of a purchased DTS migration job.
options:
  job_id: {description: DTS migration job ID., type: str, required: true}
  name: {description: Migration job name., type: str}
  run_mode: {description: Job run mode., type: str, choices: [immediate, timed], default: immediate}
  expected_run_time: {description: Expected start time for timed mode., type: str}
  source: {description: Source endpoint fields accepted by DTS DBEndpointInfo., type: dict, required: true}
  destination: {description: Destination endpoint fields accepted by DTS DBEndpointInfo., type: dict, required: true}
  migration_options: {description: Fields accepted by DTS MigrateOption., type: dict, required: true}
  tags: {description: Job tags., type: dict}
  auto_retry_minutes: {description: Automatic retry window in minutes; 0 disables retries., type: int, default: 0}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dts_migration_job_config:
    job_id: dts-abcd1234
    source: {Region: ap-guangzhou, DatabaseType: mysql, InstanceId: cdb-source}
    destination: {Region: ap-shanghai, DatabaseType: mysql, InstanceId: cdb-target}
    migration_options: {MigrateType: fullAndIncrement, Consistency: afterMigration}
"""
RETURN = r"""migration_job: {description: Current DTS migration job detail., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import changed, maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dts.v20211206 import dts_client, models
    return models, dts_client


def describe(module, client, models, job_id):
    request = models.DescribeMigrationDetailRequest()
    request.JobId = job_id
    detail = module.sdk_call(client.DescribeMigrationDetail, request)._serialize(allow_none=True)
    request = models.DescribeMigrationJobsRequest()
    request.JobId, request.Limit, request.Offset = job_id, 1, 0
    response = module.sdk_call(client.DescribeMigrationJobs, request)
    if response.JobList:
        summary = response.JobList[0]._serialize(allow_none=True)
        for key in ("Tags", "AutoRetryTimeRangeMinutes"):
            detail[key] = summary.get(key)
    return detail


def _tags(values):
    return [{"TagKey": str(k), "TagValue": str(v)} for k, v in sorted((values or {}).items())]


def desired(params):
    value = {
        "JobId": params["job_id"], "RunMode": params["run_mode"],
        "SrcInfo": params["source"], "DstInfo": params["destination"],
        "MigrateOption": params["migration_options"],
        "AutoRetryTimeRangeMinutes": params["auto_retry_minutes"],
    }
    if params.get("name") is not None:
        value["JobName"] = params["name"]
    if params.get("expected_run_time") is not None:
        value["ExpectRunTime"] = params["expected_run_time"]
    if params.get("tags") is not None:
        value["Tags"] = _tags(params["tags"])
    return value


def comparable(current, wanted):
    return {key: current.get(key) for key in wanted}


def build_request(models, wanted):
    request = models.ModifyMigrationJobRequest()
    request._deserialize(wanted)
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "job_id": {"required": True}, "name": {},
            "run_mode": {"choices": ["immediate", "timed"], "default": "immediate"},
            "expected_run_time": {},
            "source": {"type": "dict", "required": True, "no_log": True},
            "destination": {"type": "dict", "required": True, "no_log": True},
            "migration_options": {"type": "dict", "required": True},
            "tags": {"type": "dict"},
            "auto_retry_minutes": {"type": "int", "default": 0},
        },
        required_if=[("run_mode", "timed", ["expected_run_time"])],
        supports_check_mode=True,
    )
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.DtsClient, "dts.tencentcloudapi.com")
    try:
        current = describe(module, client, models, module.params["job_id"])
        wanted = desired(module.params)
        before = comparable(current, wanted)
        if not changed(before, wanted):
            module.exit_json(changed=False, migration_job=current)
        if current.get("Status") not in ("created", "checkPass", "checkNotPass", "failed"):
            module.fail_json(msg="DTS migration configuration cannot be changed in the current state",
                             status=current.get("Status"), migration_job=current)
        diff = maybe_diff(module, before, wanted)
        if not module.check_mode:
            module.sdk_call(client.ModifyMigrationJob, build_request(models, wanted))
            current = describe(module, client, models, module.params["job_id"])
        module.exit_json(changed=True, **(diff or {}), migration_job=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
