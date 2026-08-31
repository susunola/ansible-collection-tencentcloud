#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tsf_vm_deployment_group
short_description: Manage a Tencent Cloud TSF virtual-machine deployment group
version_added: "0.15.0"
description: Creates, updates and deletes a TSF virtual-machine deployment group without conflating package deployment or runtime state.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  group_id: {type: str, description: Existing deployment group ID; scoped exact name is used when omitted.}
  name: {type: str, required: true, description: Deployment group name.}
  application_id: {type: str, required: true, description: Owning TSF application ID.}
  namespace_id: {type: str, required: true, description: Owning TSF namespace ID.}
  cluster_id: {type: str, required: true, description: Owning TSF cluster ID.}
  description: {type: str, description: Deployment group description.}
  alias: {type: str, description: Deployment group display remark.}
  resource_type: {type: str, choices: [DEF], default: DEF, description: Deployment group resource type, immutable after creation.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tsf_vm_deployment_group:
    name: orders-production
    application_id: application-xxxxxxxx
    namespace_id: namespace-xxxxxxxx
    cluster_id: cluster-xxxxxxxx
    description: Production VM group
'''
RETURN = r'''deployment_group: {description: Effective VM deployment group metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload

def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client
    return models, tsf_client
def _ser(x): return x._serialize(allow_none=True) if x is not None else None
def find(module,client,models,p):
    r=models.DescribeGroupsRequest(); r.ApplicationId=p["application_id"]; r.NamespaceId=p["namespace_id"]; r.ClusterId=p["cluster_id"]; r.Offset,r.Limit=0,50
    if p.get("group_id"): r.GroupIdList=[p["group_id"]]
    else: r.SearchWord=p["name"]
    result=module.sdk_call(client.DescribeGroups,r).Result
    values=[_ser(x) for x in ((result.Content if result else None) or [])]
    if p.get("group_id"): matches=[x for x in values if x.get("GroupId")==p["group_id"]]
    else: matches=[x for x in values if x.get("GroupName")==p["name"] and x.get("ApplicationId")==p["application_id"] and x.get("NamespaceId")==p["namespace_id"] and x.get("ClusterId")==p["cluster_id"]]
    if len(matches)>1: module.fail_json(msg="Multiple TSF VM deployment groups matched",name=p["name"])
    return matches[0] if matches else None
def desired(p):
    mapping={"name":"GroupName","application_id":"ApplicationId","namespace_id":"NamespaceId","cluster_id":"ClusterId","description":"GroupDesc","alias":"Alias","resource_type":"GroupResourceType"}
    return {b:p[a] for a,b in mapping.items() if p.get(a) is not None}
def comparable(current,target): return {k:current.get(k) for k in target}
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"group_id":{},"name":{"required":True},"application_id":{"required":True},"namespace_id":{"required":True},"cluster_id":{"required":True},"description":{},"alias":{},"resource_type":{"choices":["DEF"],"default":"DEF"}},supports_check_mode=True)
    p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TsfClient,"tsf.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,deployment_group=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode:
                r=models.DeleteGroupRequest(); r.GroupId=current["GroupId"]; response=module.sdk_call(client.DeleteGroup,r)
                if response.Result is False: module.fail_json(msg="Tencent Cloud rejected the TSF VM deployment group deletion",request_id=response.RequestId)
            module.exit_json(changed=True,**(diff or {}),deployment_group=None)
        target=desired(p)
        if current: require_immutable_unchanged(module,current,target,["ApplicationId","NamespaceId","ClusterId","GroupResourceType"],"TSF VM deployment group")
        if current and comparable(current,target)==target: module.exit_json(changed=False,deployment_group=current)
        diff=maybe_diff(module,comparable(current,target) if current else None,target)
        if not module.check_mode:
            if current:
                r=models.ModifyGroupRequest(); r.GroupId=current["GroupId"]
                for key in ("GroupName","GroupDesc","Alias"):
                    if key in target: setattr(r,key,target[key])
                response=module.sdk_call(client.ModifyGroup,r)
                if response.Result is False: module.fail_json(msg="Tencent Cloud rejected the TSF VM deployment group update",request_id=response.RequestId)
                p["group_id"]=current["GroupId"]
            else:
                r=models.CreateGroupRequest()
                for key,value in target.items(): setattr(r,key,value)
                p["group_id"]=module.sdk_call(client.CreateGroup,r).Result
            current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),deployment_group=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
