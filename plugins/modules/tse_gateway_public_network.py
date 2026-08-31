#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_public_network
short_description: Manage a Tencent Cloud TSE gateway public network
version_added: "0.14.0"
description: Creates, updates and deletes a gateway-group public CLB and reconciles its access-control policy.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  group_id: {type: str, description: Native gateway server group ID.}
  group_name: {type: str, description: Native gateway server group name resolved within the gateway.}
  network_id: {type: str, description: Existing public network ID.}
  config: {type: dict, description: SDK InternetConfig payload used for creation and mutable CLB fields.}
  access_control: {type: dict, description: Exact SDK NetworkAccessControl payload.}
  address_version: {type: str, choices: [IPV4, IPV6], default: IPV4, description: Public address family used for deletion.}
  vip: {type: str, description: Public VIP; required by the API when a group has multiple public networks.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 600, description: Convergence timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_public_network:
    gateway_id: gateway-xxxxxxxx
    group_name: production-secondary
    config:
      InternetAddressVersion: IPV4
      InternetPayMode: BANDWIDTH
      InternetMaxBandwidthOut: 20
      Description: Production ingress
    access_control:
      Mode: Whitelist
      CidrWhiteList: [203.0.113.0/24]
'''
RETURN = r'''public_network: {description: Effective public network metadata., type: dict, returned: always}'''
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def group_request(models,p):
    r=models.DescribeNativeGatewayServerGroupsRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],0,100; f=models.Filter(); f.Name,f.Values="Name",[p["group_name"]]; r.Filters=[f]; return r
def resolve_group(module,client,models,p):
    if p.get("group_id"): return
    result=module.sdk_call(client.DescribeNativeGatewayServerGroups,group_request(models,p)).Result; matches=[]
    for item in (result.GatewayGroupList if result else []) or []:
        value=item._serialize(allow_none=True)
        if value.get("Name")==p["group_name"]: matches.append(value.get("GroupId"))
    if not matches: module.fail_json(msg="TSE gateway group name was not found",group_name=p["group_name"])
    if len(matches)>1: module.fail_json(msg="Multiple TSE gateway groups matched the name",group_name=p["group_name"])
    p["group_id"]=matches[0]
def describe_request(models,p): r=models.DescribePublicNetworkRequest(); r.GatewayId,r.GroupId,r.NetworkId=p["gateway_id"],p["group_id"],p.get("network_id"); return r
def create_request(models,p):
    r=models.CreateCloudNativeAPIGatewayPublicNetworkRequest(); r.from_json_string(json.dumps({"GatewayId":p["gateway_id"],"GroupId":p["group_id"],"InternetConfig":p["config"]})); return r
def delete_request(models,p,current): r=models.DeleteCloudNativeAPIGatewayPublicNetworkRequest(); r.GatewayId,r.GroupId,r.InternetAddressVersion,r.Vip=p["gateway_id"],p["group_id"],p["address_version"],p.get("vip") or current.get("Vip"); return r
def basic_request(models,p,current,target): r=models.ModifyNetworkBasicInfoRequest(); r.GatewayId,r.GroupId,r.NetworkType,r.Vip=p["gateway_id"],p["group_id"],"Public",current.get("Vip"); r.InternetMaxBandwidthOut,r.Description,r.SlaType=target.get("InternetMaxBandwidthOut"),target.get("Description"),target.get("SlaType"); return r
def access_request(models,p,current,target):
    r=models.ModifyNetworkAccessStrategyRequest(); r.GatewayId,r.GroupId,r.NetworkType,r.Vip=p["gateway_id"],p["group_id"],"Public",current.get("Vip"); value=models.NetworkAccessControl(); value.from_json_string(json.dumps(target)); r.AccessControl=value; return r
def current(module,client,models,p):
    try:
        result=module.sdk_call(client.DescribePublicNetwork,describe_request(models,p)).Result; value=result.PublicNetwork if result else None
        return value._serialize(allow_none=True) if value else None
    except Exception as exc:
        code=str(exc.get_code() if hasattr(exc,"get_code") else "")
        if "notfound" in code.lower() or "notexist" in code.lower(): return None
        raise
def contains(actual,expected):
    if isinstance(expected,dict): return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list): return sorted(actual or [])==sorted(expected)
    return actual==expected
def desired(p):
    config=p.get("config") or {}; keys=("InternetMaxBandwidthOut","Description","SlaType","MultiZoneFlag","MasterZoneId","SlaveZoneId"); value={k:config[k] for k in keys if k in config}
    if p.get("access_control") is not None: value["AccessControl"]=p["access_control"]
    return value
def wait(module,client,models,p,target,absent=False):
    deadline=time.time()+p["waiter_timeout"]
    while True:
        value=current(module,client,models,p)
        if absent and not value: return None
        if not absent and value and str(value.get("Status") or "").lower() in ("open","running") and contains(value,target): return value
        if value and str(value.get("Status") or "").lower() in ("failed","createfailed"): module.fail_json(msg="TSE public network operation failed",public_network=value)
        if time.time()>=deadline: module.fail_json(msg="Timed out waiting for TSE public network convergence",public_network=value,expected=target)
        time.sleep(p["waiter_delay"])


def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"group_id":{},"group_name":{},"network_id":{},"config":{"type":"dict"},"access_control":{"type":"dict"},"address_version":{"choices":["IPV4","IPV6"],"default":"IPV4"},"vip":{}},required_one_of=[("group_id","group_name")],mutually_exclusive=[("group_id","group_name")],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        resolve_group(module,client,models,p)
        before=current(module,client,models,p)
        if p["state"]=="absent":
            if not before: module.exit_json(changed=False,public_network=None)
            diff=maybe_diff(module,before,None)
            if not module.check_mode: module.sdk_call(client.DeleteCloudNativeAPIGatewayPublicNetwork,delete_request(models,p,before)); before=wait(module,client,models,p,{},absent=True)
            module.exit_json(changed=True,**(diff or {}),public_network=None)
        target=desired(p)
        if not before and not p.get("config"): module.fail_json(msg="config is required for a new TSE gateway public network")
        if before and contains(before,target): module.exit_json(changed=False,public_network=before)
        if before:
            immutable={k:(before.get(k),v) for k,v in target.items() if k in ("MultiZoneFlag","MasterZoneId","SlaveZoneId") and not contains(before.get(k),v)}
            if immutable: module.fail_json(msg="TSE public network zone topology is immutable",immutable_drift=immutable)
        diff=maybe_diff(module,before,target)
        if not module.check_mode:
            if not before:
                response=module.sdk_call(client.CreateCloudNativeAPIGatewayPublicNetwork,create_request(models,p)); p["network_id"]=response.Result.NetworkId; before=wait(module,client,models,p,{k:v for k,v in target.items() if k!="AccessControl"})
            basic={k:v for k,v in target.items() if k in ("InternetMaxBandwidthOut","Description","SlaType")}
            if basic and not contains(before,basic): module.sdk_call(client.ModifyNetworkBasicInfo,basic_request(models,p,before,basic))
            if "AccessControl" in target and not contains(before.get("AccessControl"),target["AccessControl"]): module.sdk_call(client.ModifyNetworkAccessStrategy,access_request(models,p,before,target["AccessControl"]))
            before=wait(module,client,models,p,target)
        module.exit_json(changed=True,**(diff or {}),public_network=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
