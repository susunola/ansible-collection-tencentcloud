#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: tcb_static_store
short_description: Manage Tencent CloudBase static website hosting
version_added: "0.14.0"
description:
  - Creates or destroys the environment-level CloudBase static store.
  - Waits through asynchronous C(init), C(process), and C(destroying) states.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  env_id: {type: str, required: true, description: CloudBase environment ID.}
  enable_union: {type: bool, default: true, description: Enable the unified domain at creation.}
  external_storage: {type: dict, description: Creation-time SDK ExternalStorage payload.}
  cdn_domain: {type: str, description: CDN domain used by destruction; defaults to the discovered store domain.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 600, description: Provisioning or destruction timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tcb_static_store:
    env_id: env-xxxxxxxx
    enable_union: true
'''
RETURN = r'''static_store: {description: Effective static hosting metadata., type: dict, returned: always}'''
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcb.v20180608 import models, tcb_client
    return models, tcb_client


def describe_request(models, env_id): request = models.DescribeStaticStoreRequest(); request.EnvId = env_id; return request
def create_request(models, p):
    request = models.CreateStaticStoreRequest(); request.EnvId, request.EnableUnion = p["env_id"], p["enable_union"]
    if p.get("external_storage") is not None: request.ExternalStorage = models.ExternalStorage(); request.ExternalStorage.from_json_string(json.dumps(p["external_storage"]))
    return request
def delete_request(models, env_id, cdn_domain): request = models.DestroyStaticStoreRequest(); request.EnvId, request.CdnDomain = env_id, cdn_domain; return request


def find(module, client, models, env_id):
    response = module.sdk_call(client.DescribeStaticStore, describe_request(models, env_id)); values = [item._serialize(allow_none=True) for item in (response.Data or []) if item.EnvId in (None, env_id)]
    active = [value for value in values if (value.get("Status") or "").lower() != "offline"]
    if len(active) > 1: module.fail_json(msg="Multiple active CloudBase static stores found for one environment", env_id=env_id)
    return active[0] if active else None


def wait(module, client, models, env_id, present):
    deadline = time.time() + module.params["waiter_timeout"]; current = None
    while True:
        current = find(module, client, models, env_id); status = (current or {}).get("Status", "").lower()
        if present and current and status == "online": return current
        if not present and current is None: return None
        if status in ("fail", "failed", "error"): module.fail_json(msg="CloudBase static store entered a failure state", static_store=current)
        if time.time() >= deadline: module.fail_json(msg="Timed out waiting for CloudBase static store", env_id=env_id, expected="online" if present else "absent", static_store=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "env_id": {"required": True}, "enable_union": {"type": "bool", "default": True}, "external_storage": {"type": "dict"}, "cdn_domain": {}}, supports_check_mode=True); p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TcbClient, "tcb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["env_id"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, static_store=None)
            cdn_domain = p.get("cdn_domain") or current.get("CdnDomain")
            if not cdn_domain: module.fail_json(msg="cdn_domain was not returned by CloudBase and must be supplied for destruction", static_store=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: response = module.sdk_call(client.DestroyStaticStore, delete_request(models, p["env_id"], cdn_domain)); result = (response.Result or "").lower(); module.fail_json(msg="CloudBase rejected static store destruction", result=response.Result) if result == "fail" else None; current = wait(module, client, models, p["env_id"], False)
            module.exit_json(changed=True, **(diff or {}), static_store=current)
        if current:
            if (current.get("Status") or "").lower() == "online": module.exit_json(changed=False, static_store=current)
            if module.check_mode: module.exit_json(changed=False, static_store=current)
            current = wait(module, client, models, p["env_id"], True); module.exit_json(changed=True, static_store=current)
        target = {"EnvId": p["env_id"], "Status": "online"}; diff = maybe_diff(module, None, target)
        if not module.check_mode: response = module.sdk_call(client.CreateStaticStore, create_request(models, p)); result = (response.Result or "").lower(); module.fail_json(msg="CloudBase rejected static store creation", result=response.Result) if result == "fail" else None; current = wait(module, client, models, p["env_id"], True)
        module.exit_json(changed=True, **(diff or {}), static_store=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
