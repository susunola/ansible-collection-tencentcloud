#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__=type
DOCUMENTATION = r'''
---
module: monitor_grafana_instance
short_description: Manage Tencent Cloud Managed Grafana instances
version_added: "0.14.0"
description: Creates, renames and deletes a Managed Grafana instance.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing Grafana instance ID.}
  name: {type: str, description: Instance name.}
  vpc_id: {type: str, description: VPC ID used at creation.}
  subnet_ids: {type: list, elements: str, default: [], description: Subnet IDs used at creation.}
  enable_internet: {type: bool, default: false, description: Enable internet access at creation.}
  initial_password: {type: str, description: Initial Grafana administrator password.}
  tags: {type: dict, default: {}, description: Instance tags.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_grafana_instance:
    name: production-dashboards
    vpc_id: vpc-xxxxxxxx
    subnet_ids: [subnet-xxxxxxxx]
'''
RETURN = r'''instance: {description: Managed Grafana instance metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.monitor.v20180724 import models,monitor_client
    return models,monitor_client
def _tags(models,values):
    out=[]
    for k,v in sorted(values.items()): x=models.PrometheusTag(); x.Key,x.Value=str(k),str(v); out.append(x)
    return out
def build_describe(models,iid=None,name=None): request=models.DescribeGrafanaInstancesRequest(); request.InstanceIds=[iid] if iid else None; request.InstanceName=name; request.Offset,request.Limit=0,100; return request
def build_create(models,p): request=models.CreateGrafanaInstanceRequest(); request.InstanceName,request.VpcId,request.SubnetIds=p["name"],p["vpc_id"],p["subnet_ids"]; request.EnableInternet,request.GrafanaInitPassword=p["enable_internet"],p.get("initial_password"); request.TagSpecification=_tags(models,p["tags"]); return request
def build_update(models,iid,name): request=models.ModifyGrafanaInstanceRequest(); request.InstanceId,request.InstanceName=iid,name; return request
def build_delete(models,iid): request=models.DeleteGrafanaInstanceRequest(); request.InstanceIDs=[iid]; return request
def find(module,client,models,iid,name):
    response=module.sdk_call(client.DescribeGrafanaInstances,build_describe(models,iid,name)); items=list(response.InstanceSet or response.Instances or []); matches=[x._serialize(allow_none=True) for x in items if (iid and x.InstanceId==iid) or (not iid and x.InstanceName==name)]
    if len(matches)>1: module.fail_json(msg="Multiple Grafana instances have the requested name",name=name)
    return matches[0] if matches else None
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"instance_id":{},"name":{},"vpc_id":{},"subnet_ids":{"type":"list","elements":"str","default":[]},"enable_internet":{"type":"bool","default":False},"initial_password":{"no_log":True},"tags":{"type":"dict","default":{}}},required_one_of=[("instance_id","name")],supports_check_mode=True); p=module.params
    if p["state"]=="present" and not p["name"]: module.fail_json(msg="name is required when state=present")
    module.require_sdk(); models,cm=_load(); client=module.create_client(cm.MonitorClient,"monitor.tencentcloudapi.com")
    try:
        current=find(module,client,models,p["instance_id"],p["name"])
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,instance=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: module.sdk_call(client.DeleteGrafanaInstance,build_delete(models,current["InstanceId"]))
            module.exit_json(changed=True,**(diff or {}),instance=current if module.check_mode else None)
        if current and current.get("InstanceName")==p["name"]: module.exit_json(changed=False,instance=current)
        if not current and (not p["vpc_id"] or not p["subnet_ids"]): module.fail_json(msg="vpc_id and subnet_ids are required when creating")
        target={"InstanceName":p["name"]}; diff=maybe_diff(module,{"InstanceName":current.get("InstanceName")} if current else None,target)
        if not module.check_mode:
            if current: module.sdk_call(client.ModifyGrafanaInstance,build_update(models,current["InstanceId"],p["name"])); iid=current["InstanceId"]
            else: iid=module.sdk_call(client.CreateGrafanaInstance,build_create(models,p)).InstanceId
            current=find(module,client,models,iid,None)
        module.exit_json(changed=True,**(diff or {}),instance=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
