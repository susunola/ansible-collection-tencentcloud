#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tem_application_service
short_description: Manage Tencent Cloud TEM application access services
version_added: "0.14.0"
description: Creates, updates and deletes a TEM application service access mapping.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  application_id: {type: str, required: true, description: TEM application ID.}
  environment_id: {type: str, required: true, description: TEM environment ID.}
  name: {type: str, required: true, description: Service name.}
  access_type: {type: str, required: true, description: "Access type such as EXTERNAL, VPC or CLUSTER."}
  service: {type: dict, description: "SDK ServicePortMapping payload for ports, subnet and load balancer settings."}
  source_channel: {type: int, default: 0, description: TEM source channel.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tem_application_service:
    application_id: app-xxxxxxxx
    environment_id: en-xxxxxxxx
    name: order-api
    access_type: CLUSTER
    service:
      Ports: [8080]
      PortMappingItemList: [{Port: 80, TargetPort: 8080, Protocol: TCP}]
'''
RETURN = r'''service: {description: Effective TEM service access metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.tem.v20210701 import models,tem_client
    return models,tem_client
def _model(models,value):x=models.ServicePortMapping();x.from_json_string(json.dumps(value));return x
def describe_request(models,p):r=models.DescribeApplicationServiceListRequest();r.EnvironmentId,r.ApplicationId,r.SourceChannel=p["environment_id"],p["application_id"],p["source_channel"];return r
def payload(p):value=dict(p.get("service") or {});value["ServiceName"],value["Type"]=p["name"],p["access_type"];return value
def create_request(models,p):r=models.CreateApplicationServiceRequest();r.ApplicationId,r.EnvironmentId,r.SourceChannel=p["application_id"],p["environment_id"],p["source_channel"];r.Service=_model(models,payload(p));return r
def update_request(models,p):r=models.ModifyApplicationServiceRequest();r.ApplicationId,r.EnvironmentId,r.SourceChannel=p["application_id"],p["environment_id"],p["source_channel"];r.Data=_model(models,payload(p));return r
def delete_request(models,p):r=models.DeleteApplicationServiceRequest();r.ApplicationId,r.EnvironmentId,r.ServiceName,r.SourceChannel=p["application_id"],p["environment_id"],p["name"],p["source_channel"];return r
def describe(module,client,models,p):
    result=module.sdk_call(client.DescribeApplicationServiceList,describe_request(models,p)).Result
    items=(result.ServicePortMappingList if result else None) or []
    matches=[]
    for item in items:
        value=item._serialize(allow_none=True)
        if value.get("ServiceName")==p["name"] and value.get("Type")==p["access_type"]:matches.append(value)
    if len(matches)>1:module.fail_json(msg="Multiple TEM application service mappings matched",name=p["name"],access_type=p["access_type"])
    return matches[0] if matches else None
def contains(actual,expected):
    if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(contains(a,e) for a,e in zip(actual,expected))
    return actual==expected
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"application_id":{"required":True},"environment_id":{"required":True},"name":{"required":True},"access_type":{"required":True},"service":{"type":"dict"},"source_channel":{"type":"int","default":0}},supports_check_mode=True);p=module.params;module.require_sdk();models,cm=_load();client=module.create_client(cm.TemClient,"tem.tencentcloudapi.com")
    try:
        current=describe(module,client,models,p)
        if p["state"]=="absent":
            if not current:module.exit_json(changed=False,service=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode:module.sdk_call(client.DeleteApplicationService,delete_request(models,p))
            module.exit_json(changed=True,**(diff or {}),service=None)
        target=payload(p)
        if current and contains(current,target):module.exit_json(changed=False,service=current)
        diff=maybe_diff(module,current,target)
        if not module.check_mode:module.sdk_call(client.ModifyApplicationService if current else client.CreateApplicationService,update_request(models,p) if current else create_request(models,p));current=describe(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),service=current if not module.check_mode else target)
    except Exception as exc:module.fail_json(**sdk_error_payload(exc))
def main():run_module()
if __name__=="__main__":main()
