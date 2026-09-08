#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dts_migration_action
short_description: Control a Tencent Cloud DTS migration job
version_added: "0.14.0"
description: Starts, pauses, resumes, stops or completes a DTS migration job with state-aware idempotency.
options:
  job_id: {description: DTS migration job ID., type: str, required: true}
  action: {description: Desired operation., type: str, required: true, choices: [start, pause, resume, stop, complete]}
  resume_option: {description: Resume mode., type: str, choices: [normal, clearData, overwrite], default: normal}
  complete_mode: {description: Completion mode for supported legacy MySQL jobs., type: str, choices: [waitForSync, immediately], default: waitForSync}
  confirm_impact: {description: Explicitly authorize stop or complete operations., type: bool, default: false}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""- susunola.tencentcloud.dts_migration_action: {job_id: dts-abcd1234, action: start}"""
RETURN = r"""migration_job: {description: DTS migration job detail after the operation., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

DONE = {
    "start": {"running", "readyComplete", "success"},
    "pause": {"pausing", "manualPaused"},
    "resume": {"running", "readyComplete", "success"},
    "stop": {"stopping", "success"},
    "complete": {"completing", "success"},
}
VALID_FROM = {
    "start": {"checkPass", "readyRun"},
    "pause": {"running", "readyComplete"},
    "resume": {"manualPaused", "resumableErr", "failed"},
    "stop": {"checking", "checkPass", "checkNotPass", "readyRun", "running", "readyComplete", "failed", "manualPaused", "resumableErr"},
    "complete": {"readyComplete"},
}


def _load():
    from tencentcloud.dts.v20211206 import dts_client, models

    return models, dts_client


def describe(module, client, models, job_id):
    request = models.DescribeMigrationDetailRequest()
    request.JobId = job_id
    return module.sdk_call(client.DescribeMigrationDetail, request)._serialize(allow_none=True)


def execute(module, client, models, params):
    action = params["action"]
    cls_name = {
        "start": "StartMigrateJobRequest",
        "pause": "PauseMigrateJobRequest",
        "resume": "ResumeMigrateJobRequest",
        "stop": "StopMigrateJobRequest",
        "complete": "CompleteMigrateJobRequest",
    }[action]
    request = getattr(models, cls_name)()
    request.JobId = params["job_id"]
    if action == "resume":
        request.ResumeOption = params["resume_option"]
    if action == "complete":
        request.CompleteMode = params["complete_mode"]
    if action == "start":
        module.sdk_call(client.StartMigrateJob, request)
    elif action == "pause":
        module.sdk_call(client.PauseMigrateJob, request)
    elif action == "resume":
        module.sdk_call(client.ResumeMigrateJob, request)
    elif action == "stop":
        module.sdk_call(client.StopMigrateJob, request)
    else:
        module.sdk_call(client.CompleteMigrateJob, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "job_id": {"required": True},
            "action": {"required": True, "choices": list(DONE)},
            "resume_option": {"choices": ["normal", "clearData", "overwrite"], "default": "normal"},
            "complete_mode": {"choices": ["waitForSync", "immediately"], "default": "waitForSync"},
            "confirm_impact": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.DtsClient, "dts.tencentcloudapi.com")
    try:
        current = describe(module, client, models, module.params["job_id"])
        action, status = module.params["action"], current.get("Status")
        if status in DONE[action]:
            module.exit_json(changed=False, migration_job=current)
        if action in ("stop", "complete") and not module.params["confirm_impact"]:
            module.fail_json(msg="confirm_impact=true is required for DTS %s" % action, migration_job=current)
        if status not in VALID_FROM[action]:
            module.fail_json(msg="DTS %s is not valid in state %s" % (action, status), valid_states=sorted(VALID_FROM[action]), migration_job=current)
        if not module.check_mode:
            execute(module, client, models, module.params)
            current = describe(module, client, models, module.params["job_id"])
        module.exit_json(changed=True, migration_job=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
