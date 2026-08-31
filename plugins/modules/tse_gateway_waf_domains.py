#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tse_gateway_waf_domains
short_description: Manage Tencent Cloud TSE gateway WAF domains
version_added: "0.14.0"
description: Adds, removes or exactly reconciles gateway domains registered for WAF protection.
options:
  state: {type: str, choices: [present, absent], default: present, description: Whether listed domains are registered.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  domains: {type: list, elements: str, required: true, description: Unique domain names.}
  purge_unlisted: {type: bool, default: false, description: With state=present, remove registered domains not listed here.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_waf_domains:
    gateway_id: gateway-xxxxxxxx
    domains: [api.example.com]
    purge_unlisted: true
'''
RETURN = r'''waf_domains: {description: Effective registered WAF domains., type: list, elements: str, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models,tse_client
    return models,tse_client
def request(cls,p,domains=None):
    r=cls(); r.GatewayId=p["gateway_id"]
    if domains is not None: r.Domains=domains
    return r
def current(module,client,models,p):
    result=module.sdk_call(client.DescribeWafDomains,request(models.DescribeWafDomainsRequest,p)).Result
    return sorted(set(result.Domains or [])) if result else []
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"gateway_id":{"required":True},"domains":{"type":"list","elements":"str","required":True},"purge_unlisted":{"type":"bool","default":False}},supports_check_mode=True); p=module.params
    if not p["domains"]: module.fail_json(msg="domains must contain at least one entry")
    if len(set(p["domains"]))!=len(p["domains"]): module.fail_json(msg="domains must not contain duplicates")
    if p["state"]=="absent" and p["purge_unlisted"]: module.fail_json(msg="purge_unlisted is only valid with state=present")
    module.require_sdk(); models,cm=_load(); client=module.create_client(cm.TseClient,"tse.tencentcloudapi.com")
    try:
        before=current(module,client,models,p); requested=set(p["domains"]); existing=set(before)
        add=sorted(requested-existing) if p["state"]=="present" else []
        remove=sorted((existing-requested) if p["state"]=="present" and p["purge_unlisted"] else (requested&existing if p["state"]=="absent" else []))
        target=sorted((existing|requested)-set(remove)) if p["state"]=="present" else sorted(existing-requested)
        if not add and not remove: module.exit_json(changed=False,waf_domains=before)
        diff=maybe_diff(module,before,target)
        if not module.check_mode:
            if add: module.sdk_call(client.CreateWafDomains,request(models.CreateWafDomainsRequest,p,add))
            if remove: module.sdk_call(client.DeleteWafDomains,request(models.DeleteWafDomainsRequest,p,remove))
            target=current(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),waf_domains=target,added_domains=add,removed_domains=remove)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
