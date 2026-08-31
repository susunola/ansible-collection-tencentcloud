#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_route
short_description: Manage a Tencent Cloud TSE gateway route
version_added: "0.14.0"
description: Creates, updates and deletes an instance-unique cloud-native API gateway route.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  service_id: {type: str, description: Owning gateway service ID; required when present.}
  route_id: {type: str, description: Existing route ID.}
  name: {type: str, required: true, description: Instance-unique route name.}
  methods: {type: list, elements: str, description: Accepted HTTP methods.}
  hosts: {type: list, elements: str, description: Accepted host names.}
  paths: {type: list, elements: str, description: Accepted paths.}
  protocols: {type: list, elements: str, description: Accepted protocols.}
  preserve_host: {type: bool, description: Preserve the incoming Host header.}
  https_redirect_status_code: {type: int, description: HTTPS redirect status code.}
  strip_path: {type: bool, description: Strip the matched path before forwarding.}
  force_https: {type: bool, description: Force HTTPS.}
  destination_ports: {type: list, elements: int, description: Layer-4 destination ports.}
  headers: {type: list, elements: dict, description: SDK KVMapping header matchers.}
  request_buffering: {type: bool, description: Buffer request bodies.}
  response_buffering: {type: bool, description: Buffer response bodies.}
  regex_priority: {type: int, description: Regular-expression route priority.}
  query_string_parameters: {type: list, elements: dict, description: SDK KVMapping query matchers.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_route:
    gateway_id: gateway-xxxxxxxx
    service_id: service-xxxxxxxx
    name: orders-api
    methods: [GET, POST]
    paths: [/orders]
    protocols: [https]
    strip_path: true
'''
RETURN = r'''route: {description: Effective gateway route metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def list_request(models,p): r=models.DescribeCloudNativeAPIGatewayRoutesRequest(); r.GatewayId,r.RouteName,r.Offset,r.Limit=p["gateway_id"],p["name"],0,1000; return r
def write_request(cls,payload): r=cls(); r.from_json_string(json.dumps(payload)); return r
def delete_request(models,p,current): r=models.DeleteCloudNativeAPIGatewayRouteRequest(); r.GatewayId,r.Name=p["gateway_id"],current.get("ID") or p["name"]; return r
def find(module,client,models,p):
    result=module.sdk_call(client.DescribeCloudNativeAPIGatewayRoutes,list_request(models,p)).Result; groups=result.RouteList if result else []; matches=[]
    for group in groups or []:
        for item in group.Routes or []:
            value=item._serialize(allow_none=True)
            if (p.get("route_id") and value.get("ID")==p["route_id"]) or (not p.get("route_id") and value.get("Name")==p["name"]): matches.append(value)
    if len(matches)>1: module.fail_json(msg="Multiple TSE gateway routes matched; specify route_id")
    return matches[0] if matches else None
def desired(p):
    mapping={"methods":"Methods","hosts":"Hosts","paths":"Paths","protocols":"Protocols","preserve_host":"PreserveHost","https_redirect_status_code":"HttpsRedirectStatusCode","strip_path":"StripPath","force_https":"ForceHttps","destination_ports":"DestinationPorts","headers":"Headers","request_buffering":"RequestBuffering","response_buffering":"ResponseBuffering","regex_priority":"RegexPriority","query_string_parameters":"QueryStringParameters"}; value={"Name":p["name"],"ServiceID":p["service_id"]}
    for source,target in mapping.items():
        if p.get(source) is not None: value[target]=p[source]
    return value
def contains(actual,expected):
    if isinstance(expected,dict): return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    return actual==expected


def run_module():
    spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"service_id":{"required":True},"route_id":{},"name":{"required":True},"methods":{"type":"list","elements":"str"},"hosts":{"type":"list","elements":"str"},"paths":{"type":"list","elements":"str"},"protocols":{"type":"list","elements":"str"},"preserve_host":{"type":"bool"},"https_redirect_status_code":{"type":"int"},"strip_path":{"type":"bool"},"force_https":{"type":"bool"},"destination_ports":{"type":"list","elements":"int"},"headers":{"type":"list","elements":"dict"},"request_buffering":{"type":"bool"},"response_buffering":{"type":"bool"},"regex_priority":{"type":"int"},"query_string_parameters":{"type":"list","elements":"dict"}}
    spec["service_id"].pop("required",None)
    module=TencentCloudModule(argument_spec=spec,required_if=[("state","present",("service_id",))],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,route=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode: module.sdk_call(client.DeleteCloudNativeAPIGatewayRoute,delete_request(models,p,current))
            module.exit_json(changed=True,**(diff or {}),route=None)
        target=desired(p)
        if not any(p.get(key) for key in ("methods","hosts","paths","destination_ports")): module.fail_json(msg="At least one route matcher is required: methods, hosts, paths or destination_ports")
        if current and contains(current,target): module.exit_json(changed=False,route=current)
        diff=maybe_diff(module,current,target)
        if not module.check_mode:
            keys=("Methods","Hosts","Paths","Protocols","PreserveHost","HttpsRedirectStatusCode","StripPath","ForceHttps","DestinationPorts","Headers","RequestBuffering","ResponseBuffering","RegexPriority","QueryStringParameters"); payload={"GatewayId":p["gateway_id"],"ServiceID":p["service_id"],"RouteName":p["name"]}
            source=dict(current or {},**target)
            for key in keys:
                if key in source: payload[key]=source[key]
            if current: payload["RouteID"]=current["ID"]
            api=client.ModifyCloudNativeAPIGatewayRoute if current else client.CreateCloudNativeAPIGatewayRoute; cls=models.ModifyCloudNativeAPIGatewayRouteRequest if current else models.CreateCloudNativeAPIGatewayRouteRequest
            module.sdk_call(api,write_request(cls,payload)); current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),route=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
