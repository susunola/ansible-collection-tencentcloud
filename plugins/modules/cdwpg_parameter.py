#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdwpg_parameter
short_description: Manage a Tencent Cloud CDW PostgreSQL parameter
version_added: "0.14.0"
description:
  - Reconciles one CN or DN parameter across that node type.
  - C(default) restores the service-reported default value.
  - Reports restart requirements but never restarts the cluster implicitly.
options:
  state: {type: str, choices: [present, default], default: present, description: Set an explicit value or restore the default.}
  instance_id: {type: str, required: true, description: CDW PostgreSQL instance ID.}
  node_type: {type: str, choices: [cn, dn], required: true, description: Node type receiving the parameter.}
  name: {type: str, required: true, description: Parameter name.}
  value: {type: str, description: Desired value when state is present.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwpg_parameter:
    instance_id: cdwpg-xxxxxxxx
    node_type: cn
    name: max_connections
    value: '500'
'''
RETURN = r'''parameter: {description: Effective parameter metadata., type: dict, returned: always}
restart_required: {description: Whether applying the value requires restart., type: bool, returned: always}
task_id: {description: Asynchronous service task ID., type: int, returned: when changed}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.cdwpg.v20201230 import models,cdwpg_client
    return models,cdwpg_client
def effective_value(detail): return detail.get("LatestValue") if detail.get("LatestValue") not in (None,"") else detail.get("RunningValue")
def describe(module,client,models,p):
    offset=0; matches=[]
    while True:
        r=models.DescribeDBParamsRequest(); r.InstanceId=p["instance_id"]; r.NodeTypes=[p["node_type"]]; r.Offset=offset; r.Limit=100
        response=module.sdk_call(client.DescribeDBParams,r); items=response.Items or []
        page_count=0
        for group in items:
            if str(group.NodeType).lower()!=p["node_type"]: continue
            page_count+=len(group.Details or [])
            for detail in group.Details or []:
                value=detail._serialize(allow_none=True)
                if value.get("ParamName")==p["name"] or value.get("ParameterName")==p["name"]: matches.append(value)
        offset+=page_count
        if not items or not page_count or offset>=int(response.TotalCount or 0): break
    if not matches: module.fail_json(msg="CDW PostgreSQL parameter was not found",node_type=p["node_type"],name=p["name"])
    values={str(effective_value(x)) for x in matches}
    defaults={str(x.get("DefaultValue")) for x in matches}
    if len(values)>1 or len(defaults)>1: module.fail_json(msg="CDW PostgreSQL nodes disagree on parameter state",node_type=p["node_type"],name=p["name"],values=sorted(values),defaults=sorted(defaults))
    result=dict(matches[0]); result["EffectiveValue"]=effective_value(result); result["NodeCount"]=len(matches); return result
def change_request(models,p,current,target):
    config=models.ConfigParams(); config.ParameterName=p["name"]; config.ParameterValue=target; config.ParameterOldValue=str(current.get("EffectiveValue"))
    node=models.NodeConfigParams(); node.NodeType=p["node_type"]; node.ConfigParams=[config]
    r=models.ModifyDBParametersRequest(); r.InstanceId=p["instance_id"]; r.NodeConfigParams=[node]; return r
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","default"],"default":"present"},"instance_id":{"required":True},"node_type":{"choices":["cn","dn"],"required":True},"name":{"required":True},"value":{}},required_if=[("state","present",["value"])],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.CdwpgClient,"cdwpg.tencentcloudapi.com")
    try:
        current=describe(module,client,models,p); target=p["value"] if p["state"]=="present" else str(current.get("DefaultValue")); restart=bool(current.get("NeedRestart"))
        if str(current.get("EffectiveValue"))==target: module.exit_json(changed=False,parameter=current,restart_required=restart)
        diff=maybe_diff(module,{"value":current.get("EffectiveValue")},{"value":target}); task_id=None
        if not module.check_mode:
            response=module.sdk_call(client.ModifyDBParameters,change_request(models,p,current,target)); task_id=response.TaskId; current=describe(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),parameter=current if not module.check_mode else {"ParamName":p["name"],"EffectiveValue":target},restart_required=restart,task_id=task_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
