#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tsf_container_deployment_group
short_description: Manage a Tencent Cloud TSF container deployment group
version_added: "0.15.0"
description: Manages container group identity, replicas, resources, service exposure and rolling-update settings separately from image deployment and runtime start or stop actions.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  group_id: {type: str, description: Existing group ID; scoped exact name is used when omitted.}
  name: {type: str, required: true, description: Deployment group name.}
  application_id: {type: str, required: true, description: Owning application ID.}
  namespace_id: {type: str, required: true, description: Owning namespace ID.}
  cluster_id: {type: str, required: true, description: Owning container cluster ID.}
  replicas: {type: int, description: Desired replica count; required when state is present.}
  cpu_request: {type: str, description: Requested application CPU cores, immutable after creation.}
  cpu_limit: {type: str, description: Application CPU limit, immutable after creation.}
  memory_request: {type: str, description: Requested application memory in MiB, immutable after creation.}
  memory_limit: {type: str, description: Application memory limit in MiB, immutable after creation.}
  access_type: {type: int, choices: [0, 1, 2], default: 1, description: Service access type; public, cluster internal or NodePort.}
  protocol_ports:
    type: list
    elements: dict
    description: Exact service port definitions.
    suboptions:
      protocol: {type: str, choices: [TCP, UDP], required: true}
      port: {type: int, required: true}
      target_port: {type: int, required: true}
      node_port: {type: int}
      name: {type: str}
  update_type: {type: int, choices: [0, 1], default: 0, description: Fast or rolling update strategy.}
  update_interval: {type: int, description: Rolling update interval in seconds.}
  subnet_id: {type: str, description: Service subnet ID.}
  alias: {type: str, description: Deployment group remark.}
  resource_type: {type: str, choices: [DEF], default: DEF, description: Resource type, immutable after creation.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tsf_container_deployment_group:
    name: orders-production
    application_id: application-xxxxxxxx
    namespace_id: namespace-xxxxxxxx
    cluster_id: cluster-xxxxxxxx
    replicas: 3
    cpu_request: '0.5'
    cpu_limit: '1'
    memory_request: '512'
    memory_limit: '1024'
    protocol_ports: [{protocol: TCP, port: 80, target_port: 8080, name: http}]
'''
RETURN = r'''deployment_group: {description: Effective container deployment group metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload

def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client
    return models, tsf_client
def _ser(x): return x._serialize(allow_none=True) if x is not None else None
def _ports(values):
    result=[]
    for value in values or []:
        result.append({k:value.get(k) for k in ("Protocol","Port","TargetPort","NodePort","Name") if value.get(k) is not None})
    return sorted(result,key=lambda x:(x.get("Name") or "",x.get("Port") or 0,x.get("TargetPort") or 0))
def _port_models(models,values):
    result=[]
    for value in values or []:
        item=models.ProtocolPort(); item.from_json_string(json.dumps({"Protocol":value["protocol"],"Port":value["port"],"TargetPort":value["target_port"],"NodePort":value.get("node_port"),"Name":value.get("name")})); result.append(item)
    return result
def find(module,client,models,p):
    r=models.DescribeContainerGroupsRequest(); r.ApplicationId=p["application_id"]; r.NamespaceId=p["namespace_id"]; r.ClusterId=p["cluster_id"]; r.Offset,r.Limit=0,50
    if p.get("group_id"): r.GroupIdList=[p["group_id"]]
    else: r.SearchWord=p["name"]
    result=module.sdk_call(client.DescribeContainerGroups,r).Result
    values=((result.Content if result else None) or [])
    matches=[x for x in values if x.GroupId==p.get("group_id")] if p.get("group_id") else [x for x in values if x.GroupName==p["name"] and x.NamespaceId==p["namespace_id"] and x.ClusterId==p["cluster_id"]]
    if len(matches)>1: module.fail_json(msg="Multiple TSF container deployment groups matched",name=p["name"])
    if not matches: return None
    detail=models.DescribeContainerGroupDetailRequest(); detail.GroupId=matches[0].GroupId
    return _ser(module.sdk_call(client.DescribeContainerGroupDetail,detail).Result)
def desired(p):
    mapping={"name":"GroupName","application_id":"ApplicationId","namespace_id":"NamespaceId","cluster_id":"ClusterId","replicas":"InstanceNum","cpu_request":"CpuRequest","cpu_limit":"CpuLimit","memory_request":"MemRequest","memory_limit":"MemLimit","access_type":"AccessType","update_type":"UpdateType","update_interval":"UpdateIvl","subnet_id":"SubnetId","alias":"Alias","resource_type":"GroupResourceType"}
    target={b:p[a] for a,b in mapping.items() if p.get(a) is not None}
    if p.get("protocol_ports") is not None: target["ProtocolPorts"]=_ports([{"Protocol":x["protocol"],"Port":x["port"],"TargetPort":x["target_port"],"NodePort":x.get("node_port"),"Name":x.get("name")} for x in p["protocol_ports"]])
    return target
def comparable(current,target):
    result={k:current.get(k) for k in target}
    if "ProtocolPorts" in result: result["ProtocolPorts"]=_ports(result["ProtocolPorts"])
    return result
def run_module():
    port={"protocol":{"choices":["TCP","UDP"],"required":True},"port":{"type":"int","required":True},"target_port":{"type":"int","required":True},"node_port":{"type":"int"},"name":{}}
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"group_id":{},"name":{"required":True},"application_id":{"required":True},"namespace_id":{"required":True},"cluster_id":{"required":True},"replicas":{"type":"int"},"cpu_request":{},"cpu_limit":{},"memory_request":{},"memory_limit":{},"access_type":{"type":"int","choices":[0,1,2],"default":1},"protocol_ports":{"type":"list","elements":"dict","options":port},"update_type":{"type":"int","choices":[0,1],"default":0},"update_interval":{"type":"int"},"subnet_id":{},"alias":{},"resource_type":{"choices":["DEF"],"default":"DEF"}},supports_check_mode=True)
    p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TsfClient,"tsf.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,deployment_group=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode:
                r=models.DeleteContainerGroupRequest(); r.GroupId=current["GroupId"]; response=module.sdk_call(client.DeleteContainerGroup,r)
                if response.Result is False: module.fail_json(msg="Tencent Cloud rejected the TSF container deployment group deletion",request_id=response.RequestId)
            module.exit_json(changed=True,**(diff or {}),deployment_group=None)
        if p.get("replicas") is None: module.fail_json(msg="replicas is required when state is present")
        if p["update_type"]==1 and p.get("update_interval") is None: module.fail_json(msg="update_interval is required for rolling updates")
        target=desired(p)
        immutable=["GroupName","ApplicationId","NamespaceId","ClusterId","CpuRequest","CpuLimit","MemRequest","MemLimit","GroupResourceType"]
        if current: require_immutable_unchanged(module,current,target,immutable,"TSF container deployment group")
        if current and comparable(current,target)==target: module.exit_json(changed=False,deployment_group=current)
        diff=maybe_diff(module,comparable(current,target) if current else None,target)
        if not module.check_mode:
            if current:
                mutable=("AccessType","ProtocolPorts","UpdateType","UpdateIvl","SubnetId","Alias")
                if any(comparable(current,target).get(k)!=target.get(k) for k in mutable if k in target):
                    r=models.ModifyContainerGroupRequest(); r.GroupId=current["GroupId"]
                    for key in mutable:
                        if key in target: setattr(r,key,_port_models(models,p["protocol_ports"]) if key=="ProtocolPorts" else target[key])
                    response=module.sdk_call(client.ModifyContainerGroup,r)
                    if response.Result is False: module.fail_json(msg="Tencent Cloud rejected the TSF container group update",request_id=response.RequestId)
                if current.get("InstanceNum")!=target["InstanceNum"]:
                    r=models.ModifyContainerReplicasRequest(); r.GroupId=current["GroupId"]; r.InstanceNum=target["InstanceNum"]; response=module.sdk_call(client.ModifyContainerReplicas,r)
                    if response.Result is False: module.fail_json(msg="Tencent Cloud rejected the TSF replica change",request_id=response.RequestId)
                p["group_id"]=current["GroupId"]
            else:
                r=models.CreateContainGroupRequest()
                create_map={"GroupName":"GroupName","ApplicationId":"ApplicationId","NamespaceId":"NamespaceId","ClusterId":"ClusterId","InstanceNum":"InstanceNum","CpuRequest":"CpuRequest","CpuLimit":"CpuLimit","MemRequest":"MemRequest","MemLimit":"MemLimit","AccessType":"AccessType","UpdateType":"UpdateType","UpdateIvl":"UpdateIvl","SubnetId":"SubnetId","Alias":"GroupComment","GroupResourceType":"GroupResourceType"}
                for source,dest in create_map.items():
                    if source in target: setattr(r,dest,target[source])
                if p.get("protocol_ports") is not None: r.ProtocolPorts=_port_models(models,p["protocol_ports"])
                p["group_id"]=module.sdk_call(client.CreateContainGroup,r).Result
            current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),deployment_group=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
