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
  targets: {type: list, elements: dict, description: Authoritative SDK KongTarget list reconciled independently after service creation.}
  health_check_config: {type: dict, description: Authoritative SDK UpstreamHealthCheckConfig payload.}
  path: {type: str, description: Backend request path.}
  delete_routes: {type: bool, default: false, description: Delete bound routes together with the service.}
  waiter_delay: {type: int, default: 3, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 180, description: Reconciliation timeout.}
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
    targets:
      - {Host: 10.0.0.10, Port: 8080, Weight: 100}
    health_check_config:
      EnableActiveHealthCheck: true
      ActiveHealthCheck: {HealthyInterval: 5, UnhealthyInterval: 5, HttpPath: /healthz}
'''
RETURN = r'''service: {description: Effective gateway service metadata., type: dict, returned: always}'''
import json
import time
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
def health_detail_request(models,p,name): r=models.DescribeUpstreamHealthCheckConfigRequest(); r.GatewayId,r.Name=p["gateway_id"],name; return r
def targets_request(models,p,name,targets): return write_request(models.UpdateUpstreamTargetsRequest,p,{"GatewayId":p["gateway_id"],"Name":name,"Targets":targets})
def health_update_request(models,p,name,config): return write_request(models.UpdateUpstreamHealthCheckConfigRequest,p,{"GatewayId":p["gateway_id"],"Name":name,"HealthCheckConfig":config})
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
def targets_match(actual,expected):
    return len(actual or [])==len(expected or []) and all(any(contains(candidate,item) for candidate in actual or []) for item in expected or [])
def auxiliary_state(module,client,models,p,current):
    result={}
    if p.get("targets") is not None: result["Targets"]=((current.get("UpstreamInfo") or {}).get("Targets") or [])
    if p.get("health_check_config") is not None:
        response=module.sdk_call(client.DescribeUpstreamHealthCheckConfig,health_detail_request(models,p,current.get("Name") or p["name"])); value=response.Result
        result["HealthCheckConfig"]=value._serialize(allow_none=True) if value else None
    return result
def auxiliary_matches(value,p):
    return (p.get("targets") is None or targets_match(value.get("Targets"),p["targets"])) and (p.get("health_check_config") is None or contains(value.get("HealthCheckConfig"),p["health_check_config"]))
def wait_auxiliary(module,client,models,p,current):
    deadline=time.time()+p["waiter_timeout"]
    while True:
        value=find(module,client,models,p) or current; value.update(auxiliary_state(module,client,models,p,value))
        if auxiliary_matches(value,p): return value
        if time.time()>=deadline: module.fail_json(msg="Timed out waiting for TSE gateway upstream convergence",service=value)
        time.sleep(p["waiter_delay"])
def require_success(module,response,operation):
    if getattr(response,"Result",None) is not True: module.fail_json(msg="TSE gateway upstream operation returned an unsuccessful result",operation=operation)


def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"service_id":{},"name":{"required":True},"protocol":{},"timeout":{"type":"int"},"retries_count":{"type":"int"},"upstream_type":{},"upstream_info":{"type":"dict"},"targets":{"type":"list","elements":"dict"},"health_check_config":{"type":"dict"},"path":{},"delete_routes":{"type":"bool","default":False},"waiter_delay":{"type":"int","default":3},"waiter_timeout":{"type":"int","default":180}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,service=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: module.sdk_call(client.DeleteCloudNativeAPIGatewayService,delete_request(models,p,current))
            module.exit_json(changed=True,**(diff or {}),service=None)
        target=desired(p); existed=current is not None
        if not current:
            missing=[k for k in ("protocol","timeout","retries_count","upstream_type","upstream_info") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a TSE gateway service",missing=missing)
        auxiliary=auxiliary_state(module,client,models,p,current) if current else {}
        core_changed=not current or not contains(current,target)
        targets_changed=p.get("targets") is not None and not targets_match(auxiliary.get("Targets"),p["targets"])
        health_changed=p.get("health_check_config") is not None and not contains(auxiliary.get("HealthCheckConfig"),p["health_check_config"])
        effective=dict(current or {}); effective.update(auxiliary)
        expected=dict(target)
        if p.get("targets") is not None: expected["Targets"]=p["targets"]
        if p.get("health_check_config") is not None: expected["HealthCheckConfig"]=p["health_check_config"]
        if not core_changed and not targets_changed and not health_changed: module.exit_json(changed=False,service=effective)
        diff=maybe_diff(module,effective or None,expected)
        if not module.check_mode:
            if core_changed:
                payload={"GatewayId":p["gateway_id"],**{k:v for k,v in dict(current or {},**target).items() if k in ("Name","Protocol","Timeout","Retries","UpstreamType","UpstreamInfo","Path")}}
                if existed: payload["ID"]=current["ID"]
                api=client.ModifyCloudNativeAPIGatewayService if existed else client.CreateCloudNativeAPIGatewayService; cls=models.ModifyCloudNativeAPIGatewayServiceRequest if existed else models.CreateCloudNativeAPIGatewayServiceRequest
                module.sdk_call(api,write_request(cls,p,payload)); current=find(module,client,models,p)
            resource_name=(current or {}).get("Name") or p["name"]
            if targets_changed: require_success(module,module.sdk_call(client.UpdateUpstreamTargets,targets_request(models,p,resource_name,p["targets"])),"UpdateUpstreamTargets")
            if health_changed: require_success(module,module.sdk_call(client.UpdateUpstreamHealthCheckConfig,health_update_request(models,p,resource_name,p["health_check_config"])),"UpdateUpstreamHealthCheckConfig")
            current=wait_auxiliary(module,client,models,p,current)
        module.exit_json(changed=True,**(diff or {}),service=current if not module.check_mode else expected)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
