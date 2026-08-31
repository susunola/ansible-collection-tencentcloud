#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dts_migration_check
short_description: Run and wait for a Tencent Cloud DTS migration check
version_added: "0.14.0"
description: Starts a DTS pre-migration check when needed and waits for a conclusive result.
options:
  job_id: {description: DTS migration job ID., type: str, required: true}
  wait: {description: Wait for the check to finish., type: bool, default: true}
  fail_on_check_error: {description: Fail when DTS reports a failed or non-passing check., type: bool, default: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""- susunola.tencentcloud.dts_migration_check: {job_id: dts-abcd1234}"""
RETURN = r"""migration_check: {description: DTS check status and step details., type: dict, returned: always}"""

import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dts.v20211206 import dts_client, models
    return models, dts_client


def describe(module, client, models, job_id):
    request = models.DescribeMigrationCheckJobRequest(); request.JobId = job_id
    return module.sdk_call(client.DescribeMigrationCheckJob, request)._serialize(allow_none=True)


def start(module, client, models, job_id):
    request = models.CreateMigrateCheckJobRequest(); request.JobId = job_id
    module.sdk_call(client.CreateMigrateCheckJob, request)


def wait_check(module, client, models, job_id):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        result = describe(module, client, models, job_id)
        if result.get("Status") in ("success", "failed"):
            return result
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for DTS migration check", migration_check=result)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={"job_id": {"required": True}, "wait": {"type": "bool", "default": True},
                       "fail_on_check_error": {"type": "bool", "default": True}},
        supports_check_mode=True,
    )
    module.require_sdk(); models, client_module = _load()
    client = module.create_client(client_module.DtsClient, "dts.tencentcloudapi.com")
    try:
        result = describe(module, client, models, module.params["job_id"])
        should_start = result.get("Status") in (None, "notStarted", "failed") or result.get("CheckFlag") == "checkNotPass"
        if should_start and not module.check_mode:
            start(module, client, models, module.params["job_id"])
            result = wait_check(module, client, models, module.params["job_id"]) if module.params["wait"] else describe(module, client, models, module.params["job_id"])
        elif result.get("Status") == "running" and module.params["wait"] and not module.check_mode:
            result = wait_check(module, client, models, module.params["job_id"])
        if module.params["fail_on_check_error"] and not module.check_mode and result.get("Status") in ("success", "failed") and result.get("CheckFlag") != "checkPass":
            module.fail_json(msg="DTS migration check did not pass", migration_check=result)
        module.exit_json(changed=should_start, migration_check=result)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
