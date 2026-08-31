#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dlc_work_group_membership
short_description: Manage Tencent Cloud Data Lake Compute work-group members
version_added: "0.14.0"
description: Exactly reconciles the set of DLC users assigned to one work group.
options:
  work_group_id: {type: int, required: true, description: DLC work-group ID.}
  user_ids: {type: list, elements: str, required: true, description: Exact desired set of DLC user IDs or CAM sub-user UINs.}
  allow_empty: {type: bool, default: false, description: Explicitly authorize removing every member from the work group.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between convergence polls.}
  waiter_timeout: {type: int, default: 120, description: Overall convergence timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_work_group_membership:
    work_group_id: 10042
    user_ids: ['100012345678', '100087654321']
'''
RETURN = r'''user_ids: {description: Effective sorted work-group member IDs., type: list, elements: str, returned: always}
added: {description: Member IDs added by this run., type: list, elements: str, returned: always}
removed: {description: Member IDs removed by this run., type: list, elements: str, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state
def _load():
    from tencentcloud.dlc.v20210125 import models,dlc_client
    return models,dlc_client
def describe_request(models,work_group_id): r=models.DescribeWorkGroupsRequest(); r.WorkGroupId,r.Offset,r.Limit=work_group_id,0,100; return r
def current_users(module,client,models,work_group_id):
    response=module.sdk_call(client.DescribeWorkGroups,describe_request(models,work_group_id)); matches=[x for x in response.WorkGroupSet or [] if x.WorkGroupId==work_group_id]
    if not matches: module.fail_json(msg="DLC work group not found",work_group_id=work_group_id)
    if len(matches)>1: module.fail_json(msg="Multiple DLC work groups returned for exact ID",work_group_id=work_group_id)
    return sorted({item.UserId for item in matches[0].UserSet or []})
def membership_request(models,work_group_id,user_ids,add=True):
    info=models.UserIdSetOfWorkGroupId(); info.WorkGroupId,info.UserIds=work_group_id,user_ids
    r=models.AddUsersToWorkGroupRequest() if add else models.DeleteUsersFromWorkGroupRequest(); r.AddInfo=info; return r
def delta(current,target): return sorted(set(target)-set(current)),sorted(set(current)-set(target))
def run_module():
    module=TencentCloudModule(argument_spec={"work_group_id":{"type":"int","required":True},"user_ids":{"type":"list","elements":"str","required":True},"allow_empty":{"type":"bool","default":False}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.DlcClient,"dlc.tencentcloudapi.com")
    try:
        target=sorted(set(p["user_ids"])); current=current_users(module,client,models,p["work_group_id"])
        if not target and not p["allow_empty"]: module.fail_json(msg="set allow_empty=true to authorize removing every DLC work-group member")
        added,removed=delta(current,target)
        if not added and not removed: module.exit_json(changed=False,user_ids=current,added=[],removed=[])
        diff=maybe_diff(module,current,target)
        if not module.check_mode:
            if added: module.sdk_call(client.AddUsersToWorkGroup,membership_request(models,p["work_group_id"],added,True))
            if removed: module.sdk_call(client.DeleteUsersFromWorkGroup,membership_request(models,p["work_group_id"],removed,False))
            wait_for_state(module,lambda:"ready" if current_users(module,client,models,p["work_group_id"])==target else "pending",["ready"],timeout=p["waiter_timeout"],delay=p["waiter_delay"]); current=current_users(module,client,models,p["work_group_id"])
        module.exit_json(changed=True,**(diff or {}),user_ids=current if not module.check_mode else target,added=added,removed=removed)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
