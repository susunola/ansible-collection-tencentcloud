#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dts_migration_job
short_description: Manage Tencent Cloud DTS migration jobs
version_added: "0.14.0"
description: Purchases, renames, resizes and destroys DTS migration jobs.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  job_id: {description: Existing migration job ID., type: str}
  name: {description: Migration job name., type: str}
  source_database_type: {description: Source database engine used at creation., type: str}
  destination_database_type: {description: Destination database engine used at creation., type: str}
  source_region: {description: Source Tencent Cloud region., type: str}
  destination_region: {description: Destination Tencent Cloud region., type: str}
  instance_class: {description: DTS migration instance class., type: str, default: micro}
  tags: {description: Tags applied at creation., type: dict, default: {}}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dts_migration_job:
    name: mysql-migration
    source_database_type: mysql
    destination_database_type: mysql
    source_region: ap-guangzhou
    destination_region: ap-shanghai
    instance_class: small
"""
RETURN = r"""migration_job: {description: DTS migration job metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dts.v20211206 import dts_client, models

    return models, dts_client


def describe_request(models, job_id=None, name=None, offset=0):
    request = models.DescribeMigrationJobsRequest()
    request.JobId, request.JobName, request.Offset, request.Limit = job_id, name, offset, 100
    return request


def find(module, client, models, job_id, name):
    offset, matches = 0, []
    while job_id or name:
        response = module.sdk_call(client.DescribeMigrationJobs, describe_request(models, job_id, name, offset))
        items = list(response.JobList or [])
        matches.extend(x._serialize(allow_none=True) for x in items if (job_id and x.JobId == job_id) or (not job_id and x.JobName == name))
        offset += len(items)
        if job_id or not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DTS migration jobs have the requested name", name=name)
    return matches[0] if matches else None


def tag_list(models, values):
    result = []
    for key, value in sorted(values.items()):
        tag = models.TagItem()
        tag.TagKey, tag.TagValue = str(key), str(value)
        result.append(tag)
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "job_id": {},
            "name": {},
            "source_database_type": {},
            "destination_database_type": {},
            "source_region": {},
            "destination_region": {},
            "instance_class": {"default": "micro"},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("job_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.DtsClient, "dts.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["job_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, migration_job=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DestroyMigrateJobRequest()
                request.JobId = current["JobId"]
                module.sdk_call(client.DestroyMigrateJob, request)
            module.exit_json(changed=True, **(diff or {}), migration_job=current if module.check_mode else None)
        if current is None:
            required = ["name", "source_database_type", "destination_database_type", "source_region", "destination_region"]
            missing = [key for key in required if not p[key]]
            if missing:
                module.fail_json(msg="Creation parameters are required", missing=missing)
            wanted = {"JobName": p["name"], "InstanceClass": p["instance_class"]}
            diff = maybe_diff(module, None, wanted)
            if not module.check_mode:
                request = models.CreateMigrationServiceRequest()
                request.SrcDatabaseType, request.DstDatabaseType = p["source_database_type"], p["destination_database_type"]
                request.SrcRegion, request.DstRegion = p["source_region"], p["destination_region"]
                request.InstanceClass, request.Count, request.JobName = p["instance_class"], 1, p["name"]
                request.Tags = tag_list(models, p["tags"])
                job_id = module.sdk_call(client.CreateMigrationService, request).JobIds[0]
                current = find(module, client, models, job_id, None)
            module.exit_json(changed=True, **(diff or {}), migration_job=current)
        changes = {}
        if p["name"] and current.get("JobName") != p["name"]:
            changes["JobName"] = p["name"]
        trade = current.get("TradeInfo") or {}
        if p["instance_class"] and trade.get("InstanceClass") and trade.get("InstanceClass") != p["instance_class"]:
            changes["InstanceClass"] = p["instance_class"]
        if not changes:
            module.exit_json(changed=False, migration_job=current)
        diff = maybe_diff(module, current, changes)
        if not module.check_mode:
            if "JobName" in changes:
                request = models.ModifyMigrateNameRequest()
                request.JobId, request.JobName = current["JobId"], p["name"]
                module.sdk_call(client.ModifyMigrateName, request)
            if "InstanceClass" in changes:
                request = models.ModifyMigrateJobSpecRequest()
                request.JobId, request.NewInstanceClass = current["JobId"], p["instance_class"]
                module.sdk_call(client.ModifyMigrateJobSpec, request)
            current = find(module, client, models, current["JobId"], None)
        module.exit_json(changed=True, **(diff or {}), migration_job=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
