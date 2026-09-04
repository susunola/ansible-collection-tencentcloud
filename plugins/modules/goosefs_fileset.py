#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: goosefs_fileset
short_description: Manage Tencent Cloud GooseFS filesets
version_added: "0.14.0"
description: Creates, updates and deletes GooseFS filesets and their quota limits.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  file_system_id: {type: str, required: true, description: GooseFS file system ID.}
  fileset_id: {type: str, description: Existing fileset ID.}
  name: {type: str, description: Fileset name and immutable after creation.}
  directory: {type: str, description: Fileset directory and immutable after creation.}
  quota_size_limit: {type: str, description: "Capacity quota in bytes; represented as a decimal string by the SDK."}
  quota_files_limit: {type: str, description: "File-count quota; represented as a decimal string by the SDK."}
  audit_state: {type: str, description: Audit state.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.goosefs_fileset:
    file_system_id: x-c60-xxxxxxxx
    name: analytics
    directory: /analytics
    quota_size_limit: '1099511627776'
    quota_files_limit: '1000000'
"""
RETURN = r"""fileset: {description: Effective GooseFS fileset metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.goosefs.v20220519 import models, goosefs_client

    return models, goosefs_client


def describe_request(models, p):
    r = models.DescribeFilesetsRequest()
    r.FileSystemId = p["file_system_id"]
    if p.get("fileset_id"):
        r.FilesetIds = [p["fileset_id"]]
    elif p.get("directory"):
        r.FilesetDirs = [p["directory"]]
    return r


def create_request(models, p):
    r = models.CreateFilesetRequest()
    r.FileSystemId, r.FsetName, r.FsetDir = p["file_system_id"], p["name"], p["directory"]
    r.QuotaSizeLimit, r.QuotaFilesLimit, r.AuditState = p.get("quota_size_limit"), p.get("quota_files_limit"), p.get("audit_state")
    return r


def update_request(models, p, fileset_id):
    r = models.UpdateFilesetRequest()
    r.FileSystemId, r.FsetId = p["file_system_id"], fileset_id
    r.QuotaSizeLimit, r.QuotaFilesLimit, r.AuditState = p.get("quota_size_limit"), p.get("quota_files_limit"), p.get("audit_state")
    return r


def delete_request(models, p, fileset_id):
    r = models.DeleteFilesetRequest()
    r.FileSystemId, r.FsetId = p["file_system_id"], fileset_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeFilesets, describe_request(models, p))
    matches = []
    for item in response.FilesetList or []:
        value = item._serialize(allow_none=True)
        if (p.get("fileset_id") and value.get("FsetId") == p["fileset_id"]) or (
            not p.get("fileset_id")
            and ((p.get("directory") and value.get("FsetDir") == p["directory"]) or (not p.get("directory") and value.get("FsetName") == p.get("name")))
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple GooseFS filesets matched; specify fileset_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "FsetName": v.get("FsetName"),
        "FsetDir": v.get("FsetDir"),
        "QuotaSizeLimit": v.get("QuotaSizeLimit"),
        "QuotaFilesLimit": v.get("QuotaFilesLimit"),
        "AuditState": v.get("AuditState"),
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "file_system_id": {"required": True},
        "fileset_id": {},
        "name": {},
        "directory": {},
        "quota_size_limit": {},
        "quota_files_limit": {},
        "audit_state": {},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("fileset_id", "name", "directory")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GoosefsClient, "goosefs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, fileset=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteFileset, delete_request(models, p, current["FsetId"]))
            module.exit_json(changed=True, **(diff or {}), fileset=None)
        if not current:
            missing = [k for k in ("name", "directory") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a GooseFS fileset", missing=missing)
        before = comparable(current) if current else None
        old = before or {}
        target = {
            "FsetName": p.get("name") or old.get("FsetName"),
            "FsetDir": p.get("directory") or old.get("FsetDir"),
            "QuotaSizeLimit": p.get("quota_size_limit") if p.get("quota_size_limit") is not None else old.get("QuotaSizeLimit"),
            "QuotaFilesLimit": p.get("quota_files_limit") if p.get("quota_files_limit") is not None else old.get("QuotaFilesLimit"),
            "AuditState": p.get("audit_state") if p.get("audit_state") is not None else old.get("AuditState"),
        }
        if before == target:
            module.exit_json(changed=False, fileset=current)
        if current:
            require_immutable_unchanged(module, before, target, ("FsetName", "FsetDir"), "GooseFS fileset")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            effective.update(
                {
                    "name": target["FsetName"],
                    "directory": target["FsetDir"],
                    "quota_size_limit": target["QuotaSizeLimit"],
                    "quota_files_limit": target["QuotaFilesLimit"],
                    "audit_state": target["AuditState"],
                }
            )
            response = module.sdk_call(
                client.UpdateFileset if current else client.CreateFileset,
                update_request(models, effective, current["FsetId"]) if current else create_request(models, effective),
            )
            p["fileset_id"] = current["FsetId"] if current else response.FsetId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), fileset=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
