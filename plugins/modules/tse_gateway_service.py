#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_service
short_description: Manage a Tencent Cloud TSE gateway upstream service
version_added: "0.14.0"
description: Creates, updates and deletes a cloud-native API gateway service using its instance-unique name.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  service_id: {type: str, description: Existing service ID.}
  name: {type: str, required: true, description: Service name.}
  protocol: {type: str, description: Backend protocol.}
  timeout: {type: int, description: Backend timeout in milliseconds.}
  retries_count: {type: int, description: Backend retry count.}
  upstream_type: {type: str, description: Backend service type.}
  upstream_info: {type: dict, description: SDK KongUpstreamInfo payload.}
  path: {type: str, description: Backend request path.}
  delete_routes: {type: bool, default: false, description: Delete bound routes together with the service.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_service:
    gateway_id: gateway-xxxxxxxx
    name: orders
    protocol: http
    timeout: 30000
    retries_count: 2
    upstream_type: IPList
    upstream_info:
      Targets:
        - {Host: 10.0.0.10, Port: 8080, Weight: 100}
'''
RETURN = r'''service: {description: Effective gateway service metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def list_request(models,p):
    r=models.DescribeCloudNativeAPIGatewayServicesRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],0,100
    f=models.ListFilter(); f.Key,f.Value="name",p["name"]; r.Filters=[f]; return r
def detail_request(models,p): r=models.DescribeOneCloudNativeAPIGatewayServiceRequest(); r.GatewayId,r.ServiceName=p["gateway_id"],p["service_id"] or p["name"]; return r
def write_request(cls,p,payload): r=cls(); r.from_json_string(json.dumps(payload)); return r
def delete_request(models,p,current): r=models.DeleteCloudNativeAPIGatewayServiceRequest(); r.GatewayId,r.Name,r.DeleteRoutes=p["gateway_id"],current.get("ID") or p["name"],p["delete_routes"]; return r
def find(module,client,models,p):
    result=module.sdk_call(client.DescribeCloudNativeAPIGatewayServices,list_request(models,p)).Result; values=result.ServiceList if result else []; matches=[]
    for item in values or []:
        value=item._serialize(allow_none=True)
        if (p.get("service_id") and value.get("ID")==p["service_id"]) or (not p.get("service_id") and value.get("Name")==p["name"]): matches.append(value)
    if len(matches)>1: module.fail_json(msg="Multiple TSE gateway services matched; specify service_id")
    if not matches: return None
    local=dict(p); local["service_id"]=matches[0].get("ID"); detail=module.sdk_call(client.DescribeOneCloudNativeAPIGatewayService,detail_request(models,local)).Result
    return detail._serialize(allow_none=True) if detail else matches[0]
def desired(p):
    mapping={"protocol":"Protocol","timeout":"Timeout","retries_count":"Retries","upstream_type":"UpstreamType","upstream_info":"UpstreamInfo","path":"Path"}; value={"Name":p["name"]}
    for source,target in mapping.items():
        if p.get(source) is not None: value[target]=p[source]
    return value
def contains(actual,expected):
    if isinstance(expected,dict): return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list): return actual==expected
    return actual==expected


def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"service_id":{},"name":{"required":True},"protocol":{},"timeout":{"type":"int"},"retries_count":{"type":"int"},"upstream_type":{},"upstream_info":{"type":"dict"},"path":{},"delete_routes":{"type":"bool","default":False}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,service=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: module.sdk_call(client.DeleteCloudNativeAPIGatewayService,delete_request(models,p,current))
            module.exit_json(changed=True,**(diff or {}),service=None)
        target=desired(p)
        if not current:
            missing=[k for k in ("protocol","timeout","retries_count","upstream_type","upstream_info") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a TSE gateway service",missing=missing)
        if current and contains(current,target): module.exit_json(changed=False,service=current)
        diff=maybe_diff(module,current,target)
        if not module.check_mode:
            payload={"GatewayId":p["gateway_id"],**{k:v for k,v in dict(current or {},**target).items() if k in ("Name","Protocol","Timeout","Retries","UpstreamType","UpstreamInfo","Path")}}
            if current: payload["ID"]=current["ID"]
            api=client.ModifyCloudNativeAPIGatewayService if current else client.CreateCloudNativeAPIGatewayService; cls=models.ModifyCloudNativeAPIGatewayServiceRequest if current else models.CreateCloudNativeAPIGatewayServiceRequest
            module.sdk_call(api,write_request(cls,p,payload)); current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),service=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
