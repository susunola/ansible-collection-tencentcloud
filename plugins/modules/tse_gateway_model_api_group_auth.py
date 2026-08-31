#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_model_api_group_auth
short_description: Manage TSE gateway Model API consumer group authorization
version_added: "0.14.0"
description: Reconciles Model API authorization using ConsumerGroupModelScopes readback and delta-based mutations.
options:
  state: {type: str, choices: [present, absent], default: present, description: Whether every listed group is authorized.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  model_api_id: {type: str, description: Model API ID.}
  model_api_name: {type: str, description: Model API name resolved within the gateway.}
  consumer_group_ids: {type: list, elements: str, description: Unique consumer group IDs, one through ten entries.}
  consumer_group_names: {type: list, elements: str, description: Unique consumer group names resolved within the gateway.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_model_api_group_auth:
    gateway_id: gateway-xxxxxxxx
    model_api_name: chat-completions
    consumer_group_names: [trusted-clients]
'''
RETURN = r'''authorization: {description: Model API and effective consumer group authorization., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def detail_request(models,p):
    r=models.DescribeCloudNativeAPIGatewayLLMModelAPIRequest(); r.GatewayId,r.ModelAPIId=p["gateway_id"],p["model_api_id"]; return r
def mutation_request(cls,p,group_ids):
    r=cls(); r.GatewayId,r.ResourceType,r.ResourceId,r.ConsumerGroupIds=p["gateway_id"],"ModelAPI",p["model_api_id"],group_ids; return r
def group_ids(value):
    return sorted({item.get("PrincipalId") for item in value.get("ConsumerGroupModelScopes") or [] if item.get("PrincipalId")})
def resolve_ids(values,names,id_field):
    mapping={item.get("Name"):item.get(id_field) for item in values if item.get("Name") and item.get(id_field)}
    return [mapping[name] for name in names if name in mapping], [name for name in names if name not in mapping]
def list_values(module,api,request_factory,result_field):
    offset=0; values=[]
    while True:
        result=module.sdk_call(api,request_factory(offset)).Result; page=getattr(result,result_field) if result else []
        values.extend(item._serialize(allow_none=True) for item in page or []); offset+=len(page or [])
        if not result or offset>=int(result.TotalCount or 0): return values
def _api_list_request(models,p,offset):
    r=models.DescribeCloudNativeAPIGatewayLLMModelAPIsRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],offset,100; return r
def _group_list_request(models,p,offset):
    r=models.DescribeCloudNativeAPIGatewayConsumerGroupListRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],offset,20; return r
def resolve_names(module,client,models,p):
    if not p.get("model_api_id"):
        values=list_values(module,client.DescribeCloudNativeAPIGatewayLLMModelAPIs,lambda offset:_api_list_request(models,p,offset),"DataList")
        ids,missing=resolve_ids(values,[p["model_api_name"]],"Id")
        if missing: module.fail_json(msg="TSE gateway Model API name was not found",model_api_name=missing[0])
        p["model_api_id"]=ids[0]
    if not p.get("consumer_group_ids"):
        values=list_values(module,client.DescribeCloudNativeAPIGatewayConsumerGroupList,lambda offset:_group_list_request(models,p,offset),"ConsumerGroups")
        ids,missing=resolve_ids(values,p["consumer_group_names"],"ConsumerGroupId")
        if missing: module.fail_json(msg="TSE gateway consumer group names were not found",consumer_group_names=missing)
        p["consumer_group_ids"]=ids
def current(module,client,models,p):
    result=module.sdk_call(client.DescribeCloudNativeAPIGatewayLLMModelAPI,detail_request(models,p)).Result
    if not result: module.fail_json(msg="TSE gateway Model API was not found",model_api_id=p["model_api_id"])
    return group_ids(result._serialize(allow_none=True))
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"model_api_id":{},"model_api_name":{},"consumer_group_ids":{"type":"list","elements":"str"},"consumer_group_names":{"type":"list","elements":"str"}},required_one_of=[("model_api_id","model_api_name"),("consumer_group_ids","consumer_group_names")],mutually_exclusive=[("model_api_id","model_api_name"),("consumer_group_ids","consumer_group_names")],supports_check_mode=True); p=module.params
    supplied=p.get("consumer_group_ids") or p.get("consumer_group_names") or []
    if not 1<=len(supplied)<=10: module.fail_json(msg="consumer_group_ids or consumer_group_names must contain between 1 and 10 entries")
    if len(set(supplied))!=len(supplied): module.fail_json(msg="consumer_group_ids or consumer_group_names must not contain duplicates")
    module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        resolve_names(module,client,models,p)
        before=current(module,client,models,p); requested=set(p["consumer_group_ids"]); existing=set(before)
        affected=sorted(requested-existing) if p["state"]=="present" else sorted(requested&existing)
        target=sorted(existing|requested) if p["state"]=="present" else sorted(existing-requested)
        if not affected: module.exit_json(changed=False,authorization={"ModelAPIId":p["model_api_id"],"ConsumerGroupIds":before})
        diff=maybe_diff(module,{"ConsumerGroupIds":before},{"ConsumerGroupIds":target})
        if not module.check_mode:
            if p["state"]=="present": api,cls=client.AddCloudNativeAPIGatewayConsumerGroupAuth,models.AddCloudNativeAPIGatewayConsumerGroupAuthRequest
            else: api,cls=client.RemoveCloudNativeAPIGatewayConsumerGroupAuth,models.RemoveCloudNativeAPIGatewayConsumerGroupAuthRequest
            module.sdk_call(api,mutation_request(cls,p,affected)); target=current(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),authorization={"ModelAPIId":p["model_api_id"],"ConsumerGroupIds":target,"AffectedConsumerGroupIds":affected})
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
