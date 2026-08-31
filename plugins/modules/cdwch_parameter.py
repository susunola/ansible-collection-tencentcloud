#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdwch_parameter
short_description: Manage a Tencent Cloud CDW ClickHouse instance parameter
version_added: "0.14.0"
description:
  - Adds, updates or removes one instance key/value parameter.
  - Reports whether the service marks the change as requiring a restart; it never restarts the cluster implicitly.
options:
  state: {type: str, choices: [present, absent], default: present, description: Set the value or restore the parameter to its unconfigured state.}
  instance_id: {type: str, required: true, description: CDW ClickHouse instance ID.}
  name: {type: str, required: true, description: Configuration key.}
  value: {type: str, description: Desired configuration value.}
  remark: {type: str, description: Change annotation recorded by the service.}
  wait: {type: bool, default: true, description: Wait until the configuration list reflects the change.}
  waiter_delay: {type: int, default: 3, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 120, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwch_parameter:
    instance_id: cdwch-xxxxxxxx
    name: max_concurrent_queries
    value: '200'
    remark: Managed by Ansible
'''
RETURN = r'''parameter: {description: Effective parameter metadata., type: dict, returned: always}
restart_required: {description: Whether the service marks this parameter as requiring restart., type: bool, returned: always}
flow_id: {description: Asynchronous change flow ID., type: int, returned: when changed}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state
def _load():
    from tencentcloud.cdwch.v20200915 import models,cdwch_client
    return models,cdwch_client
def describe(module,client,models,p):
    r=models.DescribeInstanceKeyValConfigsRequest(); r.InstanceId=p["instance_id"]; r.SearchConfigName=p["name"]; response=module.sdk_call(client.DescribeInstanceKeyValConfigs,r)
    if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
    configured=[x._serialize(allow_none=True) for x in response.ConfigItems or [] if x.ConfKey==p["name"]]
    available=[x._serialize(allow_none=True) for x in response.UnConfigItems or [] if x.ConfKey==p["name"]]
    if len(configured)>1 or len(available)>1: module.fail_json(msg="Multiple ClickHouse parameters matched",name=p["name"])
    return (configured[0] if configured else None),(available[0] if available else None)
def change_request(models,p,current,available):
    r=models.ModifyInstanceKeyValConfigsRequest(); r.InstanceId=p["instance_id"]; r.Remark=p.get("remark")
    source=current or available or {}; item=models.InstanceConfigItem(); item.ConfKey=p["name"]; item.ConfValue=p.get("value"); item.OriginalConfValue=source.get("ConfValue"); item.NeedRestart=source.get("NeedRestart")
    if p["state"]=="absent": item.ModifyType="delete"; r.DelItems=[item]
    elif current: item.ModifyType="update"; r.UpdateItems=[item]
    else: item.ModifyType="add"; r.AddItems=[item]
    return r
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"instance_id":{"required":True},"name":{"required":True},"value":{},"remark":{},"wait":{"type":"bool","default":True},"waiter_delay":{"type":"int","default":3},"waiter_timeout":{"type":"int","default":120}},required_if=[("state","present",("value",))],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.CdwchClient,"cdwch.tencentcloudapi.com")
    try:
        current,available=describe(module,client,models,p); restart=bool((current or available or {}).get("NeedRestart"))
        if p["state"]=="absent" and not current: module.exit_json(changed=False,parameter=None,restart_required=restart)
        if p["state"]=="present" and current and str(current.get("ConfValue"))==p["value"]: module.exit_json(changed=False,parameter=current,restart_required=restart)
        if p["state"]=="present" and not current and not available: module.fail_json(msg="ClickHouse parameter is not exposed as configurable",name=p["name"])
        target=None if p["state"]=="absent" else {"ConfKey":p["name"],"ConfValue":p["value"]}; diff=maybe_diff(module,current,target); flow_id=None
        if not module.check_mode:
            response=module.sdk_call(client.ModifyInstanceKeyValConfigs,change_request(models,p,current,available)); flow_id=response.FlowId
            if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg,flow_id=flow_id)
            if p["wait"]:
                def poll():
                    configured,_=describe(module,client,models,p)
                    if p["state"]=="absent": return "ready" if configured is None else "pending"
                    return "ready" if configured and str(configured.get("ConfValue"))==p["value"] else "pending"
                wait_for_state(module,poll,["ready"],timeout=p["waiter_timeout"],delay=p["waiter_delay"])
            current,available=describe(module,client,models,p); restart=bool((current or available or {}).get("NeedRestart"))
        module.exit_json(changed=True,**(diff or {}),parameter=current if not module.check_mode else target,restart_required=restart,flow_id=flow_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
