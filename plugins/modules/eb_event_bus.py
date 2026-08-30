#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_event_bus
short_description: Manage Tencent Cloud EventBridge event buses
version_added: "0.14.0"
description: Creates, updates and deletes custom EventBridge event buses.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  event_bus_id: {type: str, description: Existing event bus ID.}
  name: {type: str, description: Event bus name.}
  description: {type: str, default: '', description: Event bus description.}
  save_days: {type: int, description: Event retention in days.}
  enable_store: {type: bool, description: Enable event storage.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_event_bus:
    name: production-events
    description: Production application events
    enable_store: true
    save_days: 7
'''
RETURN = r'''event_bus: {description: Effective EventBridge event bus metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.eb.v20210416 import models, eb_client
    return models, eb_client
def list_request(models, p):
    r = models.ListEventBusesRequest(); r.Offset, r.Limit = 0, 100
    return r
def get_request(models, event_bus_id):
    r = models.GetEventBusRequest(); r.EventBusId = event_bus_id; return r
def create_request(models, p):
    r = models.CreateEventBusRequest(); r.EventBusName, r.Description = p["name"], p["description"]; r.SaveDays, r.EnableStore = p.get("save_days"), p.get("enable_store"); return r
def update_request(models, p, event_bus_id):
    r = models.UpdateEventBusRequest(); r.EventBusId, r.EventBusName, r.Description = event_bus_id, p.get("name"), p["description"]; r.SaveDays, r.EnableStore = p.get("save_days"), p.get("enable_store"); return r
def delete_request(models, event_bus_id):
    r = models.DeleteEventBusRequest(); r.EventBusId = event_bus_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.ListEventBuses, list_request(models, p)); matches = []
    for item in response.EventBuses or []:
        value = item._serialize(allow_none=True)
        if (p.get("event_bus_id") and value.get("EventBusId") == p["event_bus_id"]) or (not p.get("event_bus_id") and value.get("EventBusName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple event buses matched; specify event_bus_id")
    if not matches: return None
    value = module.sdk_call(client.GetEventBus, get_request(models, matches[0]["EventBusId"]))._serialize(allow_none=True); value.pop("RequestId", None); return value


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "event_bus_id": {}, "name": {}, "description": {"default": ""}, "save_days": {"type": "int"}, "enable_store": {"type": "bool"}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("event_bus_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.EbClient, "eb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, event_bus=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteEventBus, delete_request(models, current["EventBusId"]))
            module.exit_json(changed=True, **(diff or {}), event_bus=None)
        if not current:
            if not p.get("name"): module.fail_json(msg="name is required when creating an event bus")
            target = {"EventBusName": p["name"], "Description": p["description"], "SaveDays": p.get("save_days"), "EnableStore": p.get("enable_store")}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["event_bus_id"] = module.sdk_call(client.CreateEventBus, create_request(models, p)).EventBusId; current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), event_bus=current if not module.check_mode else target)
        before = {"EventBusName": current.get("EventBusName"), "Description": current.get("Description") or "", "SaveDays": current.get("SaveDays"), "EnableStore": current.get("EnableStore")}; target = {"EventBusName": p.get("name") or before["EventBusName"], "Description": p["description"], "SaveDays": p.get("save_days") if p.get("save_days") is not None else before["SaveDays"], "EnableStore": p.get("enable_store") if p.get("enable_store") is not None else before["EnableStore"]}
        if before == target: module.exit_json(changed=False, event_bus=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.UpdateEventBus, update_request(models, p, current["EventBusId"])); p["event_bus_id"] = current["EventBusId"]; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), event_bus=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
