#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: chdfs_mount_access_groups
short_description: Reconcile CHDFS mount point access-group bindings
version_added: "0.14.0"
description: Reconciles the exact access-group set associated with a CHDFS mount point.
options:
  file_system_id: {type: str, required: true, description: Parent file system ID used to read the mount point.}
  mount_point_id: {type: str, required: true, description: Mount point ID.}
  access_group_ids: {type: list, elements: str, required: true, description: Exact desired access-group ID set.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.chdfs_mount_access_groups:
    file_system_id: f-xxxxxxxx
    mount_point_id: mp-xxxxxxxx
    access_group_ids: [ag-xxxxxxxx]
'''
RETURN = r'''access_group_ids: {description: Effective access-group IDs., type: list, elements: str, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.chdfs.v20201112 import models,chdfs_client
    return models,chdfs_client
def describe_request(models,file_system_id): r=models.DescribeMountPointsRequest(); r.FileSystemId=file_system_id; return r
def associate_request(models,mount_point_id,ids): r=models.AssociateAccessGroupsRequest(); r.MountPointId,r.AccessGroupIds=mount_point_id,ids; return r
def disassociate_request(models,mount_point_id,ids): r=models.DisassociateAccessGroupsRequest(); r.MountPointId,r.AccessGroupIds=mount_point_id,ids; return r
def current_ids(module,client,models,p):
    response=module.sdk_call(client.DescribeMountPoints,describe_request(models,p["file_system_id"])); matches=[x for x in response.MountPoints or [] if x.MountPointId==p["mount_point_id"]]
    if not matches: module.fail_json(msg="CHDFS mount point was not found",mount_point_id=p["mount_point_id"])
    return sorted(matches[0].AccessGroupIds or [])
def run_module():
    module=TencentCloudModule(argument_spec={"file_system_id":{"required":True},"mount_point_id":{"required":True},"access_group_ids":{"type":"list","elements":"str","required":True}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.ChdfsClient,"chdfs.tencentcloudapi.com")
    try:
        target=sorted(set(p["access_group_ids"])); before=current_ids(module,client,models,p)
        if before==target: module.exit_json(changed=False,access_group_ids=before)
        diff=maybe_diff(module,before,target); add=sorted(set(target)-set(before)); remove=sorted(set(before)-set(target))
        if not module.check_mode:
            if remove: module.sdk_call(client.DisassociateAccessGroups,disassociate_request(models,p["mount_point_id"],remove))
            if add: module.sdk_call(client.AssociateAccessGroups,associate_request(models,p["mount_point_id"],add))
            before=current_ids(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),access_group_ids=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
