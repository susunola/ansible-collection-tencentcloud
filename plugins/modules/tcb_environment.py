#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tcb_environment
short_description: Manage Tencent CloudBase environments
version_added: "0.14.0"
description: Creates, renames and destroys Tencent CloudBase environments.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  env_id: {type: str, description: Existing environment ID.}
  alias: {type: str, description: Environment alias used for lookup and rename.}
  package_id: {type: str, description: Creation-time CloudBase package ID.}
  resources: {type: list, elements: str, description: "Creation-time resource types such as flexdb, storage, function or postgresql."}
  period: {type: int, default: 1, description: Purchase period in months.}
  auto_voucher: {type: bool, description: Automatically select vouchers.}
  tags: {type: dict, description: Creation-time tags.}
  renew_flag: {type: str, choices: [NOTIFY_AND_AUTO_RENEW, NOTIFY_AND_MANUAL_RENEW], description: Renewal behavior.}
  external_storage: {type: dict, description: SDK ExternalStorage payload.}
  enable_overrun: {type: str, choices: ['TRUE', 'FALSE'], description: Overrun billing switch.}
  force_destroy: {type: bool, default: false, description: Force environment destruction.}
  bypass_destroy_check: {type: bool, default: false, description: Bypass server-side destruction checks.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tcb_environment:
    alias: production-app
    package_id: baas_package
    resources: [flexdb, storage, function]
    renew_flag: NOTIFY_AND_MANUAL_RENEW
'''
RETURN = r'''environment: {description: Effective CloudBase environment metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.tcb.v20180608 import models,tcb_client
    return models,tcb_client
def _model(cls,value):
    if value is None:return None
    x=cls(); x.from_json_string(json.dumps(value)); return x
def _tags(models,values):
    result=[]
    for key,value in sorted((values or {}).items()): x=models.Tag(); x.Key,x.Value=str(key),str(value); result.append(x)
    return result
def describe_request(models,env_id=None,offset=0): r=models.DescribeEnvsRequest(); r.EnvId=env_id; r.Offset,r.Limit=offset,100; return r
def create_request(models,p): r=models.CreateEnvRequest(); r.Alias,r.PackageId,r.Resources=p["alias"],p["package_id"],p["resources"]; r.Period,r.AutoVoucher=p["period"],p.get("auto_voucher"); r.Tags=_tags(models,p.get("tags")); r.RenewFlag=p.get("renew_flag"); r.ExternalStorage=_model(models.ExternalStorage,p.get("external_storage")); r.EnableOverrun=p.get("enable_overrun"); return r
def update_request(models,env_id,alias): r=models.ModifyEnvRequest(); r.EnvId,r.Alias=env_id,alias; return r
def delete_request(models,p,env_id): r=models.DestroyEnvRequest(); r.EnvId,r.IsForce,r.BypassCheck=env_id,p["force_destroy"],p["bypass_destroy_check"]; return r
def find(module,client,models,p):
    offset=0; matches=[]
    while True:
        response=module.sdk_call(client.DescribeEnvs,describe_request(models,p.get("env_id"),offset)); page=response.EnvList or []
        for item in page:
            value=item._serialize(allow_none=True)
            if (p.get("env_id") and value.get("EnvId")==p["env_id"]) or (not p.get("env_id") and value.get("Alias")==p.get("alias")): matches.append(value)
        offset+=len(page)
        if not page or offset>=int(response.Total or 0):break
    if len(matches)>1:module.fail_json(msg="Multiple CloudBase environments matched; specify env_id")
    return matches[0] if matches else None
def run_module():
    spec={"state":{"choices":["present","absent"],"default":"present"},"env_id":{},"alias":{},"package_id":{},"resources":{"type":"list","elements":"str"},"period":{"type":"int","default":1},"auto_voucher":{"type":"bool"},"tags":{"type":"dict"},"renew_flag":{"choices":["NOTIFY_AND_AUTO_RENEW","NOTIFY_AND_MANUAL_RENEW"]},"external_storage":{"type":"dict"},"enable_overrun":{"choices":["TRUE","FALSE"]},"force_destroy":{"type":"bool","default":False},"bypass_destroy_check":{"type":"bool","default":False}}
    module=TencentCloudModule(argument_spec=spec,required_one_of=[("env_id","alias")],supports_check_mode=True);p=module.params;module.require_sdk();models,cm=_load();client=module.create_client(cm.TcbClient,"tcb.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current:module.exit_json(changed=False,environment=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode:module.sdk_call(client.DestroyEnv,delete_request(models,p,current["EnvId"]))
            module.exit_json(changed=True,**(diff or {}),environment=None)
        if not current:
            missing=[x for x in ("alias","package_id","resources") if not p.get(x)]
            if missing:module.fail_json(msg="creation parameters are required for a CloudBase environment",missing=missing)
            target={"Alias":p["alias"],"PackageId":p["package_id"],"Resources":p["resources"]};diff=maybe_diff(module,None,target)
            if not module.check_mode:p["env_id"]=module.sdk_call(client.CreateEnv,create_request(models,p)).EnvId;current=find(module,client,models,p)
            module.exit_json(changed=True,**(diff or {}),environment=current if not module.check_mode else target)
        alias=p.get("alias") or current.get("Alias")
        if alias==current.get("Alias"):module.exit_json(changed=False,environment=current)
        diff=maybe_diff(module,{"Alias":current.get("Alias")},{"Alias":alias})
        if not module.check_mode:module.sdk_call(client.ModifyEnv,update_request(models,current["EnvId"],alias));p["env_id"]=current["EnvId"];current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),environment=current if not module.check_mode else {"Alias":alias})
    except Exception as exc:module.fail_json(**sdk_error_payload(exc))
def main():run_module()
if __name__=="__main__":main()
