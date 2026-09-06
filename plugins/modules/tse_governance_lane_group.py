#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_governance_lane_group
short_description: Manage a Tencent Cloud TSE governance lane group
version_added: "0.14.0"
description: Creates, updates and deletes a governance lane group with its traffic entries, destinations and lane rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  lane_group_id: {type: str, description: Existing lane group ID.}
  name: {type: str, description: Lane group name.}
  traffic_entries: {type: list, elements: dict, description: Authoritative SDK LaneTrafficEntry list.}
  destinations: {type: list, elements: dict, description: Authoritative SDK GovernanceServiceDestination list.}
  description: {type: str, description: Lane group description.}
  rules: {type: list, elements: dict, description: Authoritative SDK GovernanceLaneRule list.}
  waiter_delay: {type: int, default: 2, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 60, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_governance_lane_group:
    instance_id: ins-xxxxxxxx
    name: checkout-gray
    traffic_entries:
      - {Namespace: production, Service: edge-gateway}
    destinations:
      - {Namespace: production, Service: checkout}
    rules:
      - {Name: gray, Enable: true}
"""
RETURN = r"""lane_group: {description: Effective governance lane group metadata., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p, offset=0):
    r = models.DescribeGovernanceLaneGroupsRequest()
    r.InstanceId, r.Offset, r.Limit, r.Name, r.GroupID, r.Brief = p["instance_id"], offset, 100, p.get("name"), p.get("lane_group_id"), False
    return r


def model(models, value):
    r = models.GovernanceLaneGroup()
    r.from_json_string(json.dumps(value))
    return r


def write_request(cls, models, p, value):
    r = cls()
    r.InstanceId = p["instance_id"]
    r.LaneGroups = [model(models, value)]
    return r


def delete_request(models, p, current):
    item = models.DeleteGovernanceLaneGroup()
    item.from_json_string(json.dumps({"ID": current.get("ID"), "Name": current.get("Name")}))
    r = models.DeleteGovernanceLaneGroupsRequest()
    r.InstanceId, r.LaneGroups = p["instance_id"], [item]
    return r


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        unmatched = list(actual)
        for item in expected:
            index = next((i for i, candidate in enumerate(unmatched) if contains(candidate, item)), None)
            if index is None:
                return False
            unmatched.pop(index)
        return True
    return actual == expected


def desired(p, current=None):
    value = {}
    mapping = (("name", "Name"), ("traffic_entries", "TrafficEntries"), ("destinations", "Destinations"), ("description", "Description"), ("rules", "Rules"))
    for source, target in mapping:
        selected = p.get(source) if p.get(source) is not None else (current or {}).get(target)
        if selected is not None:
            value[target] = selected
    if current and current.get("ID"):
        value["ID"] = current["ID"]
    return value


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeGovernanceLaneGroups, describe_request(models, p, offset))
        page = response.LaneGroups or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("lane_group_id") and value.get("ID") == p["lane_group_id"]) or (not p.get("lane_group_id") and value.get("Name") == p.get("name")):
                matches.append(value)
        offset += len(page)
        if offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE governance lane groups matched; specify lane_group_id")
    return matches[0] if matches else None


def wait(module, client, models, p, target=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        value = find(module, client, models, p)
        if absent and value is None:
            return None
        if not absent and value is not None and contains(value, target or {}):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE governance lane group convergence", lane_group=value)
        time.sleep(p["waiter_delay"])


def require_success(module, response, operation):
    if getattr(response, "Result", None) is not True:
        module.fail_json(msg="TSE governance lane group operation returned an unsuccessful result", operation=operation)


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "lane_group_id": {},
        "name": {},
        "traffic_entries": {"type": "list", "elements": "dict"},
        "destinations": {"type": "list", "elements": "dict"},
        "description": {},
        "rules": {"type": "list", "elements": "dict"},
        "waiter_delay": {"type": "int", "default": 2},
        "waiter_timeout": {"type": "int", "default": 60},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("lane_group_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, lane_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                require_success(module, module.sdk_call(client.DeleteGovernanceLaneGroups, delete_request(models, p, current)), "DeleteGovernanceLaneGroups")
                wait(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), lane_group=None)
        if not current and p.get("name") is None:
            module.fail_json(msg="name is required to create a TSE governance lane group")
        target = desired(p, current)
        if current and contains(current, target):
            module.exit_json(changed=False, lane_group=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            cls = models.ModifyGovernanceLaneGroupsRequest if current else models.CreateGovernanceLaneGroupsRequest
            api = client.ModifyGovernanceLaneGroups if current else client.CreateGovernanceLaneGroups
            require_success(
                module, module.sdk_call(api, write_request(cls, models, p, target)), "ModifyGovernanceLaneGroups" if current else "CreateGovernanceLaneGroups"
            )
            lookup = dict(p, lane_group_id=current.get("ID") if current else p.get("lane_group_id"))
            current = wait(module, client, models, lookup, target)
        module.exit_json(changed=True, **(diff or {}), lane_group=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
