#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: oceanus_resource
short_description: Manage Tencent Cloud Oceanus resources
version_added: "0.14.0"
description:
  - Creates and deletes a named workspace resource and its initial immutable version.
  - Deletion is blocked while any job configuration references the resource unless explicitly authorized.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  resource_id: {type: str, description: Existing resource ID.}
  name: {type: str, description: Resource name.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  resource_type: {type: int, choices: [1], default: 1, description: Resource type; currently JAR.}
  resource_location: {type: dict, description: Initial SDK ResourceLoc containing COS storage location.}
  remark: {type: str, description: Resource description.}
  version_remark: {type: str, description: Initial version description.}
  folder_id: {type: str, default: root, description: Resource folder ID.}
  allow_delete_in_use: {type: bool, default: false, description: Explicitly authorize deleting a resource referenced by job configurations.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.oceanus_resource:
    name: orders-processor
    workspace_id: space-xxxxxxxx
    resource_location:
      StorageType: 1
      Param: {Bucket: flink-artifacts-1250000000, Path: jars/orders-1.0.jar, Region: ap-guangzhou}
'''
RETURN = r'''resource: {description: Effective Oceanus resource metadata., type: dict, returned: always}
version: {description: Initial resource version., type: int, returned: when created}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.oceanus.v20190422 import models,oceanus_client
    return models,oceanus_client
def _model(cls,value): x=cls(); x.from_json_string(json.dumps(value)); return x
def describe_request(models,p,offset=0):
    r=models.DescribeResourcesRequest(); r.Offset,r.Limit,r.WorkSpaceId,r.SystemResource=offset,100,p["workspace_id"],0
    if p.get("resource_id"): r.ResourceIds=[p["resource_id"]]
    elif p.get("name"): f=models.Filter(); f.Name,f.Values="ResourceName",[p["name"]]; r.Filters=[f]
    return r
def find(module,client,models,p):
    offset=0; matches=[]
    while True:
        response=module.sdk_call(client.DescribeResources,describe_request(models,p,offset)); page=response.ResourceSet or []
        for item in page:
            value=item._serialize(allow_none=True)
            if (p.get("resource_id") and value.get("ResourceId")==p["resource_id"]) or (not p.get("resource_id") and value.get("Name")==p.get("name")): matches.append(value)
        offset+=len(page)
        if not page or offset>=int(response.TotalCount or 0): break
    if len(matches)>1: module.fail_json(msg="Multiple Oceanus resources matched; specify resource_id")
    return matches[0] if matches else None
def references(module,client,models,p,resource_id):
    offset=0; result=[]
    while True:
        r=models.DescribeResourceRelatedJobsRequest(); r.ResourceId,r.WorkSpaceId,r.Offset,r.Limit=resource_id,p["workspace_id"],offset,100
        response=module.sdk_call(client.DescribeResourceRelatedJobs,r); page=response.RefJobInfos or []; result.extend(x._serialize(allow_none=True) for x in page); offset+=len(page)
        if not page or offset>=int(response.TotalCount or 0): break
    return result
def create_request(models,p):
    r=models.CreateResourceRequest(); r.ResourceLoc=_model(models.ResourceLoc,p["resource_location"]); r.ResourceType=p["resource_type"]; r.Remark,r.Name=p.get("remark"),p["name"]; r.ResourceConfigRemark=p.get("version_remark"); r.FolderId,r.WorkSpaceId=p["folder_id"],p["workspace_id"]; return r
def delete_request(models,p,resource_id): r=models.DeleteResourcesRequest(); r.ResourceIds=[resource_id]; r.WorkSpaceId=p["workspace_id"]; return r
def run_module():
    spec={"state":{"choices":["present","absent"],"default":"present"},"resource_id":{},"name":{},"workspace_id":{"required":True},"resource_type":{"type":"int","choices":[1],"default":1},"resource_location":{"type":"dict"},"remark":{},"version_remark":{},"folder_id":{"default":"root"},"allow_delete_in_use":{"type":"bool","default":False}}
    module=TencentCloudModule(argument_spec=spec,required_one_of=[("resource_id","name")],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.OceanusClient,"oceanus.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,resource=None)
            refs=references(module,client,models,p,current["ResourceId"])
            if refs and not p["allow_delete_in_use"]: module.fail_json(msg="Oceanus resource is referenced by job configurations; set allow_delete_in_use=true to authorize deletion",references=refs)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: module.sdk_call(client.DeleteResources,delete_request(models,p,current["ResourceId"]))
            module.exit_json(changed=True,**(diff or {}),resource=None)
        if not current:
            missing=[x for x in ("name","resource_location") if p.get(x) is None]
            if missing: module.fail_json(msg="name and resource_location are required to create an Oceanus resource",missing=missing)
            target={"Name":p["name"],"ResourceType":p["resource_type"],"ResourceLoc":p["resource_location"]}; diff=maybe_diff(module,None,target); version=None
            if not module.check_mode:
                response=module.sdk_call(client.CreateResource,create_request(models,p)); p["resource_id"],version=response.ResourceId,response.Version; current=find(module,client,models,p)
            module.exit_json(changed=True,**(diff or {}),resource=current if not module.check_mode else target,version=version)
        drift={}
        if p.get("name") and current.get("Name")!=p["name"]: drift["Name"]=(current.get("Name"),p["name"])
        if p.get("resource_type") is not None and current.get("ResourceType")!=p["resource_type"]: drift["ResourceType"]=(current.get("ResourceType"),p["resource_type"])
        if drift: module.fail_json(msg="Oceanus resource name and type are immutable",immutable_drift=drift)
        module.exit_json(changed=False,resource=current,version=current.get("LatestResourceConfigVersion"))
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
