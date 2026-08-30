#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_connection
short_description: Manage Tencent Cloud EventBridge connections
version_added: "0.14.0"
description: Creates, updates and deletes EventBridge event-source connections.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  event_bus_id: {type: str, required: true, description: Event bus ID.}
  connection_id: {type: str, description: Existing connection ID.}
  name: {type: str, description: Connection name.}
  connection_type: {type: str, description: Connection source type; immutable after creation.}
  connection_description: {type: dict, description: SDK ConnectionDescription payload; immutable after creation.}
  enabled: {type: bool, default: true, description: Enable the connection.}
  description: {type: str, default: '', description: Human-readable connection description.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_connection:
    event_bus_id: eb-l8q2xxxx
    name: kafka-orders
    connection_type: ckafka
    connection_description:
      ResourceDescription: '{"InstanceId":"ckafka-xxxx","TopicName":"orders"}'
'''
RETURN = r'''connection: {description: Effective EventBridge connection metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.eb.v20210416 import models, eb_client
    return models, eb_client
def _model(cls, value):
    if value is None: return None
    item = cls(); item.from_json_string(json.dumps(value)); return item
def list_request(models, p):
    r = models.ListConnectionsRequest(); r.EventBusId, r.Offset, r.Limit = p["event_bus_id"], 0, 100; return r
def create_request(models, p):
    r = models.CreateConnectionRequest(); r.EventBusId, r.ConnectionName, r.Type = p["event_bus_id"], p["name"], p["connection_type"]; r.ConnectionDescription = _model(models.ConnectionDescription, p["connection_description"]); r.Enable, r.Description = p["enabled"], p["description"]; return r
def update_request(models, p, connection_id):
    r = models.UpdateConnectionRequest(); r.EventBusId, r.ConnectionId, r.ConnectionName = p["event_bus_id"], connection_id, p.get("name"); r.Enable, r.Description = p["enabled"], p["description"]; return r
def delete_request(models, p, connection_id):
    r = models.DeleteConnectionRequest(); r.EventBusId, r.ConnectionId = p["event_bus_id"], connection_id; return r
def find(module, client, models, p):
    response = module.sdk_call(client.ListConnections, list_request(models, p)); items = []
    for item in response.Connections or []:
        value = item._serialize(allow_none=True)
        if (p.get("connection_id") and value.get("ConnectionId") == p["connection_id"]) or (not p.get("connection_id") and value.get("ConnectionName") == p.get("name")): items.append(value)
    if len(items) > 1: module.fail_json(msg="Multiple EventBridge connections matched; specify connection_id")
    return items[0] if items else None


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "event_bus_id": {"required": True}, "connection_id": {}, "name": {}, "connection_type": {}, "connection_description": {"type": "dict"}, "enabled": {"type": "bool", "default": True}, "description": {"default": ""}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("connection_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.EbClient, "eb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, connection=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteConnection, delete_request(models, p, current["ConnectionId"]))
            module.exit_json(changed=True, **(diff or {}), connection=None)
        if not current:
            missing = [k for k in ("name", "connection_type", "connection_description") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new EventBridge connection", missing=missing)
            target = {"ConnectionName": p["name"], "Type": p["connection_type"], "ConnectionDescription": p["connection_description"], "Enable": p["enabled"], "Description": p["description"]}; diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["connection_id"] = module.sdk_call(client.CreateConnection, create_request(models, p)).ConnectionId; current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), connection=current if not module.check_mode else target)
        before = {"ConnectionName": current.get("ConnectionName"), "Type": current.get("Type"), "ConnectionDescription": current.get("ConnectionDescription"), "Enable": current.get("Enable"), "Description": current.get("Description") or ""}; target = {"ConnectionName": p.get("name") or before["ConnectionName"], "Type": p.get("connection_type") or before["Type"], "ConnectionDescription": p.get("connection_description") if p.get("connection_description") is not None else before["ConnectionDescription"], "Enable": p["enabled"], "Description": p["description"]}
        require_immutable_unchanged(module, before, target, ("Type", "ConnectionDescription"), "EventBridge connection")
        if before == target: module.exit_json(changed=False, connection=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.UpdateConnection, update_request(models, p, current["ConnectionId"])); p["connection_id"] = current["ConnectionId"]; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), connection=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
