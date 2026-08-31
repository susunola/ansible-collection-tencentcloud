#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_autoscaler_binding
short_description: Bind a TSE gateway autoscaler strategy to gateway groups
version_added: "0.14.0"
description: Reconciles autoscaler strategy group bindings with paginated readback and delta mutations.
options:
  state: {type: str, choices: [present, absent], default: present, description: Whether listed bindings exist.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  strategy_id: {type: str, description: Autoscaler strategy ID.}
  strategy_name: {type: str, description: Autoscaler strategy name resolved within the gateway.}
  group_ids: {type: list, elements: str, required: true, description: Unique gateway group IDs.}
  purge_unlisted: {type: bool, default: false, description: With state=present, unbind groups not listed here.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_autoscaler_binding:
    gateway_id: gateway-xxxxxxxx
    strategy_name: production-elasticity
    group_ids: [group-xxxxxxxx]
    purge_unlisted: true
'''
RETURN = r'''binding: {description: Effective strategy group bindings., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def describe_request(models,p,offset=0):
    r=models.DescribeAutoScalerResourceStrategyBindingGroupsRequest(); r.GatewayId,r.StrategyId,r.Offset,r.Limit=p["gateway_id"],p["strategy_id"],offset,100; return r
def mutation_request(cls,p,group_ids):
    r=cls(); r.GatewayId,r.StrategyId,r.GroupIds=p["gateway_id"],p["strategy_id"],group_ids; return r
def strategy_request(models,p):
    r=models.DescribeAutoScalerResourceStrategiesRequest(); r.GatewayId=p["gateway_id"]; return r
def resolve_strategy(module,client,models,p):
    if p.get("strategy_id"): return
    result=module.sdk_call(client.DescribeAutoScalerResourceStrategies,strategy_request(models,p)).Result; matches=[]
    for item in (result.StrategyList if result else []) or []:
        value=item._serialize(allow_none=True)
        if value.get("StrategyName")==p["strategy_name"]: matches.append(value.get("StrategyId"))
    if not matches: module.fail_json(msg="TSE autoscaler strategy name was not found",strategy_name=p["strategy_name"])
    if len(matches)>1: module.fail_json(msg="Multiple TSE autoscaler strategies matched the name",strategy_name=p["strategy_name"])
    p["strategy_id"]=matches[0]
def current(module,client,models,p):
    offset=0; values=[]
    while True:
        result=module.sdk_call(client.DescribeAutoScalerResourceStrategyBindingGroups,describe_request(models,p,offset)).Result; page=result.GroupInfos if result else []
        values.extend(item._serialize(allow_none=True) for item in page or []); offset+=len(page or [])
        if not result or offset>=int(result.TotalCount or 0): return values
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"strategy_id":{},"strategy_name":{},"group_ids":{"type":"list","elements":"str","required":True},"purge_unlisted":{"type":"bool","default":False}},required_one_of=[("strategy_id","strategy_name")],mutually_exclusive=[("strategy_id","strategy_name")],supports_check_mode=True); p=module.params
    if not p["group_ids"]: module.fail_json(msg="group_ids must contain at least one entry")
    if len(set(p["group_ids"]))!=len(p["group_ids"]): module.fail_json(msg="group_ids must not contain duplicates")
    if p["state"]=="absent" and p["purge_unlisted"]: module.fail_json(msg="purge_unlisted is only valid with state=present")
    module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        resolve_strategy(module,client,models,p)
        details=current(module,client,models,p); existing={item.get("GroupId") for item in details if item.get("GroupId")}; requested=set(p["group_ids"])
        add=sorted(requested-existing) if p["state"]=="present" else []
        remove=sorted(existing-requested) if p["state"]=="present" and p["purge_unlisted"] else (sorted(requested&existing) if p["state"]=="absent" else [])
        target=sorted((existing|requested)-set(remove)) if p["state"]=="present" else sorted(existing-requested)
        if not add and not remove: module.exit_json(changed=False,binding={"StrategyId":p["strategy_id"],"GroupIds":sorted(existing),"Groups":details})
        diff=maybe_diff(module,{"GroupIds":sorted(existing)},{"GroupIds":target})
        if not module.check_mode:
            if add: module.sdk_call(client.BindAutoScalerResourceStrategyToGroups,mutation_request(models.BindAutoScalerResourceStrategyToGroupsRequest,p,add))
            if remove: module.sdk_call(client.UnbindAutoScalerResourceStrategyFromGroups,mutation_request(models.UnbindAutoScalerResourceStrategyFromGroupsRequest,p,remove))
            details=current(module,client,models,p); target=sorted(item.get("GroupId") for item in details if item.get("GroupId"))
        module.exit_json(changed=True,**(diff or {}),binding={"StrategyId":p["strategy_id"],"GroupIds":target,"Groups":details if not module.check_mode else [],"AddedGroupIds":add,"RemovedGroupIds":remove})
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
