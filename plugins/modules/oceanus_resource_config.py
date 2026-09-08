#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_resource_config
short_description: Manage Tencent Cloud Oceanus resource versions
version_added: "0.14.0"
description:
  - Publishes an immutable resource version only when its managed content differs from the latest version.
  - Deletion is blocked while a job configuration references the selected version unless explicitly authorized.
options:
  state: {type: str, choices: [present, absent], default: present, description: Ensure the desired latest version or remove a historical version.}
  resource_id: {type: str, required: true, description: Oceanus resource ID.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  version: {type: int, description: Resource version required for deletion.}
  resource_location: {type: dict, description: SDK ResourceLoc containing the version artifact location.}
  remark: {type: str, description: Version description.}
  auto_delete_oldest: {type: bool, default: false, description: Automatically delete the earliest deletable version at the service limit.}
  allow_delete_in_use: {type: bool, default: false, description: Explicitly authorize deleting a version referenced by job configurations.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_resource_config:
    resource_id: resource-xxxxxxxx
    workspace_id: space-xxxxxxxx
    resource_location:
      StorageType: 1
      Param: {Bucket: flink-artifacts-1250000000, Path: jars/orders-1.1.jar, Region: ap-guangzhou}
    remark: release-1.1
"""
RETURN = r"""resource_config: {description: Effective immutable resource version., type: dict, returned: always}
version: {description: Effective resource version number., type: int, returned: when present}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def _model(cls, value):
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def desired(p):
    value = {"ResourceLoc": p["resource_location"]}
    if p.get("remark") is not None:
        value["Remark"] = p["remark"]
    return value


def managed_value(current, target):
    if isinstance(target, dict):
        current = current if isinstance(current, dict) else {}
        return {key: managed_value(current.get(key), value) for key, value in target.items()}
    if isinstance(target, list):
        current = current if isinstance(current, list) else []
        return [managed_value(current[index] if index < len(current) else None, value) for index, value in enumerate(target)]
    return current


def describe(module, client, models, p, version=None):
    offset = 0
    values = []
    while True:
        r = models.DescribeResourceConfigsRequest()
        r.ResourceId, r.WorkSpaceId, r.Offset, r.Limit = p["resource_id"], p["workspace_id"], offset, 100
        if version is not None:
            r.ResourceConfigVersions = [version]
        response = module.sdk_call(client.DescribeResourceConfigs, r)
        page = response.ResourceConfigSet or []
        values.extend(x._serialize(allow_none=True) for x in page)
        offset += len(page)
        if version is not None or not page or offset >= int(response.TotalCount or 0):
            break
    if version is not None:
        return next((x for x in values if x.get("Version") == version), None)
    return max(values, key=lambda x: x.get("Version", -1)) if values else None


def references(module, client, models, p, version):
    offset = 0
    result = []
    while True:
        r = models.DescribeResourceRelatedJobsRequest()
        r.ResourceId, r.ResourceConfigVersion, r.WorkSpaceId = p["resource_id"], version, p["workspace_id"]
        r.Offset, r.Limit = offset, 100
        response = module.sdk_call(client.DescribeResourceRelatedJobs, r)
        page = response.RefJobInfos or []
        result.extend(x._serialize(allow_none=True) for x in page)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    return result


def create_request(models, p):
    r = models.CreateResourceConfigRequest()
    r.ResourceId, r.WorkSpaceId = p["resource_id"], p["workspace_id"]
    r.ResourceLoc = _model(models.ResourceLoc, p["resource_location"])
    r.Remark = p.get("remark")
    r.AutoDelete = 1 if p["auto_delete_oldest"] else 0
    return r


def delete_request(models, p):
    r = models.DeleteResourceConfigsRequest()
    r.ResourceId, r.WorkSpaceId = p["resource_id"], p["workspace_id"]
    r.ResourceConfigVersions = [p["version"]]
    return r


def wait_config(module, client, models, p, version, present):
    def poll():
        current = describe(module, client, models, p, version)
        if not present:
            return "absent" if current is None else "present"
        return "ready" if current is not None and current.get("Status") in (None, 1) else "pending"

    wait_for_state(module, poll, ["ready" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "resource_id": {"required": True},
        "workspace_id": {"required": True},
        "version": {"type": "int"},
        "resource_location": {"type": "dict"},
        "remark": {},
        "auto_delete_oldest": {"type": "bool", "default": False},
        "allow_delete_in_use": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(
        argument_spec=spec, required_if=[("state", "present", ["resource_location"]), ("state", "absent", ["version"])], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        if p["state"] == "absent":
            current = describe(module, client, models, p, p["version"])
            if not current:
                module.exit_json(changed=False, resource_config=None)
            refs = references(module, client, models, p, p["version"])
            if refs and not p["allow_delete_in_use"]:
                module.fail_json(
                    msg="Oceanus resource version is referenced by job configurations; set allow_delete_in_use=true to authorize deletion",
                    version=p["version"],
                    references=refs,
                )
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteResourceConfigs, delete_request(models, p))
                wait_config(module, client, models, p, p["version"], False)
            module.exit_json(changed=True, **(diff or {}), resource_config=None)
        target = desired(p)
        current = describe(module, client, models, p)
        before = managed_value(current, target) if current else None
        if before == target:
            module.exit_json(changed=False, resource_config=current, version=current.get("Version"))
        diff = maybe_diff(module, before, target)
        version = None
        if not module.check_mode:
            version = module.sdk_call(client.CreateResourceConfig, create_request(models, p)).Version
            wait_config(module, client, models, p, version, True)
            current = describe(module, client, models, p, version)
        module.exit_json(changed=True, **(diff or {}), resource_config=current if not module.check_mode else target, version=version)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
