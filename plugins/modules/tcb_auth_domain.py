#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tcb_auth_domain
short_description: Manage Tencent CloudBase authentication domains
version_added: "0.14.0"
description: Creates and deletes user authentication domains in a CloudBase environment.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  env_id: {type: str, required: true, description: CloudBase environment ID.}
  domain: {type: str, required: true, description: Authentication domain name.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 120, description: Polling timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tcb_auth_domain:
    env_id: env-xxxxxxxx
    domain: app.example.com
'''
RETURN = r'''auth_domain: {description: Effective authentication-domain metadata., type: dict, returned: always}'''
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcb.v20180608 import models, tcb_client
    return models, tcb_client


def describe_request(models, env_id): request = models.DescribeAuthDomainsRequest(); request.EnvId = env_id; return request
def create_request(models, env_id, domain): request = models.CreateAuthDomainRequest(); request.EnvId, request.Domains = env_id, [domain]; return request
def delete_request(models, env_id, domain_id): request = models.DeleteAuthDomainRequest(); request.EnvId, request.DomainIds = env_id, [domain_id]; return request


def find(module, client, models, env_id, domain):
    response = module.sdk_call(client.DescribeAuthDomains, describe_request(models, env_id)); matches = [item._serialize(allow_none=True) for item in (response.Domains or []) if item.Domain == domain]
    if len(matches) > 1: module.fail_json(msg="Multiple CloudBase authentication domains matched", domain=domain)
    return matches[0] if matches else None


def wait(module, client, models, env_id, domain, present):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find(module, client, models, env_id, domain)
        if bool(current) == present: return current
        if time.time() >= deadline: module.fail_json(msg="Timed out waiting for CloudBase authentication domain", domain=domain, expected="present" if present else "absent")
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "env_id": {"required": True}, "domain": {"required": True}}, supports_check_mode=True); p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TcbClient, "tcb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["env_id"], p["domain"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, auth_domain=None)
            if current.get("Type") == "SYSTEM": module.fail_json(msg="CloudBase system authentication domains cannot be deleted", auth_domain=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAuthDomain, delete_request(models, p["env_id"], current["Id"])); current = wait(module, client, models, p["env_id"], p["domain"], False)
            module.exit_json(changed=True, **(diff or {}), auth_domain=current)
        if current: module.exit_json(changed=False, auth_domain=current)
        target = {"Domain": p["domain"], "Type": "USER"}; diff = maybe_diff(module, None, target)
        if not module.check_mode: module.sdk_call(client.CreateAuthDomain, create_request(models, p["env_id"], p["domain"])); current = wait(module, client, models, p["env_id"], p["domain"], True)
        module.exit_json(changed=True, **(diff or {}), auth_domain=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
