#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_consumer_group_membership
short_description: Manage TSE API gateway consumer group membership
version_added: "0.14.0"
description: Adds or removes up to ten consumers using consumer detail readback for idempotent reconciliation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Whether every listed consumer belongs to the group.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  consumer_group_id: {type: str, description: Consumer group ID.}
  consumer_group_name: {type: str, description: Consumer group name resolved within the gateway.}
  consumer_ids: {type: list, elements: str, description: Unique consumer IDs, one through ten entries.}
  consumer_names: {type: list, elements: str, description: Unique consumer names resolved within the gateway.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_consumer_group_membership:
    gateway_id: gateway-xxxxxxxx
    consumer_group_name: trusted-clients
    consumer_names: [mobile-app, batch-worker]
'''
RETURN = r'''membership: {description: Requested group and effective member IDs., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def detail_request(models,p,consumer_id):
    r=models.DescribeCloudNativeAPIGatewayConsumerRequest(); r.GatewayId,r.ConsumerId=p["gateway_id"],consumer_id; return r
def mutation_request(cls,p,consumer_ids):
    r=cls(); r.GatewayId,r.ConsumerGroupId,r.ConsumerIds=p["gateway_id"],p["consumer_group_id"],consumer_ids; return r
def group_ids(value):
    groups=value.get("ConsumerGroups") or []
    return {item.get("ConsumerGroupId") for item in groups if item.get("ConsumerGroupId")}
def resolve_ids(values,names,id_field):
    mapping={item.get("Name"):item.get(id_field) for item in values if item.get("Name") and item.get(id_field)}
    return [mapping[name] for name in names if name in mapping], [name for name in names if name not in mapping]
def list_values(module,client,request_factory,api,result_field):
    offset=0; values=[]
    while True:
        result=module.sdk_call(api,request_factory(offset)).Result; page=getattr(result,result_field) if result else []
        values.extend(item._serialize(allow_none=True) for item in page or []); offset+=len(page or [])
        if not result or offset>=int(result.TotalCount or 0): return values
def resolve_names(module,client,models,p):
    if not p.get("consumer_group_id"):
        groups=list_values(module,client,lambda offset: _group_list_request(models,p,offset),client.DescribeCloudNativeAPIGatewayConsumerGroupList,"ConsumerGroups")
        ids,missing=resolve_ids(groups,[p["consumer_group_name"]],"ConsumerGroupId")
        if missing: module.fail_json(msg="TSE gateway consumer group name was not found",consumer_group_name=missing[0])
        p["consumer_group_id"]=ids[0]
    if not p.get("consumer_ids"):
        consumers=list_values(module,client,lambda offset: _consumer_list_request(models,p,offset),client.DescribeCloudNativeAPIGatewayConsumerList,"Consumers")
        ids,missing=resolve_ids(consumers,p["consumer_names"],"ConsumerId")
        if missing: module.fail_json(msg="TSE gateway consumer names were not found",consumer_names=missing)
        p["consumer_ids"]=ids
def _group_list_request(models,p,offset):
    r=models.DescribeCloudNativeAPIGatewayConsumerGroupListRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],offset,20; return r
def _consumer_list_request(models,p,offset):
    r=models.DescribeCloudNativeAPIGatewayConsumerListRequest(); r.GatewayId,r.Offset,r.Limit=p["gateway_id"],offset,20; return r
def inspect_members(module,client,models,p):
    present=[]
    for consumer_id in p["consumer_ids"]:
        result=module.sdk_call(client.DescribeCloudNativeAPIGatewayConsumer,detail_request(models,p,consumer_id)).Result
        if not result: module.fail_json(msg="TSE gateway consumer was not found",consumer_id=consumer_id)
        if p["consumer_group_id"] in group_ids(result._serialize(allow_none=True)): present.append(consumer_id)
    return present
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"consumer_group_id":{},"consumer_group_name":{},"consumer_ids":{"type":"list","elements":"str"},"consumer_names":{"type":"list","elements":"str"}},required_one_of=[("consumer_group_id","consumer_group_name"),("consumer_ids","consumer_names")],mutually_exclusive=[("consumer_group_id","consumer_group_name"),("consumer_ids","consumer_names")],supports_check_mode=True); p=module.params
    supplied=p.get("consumer_ids") or p.get("consumer_names") or []
    if not 1<=len(supplied)<=10: module.fail_json(msg="consumer_ids or consumer_names must contain between 1 and 10 entries")
    if len(set(supplied))!=len(supplied): module.fail_json(msg="consumer_ids or consumer_names must not contain duplicates")
    module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        resolve_names(module,client,models,p)
        before=inspect_members(module,client,models,p)
        affected=[item for item in p["consumer_ids"] if (item not in before if p["state"]=="present" else item in before)]
        target=p["consumer_ids"] if p["state"]=="present" else []
        if not affected: module.exit_json(changed=False,membership={"ConsumerGroupId":p["consumer_group_id"],"ConsumerIds":before})
        diff=maybe_diff(module,{"ConsumerIds":before},{"ConsumerIds":target})
        if not module.check_mode:
            if p["state"]=="present": api,cls=client.AddCloudNativeAPIGatewayConsumerInGroup,models.AddCloudNativeAPIGatewayConsumerInGroupRequest
            else: api,cls=client.RemoveCloudNativeAPIGatewayConsumerInGroup,models.RemoveCloudNativeAPIGatewayConsumerInGroupRequest
            module.sdk_call(api,mutation_request(cls,p,affected)); effective=inspect_members(module,client,models,p)
        else: effective=target
        module.exit_json(changed=True,**(diff or {}),membership={"ConsumerGroupId":p["consumer_group_id"],"ConsumerIds":effective,"AffectedConsumerIds":affected})
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
