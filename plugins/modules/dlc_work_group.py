#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dlc_work_group
short_description: Manage Tencent Cloud Data Lake Compute work groups
version_added: "0.14.0"
description:
  - Creates, describes, updates and deletes DLC work groups.
  - Work-group names are immutable; descriptions remain mutable.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired work-group state.}
  work_group_id: {type: int, description: Existing DLC work-group ID.}
  name: {type: str, description: Work-group name.}
  description: {type: str, description: Work-group description.}
  initial_user_ids: {type: list, elements: str, description: Users bound during creation; use C(dlc_work_group_membership) for ongoing exact reconciliation.}
  initial_policies: {type: list, elements: dict, description: SDK Policy objects bound during creation; use C(dlc_work_group_policy) for ongoing exact reconciliation.}
  allow_delete_nonempty: {type: bool, default: false, description: Explicitly authorize deleting a work group that still has users or policies.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between convergence polls.}
  waiter_timeout: {type: int, default: 120, description: Overall convergence timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_work_group:
    name: analytics-engineers
    description: Production lakehouse users

- susunola.tencentcloud.dlc_work_group:
    work_group_id: 10042
    state: absent
    allow_delete_nonempty: true
'''
RETURN = r'''work_group: {description: Effective DLC work-group metadata., type: dict, returned: always}
work_group_id: {description: DLC work-group ID., type: int, returned: when present}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state
def _load():
    from tencentcloud.dlc.v20210125 import models,dlc_client
    return models,dlc_client
def describe_request(models,p,offset=0):
    r=models.DescribeWorkGroupsRequest(); r.Offset,r.Limit=offset,100
    if p.get("work_group_id") is not None: r.WorkGroupId=p["work_group_id"]
    elif p.get("name"): f=models.Filter(); f.Name,f.Values="workgroup-name",[p["name"]]; r.Filters=[f]
    return r
def find(module,client,models,p):
    offset=0; matches=[]
    while True:
        response=module.sdk_call(client.DescribeWorkGroups,describe_request(models,p,offset)); page=response.WorkGroupSet or []
        for item in page:
            value=item._serialize(allow_none=True)
            if (p.get("work_group_id") is not None and value.get("WorkGroupId")==p["work_group_id"]) or (p.get("work_group_id") is None and value.get("WorkGroupName")==p.get("name")): matches.append(value)
        offset+=len(page)
        if not page or offset>=int(response.TotalCount or 0): break
    if len(matches)>1: module.fail_json(msg="Multiple DLC work groups matched; specify work_group_id")
    return matches[0] if matches else None
def create_request(models,p):
    payload={"WorkGroupName":p["name"],"WorkGroupDescription":p.get("description"),"PolicySet":p.get("initial_policies"),"UserIds":p.get("initial_user_ids")}; r=models.CreateWorkGroupRequest(); r.from_json_string(json.dumps(payload)); return r
def modify_request(models,work_group_id,description): r=models.ModifyWorkGroupRequest(); r.WorkGroupId,r.WorkGroupDescription=work_group_id,description; return r
def delete_request(models,work_group_id): r=models.DeleteWorkGroupRequest(); r.WorkGroupIds=[work_group_id]; return r
def wait_group(module,client,models,p,present,description=None):
    def poll():
        current=find(module,client,models,p)
        if not present: return "absent" if current is None else "present"
        if current is None: return "absent"
        return "ready" if description is None or (current.get("WorkGroupDescription") or "")==description else "pending"
    wait_for_state(module,poll,["ready" if present else "absent"],timeout=p["waiter_timeout"],delay=p["waiter_delay"])
def run_module():
    spec={"state":{"choices":["present","absent"],"default":"present"},"work_group_id":{"type":"int"},"name":{},"description":{},"initial_user_ids":{"type":"list","elements":"str"},"initial_policies":{"type":"list","elements":"dict"},"allow_delete_nonempty":{"type":"bool","default":False}}
    module=TencentCloudModule(argument_spec=spec,required_one_of=[("work_group_id","name")],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.DlcClient,"dlc.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,work_group=None,work_group_id=None)
            if (current.get("UserSet") or current.get("PolicySet")) and not p["allow_delete_nonempty"]: module.fail_json(msg="DLC work group still has users or policies; set allow_delete_nonempty=true to authorize deletion",work_group=current)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: p["work_group_id"]=current["WorkGroupId"]; module.sdk_call(client.DeleteWorkGroup,delete_request(models,current["WorkGroupId"])); wait_group(module,client,models,p,False)
            module.exit_json(changed=True,**(diff or {}),work_group=None,work_group_id=None)
        if not current:
            if not p.get("name"): module.fail_json(msg="name is required to create a DLC work group")
            target={"WorkGroupName":p["name"],"WorkGroupDescription":p.get("description") or ""}; diff=maybe_diff(module,None,target)
            if not module.check_mode: p["work_group_id"]=module.sdk_call(client.CreateWorkGroup,create_request(models,p)).WorkGroupId; wait_group(module,client,models,p,True,target["WorkGroupDescription"]); current=find(module,client,models,p)
            module.exit_json(changed=True,**(diff or {}),work_group=current if not module.check_mode else target,work_group_id=p.get("work_group_id"))
        if p.get("name") and current.get("WorkGroupName")!=p["name"]: module.fail_json(msg="DLC work-group name is immutable",immutable_drift={"WorkGroupName":[current.get("WorkGroupName"),p["name"]]})
        desired=p.get("description") if p.get("description") is not None else current.get("WorkGroupDescription"); before=current.get("WorkGroupDescription") or ""; desired=desired or ""
        if before==desired: module.exit_json(changed=False,work_group=current,work_group_id=current["WorkGroupId"])
        diff=maybe_diff(module,{"WorkGroupDescription":before},{"WorkGroupDescription":desired})
        if not module.check_mode: module.sdk_call(client.ModifyWorkGroup,modify_request(models,current["WorkGroupId"],desired)); p["work_group_id"]=current["WorkGroupId"]; wait_group(module,client,models,p,True,desired); current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),work_group=current if not module.check_mode else {**current,"WorkGroupDescription":desired},work_group_id=current["WorkGroupId"])
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
