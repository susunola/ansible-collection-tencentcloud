#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: oceanus_folder
short_description: Manage Tencent Cloud Oceanus folders
version_added: "0.14.0"
description: Creates, renames, moves and safely deletes Oceanus job or resource folders inside a workspace.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired folder state.}
  folder_id: {type: str, description: Existing folder ID; required to rename a folder without recreating it.}
  name: {type: str, description: Folder name.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  folder_type: {type: int, choices: [0, 1], required: true, description: Job folder or resource dependency folder.}
  parent_id: {type: str, default: root, description: Desired parent folder ID.}
  allow_delete_nonempty: {type: bool, default: false, description: Explicitly authorize deleting a folder that contains children or resources.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.oceanus_folder:
    name: production-jobs
    workspace_id: space-xxxxxxxx
    folder_type: 0
    parent_id: root
"""
RETURN = r"""folder: {description: Effective folder metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.oceanus.v20190422 import models, oceanus_client

    return models, oceanus_client


def _walk(node):
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("Children") or []:
        for value in _walk(child):
            yield value


def tree(module, client, models, p):
    if p["folder_type"] == 0:
        r = models.DescribeTreeJobsRequest()
        r.WorkSpaceId, r.FlatMode = p["workspace_id"], 0
        response = module.sdk_call(client.DescribeTreeJobs, r)
    else:
        r = models.DescribeTreeResourcesRequest()
        r.WorkSpaceId, r.Offset, r.Limit = p["workspace_id"], 0, 100
        response = module.sdk_call(client.DescribeTreeResources, r)
    return response._serialize(allow_none=True)


def find(module, client, models, p):
    matches = []
    for node in _walk(tree(module, client, models, p)):
        if (p.get("folder_id") and node.get("Id") == p["folder_id"]) or (
            not p.get("folder_id") and node.get("Name") == p.get("name") and node.get("ParentId") == p["parent_id"]
        ):
            matches.append(node)
    if len(matches) > 1:
        module.fail_json(msg="Multiple Oceanus folders matched; specify folder_id")
    return matches[0] if matches else None


def create_request(models, p):
    r = models.CreateFolderRequest()
    r.FolderName, r.ParentId, r.FolderType, r.WorkSpaceId = p["name"], p["parent_id"], p["folder_type"], p["workspace_id"]
    return r


def modify_request(models, p, folder_id):
    r = models.ModifyFolderRequest()
    r.SourceFolderId, r.TargetFolderId, r.FolderName, r.FolderType, r.WorkSpaceId = folder_id, p["parent_id"], p["name"], p["folder_type"], p["workspace_id"]
    return r


def delete_request(models, p, folder_id):
    r = models.DeleteFoldersRequest()
    r.FolderIds, r.FolderType, r.WorkSpaceId = [folder_id], p["folder_type"], p["workspace_id"]
    return r


def nonempty(folder, p):
    return bool(folder.get("Children") or folder.get("JobSet") or folder.get("Items"))


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "folder_id": {},
        "name": {},
        "workspace_id": {"required": True},
        "folder_type": {"type": "int", "choices": [0, 1], "required": True},
        "parent_id": {"default": "root"},
        "allow_delete_nonempty": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("folder_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OceanusClient, "oceanus.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, folder=None)
            if nonempty(current, p) and not p["allow_delete_nonempty"]:
                module.fail_json(msg="Oceanus folder is not empty; set allow_delete_nonempty=true to authorize recursive deletion", folder=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteFolders, delete_request(models, p, current["Id"]))
            module.exit_json(changed=True, **(diff or {}), folder=None)
        if not current:
            if not p.get("name"):
                module.fail_json(msg="name is required to create an Oceanus folder")
            target = {"Name": p["name"], "ParentId": p["parent_id"], "FolderType": p["folder_type"]}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["folder_id"] = module.sdk_call(client.CreateFolder, create_request(models, p)).FolderId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), folder=current if not module.check_mode else target)
        desired = {"Name": p.get("name") or current.get("Name"), "ParentId": p["parent_id"]}
        before = {key: current.get(key) for key in desired}
        if before == desired:
            module.exit_json(changed=False, folder=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            module.sdk_call(client.ModifyFolder, modify_request(models, {**p, "name": desired["Name"]}, current["Id"]))
            p["folder_id"] = current["Id"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), folder=current if not module.check_mode else {**current, **desired})
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
