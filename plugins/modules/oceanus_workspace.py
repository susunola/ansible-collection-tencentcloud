#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_workspace
short_description: Manage Tencent Cloud Oceanus workspaces
version_added: "0.14.0"
description: Creates, renames, describes and deletes Oceanus workspaces, the ownership boundary for jobs, resources and variables.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  workspace_id: {type: str, description: Existing workspace ID.}
  name: {type: str, description: Workspace name.}
  description: {type: str, description: Workspace description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_workspace:
    name: production-streaming
    description: Production Flink jobs and resources
"""
RETURN = r"""workspace: {description: Effective Oceanus workspace metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def describe_request(models, p, offset=0):
    r = models.DescribeWorkSpacesRequest()
    r.Offset, r.Limit = offset, 100
    if p.get("workspace_id") or p.get("name"):
        f = models.Filter()
        f.Name, f.Values = ("WorkSpaceId", [p["workspace_id"]]) if p.get("workspace_id") else ("WorkSpaceName", [p["name"]])
        r.Filters = [f]
    return r


def create_request(models, p):
    r = models.CreateWorkSpaceRequest()
    r.WorkSpaceName, r.Description = p["name"], p.get("description")
    return r


def modify_request(models, workspace_id, name, description):
    r = models.ModifyWorkSpaceRequest()
    r.WorkSpaceId, r.WorkSpaceName, r.Description = workspace_id, name, description
    return r


def delete_request(models, workspace_id):
    r = models.DeleteWorkSpaceRequest()
    r.WorkSpaceId = workspace_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeWorkSpaces, describe_request(models, p))
    matches = []
    for item in response.WorkSpaceSetItem or []:
        value = item._serialize(allow_none=True)
        if (p.get("workspace_id") and value.get("WorkSpaceId") == p["workspace_id"]) or (
            not p.get("workspace_id") and value.get("WorkSpaceName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple Oceanus workspaces matched; specify workspace_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "workspace_id": {}, "name": {}, "description": {}},
        required_one_of=[("workspace_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, workspace=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteWorkSpace, delete_request(models, current["WorkSpaceId"]))
            module.exit_json(changed=True, **(diff or {}), workspace=None)
        if not current:
            if not p.get("name"):
                module.fail_json(msg="name is required to create an Oceanus workspace")
            target = {"WorkSpaceName": p["name"], "Description": p.get("description") or ""}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["workspace_id"] = module.sdk_call(client.CreateWorkSpace, create_request(models, p)).WorkSpaceId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), workspace=current if not module.check_mode else target)
        desired = {
            "WorkSpaceName": p.get("name") or current.get("WorkSpaceName"),
            "Description": p.get("description") if p.get("description") is not None else current.get("Description"),
        }
        before = {k: current.get(k) for k in desired}
        if before == desired:
            module.exit_json(changed=False, workspace=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            module.sdk_call(client.ModifyWorkSpace, modify_request(models, current["WorkSpaceId"], desired["WorkSpaceName"], desired["Description"]))
            p["workspace_id"] = current["WorkSpaceId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), workspace=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
